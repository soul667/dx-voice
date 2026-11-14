"""Lightweight active window/workspace inspector and SQLite FTS5 context index."""
from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import threading
import time

PROJECT_MARKERS = ('.git', 'pyproject.toml', 'package.json', 'Cargo.toml', 'go.mod', 'CMakeLists.txt', '.project')
SKIP_DIRS = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', 'build', 'dist', 'target', '.mypy_cache', '.pytest_cache', '.tox', '.cache'}
SECRET_FILES = ('settings.txt', 'history.db', 'context.db')
GENERIC_STEMS = {'__init__', 'index', 'main', 'test', 'tests', 'utils', 'helpers', 'common', 'config', 'setup', 'readme'}
SHELL_PROCS = {'fish', 'zsh', 'bash', 'sh', 'nu', 'xonsh'}
TERM_CLASSES = {'gnome-terminal', 'kitty', 'alacritty', 'terminator', 'wezterm', 'konsole', 'ghostty', 'foot', 'tilix', 'xfce4-terminal', 'mate-terminal', 'warp', 'tabby'}

_SECRET_PATTERNS = (
    re.compile(r'sk-[A-Za-z0-9_-]{12,}'),
    re.compile(r'(?i)\bBearer\s+\S+'),
    re.compile(r'(?i)\b(?:api_?key|secret|token|password|passwd|auth)\s*[:=]\s*\S+'),
    re.compile(r'https?://[^/\s:@]+:[^/\s@]+@'),
)
_PATH_HINT_RE = re.compile(r'(?:~|/)[A-Za-z0-9._/+~-]+')
_TOKEN_RE = re.compile(r'[A-Za-z0-9_.-]{2,}|[\u4e00-\u9fff]{2,}')


@dataclass
class ActiveSnapshot:
    window_id: str = ''
    app_name: str = ''
    wm_class: str = ''
    window_title: str = ''
    pid: int = 0
    cwd: str = ''
    workspace_root: str = ''


def redact_secrets(text: str) -> str:
    """Mask likely API keys, tokens, credentials and control characters."""
    if not text:
        return ''
    cleaned = re.sub(r'[\x00-\x1f\x7f]+', ' ', str(text))
    for pattern in _SECRET_PATTERNS:
        if 'https?://' in pattern.pattern:
            cleaned = pattern.sub('https://***@', cleaned)
        else:
            cleaned = pattern.sub('[REDACTED]', cleaned)
    return re.sub(r'\s+', ' ', cleaned).strip()


def _is_sensitive_filename(name: str) -> bool:
    low = name.lower()
    if low in SECRET_FILES or low.startswith('.env') or low.startswith('id_rsa') or low.startswith('id_ed25519'):
        return True
    if any(word in low for word in ('secret', 'credential', 'token')):
        return True
    return low.endswith(('.pem', '.key', '.p12', '.pfx'))


def find_project_root(cwd: str | Path) -> str:
    """Walk parent directories from cwd up to (excluding) $HOME looking for project markers."""
    if not cwd:
        return ''
    try:
        current = Path(cwd).expanduser().resolve()
    except OSError:
        return ''
    if current.is_file():
        current = current.parent
    if not current.is_dir():
        return ''
    home = Path.home().resolve()
    if current == home or current == Path('/'):
        return ''
    while True:
        if current == home or current == Path('/'):
            return ''
        for marker in PROJECT_MARKERS:
            if (current / marker).exists():
                return str(current)
        parent = current.parent
        if parent == current:
            return ''
        current = parent


def _read_proc_cwd(pid: int) -> str:
    try:
        target = os.readlink(f'/proc/{pid}/cwd')
        return target if os.path.isdir(target) else ''
    except OSError:
        return ''


def _read_proc_comm(pid: int) -> str:
    try:
        return Path(f'/proc/{pid}/comm').read_text(encoding='utf-8', errors='replace').strip().lower()
    except OSError:
        return ''


