"""Restoreable GNOME Super-key ownership; other Super shortcuts remain untouched."""
import json
from pathlib import Path
import subprocess


class SuperBinding:
    def __init__(self, state):
        self.path = Path(state) / 'super-key-binding.json'
        self.owned = False

    @staticmethod
    def get():
        result = subprocess.run(['gsettings', 'get', 'org.gnome.mutter', 'overlay-key'],
                                text=True, capture_output=True, timeout=3)
        if result.returncode:
            return None
        return result.stdout.strip()

    def acquire(self):
        value = self.get()
        if value is None:
            return
        if not self.path.exists() and value not in ("''", '""'):
            self.path.write_text(json.dumps({'original': value}))
            self.path.chmod(0o600)
        if self.path.exists():
            result = subprocess.run(['gsettings', 'set', 'org.gnome.mutter', 'overlay-key', "''"],
                                    capture_output=True, timeout=3)
            self.owned = result.returncode == 0

    def release(self):
        if not self.owned or not self.path.exists():
            return
        saved = json.loads(self.path.read_text())
        if self.get() in ("''", '""'):
            restored = subprocess.run(['gsettings', 'set', 'org.gnome.mutter', 'overlay-key', saved['original']],
                                      capture_output=True, timeout=3)
            if restored.returncode:
                return
        self.path.unlink(missing_ok=True)
