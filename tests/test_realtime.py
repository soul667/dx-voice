import json
import queue
import threading
import time
import unittest

from websockets.sync.server import serve
from dx_voice.realtime import Realtime


class RealtimeTests(unittest.TestCase):
    def setUp(self):
        self.connections = 0
        self.events = queue.Queue()
        self.commands = []
        def handler(ws):
            self.connections += 1
            item, sent = None, False
            try:
                ws.send(json.dumps({'type': 'session.created'}))
                for message in ws:
                    event = json.loads(message)
                    kind = event['type']
                    self.commands.append(kind)
                    if kind == 'session.update':
                        self.assertEqual(event['session']['audio']['input']['format']['rate'], 24000)
                        ws.send(json.dumps({'type': 'session.updated'}))
                    elif kind == 'input_audio_buffer.clear':
                        item, sent = str(time.monotonic_ns()), False
                    elif kind == 'input_audio_buffer.append' and not sent:
                        sent = True
                        ws.send(json.dumps({'type': 'conversation.item.input_audio_transcription.delta', 'item_id': item, 'delta': '实时文字'}))
                    elif kind == 'input_audio_buffer.commit':
                        ws.send(json.dumps({'type': 'input_audio_buffer.committed', 'item_id': item}))
                        ws.send(json.dumps({'type': 'conversation.item.input_audio_transcription.completed', 'item_id': item, 'transcript': '实时文字。'}))
            except Exception:
                pass
        self.server = serve(handler, '127.0.0.1', 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = Realtime(lambda *args: self.events.put(args))
        self.cfg = dict(base_url=f'http://127.0.0.1:{self.server.socket.getsockname()[1]}/v1',
                        api_key='test-only', proxy_url=None, realtime_model='gpt-live-transcribe', prompt='')

    def tearDown(self):
        self.client.close()
        self.client.thread.join(timeout=2)
        self.server.shutdown()
        self.thread.join(timeout=2)

    def event(self, expected, token):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            kind, actual, data = self.events.get(timeout=3)
            if kind == 'error':
                self.fail(data)
            if kind == expected:
                self.assertEqual(actual, token)
                return data
        self.fail('Missing ' + expected)

    def test_audio_produces_partial_before_release_then_final(self):
        self.client.prepare(self.cfg)
        self.client.begin('one', self.cfg)
        self.client.append('one', b'\0' * 4800)
        self.assertEqual(self.event('partial', 'one'), '实时文字')
        self.assertNotIn('input_audio_buffer.commit', self.commands)
        self.client.commit('one')
        self.assertEqual(self.event('final', 'one')[0], '实时文字。')

    def test_two_turns_reuse_connection_without_mixing_text(self):
        for token in ('one', 'two'):
            self.client.begin(token, self.cfg)
            self.client.append(token, b'\0' * 4800)
            self.assertEqual(self.event('partial', token), '实时文字')
            self.client.commit(token)
            self.assertEqual(self.event('final', token)[0], '实时文字。')
        self.assertEqual(self.connections, 1)

    def test_cancel_discards_late_audio_and_next_turn_is_clean(self):
        self.client.begin('cancelled', self.cfg)
        self.event('connected', 'cancelled')
        self.client.cancel('cancelled')
        self.client.append('cancelled', b'\0' * 4800)
        self.client.begin('new', self.cfg)
        self.client.append('new', b'\0' * 4800)
        self.assertEqual(self.event('partial', 'new'), '实时文字')
        self.client.commit('new')
        self.assertEqual(self.event('final', 'new')[0], '实时文字。')


if __name__ == '__main__':
    unittest.main()
