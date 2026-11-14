from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from textual.widgets import Input, Select, TabbedContent, TextArea, Button, DataTable
from dx_voice import app as voice
from dx_voice.history import History
from dx_voice.tui import VoiceTUI, SPEECH, COMMAND, CONNECTION, REWRITE, TOOLS, LAN_INPUT


class TUITests(unittest.IsolatedAsyncioTestCase):
    async def test_all_settings_edit_in_one_tui_and_key_is_masked(self):
        self.assertEqual({k for k, _ in SPEECH + COMMAND + CONNECTION + REWRITE + TOOLS + LAN_INPUT}, set(voice.DEFAULT))
        with tempfile.TemporaryDirectory() as tmp:
            saved = []
            app = VoiceTUI(settings=dict(voice.DEFAULT, api_key='test-only-secret'), save=saved.append,
                           history_path=Path(tmp) / 'history.db', palette={})
            async with app.run_test(size=(120, 38)) as pilot:
                app.query_one('#hotkey_hold_ms', Input).value = '600'
                app.query_one('#cleanup_mode', Select).value = 'light'
                app.query_one('#theme', Select).value = 'classic-light'
                app.query_one('#command_model', Input).value = 'gpt-6.1-terra'
                self.assertTrue(app.query_one('#api_key', Input).password)
                await pilot.press('ctrl+s')
                await pilot.pause()
                self.assertEqual(saved[0]['hotkey_hold_ms'], '600')
                self.assertEqual(saved[0]['cleanup_mode'], 'light')
                self.assertEqual(saved[0]['theme'], 'classic-light')
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

    async def test_history_search_filters_rows_without_deleting_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / 'history.db'
            history = History(history_path)
            history.begin('t1', 'dictation')
            history.update('t1', raw='语音输入测试', result='语音输入测试', status='inserted')
            history.begin('t2', 'command')
            history.update('t2', raw='查看容器', result='docker ps', status='copied')

            app = VoiceTUI(settings={}, history_path=history_path, palette={})
            async with app.run_test(size=(120, 40)) as pilot:
                table = app.query_one('#history-table', DataTable)
                self.assertEqual(table.row_count, 2)
                search = app.query_one('#history-search', Input)
                search.value = 'docker'
                await pilot.pause()
                self.assertEqual(table.row_count, 1)
                search.value = ''
                await pilot.pause()
                self.assertEqual(table.row_count, 2)
                self.assertEqual(len(history.recent(10)), 2)

    async def test_dashboard_sections_and_preview_hud_button(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = VoiceTUI(settings={}, history_path=Path(tmp) / 'history.db', palette={})
            async with app.run_test(size=(120, 40)) as pilot:
                preview_btn = app.query_one('#preview-hud', Button)
                self.assertIsNotNone(preview_btn)
                count_badge = app.query_one('#history-count')
                self.assertIsNotNone(count_badge)
                with patch('dx_voice.tui.socket.socket') as mock_sock:
                    await pilot.click('#preview-hud')
                    await pilot.pause()
                    mock_sock.return_value.__enter__.return_value.sendto.assert_called()
