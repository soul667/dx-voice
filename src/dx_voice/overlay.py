"""Native GTK/Cairo implementation of the DX Voice Figma pill and transcript card."""
from collections import deque
from functools import lru_cache
from importlib.resources import files
import io
import json
import math
import time

import gi
gi.require_foreign('cairo')
gi.require_version('Gtk', '3.0')
gi.require_version('PangoCairo', '1.0')
gi.require_version('Rsvg', '2.0')
from gi.repository import Gtk, Gdk, GLib, Pango, PangoCairo, Rsvg
import cairo
from PIL import Image, ImageDraw, ImageFilter

ASSETS = files('dx_voice').joinpath('assets')
TOKENS = json.loads(ASSETS.joinpath('tokens.json').read_text())


def rounded(cr, x, y, width, height, radius):
    radius = min(radius, width / 2, height / 2)
    cr.new_sub_path()
    for cx, cy, angle in [(x + width - radius, y + radius, -math.pi / 2),
                          (x + width - radius, y + height - radius, 0),
                          (x + radius, y + height - radius, math.pi / 2),
                          (x + radius, y + radius, math.pi)]:
        cr.arc(cx, cy, radius, angle, angle + math.pi / 2)
    cr.close_path()


def color(hex_value):
    return tuple(int(hex_value[i:i + 2], 16) / 255 for i in (1, 3, 5))


@lru_cache(maxsize=4)
def shadow(width, height, radius):
    # Figma floating shadow: (0,12,36,.10) + (0,2,8,.05).
    margin = 40
    size = (width + margin * 2, height + margin * 2)
    image = Image.new('RGBA', size)
    for offset, blur, alpha in ((12, 18, 26), (2, 4, 13)):
        mask = Image.new('L', size)
        ImageDraw.Draw(mask).rounded_rectangle((margin, margin + offset, margin + width - 1,
                                               margin + height + offset - 1), radius, fill=alpha)
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
        layer = Image.new('RGBA', size, (13, 23, 41, 0))
        layer.putalpha(mask)
        image = Image.alpha_composite(image, layer)
    data = io.BytesIO()
    image.save(data, format='PNG')
    data.seek(0)
    return cairo.ImageSurface.create_from_png(data)


