"""DX Voice modules: ASR providers, rewrite, command generation, and explicit tools."""
MODULES = {
    'asr': {'name': '语音识别', 'provider_interface': 'dx_voice.asr entry points'},
    'rewrite': {'name': '快速重写', 'optional': True, 'screen_context_opt_in': True},
    'command': {'name': '命令生成', 'executes': False},
    'tools': {'name': 'DX Tools（实验）', 'executes': 'registered DX actions only'},
}
