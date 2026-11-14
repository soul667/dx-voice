"""DX Voice LAN Delta Input module — zero-dependency HTTP + SSE streaming delta input server."""
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import queue
import secrets
import socket
import subprocess
import threading
import time
from urllib.parse import parse_qs, urlparse

MAX_TEXT = 20000
MAX_DELETE = 256
DEFAULT_PORT = 8990
TERMINAL_CLASSES = (
    'terminal', 'kitty', 'alacritty', 'terminator', 'wezterm', 'konsole',
    'ghostty', 'foot', 'tilix', 'xfce4-terminal', 'mate-terminal', 'lxterminal',
    'sakura', 'rio', 'warp', 'tabby', 'hyper',
)


def compute_delta(prev_text, next_text):
    """Return (delete_count, append_text) to transform prev_text into next_text via common prefix."""
    prev_text = prev_text or ''
    next_text = next_text or ''
    limit = min(len(prev_text), len(next_text))
    prefix = 0
    while prefix < limit and prev_text[prefix] == next_text[prefix]:
        prefix += 1
    return len(prev_text) - prefix, next_text[prefix:]


def lan_ips():
    """Discover non-loopback LAN IPv4 addresses, prioritizing private LAN subnets over docker bridges."""
    ips = set()
    try:
        out = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=3).stdout.split()
        for ip in out:
            if ':' in ip or ip.startswith('127.'):
                continue
            ips.add(ip)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(('223.5.5.5', 80))
            local = sock.getsockname()[0]
            if local and not local.startswith('127.'):
                ips.add(local)
    except OSError:
        pass
    if not ips:
        return ['127.0.0.1']

    def _rank(ip):
        if ip.startswith('192.168.'):
            return (0, ip)
        if ip.startswith('10.'):
            return (1, ip)
        if ip.startswith('172.17.') or ip.startswith('172.18.'):
            return (3, ip)
        return (2, ip)

    return sorted(ips, key=_rank)


def norm_win_id(win_id):
    try:
        return hex(int(str(win_id).strip(), 16))
    except (TypeError, ValueError):
        return str(win_id or '').strip().lower()


