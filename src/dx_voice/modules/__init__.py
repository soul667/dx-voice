"""DX Voice modules: ASR providers, context index, rewrite, command generation, and explicit tools."""
MODULES = {
    'asr': {'name': '语音识别', 'provider_interface': 'dx_voice.asr entry points'},
    'context': {'name': '工作区上下文索引', 'local_index': 'sqlite-fts5', 'uploads_files': False},
    'rewrite': {'name': '快速重写', 'optional': True, 'screen_context_opt_in': True},
    'command': {'name': '命令生成', 'executes': False},
    'tools': {'name': 'DX Tools（实验）', 'executes': 'registered DX actions only'},
    'lan_input': {'name': '局域网流式输入', 'transport': 'http+sse', 'delta_streaming': True},
}
