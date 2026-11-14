"""DX Voice terminal workspace assembled from Textual widgets and the shared DX theme."""
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import uuid

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.theme import Theme
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
    Switch,
    TabbedContent,
    TabPane,
    TextArea,
)

from . import __version__
from . import app as voice
from .history import History
from .modules.context import ContextIndex, inspect_active_window

# All application settings are represented here; fields are standard Textual widgets.
SPEECH = [
    ('hotkey_hold_ms', '长按门槛 / ms'),
    ('asr_provider', '识别后端'),
    ('realtime_model', '实时识别模型'),
    ('realtime_delay', '实时识别延迟'),
    ('source', '麦克风源（空为默认）'),
    ('vocabulary', '自定义词汇 / 逗号分隔'),
    ('prompt', '识别上下文提示'),
    ('max_seconds', '最长录音 / s'),
    ('theme', '浮窗外观'),
    ('asr_api_key', 'ASR Key（空则继承）'),
    ('asr_base_url', 'ASR 地址（空则继承）'),
]
REWRITE = [
    ('cleanup_mode', '快速重写开关'),
    ('cleanup_model', '快速重写模型'),
    ('cleanup_timeout_s', '重写超时 / s'),
    ('context_enabled', '智能工作区上下文索引'),
    ('context_roots', '额外索引目录（逗号分隔，空则自动）'),
    ('rewrite_use_screen', '提供当前鼠标屏幕截图'),
    ('rewrite_image_detail', '截图精度'),
]
COMMAND = [
    ('command_model', '命令模型'),
    ('command_shell', '目标 Shell'),
    ('command_output', '命令输出'),
    ('command_timeout_s', '生成超时 / s'),
]
TOOLS = [
    ('tools_enabled', '开启实验工具模块'),
    ('tools_model', '动作选择模型'),
    ('tools_timeout_s', '动作选择超时 / s'),
]
CONNECTION = [
    ('api_key', '公共 API Key'),
    ('base_url', '公共 API 地址'),
    ('proxy_url', '网络代理'),
    ('text_api_key', '文字 Key（空则继承）'),
    ('text_base_url', '文字地址（空则继承）'),
    ('model', '失败录音重试模型'),
    ('history_enabled', '记录本地输入历史'),
]
LAN_INPUT = [
    ('lan_input_enabled', '启用局域网流式输入服务'),
    ('lan_input_port', '局域网服务端口'),
    ('lan_input_token', '访问 Token（留空自动生成）'),
]
ALL_FIELDS = SPEECH + REWRITE + COMMAND + TOOLS + CONNECTION + LAN_INPUT
FIELD_LABELS = dict(ALL_FIELDS)
SWITCHES = {'history_enabled', 'rewrite_use_screen', 'tools_enabled', 'context_enabled', 'lan_input_enabled'}
CHOICES = {
    'cleanup_mode': [('关闭 · 原文直出最快', 'none'), ('开启 · 保守重写', 'light')],
    'realtime_delay': [(x, x) for x in ('minimal', 'low', 'medium', 'high', 'xhigh')],
    'rewrite_image_detail': [(x, x) for x in ('low', 'high', 'auto')],
    'theme': [
        ('极简浅色 · Minimal Light', 'light'),
        ('极简深色 · Minimal Dark', 'dark'),
        ('极简磨砂 · Minimal Frosted', 'frosted'),
        ('极简跟随桌面 · Minimal Auto', 'auto'),
        ('经典浅色（上一版） · Classic Light', 'classic-light'),
        ('经典深色（上一版） · Classic Dark', 'classic-dark'),
        ('经典磨砂（上一版） · Classic Frosted', 'classic-frosted'),
        ('经典跟随桌面（上一版） · Classic Auto', 'classic-auto'),
    ],
    'command_shell': [(x, x) for x in ('bash', 'fish', 'zsh', 'sh')],
    'command_output': [('只复制 · 手动粘贴', 'clipboard'), ('填入当前窗口 · 不回车', 'paste')],
}
NUMBERS = {
    'hotkey_hold_ms': (200, 5000),
    'max_seconds': (1, 600),
    'cleanup_timeout_s': (.2, 120),
    'command_timeout_s': (1, 120),
    'tools_timeout_s': (1, 120),
    'lan_input_port': (1024, 65535),
}

