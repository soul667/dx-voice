from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from dx_voice import app as voice
from dx_voice.history import History


class DeliveryTests(unittest.TestCase):
    def test_command_default_copies_only_and_logs_raw_and_final(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            instance = voice.App.__new__(voice.App)
            instance.token = 'test-command'
            instance.mode = 'command'
            instance.turn_cfg = {'command_output': 'clipboard'}
            instance.target = 'original-window'
            instance.history = History(root / 'history.db')
            instance.history_on = True
            instance.history_error = False
            instance.overlay = Mock()
            instance.path = root / 'speech.wav'
            instance.path.write_bytes(b'test')
            instance.record_begin()
            instance.record(raw='查看当前路径')
            with patch.object(voice, 'STATE', root), patch.object(voice, 'paste', return_value=False) as paste, patch.object(voice, 'notify'):
                instance.complete('pwd', '', 'command:gpt-6.1-terra')
            paste.assert_called_once_with('pwd', '')
            row = instance.history.recent()[0]
            self.assertEqual((row['raw'], row['result'], row['status']), ('查看当前路径', 'pwd', 'copied'))
            self.assertFalse(instance.path.exists())
