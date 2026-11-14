"""Persistent live transcription and low-latency PCM capture. No GUI dependencies."""
import audioop
import base64
import json
import os
import queue
import shutil
import signal
import subprocess
import threading
import time
from urllib.parse import urlsplit, urlunsplit
import wave

from websockets.sync.client import connect

RATE = 24000


class Capture:
    def __init__(self, path, source, on_chunk, on_done):
        self.path, self.on_chunk, self.on_done = path, on_chunk, on_done
        self.cancelled = False
        self.bytes = 0
        if shutil.which('parec'):
            command = ['parec', '--raw', '--rate=24000', '--channels=1', '--format=s16le',
                       '--latency-msec=20', '--process-time-msec=10',
                       '--client-name=DX Voice', '--stream-name=Voice input']
            if source:
                command.append('--device=' + source)
        elif shutil.which('arecord'):
            command = ['arecord', '-q', '-t', 'raw', '-f', 'S16_LE', '-c', '1', '-r', '24000']
            if source:
                command.extend(['-D', source])
        else:
            raise OSError('No audio capture utility (parec/arecord) available')
        self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self):
        error = ''
        try:
            with wave.open(str(self.path), 'wb') as out:
                out.setnchannels(1)
                out.setsampwidth(2)
                out.setframerate(RATE)
                tail = b''
                while True:
                    data = os.read(self.process.stdout.fileno(), 1920)
                    if not data:
                        break
                    data = tail + data
                    tail = data[len(data) // 2 * 2:]
                    data = data[:len(data) // 2 * 2]
                    if data:
                        self.bytes += len(data)
                        out.writeframesraw(data)
                        if not self.cancelled:
                            self.on_chunk(data, min(1.0, audioop.rms(data, 2) / 5200))
            self.process.wait(timeout=2)
            if self.process.returncode not in (0, -signal.SIGINT):
                error = '麦克风连接中断。'
        except Exception:
            error = '无法读取麦克风，请检查系统录音设备。'
        finally:
            self.process.stdout.close()
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait()
            self.on_done(self.bytes / (RATE * 2), self.cancelled, error)

    def stop(self, cancel=False):
        self.cancelled = self.cancelled or cancel
        if self.process.poll() is None:
            try:
                self.process.send_signal(signal.SIGINT)
            except ProcessLookupError:
                return
            def force():
                if self.process.poll() is None:
                    try:
                        self.process.kill()
                    except ProcessLookupError:
                        pass
            timer = threading.Timer(1, force)
            timer.daemon = True
            timer.start()


def session_update(cfg):
    transcription = {'model': cfg.get('realtime_model', 'gpt-live-transcribe'),
                     'delay': cfg.get('realtime_delay', 'low'),
                     'languages': ['zh', 'en'], 'prompt': cfg.get('prompt', '')}
    keywords = [word.strip() for word in cfg.get('vocabulary', '').replace('，', ',').split(',')]
    keywords = [word for word in keywords if word and len(word) <= 80 and not any(c in word for c in '<>\r\n')]
    if keywords:
        transcription['keywords'] = keywords[:64]
    return {'type': 'session.update', 'session': {'type': 'transcription', 'audio': {'input': {
        'format': {'type': 'audio/pcm', 'rate': RATE},
        'transcription': transcription,
        'turn_detection': None}}}}


class Realtime:
    """One warm connection; event-driven reader avoids idle polling and coalesces PCM frames."""
    def __init__(self, callback):
        self.callback = callback
        self.commands = queue.Queue()
        self.stopping = threading.Event()
        self.ready = False
        self.ws = None
        self._conn_id = 0
        self._reader = None
        self.current = None
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def prepare(self, cfg):
        self.commands.put(('prepare', None, cfg))

    def begin(self, token, cfg):
        self.commands.put(('begin', token, cfg))

    def append(self, token, data):
        self.commands.put(('audio', token, data))

    def commit(self, token):
        self.commands.put(('commit', token, None))

    def cancel(self, token):
        self.commands.put(('cancel', token, None))

    def close(self):
        self.stopping.set()
        self.commands.put(('close', None, None))

    @staticmethod
    def connection_signature(cfg):
        return tuple(cfg.get(k, '') for k in ('base_url', 'api_key', 'proxy_url', 'realtime_model'))

    @staticmethod
    def session_signature(cfg):
        return tuple(cfg.get(k, '') for k in ('realtime_delay', 'prompt', 'vocabulary'))

    @staticmethod
    def signature(cfg):
        return Realtime.connection_signature(cfg) + Realtime.session_signature(cfg)

    def _reader_loop(self, ws, conn_id):
        try:
            while not self.stopping.is_set():
                raw = ws.recv()
                self.commands.put(('server', conn_id, json.loads(raw)))
        except Exception as exc:
            self.commands.put(('ws_closed', conn_id, exc))

    def _disconnect(self):
        self.ready = False
        self._conn_id += 1
        ws, self.ws = self.ws, None
        reader, self._reader = self._reader, None
        if ws:
            try:
                ws.close()
            except Exception:
                pass
        if reader and reader is not threading.current_thread():
            reader.join(timeout=0.5)

    def _connect(self, cfg):
        parsed = urlsplit(cfg['base_url'].rstrip('/'))
        if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1', '::1')):
            raise RuntimeError('实时接口需要安全的 HTTPS 地址。')
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise RuntimeError('API 基础地址格式不正确。')
        url = urlunsplit(('wss' if parsed.scheme == 'https' else 'ws', parsed.netloc,
                          parsed.path + '/realtime', 'intent=transcription', ''))
        self.ws = connect(url, additional_headers={'Authorization': 'Bearer ' + cfg['api_key'].strip()},
                          proxy=cfg.get('proxy_url') or True, open_timeout=8, close_timeout=.5,
                          compression=None, ping_interval=20, ping_timeout=10, max_size=2**20)
        self.ws.recv(timeout=5)  # session.created
        self.ws.send(json.dumps(session_update(cfg)))
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            event = json.loads(self.ws.recv(timeout=6))
            if event.get('type') == 'error':
                raise RuntimeError('实时语音配置未被 API 接受，请检查实时模型。')
            if event.get('type') == 'session.updated':
                self.ready = True
                self._conn_id += 1
                conn_id = self._conn_id
                self._reader = threading.Thread(target=self._reader_loop, args=(self.ws, conn_id), daemon=True)
                self._reader.start()
                print('realtime=ready', flush=True)
                return
        raise RuntimeError('实时语音连接超时。')

    def _run(self):
        cfg = None
        conn_sig = None
        sess_sig = None
        retry_at = 0.0
        item_id = None
        text = ''
        committed_at = None
        while not self.stopping.is_set():
            try:
                messages = []
                need_connect = not self.ws and bool(cfg and cfg.get('api_key'))
                if need_connect and time.monotonic() >= retry_at:
                    wait_for = 0.0
                elif need_connect:
                    wait_for = max(0.05, retry_at - time.monotonic())
                else:
                    wait_for = 5.0
                try:
                    if wait_for > 0:
                        messages.append(self.commands.get(timeout=wait_for))
                    else:
                        messages.append(self.commands.get_nowait())
                    while len(messages) < 80:
                        messages.append(self.commands.get_nowait())
                except queue.Empty:
                    pass

                audio_buf = bytearray()

                def flush_audio():
                    if audio_buf and self.ws and self.current:
                        self.ws.send(json.dumps({
                            'type': 'input_audio_buffer.append',
                            'audio': base64.b64encode(bytes(audio_buf)).decode(),
                        }))
                    audio_buf.clear()

                for command, token, payload in messages:
                    if command == 'audio':
                        if token == self.current:
                            audio_buf.extend(payload)
                        continue
                    flush_audio()
                    if command == 'close':
                        self._disconnect()
                        return
                    if command in ('prepare', 'begin'):
                        new_conn_sig = self.connection_signature(payload)
                        new_sess_sig = self.session_signature(payload)
                        if new_conn_sig != conn_sig:
                            self._disconnect()
                            cfg, conn_sig, sess_sig = payload, new_conn_sig, new_sess_sig
                        elif new_sess_sig != sess_sig:
                            cfg, sess_sig = payload, new_sess_sig
                            if self.ws:
                                self.ready = False
                                self.ws.send(json.dumps(session_update(cfg)))
                        if command == 'begin':
                            self.current = token
                            item_id, text, committed_at = None, '', None
                            if not self.ws:
                                self._connect(cfg)
                            self.ws.send(json.dumps({'type': 'input_audio_buffer.clear'}))
                            self.callback('connected', token, None)
                    elif command == 'commit' and token == self.current:
                        committed_at = time.monotonic()
                        self.ws.send(json.dumps({'type': 'input_audio_buffer.commit'}))
                    elif command == 'cancel' and token == self.current:
                        self.current = None
                        self._disconnect()  # cancel late server events as well as buffered audio
                        retry_at = 0.0
                    elif command == 'ws_closed':
                        if token == self._conn_id:
                            raise RuntimeError('实时语音网络连接中断，录音已保留。')
                    elif command == 'server':
                        if token != self._conn_id:
                            continue
                        event = payload
                        kind = event.get('type', '')
                        if kind == 'session.updated':
                            self.ready = True
                            continue
                        if kind == 'error':
                            raise RuntimeError('实时语音服务返回错误，请检查模型、余额或网络。')
                        if not self.current:
                            continue
                        if kind == 'input_audio_buffer.committed':
                            item_id = event.get('item_id')
                        elif kind == 'conversation.item.input_audio_transcription.delta':
                            if item_id and event.get('item_id') != item_id:
                                continue
                            item_id = event.get('item_id') or item_id
                            text += event.get('delta', '')
                            self.callback('partial', self.current, text)
                        elif kind == 'conversation.item.input_audio_transcription.completed':
                            if not committed_at or (item_id and event.get('item_id') != item_id):
                                continue
                            final = event.get('transcript', '').strip()
                            latency = time.monotonic() - committed_at
                            self.callback('final', self.current, (final, latency))
                            self.current = None
                        elif kind == 'conversation.item.input_audio_transcription.failed':
                            raise RuntimeError('实时识别未完成，录音已保留。')
                flush_audio()
                if not self.ws and cfg and cfg.get('api_key') and time.monotonic() >= retry_at:
                    self._connect(cfg)
            except Exception as exc:
                token, self.current = self.current, None
                self._disconnect()
                retry_at = time.monotonic() + 5
                if token:
                    message = str(exc) if isinstance(exc, RuntimeError) else '实时语音网络连接中断，录音已保留。'
                    self.callback('error', token, message)
        self._disconnect()