FIELD_GROUPS = {
    'speech': [
        ('触发与识别模型', '设置长按门槛、语音后端与实时延迟偏好', ('hotkey_hold_ms', 'asr_provider', 'realtime_model', 'realtime_delay')),
        ('音频采集与热词', '配置输入设备、热词词表、语境引导及悬浮窗材质', ('source', 'vocabulary', 'prompt', 'max_seconds', 'theme')),
        ('ASR 独立接口覆盖（可选）', '留空时自动复用“连接”页的公共凭据', ('asr_api_key', 'asr_base_url')),
    ],
    'rewrite': [
        ('轻量文本重写', '在极速原文直出与保守润色纠错间切换', ('cleanup_mode', 'cleanup_model', 'cleanup_timeout_s')),
        ('工作区上下文索引', '本地 SQLite FTS5 自动采集窗口与工程术语，显著改善中英同音识别（建议保持开启）', ('context_enabled', 'context_roots')),
        ('屏幕截图上下文（默认关闭）', '需配合上方“快速重写”同时开启；关闭可避免截屏+视觉模型耗时', ('rewrite_use_screen', 'rewrite_image_detail')),
    ],
    'command': [
        ('纯命令生成设置', '模型仅输出单行命令并作语法检查，绝不自动执行或发送回车', ('command_model', 'command_shell', 'command_output', 'command_timeout_s')),
    ],
    'tools': [
        ('实验动作路由器', '模型仅选择白名单 DX/工作区动作 ID，固定 argv 安全执行', ('tools_enabled', 'tools_model', 'tools_timeout_s')),
    ],
    'connection': [
        ('公共连接与网络代理', '以 0600 权限保存在本机配置文件，密钥输入框默认掩码隐藏', ('api_key', 'base_url', 'proxy_url')),
        ('文本接口覆盖与持久化', '可独立指定文字模型地址，配置失败录音重试模型及本地历史', ('text_api_key', 'text_base_url', 'model', 'history_enabled')),
    ],
    'lan': [
        ('局域网 Delta 流式输入框', '手机或局域网浏览器打开页面即可实时流式逐字注入（Delta）到电脑当前/指定窗口，也可独立运行 dx v lan serve', ('lan_input_enabled', 'lan_input_port', 'lan_input_token')),
    ],
}