def _resolve_cwd_from_pid(pid: int) -> str:
    """Inspect /proc/<pid> and bounded descendants to find the active shell or working directory."""
    if pid <= 0:
        return ''
    home = str(Path.home().resolve())
    root_cwd = _read_proc_cwd(pid)
    visited = {pid}
    queue: deque[tuple[int, int]] = deque([(pid, 0)])
    candidates: list[tuple[int, int, str]] = []
    while queue and len(visited) < 32:
        cur, depth = queue.popleft()
        if depth >= 4:
            continue
        children_pids: list[int] = []
        try:
            for child_file in Path(f'/proc/{cur}/task').glob('*/children'):
                for item in child_file.read_text(encoding='utf-8', errors='replace').split():
                    if item.isdigit():
                        cpid = int(item)
                        if cpid not in visited:
                            visited.add(cpid)
                            children_pids.append(cpid)
                            if len(visited) >= 32:
                                break
                if len(visited) >= 32:
                    break
        except OSError:
            continue
        for cpid in children_pids:
            queue.append((cpid, depth + 1))
            ccwd = _read_proc_cwd(cpid)
            if not ccwd or ccwd == '/':
                continue
            comm = _read_proc_comm(cpid)
            score = 0
            if ccwd != home:
                score += 10
            if comm in SHELL_PROCS:
                score += 5
            if find_project_root(ccwd):
                score += 8
            candidates.append((score, cpid, ccwd))
    if candidates:
        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        if candidates[0][0] > 0 or not root_cwd or root_cwd in (home, '/'):
            return candidates[0][2]
    return root_cwd


def _path_from_title(title: str) -> str:
    for match in _PATH_HINT_RE.findall(title or ''):
        candidate = match.rstrip('.,:;)]}\'"')
        try:
            path = Path(candidate).expanduser()
            if path.exists():
                return str((path.parent if path.is_file() else path).resolve())
        except OSError:
            continue
    return ''


def _decode_window_title(window, display_conn) -> str:
    from Xlib import X
    for atom_name in ('_NET_WM_NAME', 'WM_NAME'):
        try:
            atom = display_conn.intern_atom(atom_name)
            prop = window.get_full_property(atom, X.AnyPropertyType)
            if prop and prop.value:
                val = prop.value
                if isinstance(val, bytes):
                    return val.decode('utf-8', errors='replace')
                if isinstance(val, str):
                    return val
        except Exception:
            continue
    return ''


def inspect_active_window(xdisplay=None) -> ActiveSnapshot:
    """Capture active window class, title, pid, cwd and project root via X11 + /proc."""
    own_display = None
    conn = xdisplay
    snapshot = ActiveSnapshot()
    try:
        if conn is None:
            from Xlib import display
            own_display = display.Display()
            conn = own_display
        from Xlib import X
        root = conn.screen().root
        active_atom = conn.intern_atom('_NET_ACTIVE_WINDOW')
        prop = root.get_full_property(active_atom, X.AnyPropertyType)
        wid = int(prop.value[0]) if prop and prop.value else 0
        if not wid:
            return snapshot
        snapshot.window_id = str(wid)
        win = conn.create_resource_object('window', wid)
        wm_class = win.get_wm_class() or ()
        snapshot.wm_class = ' '.join(part for part in wm_class if part)
        snapshot.app_name = (wm_class[1] if len(wm_class) > 1 else wm_class[0]) if wm_class else ''
        snapshot.window_title = redact_secrets(_decode_window_title(win, conn))[:160]
        if snapshot.app_name == 'DX Voice' or snapshot.window_title == 'DX Voice':
            return ActiveSnapshot()
        pid_atom = conn.intern_atom('_NET_WM_PID')
        pid_prop = win.get_full_property(pid_atom, X.AnyPropertyType)
        snapshot.pid = int(pid_prop.value[0]) if pid_prop and pid_prop.value else 0
    except Exception:
        try:
            wid = subprocess.check_output(['xdotool', 'getactivewindow'], text=True, timeout=1).strip()
            snapshot.window_id = wid
        except (subprocess.SubprocessError, OSError):
            return snapshot
    finally:
        if own_display is not None:
            try:
                own_display.close()
            except Exception:
                pass

    home = str(Path.home().resolve())
    cwd = _resolve_cwd_from_pid(snapshot.pid) if snapshot.pid else ''
    title_path = _path_from_title(snapshot.window_title)
    if title_path and (not cwd or cwd in (home, '/') or not find_project_root(cwd)):
        if find_project_root(title_path) or not cwd or cwd in (home, '/'):
            cwd = title_path
    snapshot.cwd = cwd
    snapshot.workspace_root = find_project_root(cwd)
    return snapshot


