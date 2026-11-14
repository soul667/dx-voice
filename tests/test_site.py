from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'site'


class _AssetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.subresources = []

    def handle_starttag(self, tag, attrs):
        attr_map = dict(attrs)
        for key in ('src', 'href'):
            val = attr_map.get(key)
            if val and tag in ('link', 'script', 'img'):
                self.subresources.append((tag, key, val))


class SiteTests(unittest.TestCase):
    def test_react_project_structure_present(self):
        required = (
            'package.json',
            'vite.config.js',
            'index.html',
            'en.html',
            'src/App.jsx',
            'src/content.jsx',
            'src/styles.css',
            'src/entry-zh.jsx',
            'src/entry-en.jsx',
            'src/components/HeroStage.jsx',
            'src/components/CarbonHudSimulator.jsx',
            'src/components/DexEcosystem.jsx',
            'src/components/ContextXRay.jsx',
            'src/components/TuiWorkspace.jsx',
        )
        for rel in required:
            path = SITE / rel
            self.assertTrue(path.is_file(), f'missing React site file: {rel}')
            self.assertGreater(path.stat().st_size, 100, f'unexpectedly small file: {rel}')

        pkg = json.loads((SITE / 'package.json').read_text(encoding='utf-8'))
        deps = pkg.get('dependencies', {})
        for dep in ('react', 'react-dom', 'framer-motion'):
            self.assertIn(dep, deps, f'missing React dependency: {dep}')

    def test_html_entries_use_no_external_cdns(self):
        for entry in ('index.html', 'en.html'):
            html = (SITE / entry).read_text(encoding='utf-8')
            parser = _AssetParser()
            parser.feed(html)
            for tag, attr, val in parser.subresources:
                self.assertFalse(
                    val.startswith(('http://', 'https://', '//')),
                    f'unexpected external CDN in {entry} <{tag} {attr}>: {val}',
                )

    def test_philosophy_dex_module_and_v060_facts_present(self):
        src_files = sorted((SITE / 'src').rglob('*'))
        combined = '\n'.join(
            p.read_text(encoding='utf-8')
            for p in src_files
            if p.is_file() and p.suffix in ('.js', '.jsx', '.css')
        )
        for phrase in (
            'JUST SPEAK',
            'JUST THINK',
            'JUST ACT',
            'LET EVERYTHING THAT SLOWS YOUR THINKING FALL AWAY',
            'Dex',
            'builtin:voice',
            'Ctrl+Win',
            'Alt+Win',
            'Ctrl',
            'dx v',
            '0.6.0',
        ):
            self.assertIn(phrase, combined, f'missing required copy or fact: {phrase}')

    def test_no_private_host_paths_or_secrets(self):
        home_path_re = re.compile(r'/(?:home|Users)/[A-Za-z0-9._-]+')
        secret_re = re.compile(r'\bsk-[A-Za-z0-9_-]{8,}')
        skip_dirs = {'node_modules', 'dist', '.vite'}

        for path in sorted(SITE.rglob('*')):
            if not path.is_file():
                continue
            if any(part in skip_dirs for part in path.relative_to(SITE).parts):
                continue
            if path.name == 'bun.lock':
                continue
            text = path.read_text(encoding='utf-8')
            self.assertIsNone(home_path_re.search(text), f'private home path found in {path}')
            self.assertIsNone(secret_re.search(text), f'secret-like pattern found in {path}')


if __name__ == '__main__':
    unittest.main()
