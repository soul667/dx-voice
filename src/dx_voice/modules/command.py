"""Command-generation module. It never executes a generated command."""
from ..text_tools import Outcome, text_settings, validate_command


def generate(tools, raw, cfg, context_text=''):
    cfg = text_settings(cfg)
    shell = cfg.get('command_shell', 'bash')
    if shell not in ('bash', 'sh', 'zsh', 'fish'):
        raise RuntimeError('请选择支持的命令行 shell。')
    prompt = (f'你是纯文本 Linux {shell} 命令生成器。根据口述需求生成一条可直接粘贴的命令。'
              'text 字段只允许命令本身，不要解释、Markdown、代码围栏、前缀或尾注。'
              '不调用任何工具，不执行任何命令。缺少关键参数时使用清晰的占位符，不猜测私有地址或凭据。')
    if context_text:
        prompt += '当用户需求提到“当前项目/目录”或工作区索引中已列出的本地项目名时，可优先使用上下文中提供的已知路径、文件或技术栈来生成更准确的命令。'
    user_input = (
        f'【工作区上下文参考】\n{context_text}\n\n【命令需求】\n{raw}'
        if context_text else raw
    )
    try:
        command = tools.request(cfg, cfg.get('command_model', 'gpt-6.1-terra'), prompt, user_input,
                                float(cfg.get('command_timeout_s', 25)), 'low')
    except Exception:
        raise RuntimeError('命令生成失败，原始需求已保存在输入历史。') from None
    validate_command(command, shell)
    tag = 'command+ctx:' if context_text else 'command:'
    return Outcome(command, tag + cfg.get('command_model', 'gpt-6.1-terra'))
