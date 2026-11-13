"""A single private SQLite file for compact dictation/command history."""
from datetime import datetime
from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3


class History:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.parent.chmod(0o700)
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(fd)
        self.path.chmod(0o600)
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS entries (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, mode TEXT NOT NULL,
                raw TEXT NOT NULL DEFAULT '', result TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL, processing TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT '', audio_file TEXT NOT NULL DEFAULT '')''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=2)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def begin(self, token, mode, audio_file=''):
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO entries(id,created_at,mode,status,audio_file) VALUES(?,?,?,?,?)',
                       (token, datetime.now().astimezone().isoformat(timespec='seconds'), mode, 'recording', str(audio_file)))

    def update(self, token, **values):
        allowed = {'raw', 'result', 'status', 'processing', 'error', 'audio_file'}
        if not values or not set(values) <= allowed:
            raise ValueError('Invalid history fields')
        with self.connect() as db:
            db.execute('UPDATE entries SET ' + ','.join(k + '=?' for k in values) + ' WHERE id=?',
                       (*values.values(), token))

    def recent(self, limit=100):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM entries ORDER BY created_at DESC,rowid DESC LIMIT ?',
                                                   (max(1, min(int(limit), 1000)),))]

    def for_audio(self, path):
        with self.connect() as db:
            row = db.execute('SELECT * FROM entries WHERE audio_file=? ORDER BY rowid DESC LIMIT 1', (str(path),)).fetchone()
            return dict(row) if row else None
