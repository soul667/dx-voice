import json
import subprocess
import threading
import unittest
from types import SimpleNamespace
import urllib.error
import urllib.request

from dx_voice.modules import MODULES
from dx_voice.modules.lan_input import LanInputServer, XDeltaInjector, compute_delta


class LanInputTests(unittest.TestCase):
    def test_module_registered(self):
        self.assertIn('lan_input', MODULES)
        self.assertTrue(MODULES['lan_input']['delta_streaming'])

    def test_compute_delta_handles_append_backspace_and_unicode(self):
        self.assertEqual(compute_delta('', '你好'), (0, '你好'))
        self.assertEqual(compute_delta('你好', '你好世界'), (0, '世界'))
        self.assertEqual(compute_delta('你好世界', '你好'), (2, ''))
        self.assertEqual(compute_delta('hello wrld', 'hello world'), (3, 'orld'))
        self.assertEqual(compute_delta('abc', 'abc'), (0, ''))

    def test_injector_uses_clipboard_paste_for_terminal_and_backspaces(self):
        calls = []

        def fake_runner(cmd, **kwargs):
            calls.append((cmd, kwargs.get('input')))
            if cmd[:2] == ['xdotool', 'getactivewindow']:
                return SimpleNamespace(returncode=0, stdout='12345\n', stderr='')
            if cmd[:2] == ['xprop', '-id']:
                return SimpleNamespace(returncode=0, stdout='WM_CLASS(STRING) = "kitty", "kitty"\n', stderr='')
            if cmd[:3] == ['xclip', '-selection', 'clipboard'] and '-o' in cmd:
                return SimpleNamespace(returncode=0, stdout=b'old-clip', stderr=b'')
            return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')

        inj = XDeltaInjector(dry_run=False, runner=fake_runner)
        mode = inj.apply_delta(delete_count=2, text='新词', enter=True, restore_clipboard=False)
        self.assertEqual(mode, 'paste')
        cmds = [c[0] for c in calls]
        self.assertIn(['xdotool', 'key', '--clearmodifiers', '--delay', '0', 'BackSpace', 'BackSpace'], cmds)
        self.assertIn(['xdotool', 'key', '--clearmodifiers', '--delay', '0', 'ctrl+shift+v'], cmds)
        self.assertIn(['xdotool', 'key', '--clearmodifiers', '--delay', '0', 'Return'], cmds)
        clip_writes = [c[1] for c in calls if c[0] == ['xclip', '-selection', 'clipboard']]
        self.assertEqual(clip_writes, ['新词'.encode('utf-8')])

    def test_injector_refuses_when_locked_window_fails_to_focus(self):
        def fake_runner(cmd, **kwargs):
            if cmd[:2] == ['xdotool', 'getactivewindow']:
                return SimpleNamespace(returncode=0, stdout='999\n', stderr='')
            if cmd[:2] == ['wmctrl', '-i']:
                return SimpleNamespace(returncode=1, stdout='', stderr='BadWindow')
            return SimpleNamespace(returncode=0, stdout='', stderr='')

        inj = XDeltaInjector(dry_run=False, runner=fake_runner)
        with self.assertRaisesRegex(RuntimeError, '聚焦失败'):
            inj.apply_delta(text='abc', window_id='0x1234')

    def test_http_server_auth_delta_streaming_dedup_and_sse(self):
        received = []

        class RecordingInjector:
            dry_run = False

            def list_windows(self):
                return [{'id': '0x1', 'title': 'Terminal'}]

            def activate_window(self, win_id):
                return True, ''

            def apply_delta(self, delete_count=0, text='', enter=False, **kwargs):
                received.append((delete_count, text, enter))
                return 'paste'

        srv = LanInputServer(host='127.0.0.1', port=0, token='t12345', injector=RecordingInjector())
        port = srv.start(blocking=False)
        try:
            base = f'http://127.0.0.1:{port}'
            # Unauthenticated GET / shows gate; /api/status returns 403
            with urllib.request.urlopen(f'{base}/') as resp:
                self.assertIn('DX Voice', resp.read().decode('utf-8'))
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(f'{base}/api/status')
            self.assertEqual(ctx.exception.code, 403)

            # Fullwidth question mark normalization works
            with urllib.request.urlopen(f'{base}/%EF%BC%9Fk=t12345') as resp:
                self.assertIn('LAN Delta', resp.read().decode('utf-8'))

            # Stream incremental deltas + deduplicate replayed seq
            def post(path, payload):
                req = urllib.request.Request(
                    f'{base}{path}?k=t12345',
                    data=json.dumps(payload).encode('utf-8'),
                    headers={'Content-Type': 'application/json'},
                    method='POST',
                )
                with urllib.request.urlopen(req) as r:
                    return json.loads(r.read().decode('utf-8'))

            r1 = post('/api/delta', {'client_id': 'c1', 'seq': 1, 'delete_count': 0, 'text': '你好'})
            r2 = post('/api/delta', {'client_id': 'c1', 'seq': 1, 'delete_count': 0, 'text': '你好'})
            r3 = post('/api/delta', {'client_id': 'c1', 'seq': 2, 'delete_count': 1, 'text': '好世界', 'enter': True})
            self.assertEqual(r1['added_chars'], 2)
            self.assertTrue(r2['duplicate'])
            self.assertEqual(r3['delete_count'], 1)
            self.assertEqual(received, [(0, '你好', False), (1, '好世界', True)])

            # History reflects non-duplicate deltas
            with urllib.request.urlopen(f'{base}/api/history?k=t12345&limit=10') as resp:
                hist = json.loads(resp.read().decode('utf-8'))['history']
            self.assertEqual(len(hist), 2)

            # SSE stream receives broadcast events
            sse_lines = []
            ready = threading.Event()

            def read_sse():
                with urllib.request.urlopen(f'{base}/api/events?k=t12345', timeout=3) as resp:
                    for _ in range(8):
                        line = resp.readline().decode('utf-8')
                        if not line:
                            break
                        sse_lines.append(line.strip())
                        if 'ready' in line:
                            ready.set()
                        if '语音增量' in line:
                            break

            t = threading.Thread(target=read_sse, daemon=True)
            t.start()
            self.assertTrue(ready.wait(timeout=2))
            srv.broadcast_event('voice_partial', {'text': '语音增量'})
            t.join(timeout=2)
            self.assertTrue(any('语音增量' in ln for ln in sse_lines))
        finally:
            srv.stop()


if __name__ == '__main__':
    unittest.main()