class XDeltaInjector:
    """Thread-safe Linux X11 incremental delta injector (xclip + xdotool + wmctrl)."""

    def __init__(self, dry_run=False, runner=subprocess.run):
        self.dry_run = bool(dry_run)
        self.runner = runner
        self.lock = threading.Lock()
        self._restore_timer = None
        self._last_clipboard_sent = b''

    def list_windows(self):
        try:
            out = self.runner(['wmctrl', '-l'], capture_output=True, text=True, timeout=3).stdout
        except (OSError, subprocess.SubprocessError):
            return []
        windows = []
        for line in out.splitlines():
            parts = line.split(None, 3)
            if len(parts) >= 4:
                windows.append({'id': parts[0], 'title': parts[3][:80]})
        return windows

    def active_window_id(self):
        try:
            out = self.runner(['xdotool', 'getactivewindow'], capture_output=True, text=True, timeout=2).stdout.strip()
            if out:
                return hex(int(out))
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
        try:
            out = self.runner(
                ['xprop', '-root', '_NET_ACTIVE_WINDOW'], capture_output=True, text=True, timeout=2
            ).stdout
            if '#' in out:
                return norm_win_id(out.rsplit('#', 1)[1].strip())
        except (OSError, subprocess.SubprocessError):
            pass
        return ''

    def activate_window(self, win_id):
        target = norm_win_id(win_id)
        if not target:
            return False, '缺少窗口 ID'
        if self.dry_run:
            return True, ''
        try:
            res = self.runner(['wmctrl', '-i', '-a', win_id], capture_output=True, text=True, timeout=3)
        except (OSError, subprocess.SubprocessError) as exc:
            return False, str(exc)[:160]
        if res.returncode != 0:
            detail = (res.stderr or res.stdout or f'rc={res.returncode}').strip()
            return False, detail[:160]
        for _ in range(10):
            if self.active_window_id() == target:
                return True, ''
            time.sleep(0.05)
        return False, f'目标窗口 {win_id} 未获得焦点'

    def _get_clipboard(self):
        try:
            res = self.runner(['xclip', '-selection', 'clipboard', '-o'], capture_output=True, timeout=2)
            return res.stdout if res.returncode == 0 and res.stdout else b''
        except (OSError, subprocess.SubprocessError):
            return b''

    def _set_clipboard(self, data):
        res = self.runner(['xclip', '-selection', 'clipboard'], input=data, capture_output=True, timeout=2)
        if res.returncode != 0:
            detail = (res.stderr or b'').decode('utf-8', 'replace').strip()[:120]
            raise RuntimeError(f'写剪贴板失败: {detail or res.returncode}')

    def _schedule_restore(self, previous_bytes, sent_bytes, delay=1.2):
        if self._restore_timer is not None:
            self._restore_timer.cancel()

        def _restore():
            with self.lock:
                try:
                    if self._get_clipboard() == sent_bytes:
                        self._set_clipboard(previous_bytes)
                except (OSError, subprocess.SubprocessError, RuntimeError):
                    pass

        timer = threading.Timer(delay, _restore)
        timer.daemon = True
        timer.start()
        self._restore_timer = timer

    def _is_terminal_active(self):
        try:
            active = self.runner(['xdotool', 'getactivewindow'], capture_output=True, text=True, timeout=2).stdout.strip()
            if not active:
                return False
            wmclass = self.runner(['xprop', '-id', active, 'WM_CLASS'], capture_output=True, text=True, timeout=2).stdout.lower()
            return any(term in wmclass for term in TERMINAL_CLASSES)
        except (OSError, subprocess.SubprocessError):
            return False

    @staticmethod
    def _is_ascii_typable(text):
        return all(ch == '\n' or (0x20 <= ord(ch) <= 0x7E) for ch in text)

    def apply_delta(self, delete_count=0, text='', enter=False, window_id='',
                    restore_clipboard=True, prefer_keys=False):
        """Inject incremental backspaces and/or text delta into the active or locked X11 window."""
        delete_count = max(0, int(delete_count or 0))
        if delete_count > MAX_DELETE:
            raise ValueError(f'单次退格数不能超过 {MAX_DELETE}')
        text = str(text or '')
        if len(text) > MAX_TEXT:
            raise ValueError(f'单次文本不能超过 {MAX_TEXT} 字符')

        with self.lock:
            if window_id and not self.dry_run:
                target = norm_win_id(window_id)
                if self.active_window_id() != target:
                    ok, detail = self.activate_window(window_id)
                    if not ok:
                        raise RuntimeError(f'聚焦失败，未注入: {detail}')

            if self.dry_run:
                return 'dry-run'

            if delete_count > 0:
                keys = ['BackSpace'] * delete_count
                self.runner(['xdotool', 'key', '--clearmodifiers', '--delay', '0', *keys],
                            check=True, timeout=4)

            mode = 'none'
            if text:
                if prefer_keys and self._is_ascii_typable(text):
                    self.runner(['xdotool', 'type', '--clearmodifiers', '--delay', '0', text],
                                check=True, timeout=4)
                    mode = 'keys'
                else:
                    previous = self._get_clipboard() if restore_clipboard else b''
                    payload = text.encode('utf-8')
                    self._set_clipboard(payload)
                    self._last_clipboard_sent = payload
                    paste_key = 'ctrl+shift+v' if self._is_terminal_active() else 'ctrl+v'
                    self.runner(['xdotool', 'key', '--clearmodifiers', '--delay', '0', paste_key],
                                check=True, timeout=3)
                    if restore_clipboard:
                        self._schedule_restore(previous, payload)
                    mode = 'paste'
            elif delete_count > 0:
                mode = 'backspace'

            if enter:
                self.runner(['xdotool', 'key', '--clearmodifiers', '--delay', '0', 'Return'],
                            check=True, timeout=3)
                if mode == 'none':
                    mode = 'enter'

            return mode


