"""DX Voice v0.7 Pure Monolith HUD — Zero-Chrome Obsidian/Porcelain capsule with 1.5px chamfered conic rim."""
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

    def __init__(self, value=0.0, stiffness=310.0, damping=27.0):
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
    """Zero-Chrome Pure Monolith voice capsule on a fixed-size click-through X11 stage."""

    WIDTH = 520
    STAGE_HEIGHT = 320
    MARGIN = 34
    HEIGHT = STAGE_HEIGHT

    # v0.7 Pure Monolith proportions (68% smaller compact footprint, zero header/footer chrome)
    ARMING_W = 128.0
    ARMING_H = 30.0
    COMPACT_W = 168.0
    COMPACT_H = 38.0
    DONE_W = 118.0
    DONE_H = 34.0
    INFO_W = 204.0
    EXPANDED_W = 392.0
    ERROR_W = 376.0
    ERROR_H = 52.0

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

        self.levels = deque([0.0] * 15, maxlen=15)
        self.bars = [0.0] * 15
        self.smooth_level = 0.0
        self.level = 0.0
        self.ring_angle = 0.52
        self.wave_phase = 0.0
        self.started = 0.0
        self.phase_at = 0.0
        self.hide_at = 0.0
        self._last_tick = time.monotonic()
        self._conic_cache = {}

        self.w_spring = Spring(self.COMPACT_W, stiffness=310.0, damping=27.0)
        self.h_spring = Spring(self.COMPACT_H, stiffness=300.0, damping=26.0)
        self.r_spring = Spring(19.0, stiffness=290.0, damping=26.0)
        self.y_spring = Spring(0.0, stiffness=330.0, damping=25.0)

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
        if self.phase in ('hidden', 'arming', 'cancelled', 'info', 'success'):
            return False
        if self.phase in ('error', 'action'):
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
        dark = self._is_dark_surface()
        if self.phase == 'error':
            err = self.colors['status/error']
            return err, err
        if self.phase in ('success', 'action'):
            ok = self.colors['status/success']
            return ok, ok
        if self.mode == 'command':
            return (color('#FDE68A') if dark else color('#D97706')), (color('#F59E0B') if dark else color('#EA580C'))
        if self.mode == 'tools':
            return (color('#A7F3D0') if dark else color('#059669')), (color('#34D399') if dark else color('#0D9488'))
        return (color('#BAE6FD') if dark else color('#0284C7')), (color('#7DD3FC') if dark else color('#4F46E5'))

    def _display_transcript(self):
        if self.phase == 'error':
            return self.message or '连接暂时中断 · 录音已保留'
        words = self.partial
        if not words:
            return ''
        if len(words) > 90:
            return words[:160] if self.mode in ('tools', 'action') else '…' + words[-90:]
        return words

    def _measure_lines(self, text, width=320):
        if not text:
            return 1
        layout = PangoCairo.create_layout(self._measure_cr)
        font = Pango.FontDescription()
        font.set_family('Noto Sans SC, Inter')
        font.set_absolute_size(15 * Pango.SCALE)
        layout.set_font_description(font)
        attributes = Pango.AttrList()
        attributes.insert(Pango.attr_line_height_new_absolute(24 * Pango.SCALE))
        layout.set_attributes(attributes)
        layout.set_text(text, -1)
        layout.set_width(int(width * Pango.SCALE))
        layout.set_height(-3)
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        layout.set_ellipsize(Pango.EllipsizeMode.END)
        return max(1, min(3, layout.get_line_count()))

    def _target_geometry(self):
        if self.phase == 'arming':
            return self.ARMING_W, self.ARMING_H, 15.0
        if self.phase in ('success', 'cancelled'):
            return self.DONE_W, self.DONE_H, 17.0
        if self.phase == 'info':
            return self.INFO_W, self.COMPACT_H, 19.0
        if not self.expanded:
            return self.COMPACT_W, self.COMPACT_H, 19.0
        if self.phase == 'error':
            return self.ERROR_W, self.ERROR_H, 20.0
        lines = self._measure_lines(self._display_transcript(), width=self.EXPANDED_W - 72.0)
        target_h = {1: 54.0, 2: 78.0, 3: 102.0}[lines]
        return self.EXPANDED_W, target_h, 20.0

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
        """Show whisper-thin pre-hold charge capsule before threshold crosses."""
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
            self.w_spring.snap(self.ARMING_W * 0.88)
            self.w_spring.target = self.ARMING_W
            self.h_spring.snap(self.ARMING_H - 4.0)
            self.h_spring.target = self.ARMING_H
            self.r_spring.snap(15.0)
            self.y_spring.snap(10.0)
            self.y_spring.target = 0.0
            self._position()
            self.window.show_all()
            self._position()
        self._ensure_animator()
        self.canvas.queue_draw()

    def dismiss_arming(self):
        """Fade/sink the pre-hold capsule smoothly when hold is released early."""
        if self.phase != 'arming':
            return
        now = time.monotonic()
        if not self.hide_at:
            self.hide_at = now + 0.12
            self.y_spring.target = 8.0
        self._ensure_animator()

    def show(self, phase, message='', partial=None):
        now = time.monotonic()
        was_hidden = self.phase == 'hidden' or not self.window.get_visible()
        was_arming = self.phase == 'arming'
        if phase in ('connecting', 'recording') and self.phase not in ('connecting', 'recording'):
            self.started = now
            self.levels = deque([0.0] * 15, maxlen=15)
            self.bars = [0.0] * 15
            self.smooth_level = 0.0
        if phase != self.phase:
            self.phase_at = now
        self.phase, self.message = phase, message
        if partial is not None:
            self._partial = partial
        if phase == 'cancelled':
            self._partial = ''
        self.hide_at = (
            now + (4.5 if phase == 'action' else 4.8 if phase == 'error' else 0.95)
            if phase in ('error', 'success', 'cancelled', 'info', 'action')
            else 0.0
        )
        self._update_spring_targets()
        tw, th, tr = self.w_spring.target, self.h_spring.target, self.r_spring.target
        if was_hidden and not was_arming:
            self.w_spring.snap(tw * 0.88)
            self.w_spring.target = tw
            self.h_spring.snap(max(28.0, th - 6.0))
            self.h_spring.target = th
            self.r_spring.snap(tr)
            self.y_spring.snap(10.0)
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
            if remaining < 0.18:
                self.y_spring.target = 8.0

        self._update_spring_targets()
        self.w_spring.step(dt)
        self.h_spring.step(dt)
        self.r_spring.step(dt)
        self.y_spring.step(dt)

        if self.phase == 'recording':
            target = min(1.0, max(0.0, self.level))
            rate = 0.52 if target > self.smooth_level else 0.16
            self.smooth_level += (target - self.smooth_level) * rate
            self.levels.append(self.smooth_level)
            self.level *= 0.85
            amp = self.smooth_level ** 0.58
            for i in range(15):
                env = math.sin(math.pi * (i + 0.5) / 15.0) ** 0.85
                ripple = 0.56 + 0.28 * math.sin(now * 9.2 - i * 0.62) + 0.16 * math.cos(now * 5.4 + i * 0.92)
                idle_breath = 0.045 * (0.5 + 0.5 * math.sin(now * 2.8 - i * 0.42))
                bar_target = min(1.0, idle_breath + amp * env * ripple * 1.24)
                self.bars[i] += (bar_target - self.bars[i]) * 0.45
        else:
            self.smooth_level *= 0.88

        if self.phase == 'processing':
            omega = 4.2
        elif self.phase == 'connecting':
            omega = 2.6
        elif self.phase == 'recording':
            omega = 1.95 + 1.55 * (self.smooth_level ** 0.65)
        elif self.phase == 'arming':
            omega = 2.4 + 1.2 * self.arm_progress
        else:
            omega = 1.5
        self.ring_angle = (self.ring_angle + omega * dt) % (math.pi * 2.0)
        self.wave_phase = (self.wave_phase + (3.0 + 1.8 * self.smooth_level) * dt) % (math.pi * 2.0)

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
        base_alpha = 0.068 if dark else 0.032
        for dy, expand, mult in ((2, 1.2, 1.0), (5, 3.5, 0.78), (9, 7.0, 0.48), (13, 11.5, 0.22)):
            rounded(cr, x - expand, y + dy - expand * 0.4, width + expand * 2, height + expand * 2, radius + expand * 0.7)
            cr.set_source_rgba(4 / 255, 7 / 255, 14 / 255, base_alpha * mult)
            cr.fill()

    def _orbit_stops(self, dark):
        """Restrained v0.7 metallic chamfered light stops (Platinum-Ice / Champagne / Celadon)."""
        if self.phase in ('success', 'action'):
            return [
                (0.00, *(color('#ECFDF5') if dark else color('#10B981')), 0.94),
                (0.20, *(color('#6EE7B7') if dark else color('#059669')), 0.72),
                (0.48, *(color('#34D399') if dark else color('#0D9488')), 0.16),
                (0.76, *(color('#1F2532') if dark else color('#E4E1DA')), 0.04),
            ]
        if self.mode == 'command':
            return [
                (0.00, *(color('#FEF9C3') if dark else color('#F59E0B')), 0.96),
                (0.16, *(color('#FBBF24') if dark else color('#D97706')), 0.80),
                (0.36, *(color('#EA580C') if dark else color('#B45309')), 0.36),
                (0.64, *(color('#292524') if dark else color('#E7E5E4')), 0.04),
                (0.86, *(color('#FDE68A') if dark else color('#F59E0B')), 0.48),
            ]
        if self.mode == 'tools':
            return [
                (0.00, *(color('#ECFDF5') if dark else color('#10B981')), 0.96),
                (0.16, *(color('#34D399') if dark else color('#059669')), 0.80),
                (0.36, *(color('#14B8A6') if dark else color('#0D9488')), 0.36),
                (0.64, *(color('#1E293B') if dark else color('#E2E8F0')), 0.04),
                (0.86, *(color('#A7F3D0') if dark else color('#10B981')), 0.48),
            ]
        return [
            (0.00, *(color('#F8FAFC') if dark else color('#0284C7')), 0.96),
            (0.15, *(color('#7DD3FC') if dark else color('#0EA5E9')), 0.78),
            (0.35, *(color('#818CF8') if dark else color('#6366F1')), 0.36),
            (0.64, *(color('#1F2532') if dark else color('#E4E1DA')), 0.04),
            (0.86, *(color('#BAE6FD') if dark else color('#38BDF8')), 0.46),
        ]

    @staticmethod
    def _sample_orbit_stop(stops, pos):
        t = pos % 1.0
        n = len(stops)
        for i in range(n):
            t0, r0, g0, b0, a0 = stops[i]
            t1, r1, g1, b1, a1 = stops[(i + 1) % n]
            span_end = t1 if i + 1 < n else 1.0
            if t0 <= t <= span_end:
                span = max(1e-6, span_end - t0)
                u = 0.5 - 0.5 * math.cos(math.pi * ((t - t0) / span))
                return (
                    r0 + (r1 - r0) * u,
                    g0 + (g1 - g0) * u,
                    b0 + (b1 - b0) * u,
                    a0 + (a1 - a0) * u,
                )
        _, r0, g0, b0, a0 = stops[0]
        return r0, g0, b0, a0

    def _conic_pattern(self, dark, alpha_scale):
        bucket = max(0.02, min(1.0, round(alpha_scale * 25.0) / 25.0))
        variant = 'ok' if self.phase in ('success', 'action') else self.mode
        key = (variant, bool(dark), bucket)
        cached = self._conic_cache.get(key)
        if cached is not None:
            return cached
        if len(self._conic_cache) > 72:
            self._conic_cache.clear()
        stops = self._orbit_stops(dark)
        sectors = 28
        r_in, r_out = 0.06, 3.4
        mp = cairo.MeshPattern()
        samples = [self._sample_orbit_stop(stops, i / float(sectors)) for i in range(sectors)]
        for i in range(sectors):
            a0 = (2.0 * math.pi * i) / sectors
            a1 = (2.0 * math.pi * (i + 1)) / sectors
            c0 = samples[i]
            c1 = samples[(i + 1) % sectors]
            ca0, sa0 = math.cos(a0), math.sin(a0)
            ca1, sa1 = math.cos(a1), math.sin(a1)
            mp.begin_patch()
            mp.move_to(ca0 * r_in, sa0 * r_in)
            mp.line_to(ca0 * r_out, sa0 * r_out)
            mp.line_to(ca1 * r_out, sa1 * r_out)
            mp.line_to(ca1 * r_in, sa1 * r_in)
            mp.set_corner_color_rgba(0, c0[0], c0[1], c0[2], c0[3] * bucket)
            mp.set_corner_color_rgba(1, c0[0], c0[1], c0[2], c0[3] * bucket)
            mp.set_corner_color_rgba(2, c1[0], c1[1], c1[2], c1[3] * bucket)
            mp.set_corner_color_rgba(3, c1[0], c1[1], c1[2], c1[3] * bucket)
            mp.end_patch()
        self._conic_cache[key] = mp
        return mp

    def _set_conic_source(self, cr, cx, cy, rx, ry, angle, dark, alpha_scale=1.0):
        pattern = self._conic_pattern(dark, alpha_scale)
        c = math.cos(angle)
        s = -math.sin(angle)
        rx = max(6.0, float(rx))
        ry = max(6.0, float(ry))
        xx, xy = c / rx, -s / ry
        yx, yy = s / rx, c / ry
        pattern.set_matrix(cairo.Matrix(xx, yx, xy, yy, -xx * cx - xy * cy, -yx * cx - yy * cy))
        cr.set_source(pattern)

    def _draw_orbit_ring(self, cr, x, y, width, height, radius, dark):
        """Render v0.7 1.5px chamfered titanium/porcelain rotating light rim + whisper-soft halo."""
        active_input = self.phase in ('arming', 'connecting', 'recording', 'processing')
        celebration = 0.0
        if self.phase in ('success', 'action'):
            elapsed = max(0.0, time.monotonic() - self.phase_at)
            if elapsed < 0.45:
                celebration = 1.0 - (elapsed / 0.45)
        if not active_input and celebration <= 0.0:
            return

        cx, cy = x + width / 2.0, y + height / 2.0
        rx, ry = width * 0.52, height * 0.52
        voice_boost = (
            min(1.0, self.smooth_level ** 0.65)
            if self.phase == 'recording'
            else (0.28 if self.phase == 'processing' else 0.08)
        )
        intensity = (
            (0.50 + 0.50 * self.arm_progress) if self.phase == 'arming'
            else celebration if celebration > 0.0
            else 1.0
        )

        # Pass A: Subtle exterior-only whisper bloom (kept calm & architectural, never neon).
        cr.save()
        cr.set_fill_rule(cairo.FillRule.EVEN_ODD)
        cr.rectangle(0.0, 0.0, float(self.WIDTH), float(self.STAGE_HEIGHT))
        rounded(cr, x + 0.5, y + 0.5, width - 1.0, height - 1.0, radius)
        cr.clip()

        halo_base = (0.24 if dark else 0.16) * intensity
        spread = 1.0 + 0.35 * voice_boost
        for lw, mult in (
            (18.0 * spread, 0.06),
            (11.0 * spread, 0.15),
            (6.0 * spread, 0.32),
            (3.0 * spread, 0.58),
        ):
            self._set_conic_source(cr, cx, cy, rx, ry, self.ring_angle, dark, halo_base * mult)
            rounded(cr, x + 0.4, y + 0.4, width - 0.8, height - 0.8, max(2.0, radius - 0.2))
            cr.set_line_width(lw)
            cr.stroke()
        cr.restore()

        # Pass B: Razor-sharp 1.55px chamfered metallic conic rim.
        rim_alpha = (0.95 if dark else 0.88) * intensity
        self._set_conic_source(cr, cx, cy, rx, ry, self.ring_angle, dark, rim_alpha)
        rounded(cr, x + 0.45, y + 0.45, width - 0.9, height - 0.9, max(2.0, radius - 0.2))
        cr.set_line_width((1.55 if dark else 1.65) + 0.35 * voice_boost)
        cr.stroke()

    def panel(self, cr, x, y, width, height, radius):
        """Render v0.7 Obsidian Matte / Gallery Porcelain monolith surface."""
        self._draw_capsule_shadow(cr, x, y, width, height, radius)

        dark = self._is_dark_surface()
        cr.save()
        rounded(cr, x + 0.5, y + 0.5, width - 1.0, height - 1.0, radius)
        cr.clip()

        if self.theme == 'frosted':
            if self.backdrop:
                cr.set_source_surface(self.backdrop, 0, 0)
                cr.paint_with_alpha(0.84)
            if self.backdrop_dark:
                cr.set_source_rgba(10 / 255, 12 / 255, 16 / 255, 0.72 if self.backdrop else 0.92)
            else:
                cr.set_source_rgba(250 / 255, 249 / 255, 246 / 255, 0.76 if self.backdrop else 0.94)
            cr.paint()
        else:
            cr.set_source_rgb(*self.colors['surface/panel'])
            cr.paint()
        cr.restore()

        # Base 1px hairline border.
        rounded(cr, x + 0.5, y + 0.5, width - 1.0, height - 1.0, radius)
        if self.phase == 'error':
            cr.set_source_rgba(*self.colors['status/error'], 0.55)
        else:
            cr.set_source_rgba(*self.colors['border/default'], 0.88 if dark else 0.92)
        cr.set_line_width(1.0)
        cr.stroke()

        self._draw_orbit_ring(cr, x, y, width, height, radius, dark)

    def _capture_backdrop(self, rectangle):
        self.backdrop_rect = rectangle
        try:
            from .modules.screen import region_image
            x, y, width, height = rectangle
            raw = region_image({'left': x, 'top': y, 'width': width, 'height': height})
            small = raw.resize((max(1, width // 4), max(1, height // 4)), Image.Resampling.BILINEAR)
            small = ImageEnhance.Color(small).enhance(1.20)
            luma_pixels = small.convert('L').tobytes()
            self.backdrop_dark = (sum(luma_pixels) / max(1, len(luma_pixels))) < 118
            blurred = small.filter(ImageFilter.GaussianBlur(5.0)).resize((width, height), Image.Resampling.BILINEAR)
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

    def _draw_filaments(self, cr, center_x, center_y, count=13, pitch=5.8, max_h=20.0, busy=False):
        """Precision 2px monochromatic-platinum acoustic filaments with subtle center peak tint."""
        now = time.monotonic()
        accent_c, _ = self._mode_accents()
        ink_c = self.colors['text/primary']
        total_w = (count - 1) * pitch + 2.0
        start_x = center_x - total_w / 2.0
        mid = (count - 1) / 2.0

        for i in range(count):
            dist = abs(i - mid) / max(1.0, mid)
            tint_mix = max(0.0, 1.0 - dist * 2.1) * 0.72
            c = tuple(ink_c[k] * (1.0 - tint_mix) + accent_c[k] * tint_mix for k in range(3))

            if busy:
                travel = 0.5 + 0.5 * math.sin(now * 6.2 - i * 0.48)
                env = math.sin(math.pi * (i + 0.5) / float(count)) ** 0.75
                h = 3.2 + (max_h - 3.2) * 0.58 * travel * env
                alpha = 0.30 + 0.55 * travel * env
            else:
                idx = min(len(self.bars) - 1, int(round(i * (len(self.bars) - 1) / max(1, count - 1))))
                val = min(1.0, max(0.0, max(self.bars[idx], self.levels[idx])))
                env = math.sin(math.pi * (i + 0.5) / float(count)) ** 0.80
                idle = 0.06 + 0.10 * env * (0.5 + 0.5 * math.sin(self.wave_phase - i * 0.45))
                norm = min(1.0, max(idle, val))
                h = 3.2 + (max_h - 3.2) * norm
                alpha = (0.42 + 0.52 * (1.0 - dist * 0.65)) * (0.72 + 0.28 * norm)

            bx = start_x + i * pitch
            by = center_y - h / 2.0
            rounded(cr, bx, by, 2.0, h, 1.0)
            cr.set_source_rgba(*c, alpha)
            cr.fill()

    def _register_whisper_cancel(self, cr, x, y, width, height):
        """Invisible right-edge cancel zone; reveals a delicate 8px hairline cross only on pointer hover."""
        size = min(28.0, height - 4.0)
        hx = x + width - size - 6.0
        hy = y + (height - size) / 2.0
        self.hitboxes['cancel'] = (hx, hy, size, size)
        if self.hover == 'cancel':
            cx, cy = hx + size / 2.0, hy + size / 2.0
            cr.set_source_rgba(*self.colors['text/secondary'], 0.82)
            cr.set_line_width(1.3)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            r = 3.5
            cr.move_to(cx - r, cy - r)
            cr.line_to(cx + r, cy + r)
            cr.move_to(cx + r, cy - r)
            cr.line_to(cx - r, cy + r)
            cr.stroke()

    def _draw_animated_check(self, cr, cx, cy):
        ok = self.colors['status/success']
        t = min(1.0, max(0.0, (time.monotonic() - self.phase_at) / 0.20))
        p0 = (cx - 4.5, cy + 0.4)
        p1 = (cx - 1.2, cy + 3.8)
        p2 = (cx + 5.0, cy - 3.2)
        cr.set_source_rgb(*ok)
        cr.set_line_width(1.75)
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
        accent_c, _ = self._mode_accents()
        cy = y + height / 2.0
        track_w = width - 36.0
        track_x = x + 18.0
        rounded(cr, track_x, cy - 1.25, track_w, 2.5, 1.25)
        cr.set_source_rgba(*self.colors['border/default'], 0.65)
        cr.fill()
        fill_w = max(4.0, track_w * self.arm_progress)
        rounded(cr, track_x, cy - 1.25, fill_w, 2.5, 1.25)
        cr.set_source_rgba(*accent_c, 0.92)
        cr.fill()

    def _draw_compact(self, cr, x, y, width, height):
        cx = x + width / 2.0
        cy = y + height / 2.0
        if self.phase in ('recording', 'connecting', 'processing'):
            self._draw_filaments(
                cr, cx, cy, count=13, pitch=5.8, max_h=20.0,
                busy=(self.phase != 'recording'),
            )
            self._register_whisper_cancel(cr, x, y, width, height)
        elif self.phase in ('success', 'action'):
            copied = '已复制' in self.message
            msg = '已复制' if copied else '已输入'
            self._draw_animated_check(cr, x + 24.0, cy)
            self.text(cr, msg, x + 36.0, cy - 9.0, 12, 18, 'text/primary', width - 48.0, medium=True)
        elif self.phase == 'cancelled':
            self.text(cr, '已取消', x, cy - 9.0, 12, 18, 'text/secondary', width, align=Pango.Alignment.CENTER)
        else:
            words = self.message or '按住 Ctrl 说话'
            self.text(cr, words, x + 14.0, cy - 9.0, 12, 18, 'text/secondary', width - 28.0, align=Pango.Alignment.CENTER)

    def _draw_expanded(self, cr, x, y, width, height):
        """Frameless Thought Canvas: zero header/footer bars, pure typography + 5 micro-filaments."""
        accent_c, _ = self._mode_accents()
        now = time.monotonic()

        if self.phase == 'error':
            cy = y + height / 2.0
            cr.set_source_rgb(*self.colors['status/error'])
            cr.arc(x + 20.0, cy, 3.0, 0.0, math.pi * 2.0)
            cr.fill()
            words = self._display_transcript()
            self.text(cr, words, x + 32.0, cy - 10.0, 13, 20, 'text/primary', width - 118.0)

            retry_rect = (x + width - 78.0, cy - 12.0, 44.0, 24.0)
            rx, ry, rw, rh = retry_rect
            rounded(cr, rx, ry, rw, rh, 12.0)
            cr.set_source_rgba(*self.colors['surface/raised'], 0.95 if self.hover in ('retry', 'retry-card') else 0.78)
            cr.fill_preserve()
            cr.set_source_rgba(*self.colors['border/default'], 0.90)
            cr.set_line_width(1.0)
            cr.stroke()
            self.text(cr, '重试', rx, ry + 3.0, 11, 18, 'text/primary', rw, medium=True, align=Pango.Alignment.CENTER)
            self.hitboxes['retry-card'] = retry_rect
            self.hitboxes['retry'] = retry_rect

            close_rect = (x + width - 30.0, cy - 12.0, 24.0, 24.0)
            self.hitboxes['cancel'] = close_rect
            if self.hover == 'cancel':
                ccx, ccy = close_rect[0] + 12.0, close_rect[1] + 12.0
                cr.set_source_rgba(*self.colors['text/secondary'], 0.85)
                cr.set_line_width(1.3)
                cr.move_to(ccx - 3.2, ccy - 3.2)
                cr.line_to(ccx + 3.2, ccy + 3.2)
                cr.move_to(ccx + 3.2, ccy - 3.2)
                cr.line_to(ccx - 3.2, ccy + 3.2)
                cr.stroke()
            return

        # Left 5-filament micro-equalizer aligned with the first line of speech.
        first_line_cy = y + 27.0
        self._draw_filaments(
            cr, x + 28.0, first_line_cy, count=5, pitch=4.4, max_h=15.0,
            busy=(self.phase != 'recording'),
        )

        words = self._display_transcript()
        body_x = x + 48.0
        body_y = y + 15.0
        body_w = width - 72.0
        _, layout = self.text(
            cr, words, body_x, body_y, 15, 24, 'text/primary',
            body_w, lines=3, return_layout=True,
        )

        if self.phase in ('recording', 'connecting') and words:
            pos = layout.index_to_pos(len(words.encode('utf-8')))
            caret_x = min(body_x + body_w - 2.0, body_x + pos.x / Pango.SCALE + 3.0)
            caret_y = body_y + pos.y / Pango.SCALE + 4.0
            caret_h = max(13.0, min(16.0, pos.height / Pango.SCALE - 7.0))
            blink = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(now * 5.6))
            rounded(cr, caret_x, caret_y, 1.8, caret_h, 0.9)
            cr.set_source_rgba(*accent_c, blink)
            cr.fill()

        self._register_whisper_cancel(cr, x, y, width, height)

    def draw(self, _, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        self.hitboxes = {}

        fade = 1.0
        if self.hide_at:
            remaining = self.hide_at - time.monotonic()
            if 0.0 <= remaining < 0.18:
                fade = max(0.0, remaining / 0.18)

        if fade < 1.0:
            cr.push_group()

        cap_w = max(96.0, self.w_spring.value)
        cap_h = max(28.0, self.h_spring.value)
        cap_r = min(self.r_spring.value, cap_w / 2.0, cap_h / 2.0)
        cap_x = (self.WIDTH - cap_w) / 2.0
        cap_y = (self.STAGE_HEIGHT - self.MARGIN - cap_h) + self.y_spring.value

        self.panel(cr, cap_x, cap_y, cap_w, cap_h, cap_r)

        cr.save()
        rounded(cr, cap_x + 1.0, cap_y + 1.0, cap_w - 2.0, cap_h - 2.0, max(2.0, cap_r - 1.0))
        cr.clip()
        if self.phase == 'arming' and cap_h < 34.0:
            self._draw_arming(cr, cap_x, cap_y, cap_w, cap_h)
        elif cap_h >= 46.0 and self.expanded:
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
