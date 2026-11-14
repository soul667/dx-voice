"""Experimental voice-to-DX dispatcher. The model selects IDs, never executable shell."""
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel

CATALOG = {
    'display.status': ('查看显示器状态', ['dx', 't', '--status']),
    'system.status': ('查看本机系统状态', ['dx', 'status', 'local']),
    'gpu.status': ('查看本机 GPU 状态', ['dx', 'gpu', 'local']),
    'disk.status': ('查看本机磁盘状态', ['dx', 'disk', 'local']),
    'ports.status': ('查看本机端口状态', ['dx', 'ports', 'local']),
    'shortcuts.list': ('查看快捷键清单', ['dx', 'key', '--list']),
    'workspace.status': ('查看当前工作区与 Git 状态', None),
    'context.inspect': ('查看当前语音上下文索引摘要', None),
    'open.path': ('打开明确指定的文档或目录', None),
    'open.url': ('打开明确指定的网页', None),
}


class Plan(BaseModel):
    action: Literal['display.status', 'system.status', 'gpu.status', 'disk.status', 'ports.status',
                    'shortcuts.list', 'workspace.status', 'context.inspect', 'open.path', 'open.url', 'none']
    argument: str


@dataclass
class ToolResult:
    text: str
    action: str
    status: str = 'executed'


def select_plan(client, request, cfg, context_text=''):
    from ..text_tools import text_settings
    # Use the same provider configuration, but only a typed ID/argument can leave the model.
    values = text_settings(cfg)
    prompt = ('从以下 DX 动作清单中选择一个动作，不生成 shell。参数只能来自用户明确给出的路径、URL 或已索引工作区名。'
              'open.path 可用别名 home/documents/downloads/desktop/workspace，或用户在需求中提到的已索引项目名。'
              'open.url 可用 github/openai 书签。workspace.status 可传当前或用户点名的工作区名。'
              '不匹配或有歧义时 action=none，argument 留空。不要猜测主机或私有路径。动作：' +
              '；'.join(key + ':' + value[0] for key, value in CATALOG.items()))
    user_input = (
        f'【工作区上下文参考】\n{context_text}\n\n【动作请求】\n{request}'
        if context_text else request
    )
    response = client.client(values).with_options(timeout=float(cfg.get('tools_timeout_s', 20)), max_retries=0).responses.parse(
        model=cfg.get('tools_model', 'gpt-5.4-nano'), instructions=prompt, input=user_input,
        text_format=Plan, tools=[], store=False, reasoning={'effort': 'none'}, max_output_tokens=500)
    if response.output_parsed is None:
        raise RuntimeError('未识别到支持的 DX 动作。')
    return response.output_parsed


def _match_indexed_workspace(argument, request, workspaces=None, active_workspace=''):
    if argument == 'workspace' and active_workspace:
        return active_workspace
    if not workspaces:
        return ''
    req_low = (request or '').lower()
    arg_low = (argument or '').strip().lower()
    for ws in workspaces:
        name = ws.get('name', '')
        root = ws.get('root', '')
        if not name or not root:
            continue
        if (arg_low and arg_low == name.lower() and name.lower() in req_low) or (
            not arg_low and name.lower() in req_low
        ):
            return root
    return ''


def resolve_path(argument, request, workspaces=None, active_workspace=''):
    aliases = {'home': None, 'documents': 'DOCUMENTS', 'downloads': 'DOWNLOAD', 'desktop': 'DESKTOP'}
    if argument in aliases:
        if argument == 'home':
            path = Path.home()
        else:
            result = subprocess.run(['xdg-user-dir', aliases[argument]], capture_output=True, text=True, timeout=2)
            if result.returncode or not result.stdout.strip():
                raise RuntimeError('这个常用目录尚未配置。')
            path = Path(result.stdout.strip())
    elif argument == 'workspace':
        if not active_workspace:
            raise RuntimeError('当前没有识别到活跃工作区目录。')
        path = Path(active_workspace)
    else:
        matched = _match_indexed_workspace(argument, request, workspaces, active_workspace)
        if matched:
            path = Path(matched)
        else:
            if argument not in request or not (argument.startswith('/') or argument.startswith('~/')):
                raise RuntimeError('请明确说出文件或目录路径。')
            path = Path(argument).expanduser()
    path = path.resolve()
    if not path.exists() or not (path.is_file() or path.is_dir()):
        raise RuntimeError('指定路径不存在。')
    if path.is_file() and (os.access(path, os.X_OK) or path.suffix.lower() in ('.desktop', '.sh', '.py', '.exe', '.appimage')):
        raise RuntimeError('此模块只打开文档和目录；运行程序请使用明确的命令工作流。')
    return str(path)


