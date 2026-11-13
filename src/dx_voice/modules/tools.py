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
    'open.path': ('打开明确指定的文档或目录', None),
    'open.url': ('打开明确指定的网页', None),
}


class Plan(BaseModel):
    action: Literal['display.status', 'system.status', 'gpu.status', 'disk.status', 'ports.status',
                    'shortcuts.list', 'open.path', 'open.url', 'none']
    argument: str


@dataclass
class ToolResult:
    text: str
    action: str
    status: str = 'executed'


def select_plan(client, request, cfg):
    from ..text_tools import text_settings
    # Use the same provider configuration, but only a typed ID/argument can leave the model.
    values = text_settings(cfg)
    prompt = ('从以下 DX 动作清单中选择一个动作，不生成 shell。参数只能来自用户明确给出的路径或 URL。'
              'open.path 可用别名 home/documents/downloads/desktop。open.url 可用 github/openai 书签。'
              '不匹配或有歧义时 action=none，argument 留空。不要猜测主机或私有路径。动作：' +
              '；'.join(key + ':' + value[0] for key, value in CATALOG.items()))
    response = client.client(values).with_options(timeout=float(cfg.get('tools_timeout_s', 20)), max_retries=0).responses.parse(
        model=cfg.get('tools_model', 'gpt-5.4-nano'), instructions=prompt, input=request,
        text_format=Plan, tools=[], store=False, reasoning={'effort': 'none'}, max_output_tokens=500)
    if response.output_parsed is None:
        raise RuntimeError('未识别到支持的 DX 动作。')
    return response.output_parsed


def resolve_path(argument, request):
    aliases = {'home': None, 'documents': 'DOCUMENTS', 'downloads': 'DOWNLOAD', 'desktop': 'DESKTOP'}
    if argument in aliases:
        if argument == 'home':
            path = Path.home()
        else:
            result = subprocess.run(['xdg-user-dir', aliases[argument]], capture_output=True, text=True, timeout=2)
            if result.returncode or not result.stdout.strip():
                raise RuntimeError('这个常用目录尚未配置。')
            path = Path(result.stdout.strip())
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


def execute(plan, request, runner=subprocess.run):
    if plan.action not in CATALOG:
        raise RuntimeError('目前未接入这个动作，可在 dx v 查看支持清单。')
    if any(ord(char) < 32 or ord(char) == 127 for char in plan.argument):
        raise RuntimeError('动作参数包含无效字符。')
    title, argv = CATALOG[plan.action]
    if not shutil.which('dx'):
        raise RuntimeError('DX 尚未安装，无法调用工具模块。')
    if plan.action == 'open.path':
        argv = ['dx', 'tools.pickopen', '-a', '__xdgopen__', resolve_path(plan.argument, request)]
    elif plan.action == 'open.url':
        bookmarks = {'github': 'https://github.com', 'openai': 'https://chatgpt.com'}
        url = bookmarks.get(plan.argument, plan.argument)
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise RuntimeError('请提供明确的 HTTP/HTTPS 网页。')
        if plan.argument not in bookmarks and url not in request:
            raise RuntimeError('网页地址需要在你的需求中明确给出。')
        argv = ['dx', 'tools.pickopen', '-a', '__xdgopen__', url]
    result = runner(argv, capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise RuntimeError('DX 动作返回失败，请在历史中查看请求后重试。')
    if plan.action.startswith('open.'):
        return ToolResult('已提交打开请求。', plan.action, 'launched')
    output = result.stdout.strip()
    if len(output) > 6000:
        output = output[:6000] + '\n…输出已截断，完整信息可用原 DX 命令查询。'
    return ToolResult(title + '\n' + (output or '查询已完成。'), plan.action)


def run(client, request, cfg):
    if str(cfg.get('tools_enabled', 'true')).lower() != 'true':
        raise RuntimeError('实验工具模块已关闭，可在 dx v 中开启。')
    plan = select_plan(client, request, cfg)
    return execute(plan, request)
