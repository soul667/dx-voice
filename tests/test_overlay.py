"""Native rendering/interaction checks; skipped on a headless non-GTK test runner."""
import io
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

try:
    from dx_voice.overlay import VoiceOverlay, cairo, Gtk, ASSETS
    from PIL import Image
    GTK_READY = bool(os.environ.get('DISPLAY')) and Gtk.init_check()[0]
except (ImportError, ValueError):
    GTK_READY = False


@unittest.skipUnless(GTK_READY, 'Native GTK display required')
class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.overlay = VoiceOverlay(on_cancel=lambda: self.calls.append('cancel'),
                                    on_retry=lambda: self.calls.append('retry'))

    def tearDown(self):
        self.overlay.close()

    def render(self):
        overlay = self.overlay
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, overlay.WIDTH, overlay.height)
        overlay.draw(None, cairo.Context(surface))
        stream = io.BytesIO()
        surface.write_to_png(stream)
        stream.seek(0)
        return Image.open(stream).convert('RGBA')

    def test_partial_expands_upward_then_next_turn_clears_old_text(self):
        h = self.overlay
        h.show('recording', partial='')
        self.assertEqual(h.height, 136)
        h.partial = '边说边识别的文字'
        self.assertTrue(h.expanded)
        self.assertEqual(h.height, 344)
        h.show('processing', partial=h.partial)
        self.assertEqual(h.height, 344)
        h.show('success', '✓ 已输入。')
        h.show('connecting', partial='')
        self.assertFalse(h.expanded)
        self.assertEqual(h.partial, '')

    def test_light_and_dark_surfaces_use_figma_tokens(self):
        h = self.overlay
        h.phase = 'recording'
        for theme, expected in [('light', (255, 255, 255)), ('dark', (28, 34, 44))]:
            h.set_theme(theme)
            image = self.render()
            self.assertEqual(image.getpixel((240, 90))[:3], expected)
            self.assertEqual(image.getpixel((240, 90))[3], 255)

    def test_cancel_and_retry_controls_invoke_actions_only_on_left_click(self):
        h = self.overlay
        h.phase = 'recording'
        self.render()
        x, y, width, height = h.hitboxes['cancel']
        event = SimpleNamespace(x=x + width / 2, y=y + height / 2, button=1)
        self.assertTrue(h.on_click(None, event))
        self.assertEqual(self.calls, ['cancel'])
        event.button = 3
        self.assertFalse(h.on_click(None, event))
        h.phase = 'error'
        h.message = '连接中断，录音已保留。'
        self.render()
        x, y, width, height = h.hitboxes['retry-card']
        h.on_click(None, SimpleNamespace(x=x + width / 2, y=y + height / 2, button=1))
        self.assertEqual(self.calls, ['cancel', 'retry'])

    def test_frosted_material_uses_local_blurred_pixels_with_transparency(self):
        h = self.overlay
        h.set_theme('frosted')
        h.phase = 'recording'
        with patch('dx_voice.modules.screen.region_image', return_value=Image.new('RGB', (480, 344), (0, 100, 200))):
            h._capture_backdrop((0, 0, 480, 344))
        self.assertIsNotNone(h.backdrop)
        pixel = self.render().getpixel((240, 90))
        self.assertLess(pixel[0], pixel[2])
        self.assertLess(pixel[3], 255)
        h.close()
        self.assertIsNone(h.backdrop)

    def test_all_supplied_svg_assets_are_nonempty_at_original_geometry(self):
        self.assertEqual(len(self.overlay.icons), 14)
        for (name, theme), (_, width, height) in self.overlay.icons.items():
            self.assertGreater(ASSETS.joinpath(f'{name}-{theme}.svg').stat().st_size, 0)
            expected = 6 if name.startswith('dot-') else 20
            self.assertEqual((width, height), (expected, expected))

    def test_all_runtime_states_render_in_both_themes(self):
        h = self.overlay
        for theme in ('light', 'dark'):
            h.set_theme(theme)
            for state in ('connecting', 'recording', 'processing', 'success', 'error', 'cancelled', 'info'):
                h.show(state, '连接中断，录音已保留。' if state == 'error' else '✓ 已输入。',
                       partial='测试实时文字' if state in ('recording', 'processing', 'success') else '')
                image = self.render()
                self.assertGreater(image.getbbox()[2], 352)


if __name__ == '__main__':
    unittest.main()
