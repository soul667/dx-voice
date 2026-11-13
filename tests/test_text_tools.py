from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from dx_voice.text_tools import TextTools, TextResult


class TextToolTests(unittest.TestCase):
    def test_raw_mode_makes_no_extra_model_call(self):
        tools = TextTools()
        tools.request = Mock()
        result = tools.process('dictation', '请帮我看看这个问题。', {'cleanup_mode': 'none'})
        self.assertEqual(result.text, '请帮我看看这个问题。')
        tools.request.assert_not_called()

    def test_cleanup_failure_preserves_raw_text(self):
        tools = TextTools()
        tools.request = Mock(side_effect=TimeoutError())
        result = tools.process('dictation', '呃，端口是 2222。', {'cleanup_mode': 'light'})
        self.assertEqual(result.text, '呃，端口是 2222。')
        self.assertEqual(result.processing, 'raw:cleanup-unavailable')

    def test_cleanup_preserves_paths_and_numbers(self):
        tools = TextTools()
        tools.request = Mock(return_value='请使用另一个端口。')
        raw = '呃，文件在 /tmp/example.txt，端口是 2222。'
        self.assertEqual(tools.process('dictation', raw, {'cleanup_mode': 'light'}).text, raw)

    def test_cleanup_preserves_negation_and_numbers_next_to_chinese(self):
        tools = TextTools()
        tools.request = Mock(return_value='执行操作，端口是22。')
        raw = '不要执行操作，端口2222。'
        self.assertEqual(tools.process('dictation', raw, {'cleanup_mode': 'light'}).text, raw)

    def test_command_syntax_check_does_not_execute_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / 'must-not-exist'
            tools = TextTools()
            command = 'touch ' + str(marker)
            tools.request = Mock(return_value=command)
            outcome = tools.process('command', '创建文件', {'command_shell': 'bash'})
            self.assertEqual(outcome.text, command)
            self.assertFalse(marker.exists())

    def test_bad_command_never_falls_back_to_spoken_prose(self):
        tools = TextTools()
        tools.request = Mock(return_value='```bash\npwd\n```')
        with self.assertRaises(RuntimeError):
            tools.process('command', '当前路径是什么', {'command_shell': 'bash'})
        tools.request = Mock(side_effect=TimeoutError())
        with self.assertRaises(RuntimeError):
            tools.process('command', '当前路径是什么', {'command_shell': 'bash'})

    def test_sdk_request_has_no_tools_and_uses_requested_model(self):
        tools = TextTools()
        client = Mock()
        client.with_options.return_value = client
        client.responses.parse.return_value = SimpleNamespace(output_parsed=TextResult(text='pwd'))
        tools.client = Mock(return_value=client)
        self.assertEqual(tools.request({}, 'gpt-6.1-terra', 'commands', '路径', 5, 'low'), 'pwd')
        options = client.responses.parse.call_args.kwargs
        self.assertEqual(options['model'], 'gpt-6.1-terra')
        self.assertEqual(options['tools'], [])
        self.assertFalse(options['store'])
