"""Dex CLI adapter. Imports no GUI, starts no microphone or network at load time."""
import argparse
import json
import os
from pathlib import Path
import subprocess


def register_cli(subparsers):
    parser = subparsers.add_parser('voice', help='DX Voice: streaming voice input',
                                  description='Hold Ctrl to dictate. Commands: doctor, status, setup, start, stop, settings, run, retry.')
    parser.add_argument('voice_args', nargs=argparse.REMAINDER)
    parser.set_defaults(extension_handler=execute)


def execute(args):
    source = Path(__file__).resolve().parent / 'src'
    python = os.environ.get('DX_VOICE_PYTHON')
    if not python:
        try:
            runtime = json.loads((Path.home() / '.config/dx-voice/runtime.json').read_text())
            candidate = runtime.get('python', '')
            if candidate and Path(candidate).is_file():
                python = candidate
        except (OSError, ValueError):
            pass
    python = python or '/usr/bin/python3'
    env = dict(os.environ)
    env['PYTHONPATH'] = str(source) + (os.pathsep + env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
    return subprocess.run([python, '-m', 'dx_voice.cli', *(args.voice_args or ['status'])], env=env).returncode
