#!/usr/bin/python3
"""GNOME/X11 dictation using OpenAI's audio transcription endpoint."""
import fcntl
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlparse
import wave

import requests

STATUS_UI = None

CONFIG = Path.home() / '.config/dx-voice/settings.txt'
STATE = Path.home() / '.local/state/dx-voice'
RUNTIME = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
SOCKET = RUNTIME / 'dx-voice.sock'
DEFAULT = dict(base_url='https://api.openai.com/v1', model='gpt-transcribe',
               api_key='', prompt='中文简体与 English 混合口述。保留技术术语。',
               source='', max_seconds=300, proxy_url='',
               realtime_model='gpt-live-transcribe', realtime_delay='low', theme='light', hotkey_hold_ms=400,
               cleanup_mode='none', cleanup_model='gpt-5.4-nano', cleanup_timeout_s=4,
               command_model='gpt-6.1-terra', command_shell=Path(os.environ.get('SHELL', '/bin/bash')).name if Path(os.environ.get('SHELL', '/bin/bash')).name in ('bash', 'sh', 'fish', 'zsh') else 'bash', command_output='clipboard', command_timeout_s=25,
               asr_provider='openai', asr_api_key='', asr_base_url='', text_api_key='', text_base_url='',
               rewrite_use_screen='false', rewrite_image_detail='low',
               context_enabled='true', context_roots='',
               tools_enabled='true', tools_model='gpt-5.4-nano', tools_timeout_s=20,
               history_enabled='true', vocabulary='DX Voice,Codex,Terra,Dot,Moz,Grokbot')

_CONFIG_CACHE = {'path': None, 'mtime_ns': -1, 'env': None, 'data': None}


def private_dir(path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)


def config():
    result = DEFAULT.copy()
    if CONFIG.exists():
        for line in CONFIG.read_text(encoding='utf-8-sig').splitlines():
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            key, sep, value = line.partition('=')
            if sep and key.strip().lower() in DEFAULT:
                result[key.strip().lower()] = value.strip()
    result['api_key'] = os.environ.get('OPENAI_API_KEY') or result['api_key']
    result['base_url'] = os.environ.get('OPENAI_BASE_URL') or result['base_url']
    return result


def cached_config():
    try:
        mtime = CONFIG.stat().st_mtime_ns
    except OSError:
        mtime = -1
    env = (os.environ.get('OPENAI_API_KEY', ''), os.environ.get('OPENAI_BASE_URL', ''))
    if (_CONFIG_CACHE['path'] == CONFIG and _CONFIG_CACHE['mtime_ns'] == mtime
            and _CONFIG_CACHE['env'] == env and _CONFIG_CACHE['data'] is not None):
        return _CONFIG_CACHE['data']
    data = config()
    _CONFIG_CACHE.update({'path': CONFIG, 'mtime_ns': mtime, 'env': env, 'data': data})
    return data


