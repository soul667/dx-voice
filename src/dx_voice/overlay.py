"""Carbon Fluid Glass GTK/Cairo overlay with 60 FPS spring-morphing capsule and optical shaders."""
from collections import deque
from importlib.resources import files
import json
import math
import time

import gi
gi.require_foreign('cairo')
gi.require_version('Gtk', '3.0')
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
gi.require_version('Rsvg', '2.0')
from gi.repository import Gtk, Gdk, GLib, Pango, PangoCairo, Rsvg
import cairo
from PIL import Image, ImageEnhance, ImageFilter

ASSETS = files('dx_voice').joinpath('assets')
TOKENS = json.loads(ASSETS.joinpath('tokens.json').read_text())


def rounded(cr, x, y, width, height, radius):
    radius = max(0.0, min(float(radius), float(width) / 2.0, float(height) / 2.0))
    cr.new_sub_path()
    for cx, cy, angle in [(x + width - radius, y + radius, -math.pi / 2),
                          (x + width - radius, y + height - radius, 0),
                          (x + radius, y + height - radius, math.pi / 2),
                          (x + radius, y + radius, math.pi)]:
        cr.arc(cx, cy, radius, angle, angle + math.pi / 2)
    cr.close_path()


def color(hex_value):
    return tuple(int(hex_value[i:i + 2], 16) / 255.0 for i in (1, 3, 5))


class Spring:
    """Critically damped second-order spring for 60 FPS fluid layout transitions."""

    def __init__(self, value=0.0, stiffness=300.0, damping=26.0):
        self.value = float(value)
        self.target = float(value)
        self.velocity = 0.0
        self.stiffness = float(stiffness)
        self.damping = float(damping)

    def snap(self, value):
        self.value = float(value)
        self.target = float(value)
        self.velocity = 0.0

    def step(self, dt):
        dt = max(0.001, min(0.032, float(dt)))
        sub_dt = dt / 2.0
        for _ in range(2):
            force = -self.stiffness * (self.value - self.target)
            drag = -self.damping * self.velocity
            self.velocity += (force + drag) * sub_dt
            self.value += self.velocity * sub_dt
        if abs(self.value - self.target) < 0.08 and abs(self.velocity) < 0.6:
            self.value = self.target
            self.velocity = 0.0
            return False
        return True