GATE_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DX Voice · 局域网输入认证</title>
<style>
  :root{color-scheme:dark light;--bg:#0a0c10;--card:#131720;--bd:#263248;--fg:#f4f6fa;--mut:#94a3b8;--acc:#e4e4e7}
  @media(prefers-color-scheme:light){:root{--bg:#faf9f6;--card:#ffffff;--bd:#e4e1da;--fg:#0f172a;--mut:#475569;--acc:#18181b}}
  *{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--bg);color:var(--fg);font-family:system-ui,-apple-system,sans-serif;padding:20px}
  form{width:100%;max-width:360px;background:var(--card);border:1px solid var(--bd);border-radius:18px;padding:24px;box-shadow:0 18px 50px rgba(0,0,0,.18)}
  h1{margin:0 0 8px;font-size:18px}p{margin:0 0 16px;font-size:13px;color:var(--mut);line-height:1.5}
  input{width:100%;padding:12px 14px;border-radius:12px;border:1px solid var(--bd);background:transparent;color:var(--fg);font-size:16px;letter-spacing:2px;margin-bottom:12px}
  button{width:100%;padding:12px;border:0;border-radius:12px;background:var(--acc);color:var(--bg);font-weight:600;font-size:15px;cursor:pointer}
</style></head>
<body><form method="GET" action="/">
  <h1>DX Voice · 局域网流式输入</h1>
  <p>请输入电脑端显示的访问口令（Token），连接后即可实时向电脑传输增量文字。</p>
  <input name="k" placeholder="输入访问 Token" autofocus required autocomplete="off">
  <button type="submit">连接电脑</button>
</form></body></html>"""


APP_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>DX Voice · 局域网 Delta 流式输入</title>
<style>
  :root{
    color-scheme:dark light;
    --bg:#0a0c10;--panel:#131720;--raised:#1b2130;--border:#263248;
    --fg:#f4f6fa;--mut:#94a3b8;--accent:#f4f4f5;--accent-fg:#090d14;
    --ok:#34d399;--warn:#fbbf24;--err:#fb7185;
  }
  @media(prefers-color-scheme:light){
    :root{
      --bg:#faf9f6;--panel:#ffffff;--raised:#f2f0eb;--border:#e4e1da;
      --fg:#0f172a;--mut:#64748b;--accent:#18181b;--accent-fg:#ffffff;
      --ok:#059669;--warn:#d97706;--err:#dc2626;
    }
  }
  *{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
  body{margin:0;background:var(--bg);color:var(--fg);font-family:system-ui,-apple-system,"Noto Sans SC",sans-serif;min-height:100dvh;display:flex;flex-direction:column}
  .wrap{width:100%;max-width:680px;margin:0 auto;padding:14px 14px 22px;display:flex;flex-direction:column;gap:12px;flex:1}
  header{display:flex;align-items:center;justify-content:space-between;gap:10px}
  .brand{display:flex;align-items:center;gap:8px;font-weight:700;font-size:15px;letter-spacing:-.01em}
  .dot{width:8px;height:8px;border-radius:99px;background:var(--mut);transition:background .2s,box-shadow .2s}
  .dot.live{background:var(--ok);box-shadow:0 0 10px var(--ok)}
  .dot.busy{background:var(--warn);box-shadow:0 0 10px var(--warn)}
  .dot.err{background:var(--err)}
  .badge{font-size:12px;color:var(--mut);background:var(--raised);border:1px solid var(--border);padding:4px 10px;border-radius:99px;white-space:nowrap}
  .card{background:var(--panel);border:1px solid var(--border);border-radius:16px;padding:12px;display:flex;flex-direction:column;gap:10px}
  .row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  select{flex:1;min-width:160px;background:var(--raised);color:var(--fg);border:1px solid var(--border);border-radius:10px;padding:8px 10px;font-size:13px}
  button{background:var(--raised);color:var(--fg);border:1px solid var(--border);border-radius:10px;padding:8px 12px;font-size:13px;font-weight:500;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;gap:5px}
  button.primary{background:var(--accent);color:var(--accent-fg);border-color:transparent;font-weight:600}
  button.active{border-color:var(--ok);color:var(--ok)}
  button:active{transform:scale(.97)}
  textarea{width:100%;min-height:190px;flex:1;background:transparent;color:var(--fg);border:0;outline:none;resize:none;font-size:17px;line-height:1.55;font-family:inherit}
  textarea::placeholder{color:var(--mut);opacity:.7}
  .mirror{display:none;padding:9px 12px;border-radius:12px;background:var(--raised);border:1px solid var(--border);font-size:13px;line-height:1.45;align-items:center;justify-content:space-between;gap:8px}
  .mirror.show{display:flex}
  .mirror-text{flex:1;color:var(--fg);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .footer-bar{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;border-top:1px solid var(--border);padding-top:10px}
  .stat{font-size:12px;color:var(--mut)}
  .log{max-height:130px;overflow:auto;font-size:12px;color:var(--mut);display:flex;flex-direction:column;gap:4px}
  .log-item{display:flex;justify-content:space-between;gap:8px;padding:4px 6px;border-radius:8px;background:var(--raised)}
  .log-item b{color:var(--fg);font-weight:500}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="brand"><span class="dot" id="dot"></span><span>DX Voice · LAN Delta</span></div>
    <span class="badge" id="status-badge">连接中…</span>
  </header>

  <div class="mirror" id="mirror">
    <span class="badge">PC 听写</span>
    <span class="mirror-text" id="mirror-text"></span>
    <button type="button" id="pull-mirror">填入框内</button>
  </div>

  <div class="card">
    <div class="row">
      <select id="win-select"><option value="">当前焦点窗口（自动跟随）</option></select>
      <button type="button" id="refresh-win">刷新窗口</button>
      <button type="button" id="focus-win">聚焦</button>
    </div>
    <div class="row">
      <button type="button" id="mode-stream" class="active">⚡ 实时流式 Delta</button>
      <button type="button" id="mode-batch">批量发送</button>
      <label class="stat" style="margin-left:auto;display:flex;align-items:center;gap:5px">
        <input type="checkbox" id="opt-restore" checked> 恢复剪贴板
      </label>
    </div>
  </div>

  <div class="card" style="flex:1">
    <textarea id="editor" placeholder="在这里打字、粘贴，或使用手机键盘语音输入——每一个新字（Delta）都会实时流式注入到电脑光标处…" autofocus></textarea>
    <div class="footer-bar">
      <span class="stat" id="delta-stat">已同步 0 字 · 等待输入</span>
      <div class="row">
        <button type="button" id="btn-bksp">⌫ 退格</button>
        <button type="button" id="btn-enter">↵ 回车</button>
        <button type="button" id="btn-reset">仅清手机框</button>
        <button type="button" id="btn-send" class="primary">发送 / 补发</button>
      </div>
    </div>
  </div>

  <div class="card">
    <div class="row" style="justify-content:space-between">
      <span class="stat">最近 Delta 记录</span>
      <span class="stat" id="latency-stat">-- ms</span>
    </div>
    <div class="log" id="log"></div>
  </div>
</div>

<script>
(() => {
  const token = new URLSearchParams(location.search).get('k') || '';
  const clientId = Math.random().toString(36).slice(2, 10);
  const editor = document.getElementById('editor');
  const dot = document.getElementById('dot');
  const badge = document.getElementById('status-badge');
  const deltaStat = document.getElementById('delta-stat');
  const latencyStat = document.getElementById('latency-stat');
  const winSelect = document.getElementById('win-select');
  const logBox = document.getElementById('log');
  const mirror = document.getElementById('mirror');
  const mirrorText = document.getElementById('mirror-text');

  let streamMode = true;
  let composing = false;
  let syncedText = '';
  let seq = 0;
  let inflight = Promise.resolve();
  let flushTimer = null;
  let lastMirror = '';

  function setStatus(kind, text) {
    dot.className = 'dot ' + (kind || '');
    badge.textContent = text;
  }

  async function api(path, body) {
    const sep = path.includes('?') ? '&' : '?';
    const url = path + sep + 'k=' + encodeURIComponent(token);
    const opts = body !== undefined
      ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
      : { method: 'GET' };
    const t0 = performance.now();
    const res = await fetch(url, opts);
    const data = await res.json();
    latencyStat.textContent = Math.round(performance.now() - t0) + ' ms';
    if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
    return data;
  }

  function computeDelta(prev, next) {
    const n = Math.min(prev.length, next.length);
    let i = 0;
    while (i < n && prev.charCodeAt(i) === next.charCodeAt(i)) i++;
    return { del: prev.length - i, add: next.slice(i) };
  }

  function addLog(kind, msg) {
    const row = document.createElement('div');
    row.className = 'log-item';
    const left = document.createElement('b');
    left.textContent = msg;
    const right = document.createElement('span');
    right.textContent = kind;
    row.append(left, right);
    logBox.prepend(row);
    while (logBox.children.length > 20) logBox.lastChild.remove();
  }

  function queueDelta(del, add, enter = false) {
    if (!del && !add && !enter) return;
    const mySeq = ++seq;
    setStatus('busy', '流式传输中…');
    inflight = inflight.then(async () => {
      try {
        const res = await api('/api/delta', {
          client_id: clientId,
          seq: mySeq,
          delete_count: del,
          text: add,
          enter,
          window: winSelect.value,
          restore: document.getElementById('opt-restore').checked
        });
        setStatus('live', '已连接 · 实时同步');
        const label = (del ? '-' + del + ' ' : '') + (add ? '+' + JSON.stringify(add) : '') + (enter ? ' ↵' : '');
        deltaStat.textContent = '已同步 ' + syncedText.length + ' 字 · 最近: ' + label;
        addLog(res.mode || 'ok', label);
      } catch (err) {
        setStatus('err', err.message);
      }
    });
  }

  function flushStream() {
    if (!streamMode || composing) return;
    const next = editor.value;
    if (next === syncedText) return;
    const { del, add } = computeDelta(syncedText, next);
    syncedText = next;
    queueDelta(del, add, false);
  }

  editor.addEventListener('compositionstart', () => { composing = true; });
  editor.addEventListener('compositionend', () => {
    composing = false;
    flushStream();
  });
  editor.addEventListener('input', () => {
    if (!streamMode || composing) return;
    clearTimeout(flushTimer);
    flushTimer = setTimeout(flushStream, 65);
  });

  document.getElementById('mode-stream').onclick = () => {
    streamMode = true;
    syncedText = editor.value;
    document.getElementById('mode-stream').classList.add('active');
    document.getElementById('mode-batch').classList.remove('active');
    deltaStat.textContent = '已切换实时流式 · 从当前位置继续同步';
  };
  document.getElementById('mode-batch').onclick = () => {
    streamMode = false;
    document.getElementById('mode-batch').classList.add('active');
    document.getElementById('mode-stream').classList.remove('active');
    deltaStat.textContent = '批量模式 · 编辑完成后点击“发送”';
  };

  document.getElementById('btn-bksp').onclick = () => queueDelta(1, '', false);
  document.getElementById('btn-enter').onclick = () => {
    if (streamMode) flushStream();
    queueDelta(0, '', true);
  };
  document.getElementById('btn-reset').onclick = () => {
    editor.value = '';
    syncedText = '';
    deltaStat.textContent = '已清空手机输入框（电脑端保留已输入文字）';
    editor.focus();
  };
  document.getElementById('btn-send').onclick = () => {
    if (streamMode) {
      flushStream();
    } else if (editor.value) {
      const text = editor.value;
      syncedText = text;
      queueDelta(0, text, false);
      editor.value = '';
      syncedText = '';
    }
    editor.focus();
  };

  async function refreshWindows() {
    try {
      const cur = winSelect.value;
      const data = await api('/api/windows');
      winSelect.innerHTML = '<option value="">当前焦点窗口（自动跟随）</option>';
      for (const w of data.windows || []) {
        const opt = document.createElement('option');
        opt.value = w.id;
        opt.textContent = w.title;
        if (w.id === cur) opt.selected = true;
        winSelect.appendChild(opt);
      }
    } catch (_) {}
  }

  document.getElementById('refresh-win').onclick = refreshWindows;
  document.getElementById('focus-win').onclick = async () => {
    if (!winSelect.value) return;
    try {
      await api('/api/activate', { window: winSelect.value });
      setStatus('live', '已聚焦目标窗口');
    } catch (err) {
      setStatus('err', err.message);
    }
  };
  document.getElementById('pull-mirror').onclick = () => {
    if (!lastMirror) return;
    editor.value += lastMirror;
    if (streamMode) flushStream();
    editor.focus();
  };

  function connectEvents() {
    const es = new EventSource('/api/events?k=' + encodeURIComponent(token));
    es.onopen = () => setStatus('live', '已连接 · 实时同步');
    es.onerror = () => setStatus('err', '连接断开，重连中…');
    es.addEventListener('voice_partial', (e) => {
      const d = JSON.parse(e.data);
      if (d.text) {
        lastMirror = d.text;
        mirrorText.textContent = d.text;
        mirror.classList.add('show');
      }
    });
    es.addEventListener('voice_final', (e) => {
      const d = JSON.parse(e.data);
      if (d.text) {
        lastMirror = d.text;
        mirrorText.textContent = d.text;
        mirror.classList.add('show');
      }
    });
  }

  refreshWindows();
  connectEvents();
})();
</script>
</body>
</html>"""


class LanInputServer:
    """HTTP + SSE LAN delta input server that injects incremental text into the desktop."""

    def __init__(self, host='0.0.0.0', port=DEFAULT_PORT, token=None, dry_run=False, injector=None):
        self.host = host
        self.port = int(port)
        self.token = token or secrets.token_hex(3)
        self.injector = injector or XDeltaInjector(dry_run=dry_run)
        self.history = deque(maxlen=100)
        self._client_seqs = {}
        self._sse_clients = set()
        self._lock = threading.Lock()
        self._server = None
        self._thread = None

    def urls(self):
        return [f'http://{ip}:{self.port}/?k={self.token}' for ip in lan_ips()]

    def broadcast_event(self, event_type, payload):
        frame = f'event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n'.encode('utf-8')
        with self._lock:
            dead = []
            for q in self._sse_clients:
                try:
                    q.put_nowait(frame)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                self._sse_clients.discard(q)

    def _record(self, kind, **fields):
        entry = {'ts': time.strftime('%H:%M:%S'), 'kind': kind, **fields}
        with self._lock:
            self.history.appendleft(entry)
        return entry

    def _apply_delta_payload(self, body):
        client_id = str(body.get('client_id') or '').strip()[:32]
        seq = body.get('seq')
        if client_id and seq is not None:
            try:
                seq_num = int(seq)
            except (TypeError, ValueError):
                raise ValueError('seq 必须是整数') from None
            with self._lock:
                last_seq = self._client_seqs.get(client_id, 0)
                if seq_num <= last_seq:
                    return {'ok': True, 'duplicate': True, 'seq': seq_num, 'mode': 'duplicate'}
                self._client_seqs[client_id] = seq_num
        else:
            seq_num = 0

        delete_count = int(body.get('delete_count') or 0)
        text = str(body.get('text') or '')
        enter = bool(body.get('enter'))
        win_id = str(body.get('window') or '').strip()
        restore = bool(body.get('restore', True))
        prefer_keys = bool(body.get('prefer_keys', False))
        if not delete_count and not text and not enter:
            return {'ok': True, 'mode': 'noop', 'seq': seq_num}

        mode = self.injector.apply_delta(
            delete_count=delete_count,
            text=text,
            enter=enter,
            window_id=win_id,
            restore_clipboard=restore,
            prefer_keys=prefer_keys,
        )
        self._record('delta', mode=mode, delete_count=delete_count, text=text[:120], enter=enter, seq=seq_num)
        self.broadcast_event('delta_ack', {'seq': seq_num, 'mode': mode, 'delete_count': delete_count, 'added': len(text)})
        return {'ok': True, 'mode': mode, 'seq': seq_num, 'delete_count': delete_count, 'added_chars': len(text)}

    def start(self, blocking=False):
        if self._server is not None:
            return self.port
        parent = self

        class ReusableHTTPServer(ThreadingHTTPServer):
            allow_reuse_address = True
            daemon_threads = True

        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def log_message(self, fmt, *args):
                return

            def _send(self, code, payload, content_type='application/json; charset=utf-8'):
                if isinstance(payload, (dict, list)):
                    raw = json.dumps(payload, ensure_ascii=False).encode('utf-8')
                elif isinstance(payload, str):
                    raw = payload.encode('utf-8')
                else:
                    raw = payload
                self.send_response(code)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(raw)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(raw)

            def _is_authed(self, query):
                provided = query.get('k', [''])[0] or self.headers.get('X-DX-Token', '')
                return secrets.compare_digest(provided, parent.token)

            def do_GET(self):
                normalized = self.path.replace('%EF%BC%9F', '?').replace('？', '?')
                parsed = urlparse(normalized)
                query = parse_qs(parsed.query)
                if parsed.path == '/':
                    html = APP_HTML if self._is_authed(query) else GATE_HTML
                    return self._send(200, html, 'text/html; charset=utf-8')
                if not self._is_authed(query):
                    return self._send(403, {'error': 'token 无效'})
                if parsed.path == '/api/status':
                    return self._send(200, {
                        'ok': True,
                        'port': parent.port,
                        'urls': parent.urls(),
                        'dry_run': parent.injector.dry_run,
                        'clients': len(parent._sse_clients),
                        'recent_count': len(parent.history),
                    })
                if parsed.path == '/api/windows':
                    return self._send(200, {'windows': parent.injector.list_windows()})
                if parsed.path == '/api/history':
                    try:
                        limit = min(max(int(query.get('limit', ['50'])[0]), 1), 100)
                    except ValueError:
                        limit = 50
                    with parent._lock:
                        items = list(parent.history)[:limit]
                    return self._send(200, {'history': items})
                if parsed.path == '/api/events':
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
                    self.send_header('Cache-Control', 'no-cache')
                    self.send_header('Connection', 'keep-alive')
                    self.end_headers()
                    q = queue.Queue(maxsize=64)
                    with parent._lock:
                        parent._sse_clients.add(q)
                    try:
                        self.wfile.write(b'event: ready\ndata: {"ok":true}\n\n')
                        self.wfile.flush()
                        while parent._server is not None:
                            try:
                                chunk = q.get(timeout=15)
                            except queue.Empty:
                                chunk = b': keepalive\n\n'
                            self.wfile.write(chunk)
                            self.wfile.flush()
                    except OSError:
                        pass
                    finally:
                        with parent._lock:
                            parent._sse_clients.discard(q)
                    return
                return self._send(404, {'error': 'not found'})

            def do_POST(self):
                normalized = self.path.replace('%EF%BC%9F', '?').replace('？', '?')
                parsed = urlparse(normalized)
                query = parse_qs(parsed.query)
                if not self._is_authed(query):
                    return self._send(403, {'error': 'token 无效'})
                try:
                    length = int(self.headers.get('Content-Length', 0))
                    body = json.loads(self.rfile.read(length) or b'{}')
                except (ValueError, json.JSONDecodeError):
                    return self._send(400, {'error': '请求体不是合法 JSON'})

                if parsed.path == '/api/activate':
                    win_id = str(body.get('window') or '').strip()
                    ok, detail = parent.injector.activate_window(win_id)
                    if not ok:
                        return self._send(500, {'error': f'聚焦失败: {detail}'})
                    return self._send(200, {'ok': True})

                if parsed.path in ('/api/delta', '/api/send'):
                    try:
                        result = parent._apply_delta_payload(body)
                        return self._send(200, result)
                    except ValueError as exc:
                        return self._send(400, {'error': str(exc)})
                    except RuntimeError as exc:
                        return self._send(500, {'error': str(exc)})
                    except (OSError, subprocess.SubprocessError) as exc:
                        return self._send(500, {'error': f'注入失败: {exc}'})

                return self._send(404, {'error': 'not found'})

        self._server = ReusableHTTPServer((self.host, self.port), Handler)
        self.port = int(self._server.server_address[1])
        if blocking:
            try:
                self._server.serve_forever()
            finally:
                self.stop()
            return self.port
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True, name='dx-voice-lan-input')
        self._thread.start()
        return self.port

    def stop(self):
        srv = self._server
        self._server = None
        if srv is not None:
            try:
                srv.shutdown()
            except OSError:
                pass
            try:
                srv.server_close()
            except OSError:
                pass
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.5)
        self._thread = None


def render_qr_terminal(url):
    """Best-effort terminal QR code using segno if installed."""
    try:
        import segno
    except ImportError:
        return ''
    import io
    buf = io.StringIO()
    segno.make(url, error='m').terminal(out=buf, border=1)
    return buf.getvalue()
