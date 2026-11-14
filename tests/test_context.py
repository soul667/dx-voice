"""Exercise secret redaction, FTS5 workspace indexing and context injection without live APIs."""
from pathlib import Path
import tempfile
import unittest

from dx_voice.modules.context import (
    ActiveSnapshot,
    ContextIndex,
    build_turn_context,
    enrich_asr_settings,
    redact_secrets,
    scan_workspace,
)


class ContextTests(unittest.TestCase):
    def test_redact_secrets_masks_tokens_keys_and_urls(self):
        raw = (
            'workspace=dx-voice key=sk-proj-1234567890abcdef '
            'auth="Bearer header.payload.sig" api_key=mysecretpass '
            'url=https://alice:hunter2@api.example.com/v1\nline2'
        )
        cleaned = redact_secrets(raw)
        self.assertNotIn('sk-proj-1234567890abcdef', cleaned)
        self.assertNotIn('header.payload.sig', cleaned)
        self.assertNotIn('mysecretpass', cleaned)
        self.assertNotIn('hunter2', cleaned)
        self.assertIn('dx-voice', cleaned)
        self.assertIn('[REDACTED]', cleaned)
        self.assertIn('https://***@api.example.com/v1', cleaned)
        self.assertNotIn('\n', cleaned)

    def test_scan_and_fts_index_exclude_sensitive_files_and_search_projects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            alpha = root / 'alpha-voice'
            (alpha / '.git').mkdir(parents=True)
            (alpha / '.git/HEAD').write_text('ref: refs/heads/feat-ctx\n', encoding='utf-8')
            (alpha / 'pyproject.toml').write_text('[project]\nname = "alpha-voice"\n', encoding='utf-8')
            (alpha / 'README.md').write_text('# AlphaVoice 语音输入引擎\n', encoding='utf-8')
            (alpha / 'src').mkdir()
            (alpha / 'src/engine_core.py').write_text('pass\n', encoding='utf-8')
            (alpha / '.env').write_text('API_KEY=sk-should-never-appear\n', encoding='utf-8')
            (alpha / 'settings.txt').write_text('api_key=secret\n', encoding='utf-8')

            beta = root / 'beta-render'
            beta.mkdir()
            (beta / 'package.json').write_text(
                '{"name": "beta-render", "scripts": {"build_shaders": "vite build"}}',
                encoding='utf-8',
            )
            (beta / 'shader_pipeline.ts').write_text('export const ok = true;\n', encoding='utf-8')

            scanned = scan_workspace(alpha)
            self.assertEqual(scanned['branch'], 'feat-ctx')
            self.assertIn('Python', scanned['stack'])
            self.assertIn('src/engine_core.py', scanned['files_text'])
            self.assertNotIn('.env', scanned['files_text'])
            self.assertNotIn('settings.txt', scanned['files_text'])

            db_path = root / 'state/context.db'
            index = ContextIndex(db_path)
            self.assertEqual(db_path.stat().st_mode & 0o777, 0o600)
            index.upsert_workspace(alpha)
            index.upsert_workspace(beta)

            hit_beta = index.search('帮我看看 shader_pipeline 编译状态', limit=2)
            self.assertTrue(hit_beta)
            self.assertEqual(hit_beta[0]['name'], 'beta-render')

            hit_alpha = index.search('打开 alpha-voice 项目', limit=2)
            self.assertTrue(hit_alpha)
            self.assertEqual(hit_alpha[0]['name'], 'alpha-voice')

    def test_enrich_asr_settings_preserves_user_vocabulary_and_bounds_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proj = root / 'dx-voice'
            (proj / '.git').mkdir(parents=True)
            (proj / 'pyproject.toml').write_text('[project]\nname = "dx-voice"\n', encoding='utf-8')
            (proj / 'README.md').write_text('# DXVoice ContextIndex\n', encoding='utf-8')
            for i in range(70):
                (proj / f'module_term_{i}.py').write_text('pass\n', encoding='utf-8')

            index = ContextIndex(root / 'context.db')
            index.upsert_workspace(proj)
            snap = ActiveSnapshot(app_name='Gnome-terminal', cwd=str(proj), workspace_root=str(proj.resolve()))
            base_cfg = {
                'context_enabled': 'true',
                'vocabulary': '自定义词A, CustomTermB',
                'prompt': '中英文混合口述。' * 40,
            }

            enriched = enrich_asr_settings(base_cfg, snap, index)
            words = enriched['vocabulary'].split(',')
            self.assertEqual(words[:2], ['自定义词A', 'CustomTermB'])
            self.assertLessEqual(len(words), 64)
            self.assertIn('dx-voice', words)
            self.assertLessEqual(len(enriched['prompt']), 320)

            disabled = enrich_asr_settings(dict(base_cfg, context_enabled='false'), snap, index)
            self.assertEqual(disabled, dict(base_cfg, context_enabled='false'))

    def test_build_turn_context_includes_focus_and_stays_compact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proj = root / 'dx-voice'
            (proj / '.git').mkdir(parents=True)
            (proj / '.git/HEAD').write_text('ref: refs/heads/main\n', encoding='utf-8')
            (proj / 'pyproject.toml').write_text('[project]\nname = "dx-voice"\n', encoding='utf-8')
            (proj / 'overlay.py').write_text('pass\n', encoding='utf-8')

            index = ContextIndex(root / 'context.db')
            index.upsert_workspace(proj)
            snap = ActiveSnapshot(
                app_name='Code',
                window_title='overlay.py - dx-voice Bearer topsecret',
                cwd=str(proj),
                workspace_root=str(proj.resolve()),
            )

            ctx = build_turn_context('把语音输入改成工作区上下文', snap, index)
            self.assertLessEqual(len(ctx), 600)
            self.assertIn('Code', ctx)
            self.assertIn('branch=main', ctx)
            self.assertIn(str(proj), ctx)
            self.assertNotIn('topsecret', ctx)


if __name__ == '__main__':
    unittest.main()