def save_config(data):
    private_dir(CONFIG.parent)
    fd, name = tempfile.mkstemp(dir=CONFIG.parent)
    with os.fdopen(fd, 'w', encoding='utf-8') as out:
        out.write('# 语音输入法设置：填在等号右边，不要加引号。保存后下次录音自动生效。\n'
                  '# API Key 只填在本机；录音会发送到下方 API 地址。\n'
                  '# 操作：长按 Ctrl 语音输入；长按 Ctrl+Win 生成纯命令；长按 Alt+Win 调用工具；松开完成。\n\n')
        for key, title in [('api_key', '你的 OpenAI API Key'), ('base_url', 'API 基础地址，含 /v1；可填兼容中转地址'),
                           ('model', '语音模型；中转不支持默认模型时，填服务商支持的语音模型名'),
                           ('prompt', '中文 / 英文及专业术语提示'), ('source', '麦克风源：留空使用系统默认'),
                           ('max_seconds', '单次最长秒数，最多 600 秒'),
                           ('proxy_url', '网络代理地址；留空使用进程环境代理'),
                           ('realtime_model', '实时语音识别模型'), ('realtime_delay', '实时延迟：minimal 最快，low 兼顾准确率'),
                           ('theme', '浮窗主题：frosted / light / dark / auto'),
                           ('hotkey_hold_ms', '单键 Ctrl 长按触发时长，毫秒（Ctrl+Win / Alt+Win 组合键固定约 400ms）'),
                           ('cleanup_mode', '口述整理：none 直出 / light 轻整理'), ('cleanup_model', '轻整理模型'),
                           ('cleanup_timeout_s', '轻整理超时秒数，超时保留原文'),
                           ('command_model', '命令生成模型'), ('command_shell', '目标 shell：bash / sh / zsh / fish'),
                           ('command_output', '命令输出：clipboard 只复制 / paste 填入当前窗口'),
                           ('command_timeout_s', '命令生成超时秒数'), ('history_enabled', '本地历史记录：true / false'),
                           ('vocabulary', '自定义词汇，逗号分隔'),
                           ('asr_provider', '语音后端，内置 openai；其他后端由适配器提供'),
                           ('asr_api_key', '语音后端专用 Key，留空继承公共连接'), ('asr_base_url', '语音后端专用地址，留空继承'),
                           ('text_api_key', '重写/命令/工具路由专用 Key，留空继承'), ('text_base_url', '文字模型专用地址，留空继承'),
                           ('context_enabled', '工作区上下文索引：true / false，读取当前窗口与本地项目目录结构辅助识别'),
                           ('context_roots', '额外索引的工作目录根路径，逗号分隔；留空自动发现常用项目目录'),
                           ('rewrite_use_screen', '截图辅助重写：true / false，开启后发送当前鼠标所在屏幕'),
                           ('rewrite_image_detail', '截图精度：low / high / auto'),
                           ('tools_enabled', '实验 DX Tools 模块：true / false'), ('tools_model', '动作选择模型'),
                           ('tools_timeout_s', '动作选择超时秒数')]:
            value = str(data.get(key, DEFAULT[key])).replace('\n', ' ').replace('\r', ' ')
            out.write(f'# {title}\n{key}={value}\n\n')
    os.replace(name, CONFIG)
    _CONFIG_CACHE['data'] = None


def notify(body):
    if STATUS_UI is not None:
        STATUS_UI(body)
        return
    subprocess.Popen(['notify-send', '-a', 'DX Voice', '-t', '3500',
                      'DX Voice', body], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)


def transcription(path, cfg):
    if not cfg['api_key'].strip():
        raise RuntimeError('请先在设置中填写 API Key。')
    base = cfg['base_url'].rstrip('/')
    parsed = urlparse(base)
    if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost', '::1')):
        raise RuntimeError('API 地址必须使用 HTTPS（本机服务除外）。')
    if not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise RuntimeError('API 地址格式不正确，请填写包含 /v1 的基础地址。')
    if Path(path).stat().st_size > 24 * 1024 * 1024:
        raise RuntimeError('录音超过上传大小限制。')
    data = {'model': cfg['model']}
    if cfg.get('prompt'):
        data['prompt'] = cfg['prompt']
    try:
        proxy = cfg.get('proxy_url', '').strip()
        network = {'proxies': {'https': proxy, 'http': proxy}} if proxy else {}
        with open(path, 'rb') as audio:
            response = requests.post(base + '/audio/transcriptions',
                                     headers={'Authorization': 'Bearer ' + cfg['api_key'].strip()},
                                     data=data, files={'file': ('speech.wav', audio, 'audio/wav')},
                                     timeout=(15, 120), allow_redirects=False, **network)
    except requests.RequestException:
        raise RuntimeError('无法连接语音 API 或请求超时，请检查网络和 API 地址。') from None
    if response.status_code != 200:
        reasons = {401: 'API Key 无效', 403: '账号或地区无权限', 404: '模型或接口不存在',
                   413: '录音过大', 429: '额度不足或请求过快'}
        raise RuntimeError(f"API HTTP {response.status_code}：{reasons.get(response.status_code, '请求失败，请检查服务状态与设置')}。")
    try:
        text = response.json()['text'].strip()
        if not isinstance(text, str):
            raise ValueError()
    except (ValueError, KeyError, AttributeError, TypeError):
        raise RuntimeError('API 返回了无法解析的转写结果。') from None
    if not text:
        raise RuntimeError('未识别到语音。')
    return text


def active_window():
    try:
        return subprocess.check_output(['xdotool', 'getactivewindow'], text=True, timeout=2).strip()
    except (subprocess.SubprocessError, OSError):
        return ''


