"""Native rendering/interaction checks for Carbon Fluid Glass HUD."""
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
        self.overlay = VoiceOverlay(
            on_cancel=lambda: self.calls.append('cancel'),
            on_retry=lambda: self.calls.append('retry'),
        )

    def tearDown(self):
        self.overlay.close()

    def render(self):
        overlay = self.overlay
        overlay.settle()
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, overlay.WIDTH, overlay.height)
        overlay.draw(None, cairo.Context(surface))
        stream = io.BytesIO()
        surface.write_to_png(stream)
        stream.seek(0)
        return Image.open(stream).convert('RGBA')

    def test_fixed_stage_and_content_adaptive_spring_morphing(self):
        h = self.overlay
        self.assertEqual((h.WIDTH, h.height), (520, 320))

        h.show('recording', partial='')
        h.settle()
        self.assertFalse(h.expanded)
        self.assertEqual((h.w_spring.value, h.h_spring.value), (h.COMPACT_W, h.COMPACT_H))

        h.partial = '单行流式识别文本'
        h.settle()
        self.assertTrue(h.expanded)
        h_one = h.h_spring.value
        self.assertEqual(h.w_spring.value, h.EXPANDED_W)
        self.assertEqual(h_one, 136.0)

        h.partial = '这是一段足够长的中英文混合语音识别内容，用来验证当流式转录文本自动换行到三行时卡片高度能够平滑且自适应地扩展，而不会出现文字截断或按钮重叠问题。'
        h.settle()
        h_three = h.h_spring.value
        self.assertGreater(h_three, h_one)
        self.assertEqual(h_three, 190.0)

        h.show('processing', partial=h.partial)
        h.settle()
        self.assertTrue(h.expanded)

        h.show('success', '✓ 已输入。')
        h.settle()
        self.assertFalse(h.expanded)
        self.assertEqual(h.h_spring.value, h.COMPACT_H)

        h.show('connecting', partial='')
        h.settle()
        self.assertFalse(h.expanded)
        self.assertEqual(h.partial, '')

    def test_arming_charge_pill_and_dismissal(self):
        h = self.overlay
        h.show_arming(0.65, mode='dictation', theme='dark')
        self.assertEqual(h.phase, 'arming')
        self.assertFalse(h.expanded)
        h.settle()
        self.assertEqual((h.w_spring.value, h.h_spring.value), (h.ARMING_W, h.ARMING_H))
        image = self.render()
        self.assertIsNotNone(image.getbbox())

        h.dismiss_arming()
        self.assertGreater(h.hide_at, 0.0)

    def test_light_and_dark_surfaces_use_tokens(self):
        h = self.overlay
        h.phase = 'recording'
        h.partial = ''
        for theme, expected in [('light', (255, 255, 255)), ('dark', (15, 20, 30))]:
            h.set_theme(theme)
            image = self.render()
            pixel = image.getpixel((320, 278))
            self.assertEqual(pixel[:3], expected)
            self.assertEqual(pixel[3], 255)

    def test_cancel_retry_hitboxes_and_click_through(self):
        h = self.overlay
        h.phase = 'recording'
        self.render()
        self.assertIsNone(h.hit(320, 278))
        self.assertFalse(h.on_click(None, SimpleNamespace(x=320, y=278, button=1)))

        x, y, width, height = h.hitboxes['cancel']
        event = SimpleNamespace(x=x + width / 2, y=y + height / 2, button=1)
        self.assertTrue(h.on_click(None, event))
        self.assertEqual(self.calls, ['cancel'])
        event.button = 3
        self.assertFalse(h.on_click(None, event))

        h.phase = 'error'
        h.message = '连接中断，录音已保留。'
        self.render()
        for key in ('retry', 'retry-card'):
            rx, ry, rw, rh = h.hitboxes[key]
            self.assertTrue(h.on_click(None, SimpleNamespace(x=rx + rw / 2, y=ry + rh / 2, button=1)))
        self.assertEqual(self.calls, ['cancel', 'retry', 'retry'])

    def test_frosted_material_uses_local_blurred_pixels_with_transparency(self):
        h = self.overlay
        h.set_theme('frosted')
        h.phase = 'recording'
        with patch('dx_voice.modules.screen.region_image', return_value=Image.new('RGB', (520, 320), (0, 100, 200))):
            h._capture_backdrop((0, 0, 520, 320))
        self.assertIsNotNone(h.backdrop)
        pixel = self.render().getpixel((320, 278))
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

    def test_all_runtime_states_modes_and_themes_render(self):
        h = self.overlay
        h.set_context_label('dx-voice')
        for theme in ('light', 'dark', 'frosted'):
            h.set_theme(theme)
            for mode in ('dictation', 'command', 'tools'):
                h.set_mode(mode)
                h.show_arming(0.7, mode=mode)
                self.assertIsNotNone(self.render().getbbox())
                for state in ('connecting', 'recording', 'processing', 'success', 'action', 'error', 'cancelled', 'info'):
                    h.show(
                        state,
                        '连接中断，录音已保留。' if state == 'error' else '✓ 已复制到剪贴板' if state == 'success' else '提示消息',
                        partial='测试流式文本与 ContextIndex' if state in ('recording', 'processing', 'action') else '',
                    )
                    image = self.render()
                    self.assertGreater(image.getbbox()[2], 350)


if __name__ == '__main__':
    unittest.main()
