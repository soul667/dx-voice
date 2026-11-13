"""Standalone commands shared by the Dex adapter and desktop launchers."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

SERVICE = 'dx-voice.service'
LEGACY = 'openai-voice-input.service'


def systemctl(*args):
    return subprocess.run(['systemctl', '--user', *args], capture_output=True, text=True, timeout=15)


def active(name):
    return systemctl('is-active', name).returncode == 0


def quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'


def status():
    from . import app
    from . import __version__
    cfg = app.config()
    return {'version': __version__, 'ui': 'figma-v1', 'service_active': active(SERVICE), 'socket_present': app.SOCKET.is_socket(),
            'key_configured': bool(cfg.get('api_key', '').strip()),
            'legacy_service_active': active(LEGACY), 'config_file': str(app.CONFIG)}


def doctor():
    result = status()
    result['python_supported'] = (3, 10) <= sys.version_info[:2] < (3, 13)
    result['session'] = os.environ.get('XDG_SESSION_TYPE', 'unknown')
    result['display_present'] = bool(os.environ.get('DISPLAY'))
    result['modules'] = {name: importlib.util.find_spec(name) is not None
                         for name in ('gi', 'cairo', 'requests', 'websockets', 'Xlib', 'PIL')}
    try:
        import gi
        gi.require_version('Rsvg', '2.0')
        result['modules']['Rsvg'] = True
    except (ImportError, ValueError):
        result['modules']['Rsvg'] = False
    result['tools'] = {name: bool(shutil.which(name))
                       for name in ('parec', 'xdotool', 'xclip', 'xprop', 'systemctl', 'xdg-open')}
    result['runtime_ready'] = (result['python_supported'] and result['display_present']
                               and result['session'] == 'x11' and all(result['modules'].values())
                               and all(result['tools'].values()))
    return result


def setup(migrate=False):
    from . import app
    if active(LEGACY) and not migrate:
        raise RuntimeError('The legacy voice service is running. Use setup --migrate to replace it explicitly.')
    legacy_config = Path.home() / '.config/openai-voice-input/语音输入法设置.txt'
    if not app.CONFIG.exists():
        if migrate and legacy_config.exists():
            app.private_dir(app.CONFIG.parent)
            app.CONFIG.write_bytes(legacy_config.read_bytes())
            app.CONFIG.chmod(0o600)
        else:
            app.save_config(app.DEFAULT)
    source = Path(__file__).resolve().parents[1]
    units = Path.home() / '.config/systemd/user'
    units.mkdir(parents=True, exist_ok=True)
    executable = f'{quote(sys.executable)} -m dx_voice.cli run'
    (units / SERVICE).write_text(f'''[Unit]
Description=DX Voice streaming dictation
PartOf=graphical-session.target
After=graphical-session.target

[Service]
Type=simple
Environment={quote('PYTHONPATH=' + str(source))}
ExecStart={executable}
Restart=on-failure
RestartSec=3
UMask=0077

[Install]
WantedBy=graphical-session.target
''')
    app.private_dir(app.CONFIG.parent)
    runtime = app.CONFIG.parent / 'runtime.json'
    runtime.write_text(json.dumps({'python': sys.executable}))
    runtime.chmod(0o600)
    applications = Path.home() / '.local/share/applications'
    applications.mkdir(parents=True, exist_ok=True)
    for suffix, name, action in [('input', 'DX Voice', 'toggle'), ('settings', 'DX Voice Settings', 'settings')]:
        (applications / f'dx-voice-{suffix}.desktop').write_text(f'''[Desktop Entry]
Type=Application
Name={name}
Comment=Hold Ctrl to speak, release to insert
Exec=/usr/bin/env {quote('PYTHONPATH=' + str(source))} {quote(sys.executable)} -m dx_voice.cli {action}
Icon=audio-input-microphone
Terminal=false
Categories=Utility;Accessibility;
''')
    names = [k for k in ('DISPLAY', 'XAUTHORITY', 'DBUS_SESSION_BUS_ADDRESS', 'XDG_SESSION_TYPE') if os.environ.get(k)]
    if names:
        imported = systemctl('import-environment', *names)
        if imported.returncode:
            raise RuntimeError('Cannot import the graphical session environment.')
    if migrate and active(LEGACY):
        stopped = systemctl('disable', '--now', LEGACY)
        if stopped.returncode:
            raise RuntimeError('Cannot stop the legacy service; DX Voice was not started.')
    loaded = systemctl('daemon-reload')
    if loaded.returncode:
        raise RuntimeError('Cannot reload user service definitions.')
    return {'configured': True, 'started': False, 'config_file': str(app.CONFIG),
            'next': 'dx voice start', 'migrated': migrate and legacy_config.exists()}


def main(argv=None):
    parser = argparse.ArgumentParser(prog='dx-voice', description='Streaming voice input for Linux and Dex')
    sub = parser.add_subparsers(dest='action', required=True)
    for action in ('status', 'doctor', 'start', 'stop', 'run', 'toggle', 'cancel', 'retry', 'preview'):
        sub.add_parser(action)
    settings = sub.add_parser('settings')
    settings.add_argument('--gui', action='store_true')
    installer = sub.add_parser('setup')
    installer.add_argument('--migrate', action='store_true', help='Migrate and stop the legacy prototype service')
    args = parser.parse_args(argv)
    try:
        if args.action in ('doctor', 'status'):
            report = doctor() if args.action == 'doctor' else status()
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if args.action == 'status' or report['runtime_ready'] else 1
        if args.action == 'setup':
            print(json.dumps(setup(args.migrate), ensure_ascii=False, indent=2))
            return 0
        if args.action in ('start', 'stop'):
            if args.action == 'start' and active(LEGACY):
                raise RuntimeError('Legacy dictation is active. Run setup --migrate before starting DX Voice.')
            operation = ('enable', '--now') if args.action == 'start' else ('disable', '--now')
            result = systemctl(*operation, SERVICE)
            print(json.dumps({'ok': result.returncode == 0, 'action': args.action}))
            return result.returncode
        from . import app
        if args.action == 'run':
            instance = app.App()
            import signal
            signal.signal(signal.SIGTERM, lambda *_: instance.Gtk.main_quit())
            instance.run()
            return 0
        if args.action == 'settings' and not args.gui:
            if not app.CONFIG.exists():
                app.save_config(app.DEFAULT)
            subprocess.Popen(['xdg-open', str(app.CONFIG)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return 0
        import socket
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.sendto(('gui-settings' if args.action == 'settings' else args.action).encode(), str(app.SOCKET))
        return 0
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