def paste(text, target):
    # Clipboard is also a recovery path. Never send Enter or activate another app.
    subprocess.run(['xclip', '-selection', 'clipboard'], input=text.encode(), check=True, timeout=3)
    if not target or active_window() != target:
        return False
    try:
        wmclass = subprocess.check_output(['xprop', '-id', target, 'WM_CLASS'], text=True, timeout=2).lower()
        terminal = any(x in wmclass for x in (
            'terminal', 'kitty', 'alacritty', 'terminator', 'wezterm', 'konsole',
            'ghostty', 'foot', 'tilix', 'xfce4-terminal', 'mate-terminal', 'lxterminal',
            'sakura', 'rio', 'warp', 'tabby', 'hyper',
        ))
        key = 'ctrl+shift+v' if terminal else 'ctrl+v'
        subprocess.run(['xdotool', 'key', '--clearmodifiers', '--delay', '0', key], check=True, timeout=3)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


class HoldGesture:
    """Hold Ctrl alone, Ctrl+Win, or Alt+Win; other shortcuts and mouse actions take precedence."""
    def __init__(self, threshold=.4, chord_threshold=None):
        self.threshold = threshold
        self.chord_threshold = chord_threshold
        self.mode = 'dictation'
        self.since = None
        self.started_at = None
        self.active = False
        self.suppressed = False

    def block(self):
        self.active = False
        self.started_at = None
        self.suppressed = True

    def needed_threshold(self):
        if self.mode in ('command', 'tools'):
            return self.chord_threshold if self.chord_threshold is not None else min(self.threshold, .4)
        return self.threshold

    def update(self, ctrl, other, now, command=False, tools=False):
        if other:
            action = 'cancel' if self.active else None
            if ctrl:
                self.block()
            else:
                self.since, self.started_at, self.active, self.suppressed = None, None, False, False
            return action
        if not ctrl:
            action = 'finish' if self.active else None
            self.since, self.started_at, self.active, self.suppressed = None, None, False, False
            return action
        if self.suppressed:
            return None
        if self.active:
            if self.mode == 'dictation' and command and self.started_at is not None and now - self.started_at <= 1.2:
                self.mode = 'command'
                return 'upgrade'
            return None
        desired = 'tools' if tools else 'command' if command else 'dictation'
        if desired != self.mode:
            self.mode = desired
            self.since = now
        if self.since is None:
            self.since = now
        if now - self.since >= self.needed_threshold():
            self.active = True
            self.started_at = now
            return 'start'
        return None


def resolve_modifier_codes(keyboard):
    """Collect X11 keycodes for Control, Super/Win, and Alt/Meta including XKB aliases."""
    from Xlib import X, XK
    mapping = keyboard.get_keyboard_mapping(8, 248)
    super_symbols = {sym for k in ('Super_L', 'Super_R', 'Hyper_L', 'Hyper_R') if (sym := XK.string_to_keysym(k))}
    ctrl_symbols = {sym for k in ('Control_L', 'Control_R') if (sym := XK.string_to_keysym(k))}
    alt_symbols = {sym for k in ('Alt_L', 'Alt_R', 'Meta_L', 'Meta_R') if (sym := XK.string_to_keysym(k))}
    ctrl_codes = {index + 8 for index, row in enumerate(mapping) if set(row) & ctrl_symbols}
    super_codes = {index + 8 for index, row in enumerate(mapping) if set(row) & super_symbols}
    alt_codes = {index + 8 for index, row in enumerate(mapping) if set(row) & alt_symbols}
    modmap = keyboard.get_modifier_mapping()
    if modmap and len(modmap) > X.Mod4MapIndex:
        ctrl_codes |= {int(code) for code in modmap[X.ControlMapIndex] if code}
        alt_codes |= {int(code) for code in modmap[X.Mod1MapIndex] if code}
        super_codes |= {int(code) for code in modmap[X.Mod4MapIndex] if code}
    super_codes -= ctrl_codes
    alt_codes -= (ctrl_codes | super_codes)
    return ctrl_codes, super_codes, alt_codes


class PointerWatch:
    """Passive XI2 keyboard+pointer observer; avoids idle polling and catches wheel taps."""
    def __init__(self, connection):
        from Xlib.ext import xinput
        self.connection = connection
        self.root = connection.screen().root
        self.raw_button_press = xinput.RawButtonPress
        mask = xinput.RawKeyPressMask | xinput.RawKeyReleaseMask | xinput.RawButtonPressMask
        self.root.xinput_select_events([(xinput.AllMasterDevices, mask)])
        connection.sync()

    def activity(self):
        from Xlib import X
        pressed = False
        while self.connection.pending_events():
            event = self.connection.next_event()
            if getattr(event, 'evtype', None) == self.raw_button_press:
                pressed = True
        mask = X.Button1Mask | X.Button2Mask | X.Button3Mask | X.Button4Mask | X.Button5Mask
        return pressed or bool(self.root.query_pointer().mask & mask)


