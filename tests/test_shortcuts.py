from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from dx_voice.shortcuts import SuperBinding


class SuperBindingTests(unittest.TestCase):
    def test_super_overview_is_restored_after_stop_or_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = {'value': "'Super_L'"}
            def call(argv, **_):
                if argv[1] == 'get':
                    return subprocess.CompletedProcess(argv, 0, state['value'] + '\n', '')
                state['value'] = argv[-1]
                return subprocess.CompletedProcess(argv, 0, '', '')
            with patch('dx_voice.shortcuts.subprocess.run', side_effect=call):
                binding = SuperBinding(Path(tmp))
                binding.acquire()
                self.assertEqual(state['value'], "''")
                restarted = SuperBinding(Path(tmp))
                restarted.acquire()
                restarted.release()
                self.assertEqual(state['value'], "'Super_L'")
                self.assertFalse(binding.path.exists())

    def test_stop_preserves_a_user_change_made_while_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = {'value': "'Super_L'"}
            def call(argv, **_):
                if argv[1] == 'get':
                    return subprocess.CompletedProcess(argv, 0, state['value'], '')
                state['value'] = argv[-1]
                return subprocess.CompletedProcess(argv, 0, '', '')
            with patch('dx_voice.shortcuts.subprocess.run', side_effect=call):
                binding = SuperBinding(Path(tmp));binding.acquire()
                state['value'] = "'Super_R'"
                binding.release()
                self.assertEqual(state['value'], "'Super_R'")