def _blend_hex(hex_a, hex_b, weight):
    a = [int(hex_a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(hex_b[i:i + 2], 16) for i in (1, 3, 5)]
    return '#' + ''.join(f'{int(round(a[i] * (1.0 - weight) + b[i] * weight)):02x}' for i in range(3))


def dx_palette():
    if not shutil.which('dx'):
        return {}
    try:
        result = subprocess.run(['dx', 'tui.engine', 'show'], capture_output=True, text=True, timeout=2)
        return {
            parts[0]: parts[1]
            for line in result.stdout.splitlines()
            if len(parts := line.split()) >= 2 and re.fullmatch(r'#[0-9a-fA-F]{6}', parts[1])
        }
    except (OSError, subprocess.SubprocessError):
        return {}


class VoiceTUI(App):
    TITLE = f'DX Voice v{__version__} / dx v'
    BINDINGS = [
        ('ctrl+s', 'save', '保存全部'),
        ('f5', 'refresh', '刷新状态'),
        ('slash', 'focus_search', '搜索历史'),
        ('ctrl+q', 'quit', '退出'),
    ]
    CSS = '''
    #hint { height: auto; padding: 0 2; margin-bottom: 0; border-bottom: solid $panel; }
    TabbedContent { height: 1fr; }
    TabPane { padding: 1 2; }
    .mode-grid { height: auto; margin-bottom: 1; }
    .mode-card {
        width: 1fr; height: auto; padding: 1 2; margin-right: 1;
        border: round $panel; background: $surface;
    }
    .mode-card:last-of-type { margin-right: 0; }
    .mode-title { text-style: bold; color: $primary; margin-bottom: 0; }
    .mode-desc { color: $text-muted; }
    .section-card {
        height: auto; padding: 1 2; margin-bottom: 1;
        border: round $panel; background: $surface;
    }
    .section-title { text-style: bold; color: $primary; }
    .section-sub { color: $text-muted; margin-bottom: 1; }
    .field { height: 3; margin-bottom: 1; }
    .field Label { width: 30; padding-top: 1; }
    .field Input, .field Select { width: 1fr; }
    .field Switch { margin-top: 1; }
    #service-status {
        height: auto; padding: 1 2; margin-bottom: 1;
        border: round $primary; background: $surface;
    }
    #context-preview {
        height: auto; padding: 1 2; margin-bottom: 1;
        border: round $panel; background: $surface; color: $text-muted;
    }
    .search-row { height: 3; margin-bottom: 1; }
    #history-search { width: 1fr; margin-right: 1; }
    #history-count { width: 18; padding: 1 1; content-align: right middle; color: $text-muted; border: round $panel; }
    #history-table { height: 10; border: round $panel; }
    #history-meta { height: 1; padding: 0 1; margin-top: 1; color: $text-muted; }
    #history-detail { height: 8; border: round $panel; }
    #command-result { height: 9; }
    #tools-result { height: 9; }
    #command-request { margin-top: 1; }
    .buttons { height: 3; margin: 1 0; }
    .buttons Button { margin-right: 1; }
    .note { height: auto; margin-bottom: 1; color: $text-muted; }
    '''

    def __init__(self, settings=None, save=None, history_path=None, palette=None, initial_tab='overview', context_path=None):
        super().__init__()
        self.values = dict(voice.DEFAULT, **(voice.config() if settings is None else settings))
        self.save_settings = save or voice.save_config
        resolved_history = Path(history_path) if history_path else voice.STATE / 'history.db'
        self.history = History(resolved_history)
        resolved_context = Path(context_path) if context_path else (
            resolved_history.with_name('context.db') if history_path else voice.STATE / 'context.db'
        )
        self.context_index = ContextIndex(resolved_context)
        self.initial_tab = initial_tab
        self.rows = {}
        self.selected = None
        colors = dx_palette() if palette is None else palette
        if colors:
            bg = colors['bg']
            sel = colors.get('select_bg', bg)
            surface = _blend_hex(bg, sel, 0.24)
            panel = colors.get('border') or _blend_hex(bg, sel, 0.52)
            self.register_theme(Theme(
                name='dx-shared',
                primary=colors['accent'],
                secondary=colors.get('accent2'),
                background=bg,
                foreground=colors['fg'],
                surface=surface,
                panel=panel,
                warning=colors.get('warn'),
                error=colors.get('err'),
                success=colors.get('ok'),
                dark=True,
            ))
            self.theme = 'dx-shared'

    def fields(self, keys):
        for key in keys:
            title = FIELD_LABELS[key]
            with Horizontal(classes='field'):
                yield Label(title)
                value = str(self.values.get(key, ''))
                if key in SWITCHES:
                    yield Switch(value.lower() in ('true', '1', 'yes', 'on'), id=key)
                elif key in CHOICES:
                    yield Select(CHOICES[key], value=value, allow_blank=False, id=key)
                else:
                    yield Input(value, password=key.endswith('api_key'), id=key)

    def _compose_grouped_tab(self, tab_key):
        for title, subtitle, keys in FIELD_GROUPS[tab_key]:
            with Vertical(classes='section-card'):
                yield Static(title, classes='section-title')
                yield Static(subtitle, classes='section-sub')
                yield from self.fields(keys)

    def compose(self) -> ComposeResult:
        hold_ms = self.values.get('hotkey_hold_ms', '400')
        chord_ms = min(400, int(float(hold_ms))) if str(hold_ms).replace('.', '', 1).isdigit() else 400
        yield Header()
        yield Static('', id='hint')
        with TabbedContent(initial=self.initial_tab):
            with TabPane('概览', id='overview'):
                with VerticalScroll():
                    with Horizontal(classes='mode-grid'):
                        with Vertical(classes='mode-card'):
                            yield Static(f'Ctrl ({hold_ms}ms) · 实时听写', classes='mode-title')
                            yield Static('松开后直接输入至原窗口，不自动发送回车；Ctrl+滚轮自动避让。', classes='mode-desc')
                        with Vertical(classes='mode-card'):
                            yield Static(f'Ctrl + Win ({chord_ms}ms) · 纯命令', classes='mode-title')
                            yield Static('Terra 结合工作区上下文生成命令并作语法校验，绝不执行。', classes='mode-desc')
                        with Vertical(classes='mode-card'):
                            yield Static(f'Alt + Win ({chord_ms}ms) · 工作区动作', classes='mode-title')
                            yield Static('安全调度白名单 DX / Git / 目录打开动作，历史可查。', classes='mode-desc')
                    with Horizontal(classes='buttons'):
                        yield Button('启动服务', id='start', variant='primary')
                        yield Button('停止服务', id='stop')
                        yield Button('刷新上下文索引', id='refresh-context')
                        yield Button('预览浮窗动效', id='preview-hud')
                    yield Static('', id='service-status', markup=False)
                    yield Static('', id='context-preview', markup=False)
                    yield Static('设置统一维护在本工作区，按 Ctrl+S 保存；工作区上下文索引在本地 SQLite FTS5 运行，仅传递脱敏摘要术语。', classes='note')
            with TabPane('语音', id='speech'):
                with VerticalScroll():
                    yield from self._compose_grouped_tab('speech')
            with TabPane('重写', id='rewrite'):
                with VerticalScroll():
                    yield from self._compose_grouped_tab('rewrite')
            with TabPane('命令', id='command'):
                with VerticalScroll():
                    yield from self._compose_grouped_tab('command')
                    with Vertical(classes='section-card'):
                        yield Static('命令生成沙盒试用', classes='section-title')
                        yield Static('调用上方模型并注入已索引工作区上下文，仅输出与语法检查，不执行。', classes='section-sub')
                        yield Input(placeholder='例如：找出当前目录中大于 1GB 的文件', id='command-request')
                        with Horizontal(classes='buttons'):
                            yield Button('生成命令', id='generate', variant='primary')
                            yield Button('复制命令', id='copy-command', disabled=True)
                        yield TextArea(read_only=True, id='command-result', show_cursor=False)
            with TabPane('工具', id='tools'):
                with VerticalScroll():
                    yield from self._compose_grouped_tab('tools')
                    from .modules.tools import CATALOG
                    with Vertical(classes='section-card'):
                        yield Static('DX / 工作区工具试用', classes='section-title')
                        yield Static('支持动作：' + ' / '.join(v[0] for v in CATALOG.values()), classes='section-sub')
                        yield Input(placeholder='例如：查看显示器状态 / 查看当前工作区状态 / 打开下载目录', id='tools-request')
                        with Horizontal(classes='buttons'):
                            yield Button('调用 DX Tools', id='run-tool', variant='primary')
                            yield Button('复制结果', id='copy-tools', disabled=True)
                        yield TextArea(read_only=True, id='tools-result', show_cursor=False)
            with TabPane('局域网', id='lan'):
                with VerticalScroll():
                    yield from self._compose_grouped_tab('lan')
                    with Vertical(classes='section-card'):
                        yield Static('局域网访问链接与状态', classes='section-title')
                        yield Static('开启上方开关并按 Ctrl+S 保存，或命令行运行 dx v lan serve', classes='section-sub')
                        yield Static('', id='lan-status', markup=False)
                        with Horizontal(classes='buttons'):
                            yield Button('复制访问链接', id='copy-lan-url', variant='primary')
                            yield Button('保存并应用局域网服务', id='reload-lan')
            with TabPane('历史', id='history'):
                yield Static(str(self.history.path), classes='note', markup=False)
                with Horizontal(classes='search-row'):
                    yield Input(placeholder='搜索历史原文、结果、模式或状态… (/ 快速定位)', id='history-search')
                    yield Static('0 / 0 条', id='history-count', markup=False)
                yield DataTable(id='history-table', cursor_type='row')
                with Horizontal(classes='buttons'):
                    yield Button('复制结果', id='copy-result', variant='primary')
                    yield Button('复制原文', id='copy-raw')
                yield Static('未选中记录', id='history-meta', markup=False)
                yield TextArea(read_only=True, id='history-detail', show_cursor=False)
            with TabPane('连接', id='connection'):
                with VerticalScroll():
                    yield from self._compose_grouped_tab('connection')
        yield Footer()

    def on_mount(self):
        self.query_one('#history-table', DataTable).add_columns('时间', '模式', '状态', '内容')
        self.action_refresh()

    def action_focus_search(self):
        if isinstance(self.focused, (Input, TextArea)):
            return
        self.query_one(TabbedContent).active = 'history'
        self.query_one('#history-search', Input).focus()

    def collect(self):
        values = dict(self.values)
        for key, _ in ALL_FIELDS:
            widget = self.query_one('#' + key)
            value = ('true' if widget.value else 'false') if isinstance(widget, Switch) else str(widget.value).strip()
            if key in NUMBERS:
                try:
                    number = float(value)
                except ValueError:
                    raise ValueError(key + ' 必须是数字') from None
                low, high = NUMBERS[key]
                if not low <= number <= high:
                    raise ValueError(key + f' 范围是 {low}–{high}')
                value = str(int(number)) if key in ('hotkey_hold_ms', 'max_seconds', 'lan_input_port') else str(number)
            values[key] = value
        return values

    def action_save(self):
        try:
            self.values = self.collect()
            self.save_settings(self.values)
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
                    sock.sendto(b'lan-reload', str(voice.SOCKET))
            except OSError:
                pass
            self.action_refresh()
            self.notify('已保存，下次输入生效。')
        except (ValueError, OSError):
            self.notify('保存失败：请检查数值范围或文件权限。', severity='error')

    def _update_status_strip(self, state, recent_count):
        strip = Text()
        if state['service_active']:
            strip.append('● 服务运行中', style='bold green')
        else:
            strip.append('○ 服务已停止', style='bold red')
        strip.append('   |   ')
        strip.append('Key 已配置' if state['key_configured'] else 'Key 未配置',
                     style='cyan' if state['key_configured'] else 'yellow')
        hold_ms = self.values.get('hotkey_hold_ms', '400')
        strip.append(f'   |   Ctrl {hold_ms}ms / Ctrl+Win / Alt+Win   |   索引 {recent_count} 个工作区   |   v{__version__}',
                     style='dim')
        self.query_one('#hint', Static).update(strip)

    def action_refresh(self):
        from .cli import status
        try:
            state = status()
            recent = self.context_index.recent(10)
            self._update_status_strip(state, len(recent))
            self.query_one('#service-status', Static).update(
                f"运行状态：{'运行中' if state['service_active'] else '已停止'}"
                f"   |   凭据：{'已配置' if state['key_configured'] else '未配置'}"
                f"   |   浮窗材质：{self.values.get('theme', 'frosted')}"
                f"   |   重写模式：{self.values.get('cleanup_mode', 'none')}"
            )
            self._update_context_preview(recent)
            self._update_lan_status()
            self.rows = {row['id']: row for row in self.history.recent(100)}
            search = self.query_one('#history-search', Input).value
            self._populate_history_table(search)
        except (OSError, RuntimeError, sqlite3.Error):
            self.notify('状态或历史暂时不可读取。', severity='warning')

    def _update_context_preview(self, recent=None):
        if recent is None:
            recent = self.context_index.recent(5)
        if not recent:
            preview = '工作区索引：尚无记录（点击“刷新上下文索引”或开始语音输入后自动建立）。'
        else:
            lines = [f'工作区索引（最近 {len(recent)} 项）：']
            for ws in recent[:4]:
                branch = f" [{ws['branch']}]" if ws.get('branch') else ''
                summary = f" — {ws['summary']}" if ws.get('summary') else ''
                lines.append(f"• {ws['name']} ({ws['stack']}){branch} → {ws['root']}{summary}")
            preview = '\n'.join(lines)
        self.query_one('#context-preview', Static).update(preview)

    def _lan_urls(self):
        from .modules.lan_input import DEFAULT_PORT, lan_ips
        try:
            port = int(float(self.values.get('lan_input_port', str(DEFAULT_PORT)) or DEFAULT_PORT))
        except (TypeError, ValueError):
            port = DEFAULT_PORT
        token = str(self.values.get('lan_input_token') or '').strip() or '<自动生成>'
        return port, [f'http://{ip}:{port}/?k={token}' for ip in lan_ips()]

    def _update_lan_status(self):
        port, urls = self._lan_urls()
        listening = False
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=0.2):
                listening = True
        except OSError:
            pass
        enabled = str(self.values.get('lan_input_enabled', 'false')).lower() == 'true'
        state_text = '● 运行中' if listening else ('○ 已启用（待启动）' if enabled else '○ 未启用')
        lines = [f'状态：{state_text}   |   端口：{port}', *urls[:3]]
        self.query_one('#lan-status', Static).update('\n'.join(lines))

    def _populate_history_table(self, query=''):
        table = self.query_one('#history-table', DataTable)
        table.clear()
        q = (query or '').strip().lower()
        mode_map = {'command': ('命令', 'yellow'), 'tools': ('工具', 'green'), 'dictation': ('语音', 'cyan')}
        status_map = {
            'recording': ('● 录音中', 'yellow'),
            'processing': ('… 处理中', 'yellow'),
            'inserted': ('✓ 已输入', 'green'),
            'copied': ('⎘ 已复制', 'cyan'),
            'failed': ('✕ 失败', 'red'),
            'cancelled': ('◌ 已取消', 'dim'),
            'generated': ('⚙ 已生成', 'green'),
            'saved': ('✓ 已保存', 'green'),
            'executed': ('✓ 已执行', 'green'),
            'launched': ('↗ 已打开', 'green'),
        }
        shown = 0
        for row in self.rows.values():
            mode_label, mode_style = mode_map.get(row['mode'], (row['mode'], ''))
            status_label, status_style = status_map.get(row['status'], (row['status'], ''))
            if q:
                haystack = ' '.join([
                    row['raw'], row['result'], row['error'],
                    mode_label, status_label, row['mode'], row['status'], row.get('processing', ''),
                ]).lower()
                if q not in haystack:
                    continue
            shown += 1
            summary = (row['result'] or row['raw'] or row['error']).replace('\n', ' ')[:75]
            table.add_row(
                row['created_at'][5:19].replace('T', ' '),
                Text(mode_label, style=mode_style),
                Text(status_label, style=status_style),
                Text(summary),
                key=row['id'],
            )
        self.query_one('#history-count', Static).update(f'{shown} / {len(self.rows)} 条')

    def on_input_changed(self, event: Input.Changed):
        if event.input.id == 'history-search':
            self._populate_history_table(event.value)

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        self.show_history_row(event.row_key.value)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted):
        self.show_history_row(event.row_key.value)

    def show_history_row(self, key):
        self.selected = self.rows.get(key)
        if self.selected:
            row = self.selected
            pipeline = row.get('processing') or 'raw'
            self.query_one('#history-meta', Static).update(
                f"时间：{row['created_at']}   |   模式：{row['mode']}   |   状态：{row['status']}   |   处理：{pipeline}"
            )
            self.query_one('#history-detail', TextArea).load_text('原文\n' + row['raw'] + '\n\n结果\n' + row['result'])

    def copy(self, text):
        if not text:
            self.notify('没有可复制的结果。')
            return
        try:
            voice.paste(text, '')
            self.notify('已复制。')
        except (OSError, subprocess.SubprocessError):
            self.notify('剪贴板暂不可用。', severity='error')

    def on_button_pressed(self, event: Button.Pressed):
        name = event.button.id
        if name in ('start', 'stop'):
            from .cli import systemctl
            result = systemctl(*(['enable', '--now', 'dx-voice'] if name == 'start' else ['disable', '--now', 'dx-voice']))
            self.notify('已完成。' if not result.returncode else '操作失败，请检查服务配置。')
            self.action_refresh()
        elif name == 'preview-hud':
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
                    sock.sendto(b'preview', str(voice.SOCKET))
                self.notify('已发送浮窗预览信号。')
            except OSError:
                self.notify('后台服务未运行，请先点击“启动服务”。', severity='warning')
        elif name == 'refresh-context':
            try:
                cfg = self.collect()
            except ValueError:
                cfg = self.values
            snap = inspect_active_window()
            self.context_index.refresh(cfg, snap, force_discovery=True)
            self._update_context_preview()
            self.notify('工作区上下文索引已刷新。')
        elif name == 'copy-lan-url':
            _, urls = self._lan_urls()
            self.copy(urls[0] if urls else '')
        elif name == 'reload-lan':
            self.action_save()
        elif name in ('copy-result', 'copy-raw'):
            self.copy((self.selected or {}).get('result' if name == 'copy-result' else 'raw', ''))
        elif name in ('copy-command', 'copy-tools'):
            self.copy(self.query_one('#command-result' if name == 'copy-command' else '#tools-result', TextArea).text)
        elif name in ('generate', 'run-tool'):
            mode = 'command' if name == 'generate' else 'tools'
            request = self.query_one('#' + mode + '-request', Input).value.strip()
            if not request:
                self.notify('先输入需求。')
                return
            try:
                cfg = self.collect()
            except ValueError:
                self.notify('请先修正设置中的数值。', severity='error')
                return
            event.button.disabled = True
            event.button.label = '生成中…'
            self.query_one('#copy-command' if mode == 'command' else '#copy-tools', Button).disabled = True
            self.query_one('#' + mode + '-result', TextArea).load_text('')
            self.run_worker(lambda: self.generate(request, cfg, mode), thread=True, exit_on_error=False)

    def generate(self, request, cfg, mode='command'):
        from .text_tools import TextTools
        from .modules.context import build_turn_context
        token = uuid.uuid4().hex
        logging = str(cfg.get('history_enabled', 'true')).lower() == 'true'
        tools = TextTools()
        result, error = '', False
        try:
            if logging:
                self.history.begin(token, mode)
                self.history.update(token, raw=request, status='processing')
            context_text = ''
            if str(cfg.get('context_enabled', 'true')).lower() == 'true':
                context_text = build_turn_context(request, None, self.context_index)
            if mode == 'tools':
                from .modules.tools import run
                outcome = run(tools, request, cfg, context_text=context_text, workspaces=self.context_index.recent(10))
                processing = 'tools:' + outcome.action
                status = outcome.status
            else:
                outcome = tools.process('command', request, cfg, context_text=context_text) if context_text else tools.process('command', request, cfg)
                processing = outcome.processing
                status = 'generated'
            result = outcome.text
            if logging:
                self.history.update(token, result=result, status=status, processing=processing)
        except Exception:
            error = True
            if logging:
                try:
                    self.history.update(token, status='failed', error='命令生成失败' if mode == 'command' else 'DX 动作调用失败')
                except Exception:
                    pass
        finally:
            tools.close()
            self.call_from_thread(self.generation_done, result, error, mode)

    def generation_done(self, result, error, mode='command'):
        self.query_one('#' + mode + '-result', TextArea).load_text(result)
        button = self.query_one('#generate' if mode == 'command' else '#run-tool', Button)
        button.disabled = False
        button.label = '生成命令' if mode == 'command' else '调用 DX Tools'
        self.query_one('#copy-command' if mode == 'command' else '#copy-tools', Button).disabled = not bool(result)
        if error:
            self.notify(('命令生成失败' if mode == 'command' else 'DX 动作调用失败') + '；已开启历史时可找回原始需求。', severity='error')
        self.action_refresh()


def launch(in_terminal=False, initial_tab='overview'):
    if not in_terminal and sys.stdin.isatty() and sys.stdout.isatty():
        VoiceTUI(initial_tab=initial_tab).run()
        return
    terminal = shutil.which('gnome-terminal') or shutil.which('x-terminal-emulator')
    if not terminal:
        raise RuntimeError('请在交互终端运行 dx v。')
    separator = '--' if Path(terminal).name == 'gnome-terminal' else '-e'
    subprocess.Popen([terminal, separator, sys.executable, '-m', 'dx_voice.cli', 'tui', '--tab', initial_tab], env=dict(os.environ))