def _open_argv(target):
    if shutil.which('dx'):
        return ['dx', 'tools.pickopen', '-a', '__xdgopen__', target]
    if shutil.which('xdg-open'):
        return ['xdg-open', target]
    raise RuntimeError('系统缺少打开文件所需的 dx 或 xdg-open。')


def execute(plan, request, runner=subprocess.run, context_text='', workspaces=None, active_workspace=''):
    if plan.action not in CATALOG:
        raise RuntimeError('目前未接入这个动作，可在 dx v 查看支持清单。')
    if any(ord(char) < 32 or ord(char) == 127 for char in plan.argument):
        raise RuntimeError('动作参数包含无效字符。')
    title, argv = CATALOG[plan.action]
    if plan.action == 'context.inspect':
        summary = context_text.strip() or '暂无活跃工作区上下文。'
        return ToolResult(title + '\n' + summary, plan.action)
    if plan.action == 'workspace.status':
        repo = _match_indexed_workspace(plan.argument, request, workspaces, active_workspace) or active_workspace
        if not repo or not Path(repo).is_dir():
            raise RuntimeError('当前没有可查询的已索引工作区目录。')
        git_bin = shutil.which('git')
        if not git_bin:
            raise RuntimeError('本机未安装 git，无法查询工作区状态。')
        result = runner([git_bin, '-C', str(Path(repo).resolve()), 'status', '-sb'],
                        capture_output=True, text=True, timeout=10)
        if result.returncode:
            raise RuntimeError('当前工作区不是 Git 仓库或状态查询失败。')
        output = (result.stdout or '').strip() or '工作区干净。'
        return ToolResult(title + f' ({Path(repo).name})\n' + output[:6000], plan.action)
    if plan.action == 'open.path':
        argv = _open_argv(resolve_path(plan.argument, request, workspaces=workspaces, active_workspace=active_workspace))
    elif plan.action == 'open.url':
        bookmarks = {'github': 'https://github.com', 'openai': 'https://chatgpt.com'}
        url = bookmarks.get(plan.argument, plan.argument)
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise RuntimeError('请提供明确的 HTTP/HTTPS 网页。')
        if plan.argument not in bookmarks and url not in request:
            raise RuntimeError('网页地址需要在你的需求中明确给出。')
        argv = _open_argv(url)
    elif not shutil.which('dx'):
        raise RuntimeError('DX 尚未安装，无法调用工具模块。')
    result = runner(argv, capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise RuntimeError('DX 动作返回失败，请在历史中查看请求后重试。')
    if plan.action.startswith('open.'):
        return ToolResult('已提交打开请求。', plan.action, 'launched')
    output = result.stdout.strip()
    if len(output) > 6000:
        output = output[:6000] + '\n…输出已截断，完整信息可用原 DX 命令查询。'
    return ToolResult(title + '\n' + (output or '查询已完成。'), plan.action)


def run(client, request, cfg, context_text='', workspaces=None, active_workspace=''):
    if str(cfg.get('tools_enabled', 'true')).lower() != 'true':
        raise RuntimeError('实验工具模块已关闭，可在 dx v 中开启。')
    plan = select_plan(client, request, cfg, context_text=context_text)
    return execute(plan, request, context_text=context_text, workspaces=workspaces, active_workspace=active_workspace)
