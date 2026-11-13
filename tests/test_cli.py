import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

from dx_voice import app, cli


class SetupTests(unittest.TestCase):
    def test_legacy_running_is_not_stopped_without_explicit_migration(self):
        with patch.object(cli, 'active', return_value=True), patch.object(cli, 'systemctl') as control:
            with self.assertRaisesRegex(RuntimeError, '--migrate'):
                cli.setup()
            control.assert_not_called()

    def test_explicit_migration_preserves_private_key_without_autostart(self):
        with tempfile.TemporaryDirectory(prefix='voice setup ') as tmp:
            home = Path(tmp)
            old = home / '.config/openai-voice-input/语音输入法设置.txt'
            old.parent.mkdir(parents=True)
            old.write_text('api_key=test-only-secret\nrealtime_model=gpt-live-transcribe\n')
            new = home / '.config/dx-voice/settings.txt'
            with patch.object(Path, 'home', return_value=home), patch.object(app, 'CONFIG', new), \
                 patch.object(cli, 'active', return_value=True), \
                 patch.object(cli, 'systemctl', return_value=Mock(returncode=0)) as control:
                report = cli.setup(migrate=True)
            self.assertEqual(new.read_bytes(), old.read_bytes())
            self.assertEqual(new.stat().st_mode & 0o777, 0o600)
            self.assertNotIn('test-only-secret', json.dumps(report))
            self.assertFalse(report['started'])
            calls = [call.args for call in control.call_args_list]
            self.assertIn(('disable', '--now', cli.LEGACY), calls)
            self.assertFalse(any('enable' in call for call in calls))
            service = (home / '.config/systemd/user/dx-voice.service').read_text()
            self.assertIn('-m dx_voice.cli run', service)
            self.assertIn('UMask=0077', service)


class AdapterTests(unittest.TestCase):
    def test_adapter_forwards_to_same_standalone_cli(self):
        path = Path(__file__).resolve().parents[1] / 'dex_plugin.py'
        spec = importlib.util.spec_from_file_location('voice_adapter_test', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        parser = argparse.ArgumentParser()
        module.register_cli(parser.add_subparsers())
        args = parser.parse_args(['voice', 'doctor'])
        with patch.object(module.subprocess, 'run', return_value=Mock(returncode=0)) as run:
            self.assertEqual(args.extension_handler(args), 0)
        command = run.call_args.args[0]
        self.assertEqual(command[-3:], ['-m', 'dx_voice.cli', 'doctor'])

    def test_dx_v_defaults_to_terminal_workspace(self):
        path = Path(__file__).resolve().parents[1] / 'dex_plugin.py'
        spec = importlib.util.spec_from_file_location('voice_adapter_tui_test', path)
        module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        parser = argparse.ArgumentParser();module.register_cli(parser.add_subparsers())
        args = parser.parse_args(['v'])
        with patch.object(module.subprocess, 'run', return_value=Mock(returncode=0)) as run:
            args.extension_handler(args)
        self.assertEqual(run.call_args.args[0][-3:], ['-m', 'dx_voice.cli', 'tui'])


if __name__ == '__main__':
    unittest.main()
