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
    return {'version': __version__, 'ui': 'figma-v1', 'hotkeys': {'dictation': 'Ctrl', 'command': 'Ctrl+Win', 'tools': 'Alt+Win'},
            'history_file': str(app.STATE / 'history.db'),
            'service_active': active(SERVICE), 'socket_present': app.SOCKET.is_socket(),
            'key_configured': bool((cfg.get('asr_api_key') or cfg.get('api_key', '')).strip()),
            'legacy_service_active': active(LEGACY), 'config_file': str(app.CONFIG)}


def doctor():
    result = status()
    result['python_supported'] = (3, 10) <= sys.version_info[:2] < (3, 13)
    result['session'] = os.environ.get('XDG_SESSION_TYPE', 'unknown')
    result['display_present'] = bool(os.environ.get('DISPLAY'))
    result['modules'] = {name: importlib.util.find_spec(name) is not None
                         for name in ('gi', 'cairo', 'requests', 'websockets', 'Xlib', 'PIL', 'textual', 'openai', 'mss')}
    try:
        import gi
        gi.require_version('Rsvg', '2.0')
        result['modules']['Rsvg'] = True
    except (ImportError, ValueError):
        result['modules']['Rsvg'] = False
    try:
        import gi
        gi.require_foreign('cairo')
        result['modules']['gi-cairo'] = True
    except (ImportError, ValueError):
        result['modules']['gi-cairo'] = False
    result['tools'] = {name: bool(shutil.which(name))
                       for name in ('parec', 'arecord', 'xdotool', 'xclip', 'xprop', 'systemctl', 'xdg-open')}
    result['audio_capture'] = result['tools']['parec'] or result['tools']['arecord']
    result['runtime_ready'] = (result['python_supported'] and result['display_present']
                               and result['session'] == 'x11' and all(result['modules'].values())
                               and result['audio_capture']
                               and all(result['tools'][k] for k in ('xdotool', 'xclip', 'xprop', 'systemctl', 'xdg-open')))
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
Comment=Hold Ctrl to dictate; Ctrl+Win to generate a command
Exec=/usr/bin/env {quote('PYTHONPATH=' + str(source))} {quote(sys.executable)} -m dx_voice.cli {action}
Icon=audio-input-microphone
Terminal=false
Categories=Utility;Accessibility;
''')
    names = [k for k in ('DISPLAY', 'XAUTHORITY', 'DBUS_SESSION_BUS_ADDRESS', 'XDG_SESSION_TYPE', 'XDG_CURRENT_DESKTOP') if os.environ.get(k)]
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
    settings.add_argument('--file', action='store_true', help='Open the underlying private TXT settings')
    terminal = sub.add_parser('tui')
    terminal.add_argument('--tab', default='overview', choices=['overview', 'speech', 'rewrite', 'command', 'tools', 'lan', 'history', 'connection'])
    sub.add_parser('modules')
    lan = sub.add_parser('lan', help='LAN streaming delta input box')
    lan_ops = lan.add_subparsers(dest='lan_operation')
    lan_serve = lan_ops.add_parser('serve', help='Run LAN delta input server in foreground')
    lan_serve.add_argument('--host', default='0.0.0.0')
    lan_serve.add_argument('--port', type=int, default=0)
    lan_serve.add_argument('--token', default='')
    lan_serve.add_argument('--dry-run', action='store_true')
    lan_ops.add_parser('status', help='Check LAN delta input status')
    lan_ops.add_parser('url', help='Print LAN delta input URLs')
    asr = sub.add_parser('asr')
    asr.add_argument('operation', choices=['providers'], default='providers', nargs='?')
    tools = sub.add_parser('tools')
    tool_ops = tools.add_subparsers(dest='tool_operation')
    tool_ops.add_parser('list')
    run_tool = tool_ops.add_parser('run')
    run_tool.add_argument('request', nargs='+')
    history = sub.add_parser('history')
    history.add_argument('--limit', type=int, default=10)
    history.add_argument('--path', action='store_true')
    command = sub.add_parser('command')
    command.add_argument('request', nargs='+')
    context_cmd = sub.add_parser('context')
    context_cmd.add_argument('--refresh', action='store_true', help='Re-scan active window and local workspace roots')
    context_cmd.add_argument('--query', default='', help='Search indexed workspaces with a sample utterance')
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
            if args.action == 'stop' and result.returncode == 0 and not active(SERVICE):
                from . import app
                from .shortcuts import SuperBinding
                binding = SuperBinding(app.STATE)
                binding.owned = binding.path.exists()
                binding.release()
            print(json.dumps({'ok': result.returncode == 0, 'action': args.action}))
            return result.returncode
        from . import app
        if args.action in ('modules', 'asr'):
            from .modules import MODULES
            from .modules.asr import providers
            print(json.dumps({'modules': MODULES, 'asr_providers': providers()} if args.action == 'modules'
                             else {'installed': providers(), 'qwen': 'adapter interface available; not installed'}, ensure_ascii=False, indent=2))
            return 0
        if args.action == 'lan':
            import secrets
            import socket
            from .modules.lan_input import DEFAULT_PORT, LanInputServer, lan_ips, render_qr_terminal
            cfg = app.config()
            try:
                cfg_port = int(float(cfg.get('lan_input_port', str(DEFAULT_PORT)) or DEFAULT_PORT))
            except (TypeError, ValueError):
                cfg_port = DEFAULT_PORT
            token = str(getattr(args, 'token', '') or cfg.get('lan_input_token') or '').strip()
            op = args.lan_operation or 'status'
            if op in ('status', 'url'):
                if not token:
                    token = secrets.token_hex(3)
                    cfg['lan_input_token'] = token
                    app.save_config(cfg)
                listening = False
                try:
                    with socket.create_connection(('127.0.0.1', cfg_port), timeout=0.6):
                        listening = True
                except OSError:
                    pass
                urls = [f'http://{ip}:{cfg_port}/?k={token}' for ip in lan_ips()]
                if op == 'url':
                    for u in urls:
                        print(u)
                    return 0
                print(json.dumps({
                    'listening': listening,
                    'enabled_in_daemon': str(cfg.get('lan_input_enabled', 'false')).lower() == 'true',
                    'port': cfg_port,
                    'token': token,
                    'urls': urls,
                }, ensure_ascii=False, indent=2))
                return 0
            port = args.port or cfg_port
            if not token:
                token = secrets.token_hex(3)
            srv = LanInputServer(host=args.host, port=port, token=token, dry_run=args.dry_run)
            actual_port = srv.start(blocking=False)
            urls = srv.urls()
            print(f'DX Voice 局域网 Delta 流式输入已启动 (port={actual_port}, dry_run={args.dry_run})', flush=True)
            for u in urls:
                print(f'  {u}', flush=True)
            qr = render_qr_terminal(urls[0]) if urls else ''
            if qr:
                print(qr, flush=True)
            print('按 Ctrl+C 停止。', flush=True)
            try:
                while True:
                    import time
                    time.sleep(1.0)
            except KeyboardInterrupt:
                pass
            finally:
                srv.stop()
            return 0
        if args.action == 'tools':
            from .modules.tools import CATALOG, run
            if args.tool_operation is None:
                from .tui import launch
                launch(initial_tab='tools')
                return 0
            if args.tool_operation == 'list':
                print(json.dumps({key: value[0] for key, value in CATALOG.items()}, ensure_ascii=False, indent=2))
                return 0
            from .text_tools import TextTools
            from .history import History
            import uuid
            cfg = app.config();request = ' '.join(args.request);token = uuid.uuid4().hex
            history = History(app.STATE / 'history.db')
            logging = str(cfg.get('history_enabled', 'true')).lower() == 'true'
            if logging:
                history.begin(token, 'tools');history.update(token, raw=request, status='processing')
            client = TextTools()
            try:
                outcome = run(client, request, cfg)
                if logging:
                    history.update(token, result=outcome.text, status=outcome.status, processing='tools:' + outcome.action)
                print(json.dumps({'action': outcome.action, 'status': outcome.status, 'result': outcome.text}, ensure_ascii=False, indent=2))
            except Exception:
                if logging:
                    history.update(token, status='failed', error='DX 动作失败')
                raise RuntimeError('DX 动作失败，原始需求可在历史中查看。') from None
            finally:
                client.close()
            return 0
        if args.action == 'history':
            from .history import History
            path = app.STATE / 'history.db'
            print(str(path) if args.path else json.dumps(History(path).recent(args.limit), ensure_ascii=False, indent=2))
            return 0
        if args.action == 'context':
            from dataclasses import asdict
            from .modules.context import ContextIndex, build_turn_context, enrich_asr_settings, inspect_active_window
            cfg = app.config()
            index = ContextIndex(app.STATE / 'context.db')
            snapshot = inspect_active_window()
            if args.refresh or not index.recent(1):
                index.refresh(cfg, snapshot, force_discovery=args.refresh)
            workspaces = index.search(args.query, limit=5) if args.query else index.recent(10)
            asr_preview = enrich_asr_settings({'prompt': cfg.get('prompt', ''), 'vocabulary': cfg.get('vocabulary', ''),
                                               'context_enabled': cfg.get('context_enabled', 'true')}, snapshot, index)
            payload = {
                'context_enabled': str(cfg.get('context_enabled', 'true')).lower() == 'true',
                'snapshot': asdict(snapshot),
                'workspaces': [
                    {k: ws[k] for k in ('name', 'root', 'stack', 'branch', 'summary')}
                    for ws in workspaces
                ],
                'asr_prompt_preview': asr_preview.get('prompt', ''),
                'asr_keywords_preview': [w for w in asr_preview.get('vocabulary', '').split(',') if w][:20],
                'turn_context_preview': build_turn_context(args.query, snapshot, index),
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        if args.action == 'command':
            import uuid
            from .history import History
            from .text_tools import TextTools
            history = History(app.STATE / 'history.db')
            cfg = app.config()
            logging = str(cfg.get('history_enabled', 'true')).lower() == 'true'
            token = uuid.uuid4().hex
            request = ' '.join(args.request)
            if logging:
                history.begin(token, 'command')
                history.update(token, raw=request, status='processing')
            tools = TextTools()
            try:
                result = tools.process('command', request, cfg)
                if logging:
                    history.update(token, result=result.text, status='generated', processing=result.processing)
                print(result.text)
            except Exception:
                if logging:
                    history.update(token, status='failed', error='命令生成失败')
                raise RuntimeError('命令生成失败，原始需求已保存在历史。') from None
            finally:
                tools.close()
            return 0
        if args.action == 'tui' or (args.action == 'settings' and not args.file):
            from .tui import launch
            launch(initial_tab=args.tab if args.action == 'tui' else 'connection')
            return 0
        if args.action == 'run':
            instance = app.App()
            import signal
            signal.signal(signal.SIGTERM, lambda *_: instance.Gtk.main_quit())
            instance.run()
            return 0
        if args.action == 'settings' and args.file:
            if not app.CONFIG.exists():
                app.save_config(app.DEFAULT)
            subprocess.Popen(['xdg-open', str(app.CONFIG)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return 0
        import socket
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.sendto(args.action.encode(), str(app.SOCKET))
        return 0
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
