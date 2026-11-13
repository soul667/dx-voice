from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from textual.widgets import Input, Select, TabbedContent, TextArea, Button
from dx_voice import app as voice
from dx_voice.tui import VoiceTUI, SPEECH, COMMAND, CONNECTION, REWRITE, TOOLS


class TUITests(unittest.IsolatedAsyncioTestCase):
    async def test_all_settings_edit_in_one_tui_and_key_is_masked(self):
        self.assertEqual({k for k, _ in SPEECH + COMMAND + CONNECTION + REWRITE + TOOLS}, set(voice.DEFAULT))
        with tempfile.TemporaryDirectory() as tmp:
            saved = []
            app = VoiceTUI(settings=dict(voice.DEFAULT, api_key='test-only-secret'), save=saved.append,
                           history_path=Path(tmp) / 'history.db', palette={})
            async with app.run_test(size=(120, 38)) as pilot:
                app.query_one('#hotkey_hold_ms', Input).value = '600'
                app.query_one('#cleanup_mode', Select).value = 'light'
                app.query_one('#command_model', Input).value = 'gpt-6.1-terra'
                self.assertTrue(app.query_one('#api_key', Input).password)
                await pilot.press('ctrl+s')
                await pilot.pause()
                self.assertEqual(saved[0]['hotkey_hold_ms'], '600')
                self.assertEqual(saved[0]['cleanup_mode'], 'light')
                self.assertEqual(saved[0]['api_key'], 'test-only-secret')

    async def test_invalid_numeric_setting_does_not_overwrite_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            save = Mock()
            app = VoiceTUI(settings={}, save=save, history_path=Path(tmp) / 'history.db', palette={})
            async with app.run_test(size=(120, 38)) as pilot:
                app.query_one('#hotkey_hold_ms', Input).value = '0'
                await pilot.press('ctrl+s')
                save.assert_not_called()

    async def test_command_trial_uses_worker_and_shows_only_command(self):
        from dx_voice.text_tools import Outcome
        with tempfile.TemporaryDirectory() as tmp:
            app = VoiceTUI(settings={}, history_path=Path(tmp) / 'history.db', palette={})
            with patch('dx_voice.text_tools.TextTools') as factory:
                factory.return_value.process.return_value = Outcome('pwd', 'command:gpt-6.1-terra')
                async with app.run_test(size=(120, 42)) as pilot:
                    app.query_one(TabbedContent).active = 'command'
                    app.query_one('#command-request', Input).value = '查看当前目录'
                    app.query_one('#generate', Button).scroll_visible(animate=False)
                    await pilot.pause()
                    await pilot.click('#generate')
                    await app.workers.wait_for_complete()
                    await pilot.pause()
                    self.assertEqual(app.query_one('#command-result', TextArea).text, 'pwd')
                    self.assertFalse(app.query_one('#copy-command', Button).disabled)
                    self.assertEqual(app.history.recent()[0]['result'], 'pwd')
