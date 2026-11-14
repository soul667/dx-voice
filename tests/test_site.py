from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'site'


class _AssetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []
        self.subresources = []

    def handle_starttag(self, tag, attrs):
        attr_map = dict(attrs)
        for key in ('src', 'href'):
            val = attr_map.get(key)
            if val:
                self.refs.append((tag, key, val))
                if tag in ('link', 'script', 'img'):
                    self.subresources.append((tag, key, val))


class SiteTests(unittest.TestCase):
    def test_site_files_present_and_non_empty(self):
        for name in ('index.html', 'styles.css', 'app.js'):
            path = SITE / name
            self.assertTrue(path.is_file(), f'missing site file: {name}')
            self.assertGreater(path.stat().st_size, 500, f'site file unexpectedly small: {name}')

    def test_local_assets_resolve_under_site_and_no_external_cdns(self):
        html = (SITE / 'index.html').read_text(encoding='utf-8')
        parser = _AssetParser()
        parser.feed(html)

        for tag, attr, val in parser.subresources:
            self.assertFalse(
                val.startswith(('http://', 'https://', '//')),
                f'unexpected external subresource in <{tag} {attr}>: {val}',
            )

        for tag, attr, val in parser.refs:
            if val.startswith(('http://', 'https://', '#', 'data:', 'mailto:')):
                continue
            clean = val.split('#', 1)[0].split('?', 1)[0]
            target = (SITE / clean).resolve()
            self.assertEqual(SITE.resolve(), target.parents[len(target.parents) - len(SITE.resolve().parents) - 1],
                             f'local asset escapes site directory: {val}')
            self.assertTrue(target.is_file(), f'missing local asset referenced in <{tag} {attr}>: {val}')

    def test_philosophy_and_v060_facts_present(self):
        combined = '\n'.join(
            (SITE / name).read_text(encoding='utf-8')
            for name in ('index.html', 'styles.css', 'app.js')
        )
        for phrase in (
            'JUST SPEAK',
            'JUST THINK',
            'JUST NOTE',
            'LET EVERYTHING THAT SLOWS YOUR THINKING FALL AWAY',
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
        for path in sorted(SITE.rglob('*')):
            if not path.is_file():
                continue
            text = path.read_text(encoding='utf-8')
            self.assertIsNone(home_path_re.search(text), f'private home path found in {path.name}')
            self.assertIsNone(secret_re.search(text), f'secret-like pattern found in {path.name}')


if __name__ == '__main__':
    unittest.main()

