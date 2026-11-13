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
               realtime_model='gpt-live-transcribe', realtime_delay='low', theme='light')


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


def save_config(data):
    private_dir(CONFIG.parent)
    fd, name = tempfile.mkstemp(dir=CONFIG.parent)
    with os.fdopen(fd, 'w', encoding='utf-8') as out:
        out.write('# 语音输入法设置：填在等号右边，不要加引号。保存后下次录音自动生效。\n'
                  '# API Key 只填在本机；录音会发送到下方 API 地址。\n'
                  '# 操作：长按 Ctrl 开始说话，松开 Ctrl 结束并识别。\n\n')
        for key, title in [('api_key', '你的 OpenAI API Key'), ('base_url', 'API 基础地址，含 /v1；可填兼容中转地址'),
                           ('model', '语音模型；中转不支持默认模型时，填服务商支持的语音模型名'),
                           ('prompt', '中文 / 英文及专业术语提示'), ('source', '麦克风源：留空使用系统默认'),
                           ('max_seconds', '单次最长秒数，最多 600 秒'),
                           ('proxy_url', '网络代理地址；留空使用进程环境代理'),
                           ('realtime_model', '实时语音识别模型'), ('realtime_delay', '实时延迟：minimal 最快，low 兼顾准确率'),
                           ('theme', '界面主题：light / dark / auto')]:
            value = str(data.get(key, DEFAULT[key])).replace('\n', ' ').replace('\r', ' ')
            out.write(f'# {title}\n{key}={value}\n\n')
    os.replace(name, CONFIG)


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
        terminal = any(x in wmclass for x in ('terminal', 'kitty', 'alacritty', 'terminator', 'wezterm', 'konsole'))
        key = 'ctrl+shift+v' if terminal else 'ctrl+v'
        subprocess.run(['xdotool', 'key', '--clearmodifiers', '--delay', '0', key], check=True, timeout=3)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


class CtrlHold:
    """Hold Ctrl alone for 400ms; release commits, other keys suppress it."""
    def __init__(self):
        self.since = None
        self.active = False
        self.suppressed = False

    def block(self):
        self.active = False
        self.suppressed = True

    def update(self, ctrl, other, now):
        if not ctrl:
            action = 'finish' if self.active else None
            self.since, self.active, self.suppressed = None, False, False
            return action
        if other:
            action = 'cancel' if self.active else None
            self.block()
            return action
        if self.suppressed or self.active:
            return None
        if self.since is None:
            self.since = now
        if now - self.since >= 0.4:
            self.active = True
            return 'start'
        return None