class VoiceOverlay:
    """Single monolithic Carbon Fluid Glass capsule on a fixed-size click-through X11 stage."""

    WIDTH = 520
    STAGE_HEIGHT = 320
    MARGIN = 34
    HEIGHT = STAGE_HEIGHT

    COMPACT_W = 396.0
    COMPACT_H = 60.0
    ARMING_W = 216.0
    ARMING_H = 40.0
    EXPANDED_W = 452.0
    ERROR_H = 164.0
    DOCK_H = 46.0

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
        self.canvas.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.LEAVE_NOTIFY_MASK
        )
        self.canvas.connect('button-press-event', self.on_click)
        self.canvas.connect('motion-notify-event', self.on_motion)
        self.canvas.connect('leave-notify-event', self.on_leave)
        self.window.add(self.canvas)

        self.on_cancel, self.on_retry = on_cancel, on_retry
        self.phase = 'hidden'
        self.mode = 'dictation'
        self.message = ''
        self._partial = ''
        self.context_label = ''
        self.arm_progress = 0.0

        self.levels = deque([0.0] * 24, maxlen=24)
        self.bars = [0.0] * 24
        self.smooth_level = 0.0
        self.level = 0.0
        self.started = 0.0
        self.phase_at = 0.0
        self.hide_at = 0.0
        self._last_tick = time.monotonic()

        self.w_spring = Spring(self.COMPACT_W, stiffness=300.0, damping=26.0)
        self.h_spring = Spring(self.COMPACT_H, stiffness=290.0, damping=25.0)
        self.r_spring = Spring(30.0, stiffness=280.0, damping=26.0)
        self.y_spring = Spring(0.0, stiffness=320.0, damping=24.0)

        self.frames = None
        self.hover = None
        self.hitboxes = {}
        self._last_hitboxes_key = None

        self.backdrop = None
        self._backdrop_bytes = None
        self.backdrop_rect = None
        self.backdrop_dark = False
        self._geometry = None

        self._measure_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
        self._measure_cr = cairo.Context(self._measure_surface)

        self.icons = {}
        for variant in ('light', 'dark'):
            for name in ('close', 'mic', 'check', 'retry', 'dot-accent', 'dot-success', 'dot-error'):
                handle = Rsvg.Handle.new_from_file(str(ASSETS.joinpath(f'{name}-{variant}.svg')))
                valid, width, height = handle.get_intrinsic_size_in_pixels()
                if not valid or width <= 0 or height <= 0:
                    raise RuntimeError('Invalid packaged Figma SVG: ' + name)
                self.icons[name, variant] = handle, width, height

        self._palettes = [
            {name: color(TOKENS['primitives'][values[idx]]) for name, values in TOKENS['semantic'].items()}
            for idx in (0, 1)
        ]
        self.set_theme(theme)
        self._sync_geometry(force=True)

    @property
    def height(self):
        return self.STAGE_HEIGHT

    @property
    def partial(self):
        return self._partial

    @partial.setter
    def partial(self, value):
        self._partial = value or ''
        self._update_spring_targets()
        self.canvas.queue_draw()

    @property
    def expanded(self):
        if self.phase in ('hidden', 'arming', 'cancelled', 'info'):
            return False
        if self.phase in ('error', 'action'):
            return True
        if self.mode in ('command', 'tools') and self.phase in ('recording', 'processing', 'connecting'):
            return True
        return bool(self.partial) and self.phase in ('recording', 'processing', 'connecting')

    def set_mode(self, mode):
        self.mode = mode if mode in ('dictation', 'command', 'tools') else 'dictation'
        self._update_spring_targets()
        self.canvas.queue_draw()

    def set_context_label(self, label):
        self.context_label = (label or '').strip()[:24]
        self.canvas.queue_draw()

    def _is_dark_surface(self):
        return self.theme == 'dark' or (self.theme == 'frosted' and self.backdrop_dark)

    def _refresh_colors(self):
        self.colors = self._palettes[1 if self._is_dark_surface() else 0]

    def set_theme(self, theme):
        if theme == 'auto':
            settings = Gtk.Settings.get_default()
            theme = 'dark' if settings and settings.get_property('gtk-application-prefer-dark-theme') else 'light'
        self.theme = theme if theme in ('light', 'dark', 'frosted') else 'light'
        self._refresh_colors()
        self.canvas.queue_draw()

    def _mode_accents(self):
        if self.phase == 'error':
            err = self.colors['status/error']
            return err, err
        if self.phase in ('success', 'action'):
            ok = self.colors['status/success']
            return ok, self.colors['mode/tools-end']
        prefix = 'mode/' + (self.mode if self.mode in ('dictation', 'command', 'tools') else 'dictation')
        return self.colors[prefix + '-start'], self.colors[prefix + '-end']

    def _display_transcript(self):
        if self.phase == 'error':
            return self.message or '连接中断，录音已保留。'
        words = self.partial
        if not words:
            if self.mode == 'tools':
                return '说出你想让 DX Tools 做的事…'
            if self.mode == 'command':
                return '说出你需要的命令操作…'
            return ''
        if self.phase != 'error' and len(words) > 84:
            return words[:160] if self.mode in ('tools', 'action') else '…' + words[-84:]
        return words

    def _measure_lines(self, text, width=412):
        if not text:
            return 1
        layout = PangoCairo.create_layout(self._measure_cr)
        font = Pango.FontDescription()
        font.set_family('Noto Sans SC, Inter')
        font.set_absolute_size(17 * Pango.SCALE)
        layout.set_font_description(font)
        attributes = Pango.AttrList()
        attributes.insert(Pango.attr_line_height_new_absolute(27 * Pango.SCALE))
        layout.set_attributes(attributes)
        layout.set_text(text, -1)
        layout.set_width(int(width * Pango.SCALE))
        layout.set_height(-3)
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        layout.set_ellipsize(Pango.EllipsizeMode.END)
        return max(1, min(3, layout.get_line_count()))

    def _target_geometry(self):
        if self.phase == 'arming':
            return self.ARMING_W, self.ARMING_H, 20.0
        if not self.expanded:
            return self.COMPACT_W, self.COMPACT_H, 30.0
        if self.phase == 'error':
            return self.EXPANDED_W, self.ERROR_H, 22.0
        lines = self._measure_lines(self._display_transcript(), width=self.EXPANDED_W - 40)
        target_h = {1: 136.0, 2: 163.0, 3: 190.0}[lines]
        return self.EXPANDED_W, target_h, 22.0

    def _update_spring_targets(self):
        tw, th, tr = self._target_geometry()
        self.w_spring.target = tw
        self.h_spring.target = th
        self.r_spring.target = tr

    def settle(self):
        """Snap all springs and transition state immediately (used in synchronous snapshot tests)."""
        self._update_spring_targets()
        self.w_spring.snap(self.w_spring.target)
        self.h_spring.snap(self.h_spring.target)
        self.r_spring.snap(self.r_spring.target)
        self.y_spring.snap(0.0)
        if self.phase in ('success', 'action'):
            self.phase_at = time.monotonic() - 1.0

    def _sync_geometry(self, force=False):
        dimensions = (self.WIDTH, self.STAGE_HEIGHT)
        if force or dimensions != self._geometry:
            self._geometry = dimensions
            self.canvas.set_size_request(*dimensions)
            self.window.resize(*dimensions)
            if self.window.get_visible():
                self._position()
        self._update_spring_targets()
        self.canvas.queue_draw()

    def _position(self):
        display = Gdk.Display.get_default()
        _, x, y = display.get_default_seat().get_pointer().get_position()
        area = display.get_monitor_at_point(x, y).get_workarea()
        left = area.x + (area.width - self.WIDTH) // 2
        top = area.y + area.height - self.STAGE_HEIGHT + 6
        backdrop_rect = (left, top, self.WIDTH, self.STAGE_HEIGHT)
        if self.theme == 'frosted' and not self.window.get_visible() and self.backdrop_rect != backdrop_rect:
            self._capture_backdrop(backdrop_rect)
        self.window.move(left, top)
        self._sync_input_shape()

    def _sync_input_shape(self):
        native = self.window.get_window()
        if not native:
            return
        key = tuple(sorted((name, tuple(int(round(v)) for v in rect)) for name, rect in self.hitboxes.items()))
        if key == self._last_hitboxes_key:
            return
        self._last_hitboxes_key = key
        region = cairo.Region()
        for _, (bx, by, bw, bh) in key:
            region.union(cairo.RectangleInt(bx, by, max(1, bw), max(1, bh)))
        native.input_shape_combine_region(region, 0, 0)

    def _ensure_animator(self):
        self._last_tick = time.monotonic()
        if self.frames is None:
            self.frames = GLib.timeout_add(16, self.animate)

    def show_arming(self, progress, mode='dictation', theme=None):
        """Show subtle pre-hold charge pill before long hotkey threshold crosses."""
        if theme is not None:
            self.set_theme(theme)
        self.mode = mode if mode in ('dictation', 'command', 'tools') else 'dictation'
        self.arm_progress = max(0.05, min(1.0, float(progress)))
        was_hidden = self.phase == 'hidden' or not self.window.get_visible()
        self.phase = 'arming'
        self.message = ''
        self._partial = ''
        self.hide_at = 0.0
        self._update_spring_targets()
        if was_hidden:
            self.phase_at = time.monotonic()
            self.w_spring.snap(self.ARMING_W * 0.90)
            self.w_spring.target = self.ARMING_W
            self.h_spring.snap(self.ARMING_H - 6.0)
            self.h_spring.target = self.ARMING_H
            self.r_spring.snap(20.0)
            self.y_spring.snap(12.0)
            self.y_spring.target = 0.0
            self._position()
            self.window.show_all()
            self._position()
        self._ensure_animator()
        self.canvas.queue_draw()

    def dismiss_arming(self):
        """Fade/sink the pre-hold pill smoothly when hold is released before triggering."""
        if self.phase != 'arming':
            return
        now = time.monotonic()
        if not self.hide_at:
            self.hide_at = now + 0.14
            self.y_spring.target = 10.0
        self._ensure_animator()

    def show(self, phase, message='', partial=None):
        now = time.monotonic()
        was_hidden = self.phase == 'hidden' or not self.window.get_visible()
        was_arming = self.phase == 'arming'
        if phase in ('connecting', 'recording') and self.phase not in ('connecting', 'recording'):
            self.started = now
            self.levels = deque([0.0] * 24, maxlen=24)
            self.bars = [0.0] * 24
            self.smooth_level = 0.0
        if phase != self.phase:
            self.phase_at = now
        self.phase, self.message = phase, message
        if partial is not None:
            self._partial = partial
        if phase == 'cancelled':
            self._partial = ''
        self.hide_at = (
            now + (6.0 if phase == 'action' else 5.0 if phase == 'error' else 1.55)
            if phase in ('error', 'success', 'cancelled', 'info', 'action')
            else 0.0
        )
        self._update_spring_targets()
        tw, th, tr = self.w_spring.target, self.h_spring.target, self.r_spring.target
        if was_hidden and not was_arming:
            self.w_spring.snap(tw * 0.90)
            self.w_spring.target = tw
            self.h_spring.snap(max(36.0, th - 8.0))
            self.h_spring.target = th
            self.r_spring.snap(tr)
            self.y_spring.snap(12.0)
            self.y_spring.target = 0.0
        else:
            self.y_spring.target = 0.0
        self._sync_geometry()
        self._position()
        self.window.show_all()
        self._position()
        self._ensure_animator()

    def animate(self):
        if self.phase == 'hidden':
            self.frames = None
            return False
        now = time.monotonic()
        dt = min(0.032, max(0.001, now - self._last_tick))
        self._last_tick = now

        if self.hide_at:
            remaining = self.hide_at - now
            if remaining <= 0.0:
                self.window.hide()
                self.phase = 'hidden'
                self.backdrop = None
                self._backdrop_bytes = None
                self.backdrop_rect = None
                self.hitboxes = {}
                self._last_hitboxes_key = None
                self.frames = None
                return False
            if remaining < 0.20:
                self.y_spring.target = 10.0

        self._update_spring_targets()
        self.w_spring.step(dt)
        self.h_spring.step(dt)
        self.r_spring.step(dt)
        self.y_spring.step(dt)

        if self.phase == 'recording':
            target = min(1.0, max(0.0, self.level))
            rate = 0.50 if target > self.smooth_level else 0.16
            self.smooth_level += (target - self.smooth_level) * rate
            self.levels.append(self.smooth_level)
            self.level *= 0.85
            amp = self.smooth_level ** 0.58
            for i in range(24):
                env = math.sin(math.pi * (i + 0.5) / 24.0) ** 0.72
                ripple = 0.58 + 0.27 * math.sin(now * 9.8 - i * 0.54) + 0.15 * math.cos(now * 5.9 + i * 0.88)
                idle_breath = 0.055 * (0.5 + 0.5 * math.sin(now * 3.1 - i * 0.34))
                bar_target = min(1.0, idle_breath + amp * env * ripple * 1.22)
                self.bars[i] += (bar_target - self.bars[i]) * 0.44

        self.canvas.queue_draw()
        return True

    def text(self, cr, words, x, y, size=14, line=22, role='text/primary', width=None,
             lines=1, latin=False, medium=False, bold=False, align=Pango.Alignment.LEFT,
             color_rgb=None, alpha=1.0, return_layout=False):
        layout = PangoCairo.create_layout(cr)
        font = Pango.FontDescription()
        font.set_family('Inter, Noto Sans SC' if latin else 'Noto Sans SC, Inter')
        font.set_absolute_size(size * Pango.SCALE)
        weight = Pango.Weight.SEMIBOLD if bold else Pango.Weight.MEDIUM if medium else Pango.Weight.NORMAL
        font.set_weight(weight)
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
        rgb = color_rgb if color_rgb is not None else self.colors[role]
        cr.set_source_rgba(rgb[0], rgb[1], rgb[2], alpha)
        cr.move_to(x, y)
        PangoCairo.show_layout(cr, layout)
        if return_layout:
            return layout.get_pixel_size(), layout
        return layout.get_pixel_size()

    def asset(self, cr, name, x, y):
        variant = 'dark' if self._is_dark_surface() else 'light'
        handle, width, height = self.icons[name, variant]
        cr.save()
        cr.translate(x, y)
        viewport = Rsvg.Rectangle()
        viewport.x = viewport.y = 0
        viewport.width, viewport.height = width, height
        handle.render_document(cr, viewport)
        cr.restore()

    def _draw_capsule_shadow(self, cr, x, y, width, height, radius):
        dark = self._is_dark_surface()
        base_alpha = 0.060 if dark else 0.036
        for dy, expand, mult in ((2, 1.5, 1.0), (4, 3.5, 0.82), (7, 6.5, 0.56), (10, 10.0, 0.34), (13, 14.0, 0.16)):
            rounded(cr, x - expand, y + dy - expand * 0.45, width + expand * 2, height + expand * 2, radius + expand * 0.7)
            cr.set_source_rgba(5 / 255, 9 / 255, 18 / 255, base_alpha * mult)
            cr.fill()

    def panel(self, cr, x, y, width, height, radius):
        """Render the 5-layer optical Carbon Fluid Glass capsule surface."""
        # Layer 1: zero-allocation multi-layer ambient + umbra shadow.
        self._draw_capsule_shadow(cr, x, y, width, height, radius)

        start_c, end_c = self._mode_accents()
        dark = self._is_dark_surface()
        cr.save()
        rounded(cr, x + 0.5, y + 0.5, width - 1.0, height - 1.0, radius)
        cr.clip_preserve()

        # Layer 2: base obsidian/pearl fill or refractive blurred backdrop.
        if self.theme == 'frosted':
            if self.backdrop:
                cr.set_source_surface(self.backdrop, 0, 0)
                cr.paint_with_alpha(0.82)
            if self.backdrop_dark:
                cr.set_source_rgba(13 / 255, 18 / 255, 28 / 255, 0.62 if self.backdrop else 0.88)
            else:
                cr.set_source_rgba(248 / 255, 250 / 255, 252 / 255, 0.68 if self.backdrop else 0.90)
            cr.paint()
        else:
            cr.set_source_rgb(*self.colors['surface/panel'])
            cr.paint()

        # Layer 3: localized ambient voice aura near the left status badge (kept clear of center).
        if self.phase in ('arming', 'connecting', 'recording', 'processing', 'error', 'success', 'action'):
            glow_alpha = (
                (0.12 + 0.10 * self.smooth_level) if dark else (0.07 + 0.06 * self.smooth_level)
            )
            glow = cairo.RadialGradient(x + 48.0, y + 26.0, 2.0, x + 48.0, y + 26.0, 148.0)
            glow.add_color_stop_rgba(0.0, *start_c, glow_alpha)
            glow.add_color_stop_rgba(0.65, *end_c, glow_alpha * 0.28)
            glow.add_color_stop_rgba(1.0, *end_c, 0.0)
            cr.set_source(glow)
            cr.paint()

        cr.restore()

        # Layer 4: specular bevel rim (subtle inner top highlight on light, beveled sheen on dark).
        rounded(cr, x + 0.5, y + 0.5, width - 1.0, height - 1.0, radius)
        rim = cairo.LinearGradient(x, y, x, y + height)
        if self.theme == 'frosted':
            if dark:
                rim.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.28)
                rim.add_color_stop_rgba(0.4, 1.0, 1.0, 1.0, 0.12)
                rim.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, 0.06)
            else:
                rim.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.88)
                rim.add_color_stop_rgba(1.0, 15 / 255, 23 / 255, 42 / 255, 0.12)
        elif dark:
            rim.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.22)
            rim.add_color_stop_rgba(0.5, *self.colors['border/default'], 0.90)
            rim.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, 0.07)
        else:
            rim.add_color_stop_rgba(0.0, 15 / 255, 23 / 255, 42 / 255, 0.10)
            rim.add_color_stop_rgba(1.0, 15 / 255, 23 / 255, 42 / 255, 0.16)
        cr.set_source(rim)
        cr.set_line_width(1.0)
        cr.stroke()

        # Crisp 1px top inner specular highlight on light mode.
        if not dark and self.theme != 'frosted':
            rounded(cr, x + 1.5, y + 1.5, width - 3.0, height - 3.0, max(2.0, radius - 1.0))
            inner = cairo.LinearGradient(x, y, x, y + 18.0)
            inner.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.85)
            inner.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, 0.0)
            cr.set_source(inner)
            cr.set_line_width(1.0)
            cr.stroke()

        # Layer 5: processing perimeter light beam sweeping smoothly around the capsule.
        if self.phase == 'processing':
            angle = time.monotonic() * 3.2
            cx, cy = x + width / 2.0, y + height / 2.0
            rx, ry = width * 0.65, height * 0.9
            dx, dy = math.cos(angle) * rx, math.sin(angle) * ry
            beam = cairo.LinearGradient(cx - dx, cy - dy, cx + dx, cy + dy)
            beam.add_color_stop_rgba(0.0, *start_c, 0.02)
            beam.add_color_stop_rgba(0.48, *start_c, 0.08)
            beam.add_color_stop_rgba(0.75, *end_c, 0.72)
            beam.add_color_stop_rgba(0.92, *start_c, 0.92)
            beam.add_color_stop_rgba(1.0, *start_c, 0.06)
            rounded(cr, x + 0.75, y + 0.75, width - 1.5, height - 1.5, max(2.0, radius - 0.5))
            cr.set_source(beam)
            cr.set_line_width(1.6)
            cr.stroke()

    def _capture_backdrop(self, rectangle):
        self.backdrop_rect = rectangle
        try:
            from .modules.screen import region_image
            x, y, width, height = rectangle
            raw = region_image({'left': x, 'top': y, 'width': width, 'height': height})
            small = raw.resize((max(1, width // 4), max(1, height // 4)), Image.Resampling.BILINEAR)
            small = ImageEnhance.Color(small).enhance(1.35)
            luma_pixels = small.convert('L').tobytes()
            self.backdrop_dark = (sum(luma_pixels) / max(1, len(luma_pixels))) < 118
            blurred = small.filter(ImageFilter.GaussianBlur(4.5)).resize((width, height), Image.Resampling.BILINEAR)
            r, g, b = blurred.convert('RGB').split()
            alpha = Image.new('L', (width, height), 255)
            self._backdrop_bytes = bytearray(Image.merge('RGBA', (b, g, r, alpha)).tobytes())
            self.backdrop = cairo.ImageSurface.create_for_data(
                self._backdrop_bytes, cairo.FORMAT_ARGB32, width, height, width * 4
            )
            self._refresh_colors()
        except Exception:
            self.backdrop = None
            self._backdrop_bytes = None
            self.backdrop_dark = False
            self._refresh_colors()

    def _keycap_width(self):
        return 64.0 if self.mode in ('command', 'tools') else 42.0

    def keycap(self, cr, right_x, y, held, height=26.0):
        label = 'Alt+Win' if self.mode == 'tools' else 'Ctrl+Win' if self.mode == 'command' else 'Ctrl'
        width = self._keycap_width()
        draw_x = right_x - width
        start_c, _ = self._mode_accents()
        dark = self._is_dark_surface()
        draw_y = y + (1.5 if held else 0.0)
        cap_h = height - (1.5 if held else 2.0)

        if not held:
            # Physical 2px lower keycap skirt.
            rounded(cr, draw_x + 0.5, draw_y + 2.5, width - 1.0, cap_h, 7.0)
            cr.set_source_rgba(*self.colors['border/default'], 0.9 if dark else 0.8)
            cr.fill()

        rounded(cr, draw_x + 0.5, draw_y + 0.5, width - 1.0, cap_h, 7.0)
        if held:
            base = self.colors['surface/panel']
            tinted = tuple(base[k] * 0.84 + start_c[k] * 0.16 for k in range(3))
            cr.set_source_rgba(*tinted, 0.96)
            cr.fill_preserve()
            cr.set_source_rgba(*start_c, 0.85)
        else:
            cr.set_source_rgb(*self.colors['surface/raised'])
            cr.fill_preserve()
            cr.set_source_rgb(*self.colors['border/default'])
        cr.set_line_width(1.0)
        cr.stroke()

        text_c = start_c if held else self.colors['text/secondary']
        self.text(
            cr, label, draw_x, draw_y + (cap_h - 15.0) / 2.0,
            11, 15, width=width, latin=True, medium=True,
            align=Pango.Alignment.CENTER, color_rgb=text_c,
        )
        return width

    def waveform(self, cr, x, y, count=24, pitch=6.5, max_h=28.0, busy=False):
        now = time.monotonic()
        start_c, end_c = self._mode_accents()
        for i in range(count):
            t = i / max(1.0, float(count - 1))
            c = tuple(start_c[k] * (1.0 - t) + end_c[k] * t for k in range(3))
            if busy:
                travel = 0.5 + 0.5 * math.sin(now * 6.8 - i * 0.42)
                mod = 0.7 + 0.3 * math.cos(now * 2.5 + i * 0.18)
                h = 4.0 + (max_h * 0.52) * travel * mod
                alpha = 0.28 + 0.68 * travel
            else:
                idx = min(len(self.bars) - 1, int(round(i * (len(self.bars) - 1) / max(1, count - 1))))
                val = min(1.0, max(0.0, max(self.bars[idx], self.levels[idx])))
                h = 4.0 + (max_h - 4.0) * val
                alpha = 0.82 + 0.18 * val
            bx = x + i * pitch
            by = y + (max_h - h) / 2.0
            if not busy and h > 11.0:
                rounded(cr, bx - 1.0, by - 1.5, 5.0, h + 3.0, 2.5)
                cr.set_source_rgba(*c, 0.16)
                cr.fill()
            rounded(cr, bx, by, 3.0, h, 1.5)
            cr.set_source_rgba(*c, alpha)
            cr.fill()

    def _draw_cancel_button(self, cr, x, y, size=34.0):
        hovered = self.hover == 'cancel'
        rounded(cr, x, y, size, size, size / 2.0)
        if hovered:
            cr.set_source_rgba(*self.colors['surface/raised'], 0.95)
            cr.fill_preserve()
            cr.set_source_rgba(*self.colors['border/default'], 0.9)
            cr.set_line_width(1.0)
            cr.stroke()
        else:
            cr.set_source_rgba(*self.colors['surface/raised'], 0.55)
            cr.fill()
        cx, cy = x + size / 2.0, y + size / 2.0
        cr.set_source_rgba(*self.colors['text/secondary'], 0.95 if hovered else 0.78)
        cr.set_line_width(1.7)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        r = 4.5
        cr.move_to(cx - r, cy - r)
        cr.line_to(cx + r, cy + r)
        cr.move_to(cx + r, cy - r)
        cr.line_to(cx - r, cy + r)
        cr.stroke()
        self.hitboxes['cancel'] = (x, y, size, size)

    def _draw_mic_badge(self, cr, cx, cy, pulse=False):
        start_c, _ = self._mode_accents()
        if pulse:
            p = 0.5 + 0.5 * math.sin(time.monotonic() * 4.8)
            cr.set_source_rgba(*start_c, 0.12 + 0.12 * p)
            cr.arc(cx, cy, 13.0 + 3.0 * p, 0, math.pi * 2)
            cr.fill()
        cr.set_source_rgba(*start_c, 0.14)
        cr.arc(cx, cy, 13.0, 0, math.pi * 2)
        cr.fill()
        self.asset(cr, 'mic', cx - 10.0, cy - 10.0)

    def _draw_animated_check(self, cr, cx, cy):
        ok = self.colors['status/success']
        t = min(1.0, max(0.0, (time.monotonic() - self.phase_at) / 0.22))
        cr.set_source_rgba(*ok, 0.16)
        cr.arc(cx, cy, 14.0, 0, math.pi * 2)
        cr.fill()
        cr.set_source_rgba(*ok, 0.45)
        cr.set_line_width(1.2)
        cr.arc(cx, cy, 13.5, 0, math.pi * 2)
        cr.stroke()

        p0 = (cx - 5.5, cy + 0.5)
        p1 = (cx - 1.5, cy + 4.5)
        p2 = (cx + 6.0, cy - 4.0)
        cr.set_source_rgb(*ok)
        cr.set_line_width(2.2)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.move_to(*p0)
        if t <= 0.45:
            k = t / 0.45
            cr.line_to(p0[0] + (p1[0] - p0[0]) * k, p0[1] + (p1[1] - p0[1]) * k)
        else:
            k = (t - 0.45) / 0.55
            cr.line_to(*p1)
            cr.line_to(p1[0] + (p2[0] - p1[0]) * k, p1[1] + (p2[1] - p1[1]) * k)
        cr.stroke()

    def _draw_arming(self, cr, x, y, width, height):
        start_c, end_c = self._mode_accents()
        pulse = 0.5 + 0.5 * math.sin(time.monotonic() * 6.0)
        dot_x, dot_y = x + 17.0, y + height / 2.0
        cr.set_source_rgba(*start_c, 0.24 + 0.20 * pulse)
        cr.arc(dot_x, dot_y, 6.0 + 2.0 * pulse, 0, math.pi * 2)
        cr.fill()
        cr.set_source_rgb(*start_c)
        cr.arc(dot_x, dot_y, 3.2, 0, math.pi * 2)
        cr.fill()

        label = '工具动作' if self.mode == 'tools' else '命令模式' if self.mode == 'command' else '继续按住'
        self.text(cr, label, x + 30.0, y + 7.5, 12, 16, 'text/primary', 90, medium=True)

        # Progress bar below label.
        bar_x, bar_y, bar_w, bar_h = x + 30.0, y + 27.5, width - 92.0, 3.5
        rounded(cr, bar_x, bar_y, bar_w, bar_h, 1.75)
        cr.set_source_rgba(*self.colors['border/default'], 0.75)
        cr.fill()
        fill_w = max(4.0, bar_w * self.arm_progress)
        rounded(cr, bar_x, bar_y, fill_w, bar_h, 1.75)
        grad = cairo.LinearGradient(bar_x, bar_y, bar_x + fill_w, bar_y)
        grad.add_color_stop_rgb(0.0, *start_c)
        grad.add_color_stop_rgb(1.0, *end_c)
        cr.set_source(grad)
        cr.fill()

        self.keycap(cr, x + width - 10.0, y + 8.0, True, height=24.0)

    def _draw_compact(self, cr, x, y, width, height):
        cy = y + height / 2.0
        right_edge = x + width - 16.0
        if self.phase == 'recording':
            self._draw_cancel_button(cr, x + 13.0, cy - 17.0, 34.0)
            kc_w = self._keycap_width()
            self.keycap(cr, right_edge, cy - 13.0, True, height=26.0)
            seconds = max(0, int(time.monotonic() - self.started))
            timer_x = right_edge - kc_w - 42.0
            self.text(cr, f'{seconds // 60}:{seconds % 60:02d}', timer_x, cy - 8.0,
                      11, 16, 'text/secondary', 34.0, latin=True, medium=True, align=Pango.Alignment.RIGHT)
            wave_x = x + 62.0
            wave_avail = max(80.0, timer_x - 10.0 - wave_x)
            pitch = wave_avail / 24.0
            self.waveform(cr, wave_x + 1.0, cy - 14.0, count=24, pitch=pitch, max_h=28.0, busy=False)
        elif self.phase == 'processing':
            self._draw_mic_badge(cr, x + 29.0, cy, pulse=True)
            label = '调用工具' if self.mode == 'tools' else '生成命令' if self.mode == 'command' else '即将输入'
            self.text(cr, label, right_edge - 70.0, cy - 9.0, 12, 18, 'text/secondary', 70.0, medium=True, align=Pango.Alignment.RIGHT)
            self.waveform(cr, x + 56.0, cy - 14.0, count=22, pitch=7.4, max_h=28.0, busy=True)
        elif self.phase in ('success', 'action'):
            self._draw_animated_check(cr, x + 29.0, cy)
            copied = '已复制' in self.message
            msg = 'DX Tools 完成' if self.mode == 'tools' else '命令已复制' if copied and self.mode == 'command' else '已复制到剪贴板' if copied else '已输入到当前窗口'
            self.text(cr, msg, x + 54.0, cy - 10.0, 14, 20, 'text/primary', width - 130.0, medium=True)
            self.text(cr, '完成', right_edge - 46.0, cy - 9.0, 12, 18, 'status/success', 46.0, medium=True, align=Pango.Alignment.RIGHT)
        else:
            self._draw_mic_badge(cr, x + 29.0, cy, pulse=(self.phase == 'connecting'))
            words = self.message if self.phase == 'info' else '已取消' if self.phase == 'cancelled' else '正在连接…' if self.phase == 'connecting' else '长按 Ctrl 开始说话'
            self.keycap(cr, right_edge, cy - 13.0, False, height=26.0)
            self.text(cr, words, x + 54.0, cy - 10.0, 14, 20, 'text/secondary', width - 130.0)

    def _draw_context_chip(self, cr, x, y, max_w):
        if not self.context_label or max_w < 54.0:
            return 0.0
        start_c, _ = self._mode_accents()
        label = '⌖ ' + self.context_label
        layout = PangoCairo.create_layout(cr)
        font = Pango.FontDescription()
        font.set_family('Inter, Noto Sans SC')
        font.set_absolute_size(11 * Pango.SCALE)
        font.set_weight(Pango.Weight.MEDIUM)
        layout.set_font_description(font)
        layout.set_text(label, -1)
        tw, _ = layout.get_pixel_size()
        pill_w = min(max_w, float(tw) + 16.0)
        rounded(cr, x, y, pill_w, 20.0, 10.0)
        cr.set_source_rgba(*self.colors['surface/raised'], 0.85)
        cr.fill_preserve()
        cr.set_source_rgba(*start_c, 0.30)
        cr.set_line_width(1.0)
        cr.stroke()
        self.text(cr, label, x + 8.0, y + 2.0, 11, 15, 'text/secondary', pill_w - 16.0, latin=True, medium=True)
        return pill_w

    def _draw_expanded(self, cr, x, y, width, height):
        start_c, _ = self._mode_accents()
        now = time.monotonic()

        # Header row: aura dot + mode title + optional context chip + DX VOICE / status caption.
        dot_x, dot_y = x + 23.0, y + 24.0
        if self.phase in ('recording', 'processing', 'connecting'):
            pulse = 0.5 + 0.5 * math.sin(now * 4.5)
            cr.set_source_rgba(*start_c, 0.16 + 0.18 * pulse)
            cr.arc(dot_x, dot_y, 6.0 + 3.0 * pulse, 0, math.pi * 2)
            cr.fill()
        cr.set_source_rgb(*start_c)
        cr.arc(dot_x, dot_y, 3.2, 0, math.pi * 2)
        cr.fill()

        title = {
            'recording': '正在聆听',
            'processing': '正在完成',
            'success': '输入完成',
            'error': '连接已断开',
            'action': 'DX Tools 已返回',
        }.get(self.phase, '正在连接')
        if self.phase == 'success' and '已复制' in self.message:
            title = '已复制，等待粘贴'
        elif self.phase == 'error' and self.mode == 'command':
            title = '命令未生成'
        elif self.mode == 'command' and self.phase in ('recording', 'processing', 'connecting'):
            title = '生成命令' if self.phase == 'processing' else '命令模式'
        elif self.mode == 'tools' and self.phase in ('recording', 'processing', 'connecting'):
            title = '调用工具' if self.phase == 'processing' else '工具模式'

        title_size = self.text(cr, title, x + 35.0, y + 15.5, 12, 18, 'text/secondary', 140.0, medium=True)
        chip_x = x + 35.0 + title_size[0] + 8.0
        right_tag_w = 72.0
        if self.phase in ('recording', 'processing', 'connecting', 'action'):
            self._draw_context_chip(cr, chip_x, y + 14.0, (x + width - 20.0 - right_tag_w) - chip_x)

        caption = 'ERROR' if self.phase == 'error' else 'DX VOICE'
        self.text(cr, caption, x + width - 20.0 - 70.0, y + 16.0, 11, 16, 'text/muted', 70.0, latin=True, align=Pango.Alignment.RIGHT)

        # Transcript body + live streaming caret.
        words = self._display_transcript()
        body_x, body_y, body_w = x + 20.0, y + 45.0, width - 40.0
        _, layout = self.text(cr, words, body_x, body_y, 17, 27, 'text/primary', body_w, lines=3, return_layout=True)
        if self.phase in ('recording', 'connecting') and self.partial and words:
            pos = layout.index_to_pos(len(words.encode('utf-8')))
            caret_x = min(body_x + body_w - 3.0, body_x + pos.x / Pango.SCALE + 3.0)
            caret_y = body_y + pos.y / Pango.SCALE + 4.0
            caret_h = max(14.0, min(19.0, pos.height / Pango.SCALE - 7.0))
            blink = 0.42 + 0.58 * (0.5 + 0.5 * math.sin(now * 6.0))
            rounded(cr, caret_x, caret_y, 2.5, caret_h, 1.25)
            cr.set_source_rgba(*start_c, blink)
            cr.fill()

        # Hairline divider + Integrated Bottom Dock.
        dock_top = y + height - self.DOCK_H
        cr.set_source_rgba(*self.colors['border/default'], 0.65)
        cr.set_line_width(1.0)
        cr.move_to(x + 16.0, dock_top + 0.5)
        cr.line_to(x + width - 16.0, dock_top + 0.5)
        cr.stroke()

        dock_cy = dock_top + self.DOCK_H / 2.0
        if self.phase == 'error':
            self.text(cr, '录音保留在本地，可一键重试', x + 20.0, dock_cy - 8.0, 11, 16, 'text/secondary', 210.0)
            # Action pills: Retry & Close.
            retry_rect = (x + width - 144.0, dock_cy - 14.0, 68.0, 28.0)
            close_rect = (x + width - 68.0, dock_cy - 14.0, 50.0, 28.0)
            rx, ry, rw, rh = retry_rect
            rounded(cr, rx, ry, rw, rh, 14.0)
            cr.set_source_rgba(*self.colors['accent/default'], 0.18 if self.hover in ('retry', 'retry-card') else 0.12)
            cr.fill_preserve()
            cr.set_source_rgba(*self.colors['accent/default'], 0.65)
            cr.set_line_width(1.0)
            cr.stroke()
            self.text(cr, '重试', rx, ry + 5.0, 12, 18, width=rw, medium=True, align=Pango.Alignment.CENTER, color_rgb=self.colors['accent/default'])
            self.hitboxes['retry-card'] = retry_rect
            self.hitboxes['retry'] = retry_rect

            cx, cy, cw, ch = close_rect
            rounded(cr, cx, cy, cw, ch, 14.0)
            cr.set_source_rgba(*self.colors['surface/raised'], 0.9 if self.hover == 'cancel' else 0.6)
            cr.fill()
            self.text(cr, '关闭', cx, cy + 5.0, 12, 18, 'text/secondary', cw, medium=True, align=Pango.Alignment.CENTER)
            self.hitboxes['cancel'] = close_rect
            return

        if self.phase in ('recording', 'connecting', 'processing'):
            self._draw_cancel_button(cr, x + 16.0, dock_cy - 14.0, 28.0)
            wave_x = x + 54.0
            self.waveform(cr, wave_x, dock_cy - 10.0, count=18, pitch=6.0, max_h=20.0, busy=(self.phase != 'recording'))
            kc_w = self._keycap_width()
            right_edge = x + width - 16.0
            self.keycap(cr, right_edge, dock_cy - 13.0, self.phase == 'recording', height=26.0)
            seconds = max(0, int(now - self.started))
            timer_str = f'{seconds // 60}:{seconds % 60:02d}' if self.phase == 'recording' else '处理中'
            timer_x = right_edge - kc_w - 50.0
            self.text(
                cr, timer_str, timer_x, dock_cy - 8.0,
                11, 16, 'text/secondary', 44.0, latin=True, medium=True, align=Pango.Alignment.RIGHT,
            )
            action_hint = (
                '松开生成命令' if self.mode == 'command'
                else '松开调用工具' if self.mode == 'tools'
                else '松开即输入'
            ) if self.phase == 'recording' else '请稍候…'
            hint_x = wave_x + 18 * 6.0 + 10.0
            hint_w = timer_x - 8.0 - hint_x
            if hint_w >= 48.0:
                self.text(cr, action_hint, hint_x, dock_cy - 8.0, 11, 16, 'text/muted', hint_w)
        else:
            hint = '已复制，请在目标位置粘贴' if '已复制' in self.message else '完整记录保存在 dx v 历史'
            if '保留原文' in self.message:
                hint = '整理未采用，已保留原文'
            if '截图不可用' in self.message:
                hint = '截图不可用，已按纯文本处理'
            self.text(cr, hint, x + 20.0, dock_cy - 8.0, 11, 16, 'text/secondary', width - 110.0)
            self.keycap(cr, x + width - 16.0, dock_cy - 13.0, False, height=26.0)

    def draw(self, _, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        self.hitboxes = {}

        fade = 1.0
        if self.hide_at:
            remaining = self.hide_at - time.monotonic()
            if 0.0 <= remaining < 0.20:
                fade = max(0.0, remaining / 0.20)

        if fade < 1.0:
            cr.push_group()

        cap_w = max(140.0, self.w_spring.value)
        cap_h = max(36.0, self.h_spring.value)
        cap_r = min(self.r_spring.value, cap_w / 2.0, cap_h / 2.0)
        cap_x = (self.WIDTH - cap_w) / 2.0
        cap_y = (self.STAGE_HEIGHT - self.MARGIN - cap_h) + self.y_spring.value

        self.panel(cr, cap_x, cap_y, cap_w, cap_h, cap_r)

        cr.save()
        rounded(cr, cap_x + 1.0, cap_y + 1.0, cap_w - 2.0, cap_h - 2.0, max(2.0, cap_r - 1.0))
        cr.clip()
        if self.phase == 'arming' and cap_h < 50.0:
            self._draw_arming(cr, cap_x, cap_y, cap_w, cap_h)
        elif cap_h >= 96.0 or self.expanded:
            if cap_h < 105.0 and not self.expanded:
                self._draw_compact(cr, cap_x, cap_y, cap_w, cap_h)
            else:
                self._draw_expanded(cr, cap_x, cap_y, cap_w, cap_h)
        else:
            self._draw_compact(cr, cap_x, cap_y, cap_w, cap_h)
        cr.restore()

        if fade < 1.0:
            cr.pop_group_to_source()
            cr.paint_with_alpha(fade)

        self._sync_input_shape()
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
        self.backdrop = None
        self._backdrop_bytes = None
        self.backdrop_rect = None
        self._last_hitboxes_key = None