def _read_git_branch(root: Path) -> str:
    head = root / '.git/HEAD'
    try:
        if head.is_dir():
            return ''
        if not head.exists():
            git_file = root / '.git'
            if git_file.is_file():
                line = git_file.read_text(encoding='utf-8', errors='replace').strip()
                if line.startswith('gitdir:'):
                    gitdir = (root / line.split(':', 1)[1].strip()).resolve()
                    head = gitdir / 'HEAD'
        if not head.is_file():
            return ''
        content = head.read_text(encoding='utf-8', errors='replace').strip()
        if content.startswith('ref:'):
            return content.split('/')[-1][:48]
        return content[:12]
    except OSError:
        return ''


def _head_signature(root: Path) -> str:
    parts = []
    for rel in ('.git/HEAD', '.git/index', 'pyproject.toml', 'package.json', 'Cargo.toml', 'go.mod', '.'):
        candidate = root / rel
        try:
            st = candidate.stat()
            parts.append(f'{rel}:{int(st.st_mtime_ns)}')
        except OSError:
            continue
    return '|'.join(parts)


def _list_workspace_files(root: Path, limit: int = 80) -> list[str]:
    rg = shutil.which('rg')
    if rg:
        try:
            res = subprocess.run([rg, '--files', '--max-depth', '3'], cwd=str(root),
                                 capture_output=True, text=True, timeout=0.5)
            if res.returncode in (0, 1):
                files = []
                for line in res.stdout.splitlines():
                    rel = line.strip()
                    if not rel:
                        continue
                    parts = Path(rel).parts
                    if any(p in SKIP_DIRS or (p.startswith('.') and p != '.github') for p in parts[:-1]):
                        continue
                    if _is_sensitive_filename(parts[-1]):
                        continue
                    files.append(rel)
                    if len(files) >= limit:
                        break
                return files
        except (OSError, subprocess.SubprocessError):
            pass

    files: list[str] = []
    scanned = 0
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root)
        if len(rel_dir.parts) >= 3:
            dirnames[:] = []
        else:
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith('.'))
        for fname in sorted(filenames):
            scanned += 1
            if scanned > 150 or len(files) >= limit:
                return files
            if fname.startswith('.') or _is_sensitive_filename(fname):
                continue
            rel = str(rel_dir / fname) if rel_dir != Path('.') else fname
            files.append(rel)
    return files


