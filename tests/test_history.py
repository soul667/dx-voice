from pathlib import Path
import tempfile
import unittest
from dx_voice.history import History


class HistoryTests(unittest.TestCase):
    def test_single_private_file_keeps_original_and_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'private'
            history = History(folder / 'history.db')
            history.begin('one', 'dictation')
            history.update('one', raw='呃，准备一下。', result='准备一下。', status='inserted', processing='light')
            history.begin('two', 'command')
            history.update('two', raw='查看当前目录', result='pwd', status='copied')
            rows = history.recent()
            self.assertEqual(rows[0]['result'], 'pwd')
            self.assertEqual(rows[1]['raw'], '呃，准备一下。')
            self.assertEqual(rows[1]['result'], '准备一下。')
            self.assertEqual(history.path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(folder.stat().st_mode & 0o777, 0o700)
            self.assertEqual([f.name for f in folder.iterdir()], ['history.db'])

    def test_cancelled_turn_does_not_keep_partial_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            history = History(Path(tmp) / 'history.db')
            history.begin('one', 'dictation', '/private/speech.wav')
            history.update('one', status='cancelled', raw='', result='', audio_file='')
            row = history.recent()[0]
            self.assertEqual(row['status'], 'cancelled')
            self.assertEqual(row['raw'], '')
            self.assertIsNone(history.for_audio('/private/speech.wav'))

    def test_updates_reject_unknown_column_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            history = History(Path(tmp) / 'history.db')
            history.begin('one', 'command')
            with self.assertRaises(ValueError):
                history.update('one', **{'result=1;DROP TABLE entries': 'bad'})
            self.assertEqual(len(history.recent()), 1)