class VoiceOverlay:
    WIDTH = 480
    PILL = (352, 56)
    CARD = (400, 196)
    MARGIN = 40
    GAP = 12

    def __init__(self, theme='light', on_cancel=None, on_retry=None):
        self.window = Gtk.Window(type=Gtk.WindowType.POPUP)
        self.window.set_title('DX Voice')
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
        self.canvas.connect('draw', self.draw)
        self.canvas.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.POINTER_MOTION_MASK
                               | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.canvas.connect('button-press-event', self.on_click)
        self.canvas.connect('motion-notify-event', self.on_motion)
        self.canvas.connect('leave-notify-event', self.on_leave)
        self.window.add(self.canvas)
        self.on_cancel, self.on_retry = on_cancel, on_retry
        self.phase = 'hidden'
        self.message = ''
        self._partial = ''
        self.levels = deque([0.0] * 20, maxlen=20)
        self.level = 0
        self.started = 0
        self.hide_at = 0
        self.frames = None
        self.hover = None
        self.hitboxes = {}
        self._geometry = None
        self.icons = {}
        for variant in ('light', 'dark'):
            for name in ('close', 'mic', 'check', 'retry', 'dot-accent', 'dot-success', 'dot-error'):
                handle = Rsvg.Handle.new_from_file(str(ASSETS.joinpath(f'{name}-{variant}.svg')))
                valid, width, height = handle.get_intrinsic_size_in_pixels()
                if not valid or width <= 0 or height <= 0:
                    raise RuntimeError('Invalid packaged Figma SVG: ' + name)
                self.icons[name, variant] = handle, width, height
        self.set_theme(theme)
        self._sync_geometry()

    @property
    def partial(self):
        return self._partial

    @partial.setter
    def partial(self, value):
        self._partial = value or ''
        self._sync_geometry()

    @property
    def expanded(self):
        return self.phase != 'cancelled' and (bool(self.partial) or self.phase == 'error')

    @property
    def height(self):
        return self.MARGIN * 2 + self.PILL[1] + (self.CARD[1] + self.GAP if self.expanded else 0)

    def set_theme(self, theme):
        if theme == 'auto':
            settings = Gtk.Settings.get_default()
            theme = 'dark' if settings and settings.get_property('gtk-application-prefer-dark-theme') else 'light'
        self.theme = theme if theme in ('light', 'dark') else 'light'
        index = self.theme == 'dark'
        self.colors = {name: color(TOKENS['primitives'][values[index]])
                       for name, values in TOKENS['semantic'].items()}
        self.canvas.queue_draw()

    def _sync_geometry(self):
        dimensions = (self.WIDTH, self.height)
        if dimensions != self._geometry:
            self._geometry = dimensions
            self.canvas.set_size_request(*dimensions)
            self.window.resize(*dimensions)
            if self.window.get_visible():
                self._position()
        self.canvas.queue_draw()

    def _position(self):
        display = Gdk.Display.get_default()
        _, x, y = display.get_default_seat().get_pointer().get_position()
        area = display.get_monitor_at_point(x, y).get_workarea()
        self.window.move(area.x + (area.width - self.WIDTH) // 2,
                         area.y + area.height - self.height - 12)
        native = self.window.get_window()
        if native:
            region = cairo.Region()
            pill_y = self.MARGIN + (self.CARD[1] + self.GAP if self.expanded else 0)
            pill_x = (self.WIDTH - self.PILL[0]) // 2
            # Only action buttons receive pointer events. The rest of the HUD
            # is click/scroll-through, including when it overlaps an input field.
            if self.phase == 'recording':
                region.union(cairo.RectangleInt(pill_x + 12, pill_y + 12, 32, 32))
            elif self.phase == 'error':
                region.union(cairo.RectangleInt(pill_x + 304, pill_y + 8, 40, 40))
                if self.expanded:
                    region.union(cairo.RectangleInt((self.WIDTH - self.CARD[0]) // 2 + 324,
                                                      self.MARGIN + 144, 60, 36))
            native.input_shape_combine_region(region, 0, 0)

    def show(self, phase, message='', partial=None):
        if phase in ('connecting', 'recording') and self.phase not in ('connecting', 'recording'):
            self.started = time.monotonic()
            self.levels = deque([0.0] * 20, maxlen=20)
        self.phase, self.message = phase, message
        if partial is not None:
            self._partial = partial
        if phase == 'cancelled':
            self._partial = ''
        self.hide_at = time.monotonic() + (5 if phase == 'error' else 1.5) if phase in ('error', 'success', 'cancelled', 'info') else 0
        self._sync_geometry()
        self.window.show_all()
        self._position()
        if self.frames is None:
            self.frames = GLib.timeout_add(33, self.animate)

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

    def text(self, cr, words, x, y, size=14, line=22, role='text/primary', width=None,
             lines=1, latin=False, medium=False, align=Pango.Alignment.LEFT):
        layout = PangoCairo.create_layout(cr)
        font = Pango.FontDescription()
        font.set_family('Inter, Noto Sans SC' if latin else 'Noto Sans SC')
        font.set_absolute_size(size * Pango.SCALE)
        font.set_weight(Pango.Weight.MEDIUM if medium else Pango.Weight.NORMAL)
        layout.set_font_description(font)
        attributes = Pango.AttrList()
        attributes.insert(Pango.attr_line_height_new_absolute(line * Pango.SCALE))
        layout.set_attributes(attributes)
        layout.set_text(words, -1)
        if width is not None:
            layout.set_width(int(width * Pango.SCALE))
            layout.set_height(-lines)
            layout.set_wrap(Pango.WrapMode.WORD_CHAR)
            layout.set_ellipsize(Pango.EllipsizeMode.END)
            layout.set_alignment(align)
        cr.set_source_rgb(*self.colors[role])
        cr.move_to(x, y)
        PangoCairo.show_layout(cr, layout)
        return layout.get_pixel_size()

    def asset(self, cr, name, x, y):
        handle, width, height = self.icons[name, self.theme]
        cr.save()
        cr.translate(x, y)
        viewport = Rsvg.Rectangle()
        viewport.x = viewport.y = 0
        viewport.width, viewport.height = width, height
        handle.render_document(cr, viewport)
        cr.restore()

    def panel(self, cr, x, y, width, height, radius):
        cr.set_source_surface(shadow(width, height, radius), x - self.MARGIN, y - self.MARGIN)
        cr.paint()
        rounded(cr, x + .5, y + .5, width - 1, height - 1, radius)
        cr.set_source_rgb(*self.colors['surface/panel'])
        cr.fill_preserve()
        cr.set_source_rgb(*self.colors['border/default'])
        cr.set_line_width(1)
        cr.stroke()

    def keycap(self, cr, x, y, held):
        rounded(cr, x + .5, y + .5, 43, 27, TOKENS['metrics']['radius/sm'])
        cr.set_source_rgb(*self.colors['accent/soft' if held else 'surface/raised'])
        cr.fill_preserve()
        cr.set_source_rgb(*self.colors['accent/default' if held else 'border/default'])
        cr.set_line_width(1)
        cr.stroke()
        self.text(cr, 'Ctrl', x, y + 6, 11, 16,
                  'accent/default' if held else 'text/secondary', 44, latin=True, align=Pango.Alignment.CENTER)

    def waveform(self, cr, x, y, busy=False):
        for i, level in enumerate(self.levels):
            height = (10 if i % 5 == 0 else 4) if busy else 4 + 24 * min(1, max(0, level)) ** .58
            rounded(cr, x + 2.5 + i * 8, y + (28 - height) / 2, 3, height, 1.5)
            cr.set_source_rgba(*self.colors['wave/start' if i < 10 else 'wave/end'],
                               .3 + (i % 5) * .13 if busy else 1)
            cr.fill()

    def _pill(self, cr, x, y):
        self.panel(cr, x, y, *self.PILL, 28)
        recording = self.phase == 'recording'
        if recording:
            if self.hover == 'cancel':
                rounded(cr, x + 12, y + 12, 32, 32, 16)
                cr.set_source_rgb(*self.colors['surface/raised'])
                cr.fill()
            self.asset(cr, 'close', x + 19, y + 19)
            self.hitboxes['cancel'] = (x + 12, y + 12, 32, 32)
            self.waveform(cr, x + 56, y + 14)
            seconds = max(0, int(time.monotonic() - self.started))
            self.text(cr, f'{seconds // 60}:{seconds % 60:02d}', x + 253, y + 20, 11, 16,
                      'text/secondary', 31, latin=True, align=Pango.Alignment.RIGHT)
            self.keycap(cr, x + 296, y + 14, True)
        elif self.phase == 'processing':
            self.asset(cr, 'mic', x + 12, y + 18)
            self.waveform(cr, x + 44, y + 14, busy=True)
            self.text(cr, '即将输入', x + 276, y + 19, 12, 18, 'text/secondary', medium=True)
        elif self.phase == 'success':
            self.asset(cr, 'check', x + 12, y + 18)
            copied = '已复制' in self.message
            self.text(cr, '已复制到剪贴板' if copied else '已输入到当前窗口', x + 44, y + 17)
            self.text(cr, '完成', x + 316, y + 19, 12, 18, 'status/success', medium=True)
        elif self.phase == 'error':
            self.asset(cr, 'retry', x + 12, y + 18)
            self.text(cr, self.message.split('。')[0] or '连接中断，录音已保留', x + 44, y + 19, 12, 18, 'text/secondary', 240, medium=True)
            self.text(cr, '重试', x + 316, y + 19, 12, 18, 'accent/default', medium=True)
            self.hitboxes['retry'] = (x + 304, y + 8, 40, 40)
        else:
            self.asset(cr, 'mic', x + 12, y + 18)
            words = self.message if self.phase == 'info' else '已取消' if self.phase == 'cancelled' else '正在连接…' if self.phase == 'connecting' else '长按 Ctrl 开始说话'
            self.text(cr, words, x + 44, y + 17, role='text/secondary')
            self.keycap(cr, x + 296, y + 14, False)

    def _card(self, cr, x, y):
        self.panel(cr, x, y, *self.CARD, TOKENS['metrics']['radius/lg'])
        state = 'error' if self.phase == 'error' else 'success' if self.phase == 'success' else 'accent'
        self.asset(cr, 'dot-' + state, x + 20, y + 26)
        title = {'recording': '正在聆听', 'processing': '正在完成', 'success': '输入完成',
                 'error': '连接已断开'}.get(self.phase, '正在连接')
        if self.phase == 'success' and '已复制' in self.message:
            title = '已复制，等待粘贴'
        self.text(cr, title, x + 34, y + 20, 12, 18, 'text/secondary', medium=True)
        seconds = max(0, int(time.monotonic() - self.started))
        caption = f'{seconds // 60}:{seconds % 60:02d}' if self.phase == 'recording' else 'DX VOICE'
        self.text(cr, caption, x + 300, y + 21, 11, 16, 'text/muted', 80, latin=True, align=Pango.Alignment.RIGHT)
        words = self.message if self.phase == 'error' else self.partial
        # Long dictation keeps the newest words in the three-line live preview.
        if self.phase != 'error' and len(words) > 72:
            words = '…' + words[-72:]
        self.text(cr, words, x + 20, y + 50, 18, 28, width=360, lines=3)
        if self.phase == 'error':
            self.text(cr, '录音不会自动重新上传', x + 20, y + 154, 11, 16, 'text/secondary', latin=True)
            self.asset(cr, 'retry', x + 332, y + 154)
            self.text(cr, '重试', x + 356, y + 153, 12, 18, 'accent/default', medium=True)
            self.hitboxes['retry-card'] = (x + 324, y + 144, 60, 36)
        else:
            hint = '松开 Ctrl，输入到当前窗口' if self.phase == 'recording' else '正在完成最后的识别' if self.phase == 'processing' else '已复制，请在需要的位置粘贴' if '已复制' in self.message else '你可以继续下一句'
            self.text(cr, hint, x + 20, y + 154, 11, 16, 'text/secondary', 300, latin=True)
            self.keycap(cr, x + 336, y + 148, self.phase == 'recording')

    def draw(self, _, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        self.hitboxes = {}
        if self.expanded:
            self._card(cr, (self.WIDTH - self.CARD[0]) / 2, self.MARGIN)
        pill_y = self.MARGIN + (self.CARD[1] + self.GAP if self.expanded else 0)
        self._pill(cr, (self.WIDTH - self.PILL[0]) / 2, pill_y)
        return False

    def hit(self, x, y):
        return next((name for name, (bx, by, width, height) in self.hitboxes.items()
                     if bx <= x <= bx + width and by <= y <= by + height), None)

    def on_click(self, _, event):
        if event.button != 1:
            return False
        action = self.hit(event.x, event.y)
        if action == 'cancel' and self.on_cancel:
            self.on_cancel()
        elif action in ('retry', 'retry-card') and self.on_retry:
            self.on_retry()
        return bool(action)

    def on_motion(self, _, event):
        self.hover = self.hit(event.x, event.y)
        self.canvas.queue_draw()
        return False

    def on_leave(self, *_):
        self.hover = None
        self.canvas.queue_draw()
        return False

    def close(self):
        if self.frames is not None:
            GLib.source_remove(self.frames)
            self.frames = None
        self.window.destroy()
