"""Exercise config reload, API transport and safe text insertion without a paid API."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch, Mock
from dx_voice import app as voice


class Handler(BaseHTTPRequestHandler):
    code = 200
    payload = b'{"text":"hello OpenAI"}'
    received = None

    def do_POST(self):
        Handler.received = (self.path, self.headers, self.rfile.read(int(self.headers['Content-Length'])))
        self.send_response(Handler.code)
        self.end_headers()
        self.wfile.write(Handler.payload)

    def log_message(self, *_):
        pass


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.audio = Path(self.tmp.name) / 'speech.wav'
        self.audio.write_bytes(b'RIFF-audio-test')
        self.cfg = dict(voice.DEFAULT, api_key='test-only', base_url=f'http://127.0.0.1:{self.server.server_port}/v1')
        Handler.code, Handler.payload, Handler.received = 200, b'{"text":"hello OpenAI"}', None

    def test_multipart_endpoint_and_result(self):
        self.assertEqual(voice.transcription(self.audio, self.cfg), 'hello OpenAI')
        path, headers, body = Handler.received
        self.assertEqual(path, '/v1/audio/transcriptions')
        self.assertEqual(headers['Authorization'], 'Bearer test-only')
        self.assertIn(b'gpt-transcribe', body)
        self.assertIn(b'RIFF-audio-test', body)

    def test_http_failure_preserves_audio(self):
        for code in (401, 404, 429, 500, 307):
            Handler.code = code
            with self.assertRaisesRegex(RuntimeError, str(code)):
                voice.transcription(self.audio, self.cfg)
            self.assertTrue(self.audio.exists())

    def test_bad_json_and_empty_result(self):
        for payload in (b'not json', b'{}', b'{"text":""}', b'{"text":null}'):
            Handler.payload = payload
            with self.assertRaises(RuntimeError):
                voice.transcription(self.audio, self.cfg)

    def test_network_error_hides_credentials(self):
        with patch.object(voice.requests, 'post', side_effect=voice.requests.ConnectionError('SECRET')):
            with self.assertRaises(RuntimeError) as error:
                voice.transcription(self.audio, self.cfg)
            self.assertNotIn('SECRET', str(error.exception))

    def test_configured_proxy_used_by_background_process(self):
        with patch.object(voice.requests, 'post') as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = {'text': '代理测试'}
            cfg = dict(self.cfg, proxy_url='http://127.0.0.1:17890')
            self.assertEqual(voice.transcription(self.audio, cfg), '代理测试')
            self.assertEqual(post.call_args.kwargs['proxies'],
                             {'https': cfg['proxy_url'], 'http': cfg['proxy_url']})

    def test_no_key_or_insecure_remote_rejected(self):
        for changes in ({'api_key': ''}, {'base_url': 'http://example.com/v1'}, {'base_url': 'https://user:password@example.com/v1'}):
            with self.assertRaises(RuntimeError):
                voice.transcription(self.audio, dict(self.cfg, **changes))
        self.assertIsNone(Handler.received)

    def test_txt_roundtrip_reload_permissions(self):
        path = Path(self.tmp.name) / 'settings/config.txt'
        with patch.object(voice, 'CONFIG', path), patch.dict(voice.os.environ, {'OPENAI_API_KEY': '', 'OPENAI_BASE_URL': ''}):
            voice.save_config(self.cfg)
            self.assertEqual(voice.config()['api_key'], 'test-only')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            path.write_text(path.read_text().replace('api_key=test-only', 'api_key=changed'))
            self.assertEqual(voice.config()['api_key'], 'changed')

    def test_changed_focus_copies_without_paste(self):
        with patch.object(voice, 'active_window', return_value='other'), patch.object(voice.subprocess, 'run') as run:
            self.assertFalse(voice.paste('中文 mixed', 'original'))
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.kwargs['input'], '中文 mixed'.encode())

    def test_terminal_paste_does_not_press_enter(self):
        with patch.object(voice, 'active_window', return_value='test'), patch.object(voice.subprocess, 'check_output', return_value='Gnome-terminal'), patch.object(voice.subprocess, 'run') as run:
            self.assertTrue(voice.paste('中文', 'test'))
            keys = run.call_args.args[0]
            self.assertEqual(keys[-1], 'ctrl+shift+v')
            self.assertNotIn('Return', keys)

    def test_ctrl_hold_starts_once_and_release_finishes(self):
        hold = voice.CtrlHold()
        self.assertIsNone(hold.update(True, False, 0))
        self.assertIsNone(hold.update(True, False, .2))
        self.assertIsNone(hold.update(True, False, .41))
        self.assertIsNone(hold.update(True, False, 1.19))
        self.assertEqual(hold.update(True, False, 1.21), 'start')
        self.assertIsNone(hold.update(True, False, 1.5))
        self.assertEqual(hold.update(False, False, 2), 'finish')

    def test_ctrl_shortcut_and_quick_tap_do_not_record(self):
        hold = voice.CtrlHold()
        self.assertIsNone(hold.update(True, False, 0))
        self.assertIsNone(hold.update(False, False, .1))
        self.assertIsNone(hold.update(True, True, 1))
        self.assertIsNone(hold.update(True, False, 2))
        self.assertIsNone(hold.update(False, False, 3))

    def test_other_key_cancels_active_ctrl_recording(self):
        hold = voice.CtrlHold()
        hold.update(True, False, 0)
        self.assertEqual(hold.update(True, False, 1.3), 'start')
        self.assertEqual(hold.update(True, True, 1.4), 'cancel')
        self.assertIsNone(hold.update(False, False, 2))

    def test_ctrl_wheel_blocks_recording_until_ctrl_is_released(self):
        hold = voice.CtrlHold()
        hold.update(True, False, 0)
        self.assertIsNone(hold.update(True, True, .3))
        self.assertIsNone(hold.update(True, False, 3))
        self.assertIsNone(hold.update(False, False, 4))
        self.assertIsNone(hold.update(True, False, 5))
        self.assertEqual(hold.update(True, False, 6.3), 'start')

    def test_wheel_at_release_cancels_instead_of_committing(self):
        hold = voice.CtrlHold()
        hold.update(True, False, 0)
        hold.update(True, False, 1.3)
        self.assertEqual(hold.update(False, True, 1.4), 'cancel')
        self.assertIsNone(hold.update(False, False, 1.5))

    def test_transient_wheel_event_is_detected_without_a_held_button(self):
        watcher = voice.PointerWatch.__new__(voice.PointerWatch)
        watcher.raw_button_press = 15
        watcher.connection = Mock()
        watcher.connection.pending_events.side_effect = [1, 0]
        watcher.connection.next_event.return_value = SimpleNamespace(evtype=15)
        watcher.root = Mock()
        watcher.root.query_pointer.return_value = SimpleNamespace(mask=0)
        self.assertTrue(watcher.activity())

    def test_hold_duration_is_configurable_and_invalid_value_is_safe(self):
        self.assertEqual(voice.hold_threshold({'ctrl_hold_ms': '1800'}), 1.8)
        self.assertEqual(voice.hold_threshold({'ctrl_hold_ms': 'invalid'}), 1.2)


if __name__ == '__main__':
    unittest.main()
