"""DX Voice workspace assembled from Textual's standard widgets and the shared DX theme."""
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import uuid

from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.theme import Theme
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Select, Static, Switch, TabbedContent, TabPane, TextArea
from rich.text import Text

from . import app as voice
from .history import History

# All application settings are represented here; fields are standard Textual widgets.
SPEECH = [('hotkey_hold_ms', '长按门槛 / ms'), ('asr_provider', '识别后端'),
          ('realtime_model', '实时识别模型'), ('realtime_delay', '实时识别延迟'),
          ('source', '麦克风源（空为默认）'), ('vocabulary', '自定义词汇 / 逗号分隔'),
          ('prompt', '识别上下文提示'), ('max_seconds', '最长录音 / s'), ('theme', '浮窗外观'),
          ('asr_api_key', 'ASR Key（空则继承）'), ('asr_base_url', 'ASR 地址（空则继承）')]
REWRITE = [('cleanup_mode', '快速重写开关'), ('cleanup_model', '快速重写模型'),
           ('cleanup_timeout_s', '重写超时 / s'), ('rewrite_use_screen', '提供当前鼠标屏幕截图'),
           ('rewrite_image_detail', '截图精度')]
COMMAND = [('command_model', '命令模型'), ('command_shell', '目标 Shell'),
           ('command_output', '命令输出'), ('command_timeout_s', '生成超时 / s')]
TOOLS = [('tools_enabled', '开启实验工具模块'), ('tools_model', '动作选择模型'), ('tools_timeout_s', '动作选择超时 / s')]
CONNECTION = [('api_key', '公共 API Key'), ('base_url', '公共 API 地址'), ('proxy_url', '网络代理'),
              ('text_api_key', '文字 Key（空则继承）'), ('text_base_url', '文字地址（空则继承）'),
              ('model', '失败录音重试模型'), ('history_enabled', '记录本地输入历史')]
ALL_FIELDS = SPEECH + REWRITE + COMMAND + TOOLS + CONNECTION
SWITCHES = {'history_enabled', 'rewrite_use_screen', 'tools_enabled'}
CHOICES = {'cleanup_mode': [('关闭 · 原文直出最快', 'none'), ('开启 · 保守重写', 'light')],
           'realtime_delay': [(x, x) for x in ('minimal', 'low', 'medium', 'high', 'xhigh')],
           'rewrite_image_detail': [(x,x) for x in ('low','high','auto')],
           'theme': [('半透磨砂', 'frosted'), ('浅色', 'light'), ('深色', 'dark'), ('跟随桌面', 'auto')],
           'command_shell': [(x, x) for x in ('bash', 'fish', 'zsh', 'sh')],
           'command_output': [('只复制 · 手动粘贴', 'clipboard'), ('填入当前窗口 · 不回车', 'paste')]}
NUMBERS = {'hotkey_hold_ms': (200, 5000), 'max_seconds': (1, 600),
           'cleanup_timeout_s': (.2, 120), 'command_timeout_s': (1, 120), 'tools_timeout_s': (1, 120)}


def dx_palette():
    if not shutil.which('dx'):
        return {}
    try:
        result = subprocess.run(['dx', 'tui.engine', 'show'], capture_output=True, text=True, timeout=2)
        return {parts[0]: parts[1] for line in result.stdout.splitlines()
                if len(parts := line.split()) >= 2 and re.fullmatch(r'#[0-9a-fA-F]{6}', parts[1])}
    except (OSError, subprocess.SubprocessError):
        return {}