def scan_workspace(root: str | Path) -> dict:
    """Bounded <30ms metadata + file/term scan of a workspace directory (no secret contents)."""
    path = Path(root).expanduser().resolve()
    stack_parts = []
    if (path / 'pyproject.toml').exists() or (path / 'setup.py').exists() or (path / 'requirements.txt').exists():
        stack_parts.append('Python')
    if (path / 'package.json').exists() or (path / 'tsconfig.json').exists():
        stack_parts.append('TypeScript/Node')
    if (path / 'Cargo.toml').exists():
        stack_parts.append('Rust')
    if (path / 'go.mod').exists():
        stack_parts.append('Go')
    if (path / 'CMakeLists.txt').exists():
        stack_parts.append('C/C++')
    files = _list_workspace_files(path, limit=80)
    if not stack_parts:
        exts = {Path(f).suffix.lower() for f in files}
        if '.py' in exts:
            stack_parts.append('Python')
        if exts & {'.ts', '.tsx', '.js', '.jsx'}:
            stack_parts.append('JS/TS')
        if '.blend' in exts:
            stack_parts.append('Blender')
    stack = ', '.join(stack_parts) or 'Project'
    branch = _read_git_branch(path)
    terms: list[str] = [path.name]
    seen = {path.name.lower()}

    def add_term(term: str):
        clean = redact_secrets(term).strip(' .,:;()[]{}"\'`')
        if not clean or len(clean) < 2 or len(clean) > 48:
            return
        low = clean.lower()
        if low in seen or low in GENERIC_STEMS:
            return
        seen.add(low)
        terms.append(clean)

    pkg_json = path / 'package.json'
    if pkg_json.is_file():
        try:
            data = json.loads(pkg_json.read_text(encoding='utf-8', errors='replace')[:32768])
            if isinstance(data.get('name'), str):
                add_term(data['name'])
            for key in (data.get('scripts') or {}):
                add_term(str(key))
        except Exception:
            pass
    pyproject = path / 'pyproject.toml'
    if pyproject.is_file():
        try:
            raw = pyproject.read_text(encoding='utf-8', errors='replace')[:32768]
            for match in re.findall(r'^\s*name\s*=\s*["\']([^"\']+)["\']', raw, re.MULTILINE):
                add_term(match)
        except OSError:
            pass
    readme = path / 'README.md'
    if readme.is_file():
        try:
            snippet = readme.read_text(encoding='utf-8', errors='replace')[:4096]
            for line in snippet.splitlines():
                if line.lstrip().startswith('#'):
                    heading = redact_secrets(line.lstrip('#').strip())
                    for tok in _TOKEN_RE.findall(heading):
                        add_term(tok)
        except OSError:
            pass
    for rel in files:
        stem = Path(rel).stem
        add_term(stem)
        if len(terms) >= 40:
            break
    return {
        'root': str(path),
        'name': path.name,
        'stack': stack,
        'branch': branch,
        'files_text': '\n'.join(files[:80]),
        'terms': ', '.join(terms[:40]),
        'head_sig': _head_signature(path),
    }


def _discover_workspace_dirs(cfg: dict) -> list[Path]:
    roots: list[Path] = []
    raw_roots = str(cfg.get('context_roots', '') or '').replace('，', ',')
    for item in raw_roots.split(','):
        text = item.strip()
        if text:
            p = Path(text).expanduser()
            if p.is_dir():
                roots.append(p)
    if not roots:
        home = Path.home()
        for name in ('project', 'Projects', 'workspace', 'code'):
            candidate = home / name
            if candidate.is_dir():
                roots.append(candidate)
    discovered: list[tuple[float, Path]] = []
    for base in roots:
        try:
            if any((base / marker).exists() for marker in PROJECT_MARKERS):
                discovered.append((base.stat().st_mtime, base))
                continue
            for child in base.iterdir():
                if child.name.startswith('.') or not child.is_dir():
                    continue
                if any((child / marker).exists() for marker in PROJECT_MARKERS):
                    try:
                        discovered.append((child.stat().st_mtime, child))
                    except OSError:
                        continue
        except OSError:
            continue
    discovered.sort(key=lambda item: item[0], reverse=True)
    return [p.resolve() for _, p in discovered[:10]]