def hold_threshold(cfg):
    try:
        return max(.2, min(5, float(cfg.get('hotkey_hold_ms', 400)) / 1000))
    except (TypeError, ValueError):
        return .4


class App:
    def __init__(self):
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk, GLib
        self.Gtk, self.GLib = Gtk, GLib
        cfg = cached_config()
        from .overlay import VoiceOverlay
        self.overlay = VoiceOverlay(theme=cfg.get('theme', 'light'),
                                    on_cancel=lambda: self.command('cancel'),
                                    on_retry=lambda: self.command('retry'))
        global STATUS_UI
        STATUS_UI = self.show_status
        self.phase = 'idle'
        self.capture = None
        self.token = None
        self.path = None
        self.target = ''
        self.window = None
        self.started = 0
        self.released_at = None
        self.stream_error = ''
        self.indicator = None
        private_dir(STATE)
        from .history import History
        from .modules.context import ContextIndex
        from .text_tools import TextTools
        self.history = History(STATE / 'history.db')
        self.context_index = ContextIndex(STATE / 'context.db')
        self.text_tools = TextTools()
        self.mode = 'dictation'
        self.history_on = True
        self.history_error = False
        self.raw_text = ''
        self.snapshot = None
        self.screen_context = None
        self.screen_context_error = False
        self._screen_ready = None
        self.lock = open(RUNTIME / 'dx-voice.lock', 'w')
        fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        SOCKET.unlink(missing_ok=True)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.sock.bind(str(SOCKET))
        SOCKET.chmod(0o600)
        GLib.io_add_watch(self.sock.fileno(), GLib.IO_IN, self.receive)
        GLib.timeout_add(500, self.tick)
        # Query only current key state: no key grabs, no text-event recording.
        from Xlib import display
        self.keyboard = display.Display()
        from .shortcuts import SuperBinding
        self.super_binding = SuperBinding(STATE)
        self.ctrl_codes, self.super_codes, self.alt_codes = resolve_modifier_codes(self.keyboard)
        self.pointer_watch = PointerWatch(self.keyboard)
        self.hold = HoldGesture(hold_threshold(cfg))
        self._hold_timer = None
        GLib.io_add_watch(self.keyboard.fileno(), GLib.IO_IN, self._on_x11_io)
        from .modules.asr import load_backend
        self.asr_name = cfg.get('asr_provider', 'openai')
        self.asr_backend = load_backend(self.asr_name)
        self.realtime = self.asr_backend.create_realtime(lambda kind, token, data: GLib.idle_add(self._network_event, kind, token, data))
        self.realtime.prepare(self.asr_backend.settings(cfg))
        # Win alone stays available to GNOME.
        try:
            gi.require_version('AyatanaAppIndicator3', '0.1')
            from gi.repository import AyatanaAppIndicator3 as Indicator
            self.indicator = Indicator.Indicator.new('dx-voice', 'audio-input-microphone', Indicator.IndicatorCategory.APPLICATION_STATUS)
            self.indicator.set_status(Indicator.IndicatorStatus.ACTIVE)
            menu = Gtk.Menu()
            for title, command in [('开始 / 结束录音（长按 Ctrl）', 'toggle'), ('重试上次失败录音', 'retry'), ('取消录音', 'cancel'), ('设置与历史（dx v）', 'settings')]:
                item = Gtk.MenuItem(label=title)
                item.connect('activate', lambda _, cmd=command: GLib.timeout_add(300, self.command, cmd))
                menu.append(item)
            menu.show_all()
            self.indicator.set_menu(menu)
        except (ValueError, ImportError):
            pass

    def _on_x11_io(self, *_):
        self.poll_hotkey()
        self._ensure_hold_timer()
        return True

    def _ensure_hold_timer(self):
        if self._hold_timer is None and (self.hold.since is not None or self.hold.active or self.hold.suppressed or self.phase == 'recording'):
            self._hold_timer = self.GLib.timeout_add(20, self._hold_tick)

    def _hold_tick(self):
        self.poll_hotkey()
        if self.hold.since is not None or self.hold.active or self.hold.suppressed or self.phase == 'recording':
            return True
        self._hold_timer = None
        return False

    def poll_hotkey(self):
        state = self.keyboard.query_keymap()
        pressed = {k for k in range(8, 256) if state[k // 8] & (1 << (k % 8))}
        control = bool(pressed & self.ctrl_codes)
        super_key = bool(pressed & self.super_codes)
        alt = bool(pressed & self.alt_codes)
        tools = super_key and alt and not control
        command = control and super_key and not alt
        keep_chord = self.hold.active and (
            (self.hold.mode == 'tools' and (super_key or alt) and not control)
            or (self.hold.mode == 'command' and (control or super_key) and not alt)
        )
        ctrl = control or tools or keep_chord
        other = (control and alt) or bool(pressed - (self.super_codes | self.ctrl_codes | self.alt_codes)) or self.pointer_watch.activity()
        if ctrl and not other and self.hold.since is None and not self.hold.suppressed:
            self.hold.threshold = hold_threshold(cached_config())
        now = time.monotonic()
        action = self.hold.update(ctrl, other, now, command=command, tools=tools)
        if action == 'start':
            if self.phase == 'idle':
                print('hotkey_hold=start mode=' + self.hold.mode, flush=True)
                try:
                    self.start(mode=self.hold.mode)
                except (RuntimeError, ValueError, OSError):
                    self.hold.block()
                    self.phase = 'idle'
                    notify('模块配置有误，请在 dx v 中检查语音后端与连接。')
            else:
                self.hold.block()
        elif action == 'upgrade' and self.phase == 'recording':
            print('hotkey_hold=upgrade mode=' + self.hold.mode, flush=True)
            self.mode = self.hold.mode
            self.overlay.set_mode(self.mode)
            self.overlay.show('recording' if self.audio_ready else 'connecting', partial=self.overlay.partial)
        elif action == 'finish' and self.phase == 'recording':
            print('hotkey_hold=release', flush=True)
            self.finish()
        elif action == 'cancel' and self.phase == 'recording':
            self.command('cancel')
        elif action is None and self.phase == 'idle':
            if self.hold.since is not None and not self.hold.active and not self.hold.suppressed:
                elapsed = now - self.hold.since
                needed = self.hold.needed_threshold()
                if needed >= 0.55 and elapsed >= 0.26:
                    self.overlay.show_arming(
                        min(0.99, elapsed / needed),
                        mode=self.hold.mode,
                        theme=cached_config().get('theme', 'light'),
                    )
            elif self.overlay.phase == 'arming':
                self.overlay.dismiss_arming()
        return True

    def show_status(self, message):
        phase = 'success' if message.startswith('✓') else 'cancelled' if '已取消' in message else 'info' if '已保存' in message else 'error'
        self.overlay.show(phase, message, partial='' if phase == 'info' else None)

    def receive(self, *_):
        cmd = self.sock.recv(100).decode('utf-8', errors='replace')
        try:
            self.command(cmd)
        except Exception:
            notify('操作失败，请检查设置。')
        return True

    def command(self, cmd):
        print(f'command={cmd} phase={self.phase}', flush=True)
        if cmd in ('settings', 'gui-settings'):
            from .tui import launch
            launch(in_terminal=True)
        elif cmd == 'preview' and self.phase == 'idle':
            self.overlay.set_theme(cached_config().get('theme', 'light'))
            self.overlay.set_mode('dictation')
            self.overlay.set_context_label('')
            self.overlay.show('info', '长按 Ctrl 开始说话', partial='')
        elif cmd == 'toggle':
            if self.phase == 'recording':
                self.finish()
            elif self.phase == 'idle':
                self.start()
            else:
                self.overlay.show('processing', partial=self.overlay.partial)
        elif cmd == 'retry' and self.phase == 'idle':
            pending = sorted(STATE.glob('speech-*.wav'), key=lambda p: p.stat().st_mtime)
            if pending:
                self.path, self.target = pending[-1], ''
                saved = self.history.for_audio(self.path)
                self.mode = saved['mode'] if saved else 'command' if self.path.name.startswith('speech-command-') else 'tools' if self.path.name.startswith('speech-tools-') else 'dictation'
                self.process()
            else:
                notify('没有待重试的录音。')
        elif cmd == 'cancel' and self.phase in ('recording', 'finishing'):
            self.realtime.cancel(self.token)
            self.stop_recorder(cancel=True)
            self.phase = 'finishing'
            notify('录音已取消。')
        return False

    def start(self, mode='dictation'):
        import uuid
        from .modules.asr import load_backend
        from .modules.context import enrich_asr_settings, inspect_active_window
        cfg = cached_config()
        requested = cfg.get('asr_provider', 'openai')
        if requested != self.asr_name:
            backend = load_backend(requested)
            self.realtime.close()
            self.asr_backend = backend
            self.asr_name = requested
            self.realtime = backend.create_realtime(lambda kind, token, data: self.GLib.idle_add(self._network_event, kind, token, data))
        if getattr(self.asr_backend, 'requires_api_key', True) and not self.asr_backend.settings(cfg).get('api_key', '').strip():
            notify('请先在设置中填写语音后端 API Key。')
            self.command('settings')
            return
        if mode == 'tools' and str(cfg.get('tools_enabled', 'true')).lower() != 'true':
            notify('实验工具模块已关闭，可在 dx v 中开启。')
            return
        self.overlay.set_theme(cfg.get('theme', 'light'))
        self.snapshot = None
        context_on = str(cfg.get('context_enabled', 'true')).lower() == 'true'
        if context_on:
            try:
                self.snapshot = inspect_active_window(self.keyboard)
                self.context_index.refresh(cfg, self.snapshot)
            except Exception:
                self.snapshot = None
        self.target = (self.snapshot.window_id if self.snapshot and self.snapshot.window_id else '') or active_window()
        ctx_label = ''
        if self.snapshot:
            ctx_label = Path(self.snapshot.workspace_root).name if self.snapshot.workspace_root else self.snapshot.app_name
        self.overlay.set_context_label(ctx_label)
        self.token = uuid.uuid4().hex
        self.mode = mode
        self.overlay.set_mode(mode)
        self.turn_cfg = cfg
        self.history_on = str(cfg.get('history_enabled', 'true')).lower() in ('true', '1', 'yes', 'on')
        self.history_error = False
        self.raw_text = ''
        self.screen_context = None
        self.screen_context_error = False
        self._screen_ready = None
        token = self.token
        fd, name = tempfile.mkstemp(prefix='speech-' + mode + '-', suffix='.wav', dir=STATE)
        os.close(fd)
        self.path = Path(name)
        self.record_begin()
        self.started = time.monotonic()
        self.limit = max(1, min(float(cfg.get('max_seconds', 300)), 600))
        self.phase = 'recording'
        self.audio_ready = False
        self.stream_error = ''
        self.released_at = None
        self.first_delta = None
        self.overlay.show('connecting', partial='')
        asr_cfg = self.asr_backend.settings(cfg)
        if context_on:
            try:
                asr_cfg = enrich_asr_settings(asr_cfg, self.snapshot, self.context_index)
                if self.snapshot and self.snapshot.workspace_root:
                    self.context_index.maybe_distill_async(self.text_tools, cfg, self.snapshot.workspace_root)
            except Exception:
                pass
        self.realtime.begin(token, asr_cfg)
        def chunk(data, level):
            self.realtime.append(token, data)
            self.overlay.level = level
            if not self.audio_ready:
                self.audio_ready = True
                self.GLib.idle_add(self._audio_started, token)
        def done(seconds, cancelled, error):
            self.GLib.idle_add(self._audio_done, token, seconds, cancelled, error)
        try:
            self.capture = self.asr_backend.create_capture(self.path, cfg.get('source', ''), chunk, done)
        except OSError:
            self.realtime.cancel(token)
            self.phase = 'idle'
            self.path.unlink(missing_ok=True)
            notify('无法打开麦克风，请检查录音设备。')

    def _audio_started(self, token):
        if token == self.token and self.phase == 'recording':
            self.overlay.show('recording', partial=self.overlay.partial)
        return False

    def stop_recorder(self, cancel=False):
        if self.capture:
            self.capture.stop(cancel=cancel)

    def tick(self):
        if self.phase == 'recording' and time.monotonic() - self.started >= self.limit:
            self.hold.block()
            self.finish()
        elif self.phase == 'transcribing' and self.released_at and time.monotonic() - self.released_at > 12:
            self.realtime.cancel(self.token)
            self.complete('', '实时结果等待超时，录音已保留，可从托盘重试。')
        return True

    def finish(self):
        if self.phase != 'recording':
            return
        self.phase = 'finishing'
        self.released_at = time.monotonic()
        self.stop_recorder()
        self.overlay.show('processing', partial=self.overlay.partial)
        if self.mode == 'dictation' and self.turn_cfg.get('cleanup_mode') == 'light' and str(self.turn_cfg.get('rewrite_use_screen', 'false')).lower() == 'true':
            token = self.token
            turn_cfg = self.turn_cfg
            ready = threading.Event()
            self._screen_ready = ready
            def grab():
                from .modules.screen import capture_rewrite_context
                try:
                    image = capture_rewrite_context(turn_cfg)
                    if token == self.token:
                        self.screen_context = image
                except Exception:
                    if token == self.token:
                        self.screen_context = None
                        self.screen_context_error = True
                        self.record(processing='screen-context-unavailable')
                finally:
                    ready.set()
            threading.Thread(target=grab, daemon=True).start()

    def _audio_done(self, token, seconds, cancelled, error):
        if token != self.token:
            return False
        self.capture = None
        print(f'audio_seconds={seconds:.2f}', flush=True)
        if cancelled:
            self.record(status='cancelled', raw='', result='', audio_file='')
            self.path.unlink(missing_ok=True)
            self.phase = 'idle'
            return False
        if error or seconds < .1:
            self.record(status='failed', error=error or '未录到语音')
            self.realtime.cancel(token)
            self.phase = 'idle'
            if seconds < .1:
                self.path.unlink(missing_ok=True)
            notify(error or '本次未录到语音，已取消。')
            return False
        if self.stream_error:
            self.record(status='failed', error=self.stream_error)
            self.phase = 'idle'
            notify(self.stream_error)
            return False
        if self.released_at is None:
            self.released_at = time.monotonic()
        self.phase = 'transcribing'
        self.overlay.show('processing', partial=self.overlay.partial)
        self.realtime.commit(token)
        return False

    def _network_event(self, kind, token, data):
        if token != self.token:
            return False
        if kind == 'partial':
            if self.first_delta is None:
                self.first_delta = time.monotonic()
                print(f'first_text_seconds={self.first_delta - self.started:.3f} before_release={self.released_at is None}', flush=True)
            self.overlay.partial = data
            self.overlay.canvas.queue_draw()
        elif kind == 'final':
            text, latency = data
            released = self.released_at or time.monotonic()
            print(f'release_to_final_seconds={time.monotonic() - released:.3f} server_finalize_seconds={latency:.3f}', flush=True)
            if text:
                self.process_text(text)
            else:
                self.complete('', '未识别到语音。')
        elif kind == 'error':
            self.stream_error = data
            if self.phase == 'transcribing':
                self.complete('', data)
            else:
                self.overlay.show('error', data)
        return False

    def process(self):
        import uuid
        self.token = uuid.uuid4().hex
        self.turn_cfg = config()
        self.snapshot = None
        self.screen_context = None
        self.screen_context_error = False
        self._screen_ready = None
        self.history_on = str(self.turn_cfg.get('history_enabled', 'true')).lower() == 'true'
        self.history_error = False
        self.overlay.set_context_label('')
        self.overlay.set_mode(self.mode)
        self.record_begin()
        self.phase = 'retrying'
        self.overlay.show('processing', partial='正在重试录音…')
        def work():
            try:
                from .modules.asr import load_backend
                text = load_backend(self.turn_cfg.get('asr_provider', 'openai')).transcribe_file(self.path, self.turn_cfg)
                self.GLib.idle_add(self.process_text, text)
            except Exception as exc:
                message = str(exc) if isinstance(exc, RuntimeError) else '设置或录音文件异常。'
                self.GLib.idle_add(self.complete, '', message)
        threading.Thread(target=work, daemon=True).start()

    def record_begin(self):
        if self.history_on:
            try:
                self.history.begin(self.token, self.mode, self.path)
            except Exception:
                self.history_error = True
                print('history=write-failed', flush=True)

    def record(self, **values):
        if self.history_on and self.token:
            try:
                self.history.update(self.token, **values)
            except Exception:
                self.history_error = True
                print('history=write-failed', flush=True)

    def process_text(self, raw):
        self.raw_text = raw
        self.record(raw=raw, status='processing')
        cfg = self.turn_cfg
        if self.mode == 'dictation' and cfg.get('cleanup_mode', 'none') == 'none':
            return self.complete(raw, '', 'raw')
        self.phase = 'processing'
        self.overlay.show('processing', partial=raw)
        token = self.token
        screen_ready = getattr(self, '_screen_ready', None)
        def work():
            try:
                if screen_ready is not None:
                    screen_ready.wait(timeout=2.0)
                context_text = ''
                workspaces = None
                active_workspace = ''
                if str(cfg.get('context_enabled', 'true')).lower() == 'true' and getattr(self, 'context_index', None) is not None:
                    try:
                        from .modules.context import build_turn_context
                        recent_hist = self.history.recent(5) if self.history_on else None
                        snap = getattr(self, 'snapshot', None)
                        active_workspace = getattr(snap, 'workspace_root', '') if snap else ''
                        workspaces = self.context_index.recent(10)
                        context_text = build_turn_context(raw, snap, self.context_index, recent_hist)
                    except Exception:
                        context_text = ''
                if self.mode == 'tools':
                    from .modules.tools import run
                    outcome = run(self.text_tools, raw, cfg, context_text=context_text,
                                  workspaces=workspaces, active_workspace=active_workspace)
                    self.GLib.idle_add(self.complete_tools, token, outcome)
                elif self.mode == 'command':
                    from .modules.command import generate
                    outcome = generate(self.text_tools, raw, cfg, context_text=context_text)
                    self.GLib.idle_add(done, outcome.text, '', outcome.processing)
                else:
                    from .modules.rewrite import process
                    outcome = process(self.text_tools, raw, cfg, self.screen_context, context_text=context_text)
                    if self.screen_context_error:
                        outcome.processing += ':no-screen'
                    self.GLib.idle_add(done, outcome.text, '', outcome.processing)
            except Exception as exc:
                message = str(exc) if isinstance(exc, RuntimeError) else '文本处理失败，原文已保存在历史。'
                self.GLib.idle_add(done, '', message, '')
        def done(text, error, processing):
            if token == self.token:
                self.complete(text, error, processing)
            return False
        threading.Thread(target=work, daemon=True).start()
        return False

    def complete_tools(self, token, outcome):
        if token != self.token:
            return False
        self.phase = 'idle'
        self.record(result=outcome.text, status=outcome.status, processing='tools:' + outcome.action, audio_file='')
        self.overlay.show('action', 'DX Tools 动作完成', partial=outcome.text)
        self.path.unlink(missing_ok=True)
        self.screen_context = None
        self._screen_ready = None
        return False

    def complete(self, text, error, processing='raw'):
        print('transcription=' + ('failed' if error else 'succeeded'), flush=True)
        self.phase = 'idle'
        self.screen_context = None
        if error:
            self.record(status='failed', error=error)
            notify(error if '录音已保留' in error else error + ' 录音已保留，可从托盘菜单重试。')
            return False
        self.overlay.partial = text
        # Service logs stay content-free; transcripts live only in private state/history.
        latest = STATE / 'last-transcript.txt'
        fd = os.open(latest, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as out:
            out.write(text)
        try:
            target = '' if self.mode == 'command' and self.turn_cfg.get('command_output', 'clipboard') == 'clipboard' else self.target
            inserted = paste(text, target)
            self.record(result=text, status='inserted' if inserted else 'copied', processing=processing, audio_file='')
            message = '✓ 命令已复制，粘贴后自行运行。' if self.mode == 'command' and not inserted else '✓ 已输入。' if inserted else '✓ 已复制，按粘贴键输入（窗口已切换）。'
            if self.history_error:
                message += ' 本地历史保存失败。'
            elif processing.startswith('raw:'):
                message += ' 整理未采用，已保留原文。'
            elif processing.endswith(':no-screen'):
                message += ' 截图不可用，本次按纯文本处理。'
            notify(message)
            self.path.unlink(missing_ok=True)
        except (OSError, subprocess.SubprocessError):
            self.record(result=text, status='saved', processing=processing, error='剪贴板不可用')
            notify('文本已保存在 last-transcript.txt，剪贴板不可用。')
        return False

    def run(self):
        try:
            self.Gtk.main()
        finally:
            self.stop_recorder(cancel=True)
            self.realtime.close()
            try:
                self.text_tools.close()
            finally:
                try:
                    self.super_binding.release()
                finally:
                    self.overlay.close()
                    self.keyboard.close()
                    SOCKET.unlink(missing_ok=True)

