from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from PIL import Image

from dx_voice.modules import screen, tools, asr
from dx_voice import app as voice
from dx_voice.text_tools import TextTools, TextResult


class ModuleTests(unittest.TestCase):
    def test_asr_override_does_not_replace_text_credentials(self):
        cfg = {'api_key': 'text-key', 'base_url': 'https://text.invalid/v1',
               'asr_api_key': 'asr-key', 'asr_base_url': 'https://asr.invalid/v1'}
        result = asr.OpenAIBackend.settings(cfg)
        self.assertEqual(result['api_key'], 'asr-key')
        self.assertEqual(cfg['api_key'], 'text-key')
        with self.assertRaises(RuntimeError):
            asr.load_backend('not-installed')

    def test_screen_capture_requires_both_rewrite_and_context_opt_in(self):
        with patch.object(screen, 'current_monitor_image') as grab:
            self.assertIsNone(screen.capture_rewrite_context({'cleanup_mode': 'none', 'rewrite_use_screen': 'true'}))
            self.assertIsNone(screen.capture_rewrite_context({'cleanup_mode': 'light', 'rewrite_use_screen': 'false'}))
            grab.assert_not_called()
        with patch.object(screen, 'current_monitor_image', return_value=Image.new('RGB', (32, 32))):
            data = screen.capture_rewrite_context({'cleanup_mode': 'light', 'rewrite_use_screen': 'true'})
            self.assertTrue(data.startswith('data:image/jpeg;base64,'))

    def test_screen_selection_is_only_the_pointer_monitor(self):
        monitors = [{'left': 0, 'top': 0, 'width': 100, 'height': 100},
                    {'left': 100, 'top': 0, 'width': 100, 'height': 100}]
        self.assertIs(screen.monitor_for_pointer(monitors, 150, 30), monitors[1])

    def test_vision_request_keeps_text_and_image_separate_and_no_tools(self):
        adapter = TextTools();client = Mock();client.with_options.return_value = client
        client.responses.parse.return_value = SimpleNamespace(output_parsed=TextResult(text='改写'))
        adapter.client = Mock(return_value=client)
        adapter.request({}, 'fast-model', 'rewrite', '原文', 3, 'none', image='data:image/jpeg;base64,test')
        request = client.responses.parse.call_args.kwargs
        self.assertEqual([part['type'] for part in request['input'][0]['content']], ['input_text', 'input_image'])
        self.assertEqual(request['tools'], [])

    def test_tools_executes_registered_argv_without_model_shell(self):
        runner = Mock(return_value=subprocess.CompletedProcess([], 0, 'status ok', ''))
        with patch.object(tools.shutil, 'which', return_value='/usr/bin/dx'):
            result = tools.execute(tools.Plan(action='display.status', argument='; rm -rf anything'), '显示器状态', runner)
        self.assertEqual(runner.call_args.args[0], ['dx', 't', '--status'])
        self.assertFalse(runner.call_args.kwargs.get('shell', False))
        self.assertEqual(result.status, 'executed')

    def test_unsupported_action_and_invented_url_do_not_execute(self):
        runner = Mock()
        with self.assertRaises(RuntimeError):
            tools.execute(tools.Plan(action='none', argument=''), '删除全部文件', runner)
        with patch.object(tools.shutil, 'which', return_value='/usr/bin/dx'):
            with self.assertRaises(RuntimeError):
                tools.execute(tools.Plan(action='open.url', argument='https://invented.invalid'), '打开网页', runner)
        runner.assert_not_called()

    def test_open_document_reuses_dx_pickopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / 'example.txt';file.write_text('document')
            runner = Mock(return_value=subprocess.CompletedProcess([], 0, '', ''))
            with patch.object(tools.shutil, 'which', return_value='/usr/bin/dx'):
                result = tools.execute(tools.Plan(action='open.path', argument=str(file)), '打开 ' + str(file), runner)
            self.assertEqual(runner.call_args.args[0], ['dx', 'tools.pickopen', '-a', '__xdgopen__', str(file)])
            self.assertEqual(result.status, 'launched')

    def test_alt_win_has_a_separate_tools_mode(self):
        hold = voice.HoldGesture();hold.update(True, False, 0, tools=True)
        self.assertEqual(hold.update(True, False, .41, tools=True), 'start')
        self.assertEqual(hold.mode, 'tools')
