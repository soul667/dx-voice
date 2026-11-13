"""Small, non-focusing dictation HUD, with a waveform driven by microphone PCM."""
from collections import deque
import math
import time

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gtk, Gdk, GLib, Pango, PangoCairo
import cairo


def rounded(cr, x, y, width, height, radius):
    cr.new_sub_path()
    for cx, cy, a in [(x + width - radius, y + radius, -math.pi / 2),
                      (x + width - radius, y + height - radius, 0),
                      (x + radius, y + height - radius, math.pi / 2),
                      (x + radius, y + radius, math.pi)]:
        cr.arc(cx, cy, radius, a, a + math.pi / 2)
    cr.close_path()


class VoiceOverlay:
    WIDTH = 416
    HEIGHT = 130

    def __init__(self):
        self.window = Gtk.Window(type=Gtk.WindowType.POPUP)
        self.window.set_title('DX Voice状态')
        self.window.set_accept_focus(False)
        self.window.set_focus_on_map(False)
        self.window.set_keep_above(True)
        self.window.set_skip_taskbar_hint(True)
        self.window.set_skip_pager_hint(True)
        self.window.set_app_paintable(True)
        visual = self.window.get_screen().get_rgba_visual()
        if visual:
            self.window.set_visual(visual)
        self.canvas = Gtk.DrawingArea()
        self.canvas.set_size_request(self.WIDTH, self.HEIGHT)
        self.canvas.connect('draw', self.draw)
        self.window.add(self.canvas)
        self.phase = 'hidden'
        self.message = ''
        self.partial = ''
        self.levels = deque([0.0] * 45, maxlen=45)
        self.level = 0
        self.started = 0
        self.hide_at = 0
        self.frames = None

    def show(self, phase, message='', partial=None):
        if phase == 'recording' and self.phase != 'recording':
            self.started = time.monotonic()
            self.levels = deque([0.0] * 45, maxlen=45)
        self.phase, self.message = phase, message
        if partial is not None:
            self.partial = partial
        self.hide_at = time.monotonic() + (4 if phase == 'error' else 1.2) if phase in ('error', 'success', 'cancelled') else 0
        self.window.show_all()
        display = Gdk.Display.get_default()
        _, x, y = display.get_default_seat().get_pointer().get_position()
        area = display.get_monitor_at_point(x, y).get_workarea()
        self.window.move(area.x + (area.width - self.WIDTH) // 2, area.y + area.height - self.HEIGHT - 36)
        if self.frames is None:
            self.frames = GLib.timeout_add(33, self.animate)
        self.canvas.queue_draw()

    def animate(self):
        if self.hide_at and time.monotonic() >= self.hide_at:
            self.window.hide()
            self.phase = 'hidden'
            self.frames = None
            return False
        if self.phase == 'recording':
            self.levels.append(self.level)
            self.level *= .92
        self.canvas.queue_draw()
        return True

    @staticmethod
    def text(cr, text, x, y, size, color=(.94, .95, .97), width=None, weight=Pango.Weight.NORMAL):
        layout = PangoCairo.create_layout(cr)
        desc = Pango.FontDescription('Sans')
        desc.set_absolute_size(size * Pango.SCALE)
        desc.set_weight(weight)
        layout.set_font_description(desc)
        layout.set_text(text, -1)
        if width:
            layout.set_width(int(width * Pango.SCALE))
            layout.set_ellipsize(Pango.EllipsizeMode.START)
            layout.set_single_paragraph_mode(True)
        cr.set_source_rgb(*color)
        cr.move_to(x, y)
        PangoCairo.show_layout(cr, layout)

    def draw(self, _, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        for spread, alpha in [(8, .025), (5, .05), (2, .12)]:
            rounded(cr, 10 - spread, 9 - spread, 396 + 2 * spread, 108 + 2 * spread, 25 + spread)
            cr.set_source_rgba(0, 0, 0, alpha)
            cr.fill()
        rounded(cr, 10, 7, 396, 108, 24)
        cr.set_source_rgba(.085, .094, .11, .97)
        cr.fill_preserve()
        cr.set_source_rgba(1, 1, 1, .10)
        cr.set_line_width(1)
        cr.stroke()
        recording = self.phase == 'recording'
        error = self.phase == 'error'
        color = (1, .42, .37) if error else (.43, .9, .72)
        cr.set_source_rgb(*color)
        cr.arc(34, 30, 3.5, 0, 2 * math.pi)
        cr.fill()
        title = {'recording': '正在聆听', 'connecting': '正在连接', 'processing': '正在完成',
                 'success': '已输入', 'cancelled': '已取消', 'error': '暂时未完成'}.get(self.phase, '语音输入')
        if self.phase == 'success' and '已复制' in self.message:
            title = '已复制'
        self.text(cr, title, 46, 19, 13, weight=Pango.Weight.MEDIUM)
        if recording:
            seconds = max(0, int(time.monotonic() - self.started))
            self.text(cr, f'{seconds // 60}:{seconds % 60:02d}', 343, 20, 12, (.52, .56, .62))
        elif self.phase == 'processing':
            cr.set_source_rgb(.65, .7, .8)
            cr.set_line_width(2)
            cr.arc(366, 29, 6, time.monotonic() * 4, time.monotonic() * 4 + 4)
            cr.stroke()
        if self.phase in ('recording', 'connecting', 'processing'):
            levels = list(self.levels)
            for i, value in enumerate(levels):
                height = 3 + 29 * min(1, max(0, value) ** .58)
                rounded(cr, 31 + i * 7.8, 62 - height / 2, 3.3, height, 1.65)
                cr.set_source_rgba(.77, .83, .94, .35 + .55 * min(1, value * 3))
                cr.fill()
            preview = self.partial or ('松开 Ctrl 完成输入' if recording else '连接后即可实时识别')
        else:
            preview = self.message or ('文字已放入当前输入框' if not error else '请稍后重试')
        self.text(cr, preview.replace('\n', ' '), 30, 86, 12, (.66, .7, .77), width=355)
        return False