class ContextIndex:
    """Private SQLite FTS5 index of local workspace metadata and terms."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.parent.chmod(0o700)
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(fd)
        self.path.chmod(0o600)
        self._fts = True
        self._last_discovery = 0.0
        self._distill_lock = threading.Lock()
        self._inflight: set[tuple[str, str]] = set()
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS workspaces (
                root TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                stack TEXT NOT NULL DEFAULT '',
                branch TEXT NOT NULL DEFAULT '',
                files_text TEXT NOT NULL DEFAULT '',
                terms TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL DEFAULT '',
                head_sig TEXT NOT NULL DEFAULT '',
                last_seen REAL NOT NULL DEFAULT 0,
                indexed_at REAL NOT NULL DEFAULT 0
            )''')
            try:
                db.execute('''CREATE VIRTUAL TABLE IF NOT EXISTS workspaces_fts
                    USING fts5(root, name, stack, files_text, terms, summary)''')
            except sqlite3.OperationalError:
                self._fts = False

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=2)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, root: str) -> dict | None:
        if not root:
            return None
        with self.connect() as db:
            row = db.execute('SELECT * FROM workspaces WHERE root=?', (str(root),)).fetchone()
            return dict(row) if row else None

    def upsert_workspace(self, root: str | Path, touch_seen: bool = True) -> dict:
        info = scan_workspace(root)
        now = time.time()
        existing = self.get(info['root'])
        summary = existing['summary'] if existing and existing.get('head_sig') == info['head_sig'] else ''
        last_seen = now if touch_seen else (existing['last_seen'] if existing else now)
        with self.connect() as db:
            db.execute('''INSERT INTO workspaces(root, name, stack, branch, files_text, terms, summary, head_sig, last_seen, indexed_at)
                          VALUES(?,?,?,?,?,?,?,?,?,?)
                          ON CONFLICT(root) DO UPDATE SET
                            name=excluded.name, stack=excluded.stack, branch=excluded.branch,
                            files_text=excluded.files_text, terms=excluded.terms,
                            summary=excluded.summary, head_sig=excluded.head_sig,
                            last_seen=excluded.last_seen, indexed_at=excluded.indexed_at''',
                       (info['root'], info['name'], info['stack'], info['branch'], info['files_text'],
                        info['terms'], summary, info['head_sig'], last_seen, now))
            if self._fts:
                db.execute('DELETE FROM workspaces_fts WHERE root=?', (info['root'],))
                db.execute('INSERT INTO workspaces_fts(root, name, stack, files_text, terms, summary) VALUES(?,?,?,?,?,?)',
                           (info['root'], info['name'], info['stack'], info['files_text'], info['terms'], summary))
        return self.get(info['root']) or info

    def _touch_seen(self, root: str):
        with self.connect() as db:
            db.execute('UPDATE workspaces SET last_seen=? WHERE root=?', (time.time(), root))

    def set_summary(self, root: str, head_sig: str, summary: str):
        clean = redact_secrets(summary)[:120]
        if not clean:
            return
        with self.connect() as db:
            row = db.execute('SELECT * FROM workspaces WHERE root=?', (root,)).fetchone()
            if not row or row['head_sig'] != head_sig:
                return
            db.execute('UPDATE workspaces SET summary=? WHERE root=?', (clean, root))
            if self._fts:
                db.execute('DELETE FROM workspaces_fts WHERE root=?', (root,))
                db.execute('INSERT INTO workspaces_fts(root, name, stack, files_text, terms, summary) VALUES(?,?,?,?,?,?)',
                           (row['root'], row['name'], row['stack'], row['files_text'], row['terms'], clean))

    def refresh(self, cfg: dict, snapshot: ActiveSnapshot | None = None, force_discovery: bool = False):
        now = time.monotonic()
        if snapshot and snapshot.workspace_root:
            ws_path = Path(snapshot.workspace_root)
            if ws_path.is_dir():
                existing = self.get(str(ws_path))
                sig = _head_signature(ws_path)
                if not existing or existing['head_sig'] != sig or (time.time() - existing['indexed_at'] > 300):
                    self.upsert_workspace(ws_path, touch_seen=True)
                else:
                    self._touch_seen(str(ws_path))
        if force_discovery or now - self._last_discovery >= 120:
            self._last_discovery = now
            for ws_dir in _discover_workspace_dirs(cfg):
                existing = self.get(str(ws_dir))
                sig = _head_signature(ws_dir)
                if not existing or existing['head_sig'] != sig or (time.time() - existing['indexed_at'] > 600):
                    self.upsert_workspace(ws_dir, touch_seen=False)

    def recent(self, limit: int = 5) -> list[dict]:
        with self.connect() as db:
            rows = db.execute('SELECT * FROM workspaces ORDER BY last_seen DESC, indexed_at DESC LIMIT ?',
                              (max(1, min(int(limit), 50)),)).fetchall()
            return [dict(r) for r in rows]

    def search(self, query: str, limit: int = 3) -> list[dict]:
        tokens = []
        for tok in _TOKEN_RE.findall(query or ''):
            clean = tok.replace('"', '').strip()
            if clean and clean not in tokens:
                tokens.append(clean)
        if not tokens:
            return self.recent(limit)
        results: dict[str, dict] = {}
        with self.connect() as db:
            if self._fts:
                fts_query = ' OR '.join('"' + t + '"' for t in tokens[:12])
                try:
                    rows = db.execute('''SELECT w.* FROM workspaces_fts f
                                         JOIN workspaces w ON w.root = f.root
                                         WHERE workspaces_fts MATCH ?
                                         ORDER BY bm25(workspaces_fts), w.last_seen DESC
                                         LIMIT ?''', (fts_query, limit)).fetchall()
                    for row in rows:
                        results[row['root']] = dict(row)
                except sqlite3.OperationalError:
                    pass
            if len(results) < limit:
                for tok in tokens[:8]:
                    like = f'%{tok}%'
                    rows = db.execute('''SELECT * FROM workspaces
                                         WHERE name LIKE ? OR terms LIKE ? OR summary LIKE ? OR files_text LIKE ?
                                         ORDER BY last_seen DESC LIMIT ?''',
                                      (like, like, like, like, limit)).fetchall()
                    for row in rows:
                        results.setdefault(row['root'], dict(row))
                        if len(results) >= limit:
                            break
                    if len(results) >= limit:
                        break
        return list(results.values())[:limit]

    def maybe_distill_async(self, _text_tools, cfg: dict, root: str):
        if not root or str(cfg.get('context_enabled', 'true')).lower() != 'true':
            return
        from ..text_tools import TextTools, text_settings
        tcfg = text_settings(cfg)
        if not (tcfg.get('api_key') or '').strip():
            return
        row = self.get(root)
        if not row or row.get('summary'):
            return
        key = (row['root'], row['head_sig'])
        with self._distill_lock:
            if key in self._inflight:
                return
            self._inflight.add(key)
        model = (tcfg.get('tools_model') or tcfg.get('cleanup_model') or 'gpt-5.4-nano').strip()
        payload = (
            f"项目目录名: {row['name']}\n技术栈: {row['stack']}\n"
            f"关键术语: {row['terms']}\n代表文件: {row['files_text'][:600]}"
        )
        prompt = '用不超过60字的中文总结该项目的用途及最关键的2-4个中英文技术术语，只返回摘要文本，不猜测未出现的功能。'

        def worker():
            client = TextTools()
            try:
                summary = client.request(tcfg, model, prompt, payload, 6.0, 'none')
                self.set_summary(row['root'], row['head_sig'], summary)
            except Exception:
                pass
            finally:
                client.close()
                with self._distill_lock:
                    self._inflight.discard(key)

        threading.Thread(target=worker, daemon=True).start()


def enrich_asr_settings(asr_cfg: dict, snapshot: ActiveSnapshot | None, index: ContextIndex | None) -> dict:
    """Inject lightweight workspace context & prioritized vocabulary into ASR session settings."""
    updated = dict(asr_cfg)
    if str(updated.get('context_enabled', 'true')).lower() != 'true':
        return updated

    active_ws = index.get(snapshot.workspace_root) if (index and snapshot and snapshot.workspace_root) else None
    recent_ws = index.recent(4) if index else []

    hint_parts: list[str] = []
    if snapshot and snapshot.app_name:
        if active_ws:
            hint_parts.append(f"当前窗口: {snapshot.app_name} ({active_ws['name']}, {active_ws['stack']})")
        else:
            hint_parts.append(f"当前窗口: {snapshot.app_name}")
    elif active_ws:
        hint_parts.append(f"当前工作区: {active_ws['name']} ({active_ws['stack']})")
    ws_names = [w['name'] for w in recent_ws if w.get('name')]
    if ws_names:
        hint_parts.append('活跃工作区: ' + ', '.join(ws_names[:3]))
    if hint_parts:
        base_prompt = (updated.get('prompt') or '').strip()
        joined = (base_prompt + ' ' if base_prompt else '') + '；'.join(hint_parts) + '。'
        updated['prompt'] = redact_secrets(joined)[:320]

    # Preserve user's explicit vocabulary first, then append active/recent workspace terms up to 64 entries.
    user_words = [w.strip() for w in str(updated.get('vocabulary', '')).replace('，', ',').split(',') if w.strip()]
    merged: list[str] = []
    seen: set[str] = set()

    def push(word: str):
        clean = redact_secrets(word).strip()
        if not clean or len(clean) > 80 or any(c in clean for c in '<>\r\n'):
            return
        low = clean.lower()
        if low not in seen:
            seen.add(low)
            merged.append(clean)

    for w in user_words:
        push(w)
    if snapshot and snapshot.app_name:
        push(snapshot.app_name)
    if active_ws:
        push(active_ws['name'])
        for term in active_ws.get('terms', '').split(','):
            push(term.strip())
    for ws in recent_ws:
        push(ws.get('name', ''))
    updated['vocabulary'] = ','.join(merged[:64])
    return updated


def _recent_terms_snippet(recent_history: list[dict] | None) -> str:
    if not recent_history:
        return ''
    now = time.time()
    items: list[str] = []
    for row in recent_history:
        if row.get('status') not in ('inserted', 'copied', 'generated'):
            continue
        ts = row.get('created_at', '')
        try:
            age = now - datetime.fromisoformat(ts).timestamp()
            if age > 600:
                continue
        except Exception:
            pass
        text = redact_secrets((row.get('result') or row.get('raw') or '').strip())
        if text:
            items.append(text[:50])
        if len(items) >= 2:
            break
    return ' | '.join(items)[:120]


def build_turn_context(raw_text: str, snapshot: ActiveSnapshot | None, index: ContextIndex | None,
                       recent_history: list[dict] | None = None) -> str:
    """Format compact, redacted workspace & focus context (<=600 chars) for text models."""
    lines: list[str] = []
    if snapshot and (snapshot.app_name or snapshot.window_title):
        app_desc = snapshot.app_name or snapshot.wm_class
        title = redact_secrets(snapshot.window_title)[:70]
        lines.append(f'当前焦点应用: {app_desc}' + (f' ({title})' if title and title != app_desc else ''))
    if snapshot and snapshot.cwd:
        lines.append(f'当前工作目录: {snapshot.cwd}')

    active_ws = index.get(snapshot.workspace_root) if (index and snapshot and snapshot.workspace_root) else None
    if active_ws:
        detail = f"{active_ws['name']} [{active_ws['stack']}]"
        if active_ws.get('branch'):
            detail += f" branch={active_ws['branch']}"
        if active_ws.get('summary'):
            detail += f" - {active_ws['summary']}"
        elif active_ws.get('terms'):
            detail += ' | 术语: ' + ', '.join(active_ws['terms'].split(',')[:10])
        lines.append('当前工作区: ' + detail)
        if active_ws.get('files_text'):
            sample_files = ', '.join(active_ws['files_text'].splitlines()[:8])
            lines.append('代表文件: ' + sample_files)

    if index:
        matched = index.search(raw_text, limit=3)
        recent = index.recent(3)
        combined: list[dict] = []
        seen_roots = {active_ws['root']} if active_ws else set()
        for ws in matched + recent:
            if ws['root'] not in seen_roots:
                seen_roots.add(ws['root'])
                combined.append(ws)
            if len(combined) >= 3:
                break
        if combined:
            ws_desc = '; '.join(f"{w['name']}={w['root']}({w['stack']})" for w in combined)
            lines.append('相关工作区索引: ' + ws_desc)

    recent_snippet = _recent_terms_snippet(recent_history)
    if recent_snippet:
        lines.append('最近口述参考: ' + recent_snippet)
    return '\n'.join(lines)[:600]