class VoiceTUI(App):
    TITLE = 'DX Voice / dx v'
    BINDINGS = [('ctrl+s', 'save', '保存全部'), ('f5', 'refresh', '刷新'), ('ctrl+q', 'quit', '退出')]
    CSS = '''
    #hint { height: 2; padding: 0 2; color: $text-muted; }
    TabbedContent { height: 1fr; }
    TabPane { padding: 1 2; }
    .field { height: 3; margin-bottom: 1; }
    .field Label { width: 28; padding-top: 1; }
    .field Input, .field Select { width: 1fr; }
    .field Switch { margin-top: 1; }
    #overview { height: auto; padding: 1 2; border: round $primary; }
    #history-table { height: 11; }
    #history-detail { height: 10; }
    #command-result { height: 9; }
    #tools-result { height: 9; }
    #command-request { margin-top: 1; }
    .buttons { height: 3; margin: 1 0; }
    .note { height: auto; margin-bottom: 1; color: $text-muted; }
    '''

    def __init__(self, settings=None, save=None, history_path=None, palette=None, initial_tab='overview'):
        super().__init__()
        self.values = dict(voice.DEFAULT, **(voice.config() if settings is None else settings))
        self.save_settings = save or voice.save_config
        self.history = History(history_path or voice.STATE / 'history.db')
        self.initial_tab = initial_tab
        self.rows = {}
        self.selected = None
        colors = dx_palette() if palette is None else palette
        if colors:
            self.register_theme(Theme(name='dx-shared', primary=colors['accent'], secondary=colors.get('accent2'),
                                      background=colors.get('bg'), foreground=colors.get('fg'),
                                      surface=colors.get('bg'), panel=colors.get('select_bg'),
                                      warning=colors.get('warn'), error=colors.get('err'), success=colors.get('ok'), dark=True))
            self.theme = 'dx-shared'

    def fields(self, entries):
        for key, title in entries:
            with Horizontal(classes='field'):
                yield Label(title)
                value = str(self.values.get(key, ''))
                if key in SWITCHES:
                    yield Switch(value.lower() in ('true', '1', 'yes', 'on'), id=key)
                elif key in CHOICES:
                    yield Select(CHOICES[key], value=value, allow_blank=False, id=key)
                else:
                    yield Input(value, password=key.endswith('api_key'), id=key)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static('Ctrl 长按：语音输入   |   Ctrl + Win：纯命令   |   Alt + Win：工具（实验）   |   设置保存在本机', id='hint')
        with TabbedContent(initial=self.initial_tab):
            with TabPane('概览', id='overview'):
                yield Static('Ctrl → 说话 → 松开输入\nCtrl + Win → 说命令需求 → 松开生成纯命令\n\nCtrl + 滚轮操作不触发语音；命令不会自动执行。', id='overview-body')
                with Horizontal(classes='buttons'):
                    yield Button('启动服务', id='start')
                    yield Button('停止服务', id='stop')
                yield Static('', id='service-status', markup=False)
                yield Static('TUI 主题跟随 DX 共享主题引擎，不在这里重复设置。\n原文直出不增加模型等待；轻整理会额外调用小模型。', classes='note')
            with TabPane('语音', id='speech'):
                with VerticalScroll():
                    yield Static('当前内置 OpenAI；千问等后端通过独立 ASR 适配器接入。', classes='note')
                    yield from self.fields(SPEECH)
            with TabPane('重写', id='rewrite'):
                with VerticalScroll():
                    yield Static('只影响普通语音输入。截图是独立开关：开启后会发送鼠标所在屏幕，本地历史不存图。关闭重写或截图开关时不向模型发送截图。', classes='note')
                    yield from self.fields(REWRITE)
            with TabPane('命令', id='command'):
                with VerticalScroll():
                    yield from self.fields(COMMAND)
                    yield Static('试用会调用上方模型，只生成命令，不执行。', classes='note')
                    yield Input(placeholder='例如：找出当前目录中大于 1GB 的文件', id='command-request')
                    with Horizontal(classes='buttons'):
                        yield Button('生成命令', id='generate', variant='primary')
                        yield Button('复制命令', id='copy-command', disabled=True)
                    yield TextArea(read_only=True, id='command-result', show_cursor=False)
            with TabPane('工具', id='tools'):
                with VerticalScroll():
                    yield from self.fields(TOOLS)
                    from .modules.tools import CATALOG
                    yield Static('支持动作：' + ' / '.join(v[0] for v in CATALOG.values()), classes='note')
                    yield Input(placeholder='例如：查看显示器状态 / 打开下载目录', id='tools-request')
                    with Horizontal(classes='buttons'):
                        yield Button('调用 DX Tools', id='run-tool', variant='primary')
                        yield Button('复制结果', id='copy-tools', disabled=True)
                    yield TextArea(read_only=True, id='tools-result', show_cursor=False)
            with TabPane('历史', id='history'):
                yield Static(str(self.history.path), classes='note', markup=False)
                yield DataTable(id='history-table', cursor_type='row')
                with Horizontal(classes='buttons'):
                    yield Button('复制结果', id='copy-result')
                    yield Button('复制原文', id='copy-raw')
                yield TextArea(read_only=True, id='history-detail', show_cursor=False)
            with TabPane('连接', id='connection'):
                with VerticalScroll():
                    yield from self.fields(CONNECTION)
        yield Footer()

    def on_mount(self):
        self.query_one('#history-table', DataTable).add_columns('时间', '模式', '状态', '内容')
        self.action_refresh()

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
                value = str(int(number)) if key in ('hotkey_hold_ms', 'max_seconds') else str(number)
            values[key] = value
        return values

    def action_save(self):
        try:
            self.values = self.collect()
            self.save_settings(self.values)
            self.notify('已保存，下次输入生效。')
        except (ValueError, OSError):
            self.notify('保存失败：请检查数值范围或文件权限。', severity='error')

    def action_refresh(self):
        from .cli import status
        try:
            state = status()
            self.query_one('#service-status', Static).update('服务：' + ('运行中' if state['service_active'] else '已停止') +
                                                            '  |  Key：' + ('已配置' if state['key_configured'] else '未配置'))
            table = self.query_one('#history-table', DataTable)
            table.clear()
            self.rows = {row['id']: row for row in self.history.recent(100)}
            for row in self.rows.values():
                summary = (row['result'] or row['raw'] or row['error']).replace('\n', ' ')[:75]
                label = {'recording': '录音中', 'processing': '处理中', 'inserted': '已输入', 'copied': '已复制',
                         'failed': '失败', 'cancelled': '已取消', 'generated': '已生成', 'saved': '已保存', 'executed':'已执行', 'launched':'已请求打开'}.get(row['status'], row['status'])
                table.add_row(row['created_at'][5:19].replace('T',' '), {'command':'命令','tools':'工具','dictation':'语音'}.get(row['mode'],row['mode']), label, Text(summary), key=row['id'])
        except (OSError, RuntimeError, sqlite3.Error):
            self.notify('状态或历史暂时不可读取。', severity='warning')

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        self.show_history_row(event.row_key.value)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted):
        self.show_history_row(event.row_key.value)

    def show_history_row(self, key):
        self.selected = self.rows.get(key)
        if self.selected:
            row = self.selected
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
        elif name in ('copy-result', 'copy-raw'):
            self.copy((self.selected or {}).get('result' if name == 'copy-result' else 'raw', ''))
        elif name in ('copy-command','copy-tools'):
            self.copy(self.query_one('#command-result' if name=='copy-command' else '#tools-result', TextArea).text)
        elif name in ('generate','run-tool'):
            mode = 'command' if name=='generate' else 'tools'
            request = self.query_one('#'+mode+'-request', Input).value.strip()
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
            self.query_one('#copy-command' if mode=='command' else '#copy-tools', Button).disabled = True
            self.query_one('#'+mode+'-result', TextArea).load_text('')
            self.run_worker(lambda: self.generate(request, cfg, mode), thread=True, exit_on_error=False)

    def generate(self, request, cfg, mode='command'):
        from .text_tools import TextTools
        token = uuid.uuid4().hex
        logging = str(cfg.get('history_enabled', 'true')).lower() == 'true'
        tools = TextTools()
        result, error = '', False
        try:
            if logging:
                self.history.begin(token, mode)
                self.history.update(token, raw=request, status='processing')
            if mode=='tools':
                from .modules.tools import run
                outcome = run(tools, request, cfg)
                processing='tools:'+outcome.action
                status=outcome.status
            else:
                outcome=tools.process('command',request,cfg)
                processing=outcome.processing
                status='generated'
            result = outcome.text
            if logging:
                self.history.update(token, result=result, status=status, processing=processing)
        except Exception:
            error = True
            if logging:
                try:
                    self.history.update(token, status='failed', error='命令生成失败' if mode=='command' else 'DX 动作调用失败')
                except Exception:
                    pass
        finally:
            tools.close()
            self.call_from_thread(self.generation_done, result, error, mode)

    def generation_done(self, result, error, mode='command'):
        self.query_one('#'+mode+'-result', TextArea).load_text(result)
        button=self.query_one('#generate' if mode=='command' else '#run-tool', Button)
        button.disabled=False
        button.label='生成命令' if mode=='command' else '调用 DX Tools'
        self.query_one('#copy-command' if mode=='command' else '#copy-tools', Button).disabled=not bool(result)
        if error:
            self.notify(('命令生成失败' if mode=='command' else 'DX 动作调用失败') + '；已开启历史时可找回原始需求。', severity='error')
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