class App:
    def __init__(self):
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk, GLib
        self.Gtk, self.GLib = Gtk, GLib
        from .overlay import VoiceOverlay
        self.overlay = VoiceOverlay(theme=config().get('theme', 'light'),
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
        self.lock = open(RUNTIME / 'dx-voice.lock', 'w')
        fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        SOCKET.unlink(missing_ok=True)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.sock.bind(str(SOCKET))
        SOCKET.chmod(0o600)
        GLib.io_add_watch(self.sock.fileno(), GLib.IO_IN, self.receive)
        GLib.timeout_add(200, self.tick)
        # Query only current key state: no key grabs, no text-event recording.
        from Xlib import display, XK
        self.keyboard = display.Display()
        self.ctrl_codes = {self.keyboard.keysym_to_keycode(XK.string_to_keysym(k))
                           for k in ('Control_L', 'Control_R')}
        self.ctrl_hold = CtrlHold()
        GLib.timeout_add(25, self.poll_ctrl)
        from .realtime import Realtime
        self.realtime = Realtime(lambda kind, token, data: GLib.idle_add(self._network_event, kind, token, data))
        self.realtime.prepare(config())
        try:
            gi.require_version('AyatanaAppIndicator3', '0.1')
            from gi.repository import AyatanaAppIndicator3 as Indicator
            self.indicator = Indicator.Indicator.new('dx-voice', 'audio-input-microphone', Indicator.IndicatorCategory.APPLICATION_STATUS)
            self.indicator.set_status(Indicator.IndicatorStatus.ACTIVE)
            menu = Gtk.Menu()
            for title, command in [('开始 / 结束录音（也可长按 Ctrl）', 'toggle'), ('重试上次失败录音', 'retry'), ('取消录音', 'cancel'), ('打开 TXT 设置', 'settings'), ('图形设置', 'gui-settings')]:
                item = Gtk.MenuItem(label=title)
                item.connect('activate', lambda _, cmd=command: GLib.timeout_add(300, self.command, cmd))
                menu.append(item)
            menu.show_all()
            self.indicator.set_menu(menu)
        except (ValueError, ImportError):
            pass

    def poll_ctrl(self):
        state = self.keyboard.query_keymap()
        pressed = {k for k in range(8, 256) if state[k // 8] & (1 << (k % 8))}
        action = self.ctrl_hold.update(bool(pressed & self.ctrl_codes),
                                       bool(pressed - self.ctrl_codes), time.monotonic())
        if action == 'start':
            if self.phase == 'idle':
                print('ctrl_hold=start', flush=True)
                self.start()
            else:
                self.ctrl_hold.block()
        elif action == 'finish' and self.phase == 'recording':
            print('ctrl_hold=release', flush=True)
            self.finish()
        elif action == 'cancel' and self.phase == 'recording':
            self.command('cancel')
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
        if cmd == 'settings':
            if not CONFIG.exists():
                save_config(DEFAULT)
            subprocess.Popen(['xdg-open', str(CONFIG)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif cmd == 'gui-settings':
            self.settings()
        elif cmd == 'preview' and self.phase == 'idle':
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
                self.process()
            else:
                notify('没有待重试的录音。')
        elif cmd == 'cancel' and self.phase in ('recording', 'finishing'):
            self.realtime.cancel(self.token)
            self.stop_recorder(cancel=True)
            self.phase = 'finishing'
            notify('录音已取消。')
        return False

    def start(self):
        import uuid
        from .realtime import Capture
        cfg = config()
        if not cfg['api_key'].strip():
            notify('请先在设置中填写 API Key。')
            self.command('settings')
            return
        self.overlay.set_theme(cfg.get('theme', 'light'))
        self.target = active_window()
        self.token = uuid.uuid4().hex
        token = self.token
        fd, name = tempfile.mkstemp(prefix='speech-', suffix='.wav', dir=STATE)
        os.close(fd)
        self.path = Path(name)
        self.started = time.monotonic()
        self.limit = max(1, min(float(cfg.get('max_seconds', 300)), 600))
        self.phase = 'recording'
        self.audio_ready = False
        self.stream_error = ''
        self.released_at = None
        self.first_delta = None
        self.overlay.show('connecting', partial='')
        self.realtime.begin(token, cfg)
        def chunk(data, level):
            self.realtime.append(token, data)
            self.overlay.level = level
            if not self.audio_ready:
                self.audio_ready = True
                self.GLib.idle_add(self._audio_started, token)
        def done(seconds, cancelled, error):
            self.GLib.idle_add(self._audio_done, token, seconds, cancelled, error)
        try:
            self.capture = Capture(self.path, cfg.get('source', ''), chunk, done)
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
            self.ctrl_hold.block()
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
        self.overlay.show('processing', partial=self.overlay.partial)
        self.stop_recorder()

    def _audio_done(self, token, seconds, cancelled, error):
        if token != self.token:
            return False
        self.capture = None
        print(f'audio_seconds={seconds:.2f}', flush=True)
        if cancelled:
            self.path.unlink(missing_ok=True)
            self.phase = 'idle'
            return False
        if error or seconds < .1:
            self.realtime.cancel(token)
            self.phase = 'idle'
            if seconds < .1:
                self.path.unlink(missing_ok=True)
            notify(error or '本次未录到语音，已取消。')
            return False
        if self.stream_error:
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
            self.complete(text, '' if text else '未识别到语音。')
        elif kind == 'error':
            self.stream_error = data
            if self.phase == 'transcribing':
                self.complete('', data)
            else:
                self.overlay.show('error', data)
        return False

    def process(self):
        self.phase = 'retrying'
        self.token = None
        self.overlay.show('processing', partial='正在重试录音…')
        def work():
            try:
                text = transcription(self.path, config())
                self.GLib.idle_add(self.complete, text, '')
            except Exception as exc:
                message = str(exc) if isinstance(exc, RuntimeError) else '设置或录音文件异常。'
                self.GLib.idle_add(self.complete, '', message)
        threading.Thread(target=work, daemon=True).start()

    def complete(self, text, error):
        print('transcription=' + ('failed' if error else 'succeeded'), flush=True)
        self.phase = 'idle'
        if error:
            notify(error if '录音已保留' in error else error + ' 录音已保留，可从托盘菜单重试。')
            return False
        self.overlay.partial = text
        # Persist latest result only; do not log speech or API credentials.
        latest = STATE / 'last-transcript.txt'
        fd = os.open(latest, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as out:
            out.write(text)
        try:
            inserted = paste(text, self.target)
            notify('✓ 已输入。' if inserted else '✓ 已复制，按粘贴键输入（窗口已切换）。')
            self.path.unlink(missing_ok=True)
        except (OSError, subprocess.SubprocessError):
            notify('文本已保存在 last-transcript.txt，剪贴板不可用。')
        return False

    def settings(self):
        Gtk = self.Gtk
        if self.window:
            self.window.present()
            return
        cfg = config()
        dialog = Gtk.Dialog(title='DX Voice · 设置')
        dialog.set_default_size(540, 390)
        dialog.add_button('取消', Gtk.ResponseType.CANCEL)
        dialog.add_button('保存', Gtk.ResponseType.OK)
        self.window = dialog
        box = dialog.get_content_area()
        box.set_border_width(16)
        box.set_spacing(12)
        label = Gtk.Label(label='长按 Ctrl 开始录音，松开后识别并输入。\n边说边发送音频，浮窗实时显示识别结果。')
        label.set_xalign(0)
        box.add(label)
        fields = {}
        for key, title in [('api_key', 'API Key'), ('base_url', 'API 基础地址（含 /v1）'), ('realtime_model', '实时语音识别模型'), ('prompt', '术语 / 语言提示'), ('source', '麦克风源（留空使用系统默认）')]:
            row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
            name = Gtk.Label(label=title)
            name.set_xalign(0)
            row.add(name)
            entry = Gtk.Entry()
            entry.set_text(str(cfg.get(key, '')))
            if key == 'api_key':
                entry.set_visibility(False)
                entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
            row.add(entry)
            box.add(row)
            fields[key] = entry
        def response(_, code):
            if code == Gtk.ResponseType.OK:
                cfg.update({k: e.get_text().strip() for k, e in fields.items()})
                save_config(cfg)
                notify('设置已保存，可以按快捷键开始说话。')
            dialog.destroy()
            self.window = None
        dialog.connect('response', response)
        dialog.show_all()
        dialog.present()

    def run(self):
        try:
            self.Gtk.main()
        finally:
            self.stop_recorder(cancel=True)
            self.realtime.close()
            self.overlay.close()
            SOCKET.unlink(missing_ok=True)

