"""The pet window: frameless, per-pixel transparent, click-through-able, feet-anchored.

This is a thin shell: it owns Qt objects, mouse geometry and painting. Every "what should the
pet be doing / which clip / what text" answer comes from ``petcore``.
"""

from __future__ import annotations

import random
import time
from dataclasses import replace
from datetime import datetime

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QWidget
from petapp import menu as menu_mod
from petapp.frames import FrameStore
from petapp.lines import Lines
from petapp.store import SaveState, Settings
from petapp.win32 import last_input_idle_seconds, set_click_through
from petcore import clip_manifest as cm
from petcore.behavior import (STATE_CARRIED, STATE_FALL, STATE_WALK, BehaviorCore, WorldCtx)
from petcore.clips import ClipCatalog
from petcore.physics import Body, Rect, Sample, step, throw_velocity
from petcore.stats import Stats, apply_delta, feed as feed_stats
from petcore.timers import HourChime, Pomodoro, Sedentary
from petcore.timeline import Timeline

TICK_MS = 33
DRAG_THRESHOLD = 6
CLICK_MAX_MS = 0.15
DOUBLE_CLICK_WINDOW = 0.25
BUBBLE_SPACE = 120
BUBBLE_H = 26
SCALE_PRESETS = (150, 220, 300)
BUBBLE_SECONDS = 3.2
STATS_TICK_SECONDS = 60.0
WALK_PX_PER_S = 40.0


class PetWindow(QWidget):
    def __init__(self, catalog: ClipCatalog, settings: Settings | None = None,
                 state: SaveState | None = None, lines: Lines | None = None,
                 seed: int | None = None, on_save=None):
        super().__init__()
        self.catalog = catalog
        self.settings = settings or Settings()
        self.state = state or SaveState()
        self.stats: Stats = self.state.stats
        self.lines = lines or Lines.load(catalog.root / "text" / "lines.json")
        self.on_save = on_save
        self.store = FrameStore(catalog)
        self.core = BehaviorCore(catalog, seed=seed)
        self.timeline = Timeline(catalog.get(cm.IDLE))
        self.rng = random.Random(seed)

        self.chime = HourChime(enabled=self.settings.chime_enabled)
        self.sedentary = Sedentary(enabled=self.settings.sedentary_enabled,
                                   interval_min=self.settings.sedentary_min)
        self.pomodoro = Pomodoro(work_min=self.settings.pomodoro_work_min,
                                 break_min=self.settings.pomodoro_break_min)

        self.scale_index = min(max(self.settings.scale_index, 0), len(SCALE_PRESETS) - 1)
        self._aspect = (catalog.crop_box[2] - catalog.crop_box[0]) / (catalog.crop_box[3] - catalog.crop_box[1])
        self._pm: QPixmap | None = None
        self._bubble_key: str | None = None
        self._bubble_text = ""
        self._bubble_left = 0.0
        self._show_stats = False
        self._press_t: float | None = None
        self._press_pos: QPoint | None = None
        self._samples: list[Sample] = []
        self._click_pending = False
        self._last_click_at = 0.0
        self._dragging = False
        self._clock = time.perf_counter()
        self._stats_accum = 0.0
        self.tick_ms: list[float] = []
        self._menu: QMenu | None = None
        self.tray = None
        self.pomodoro_status_action = None
        self.tray_through_action = None
        self._screen_index = 0

        self.store.set_target_height(round(self.pet_h * self._dpr()))
        self._apply_size()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        if self.state.x and self.state.y:
            self.body = Body(self.state.x, self.state.y, on_ground=True)
        else:
            self.body = Body(x=0.0, y=0.0, on_ground=True)
            self._park_on_floor()
        self._place()
        self.set_click_through_enabled(self.settings.click_through)

        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._on_tick)

    # ------------------------------------------------------------------ geometry
    def _dpr(self) -> float:
        return float(self._screen().devicePixelRatio())

    def _screen(self):
        screens = QApplication.screens()
        if not screens:
            return QApplication.primaryScreen()
        return screens[min(self._screen_index, len(screens) - 1)]

    @property
    def pet_h(self) -> int:
        return SCALE_PRESETS[self.scale_index]

    def _apply_size(self) -> None:
        self.resize(max(240, round(self.pet_h * self._aspect)), self.pet_h + BUBBLE_SPACE)

    def _floor_y(self) -> float:
        return float(self._screen().availableGeometry().bottom())

    def _bounds(self) -> Rect:
        g = self._screen().availableGeometry()
        return Rect(float(g.left()), float(g.top()), float(g.right()), float(g.bottom()))

    def _park_on_floor(self) -> None:
        b = self._bounds()
        self.body = Body(x=(b.left + b.right) / 2, y=self._floor_y(), on_ground=True)
        self._place()

    def _place(self) -> None:
        x = round(self.body.x - self.width() / 2)
        y = round(self.body.y - self.height())
        # move() is a SetWindowPos round trip; standing still must not pay it 30 times a second.
        if (x, y) == getattr(self, "_placed_at", None):
            return
        self._placed_at = (x, y)
        self.move(x, y)

    # ------------------------------------------------------------------ loop
    def start(self) -> None:
        self._clock = time.perf_counter()
        self._timer.start()

    def _on_tick(self) -> None:
        now = time.perf_counter()
        dt = min(now - self._clock, 1.0)
        self._clock = now
        t0 = now
        idle = last_input_idle_seconds()

        if not self.settings.paused:
            self._reminders(dt, idle)
            ctx = WorldCtx(stats=self.stats, idle_seconds=idle, quiet=self.pomodoro.quiet)
            d = self.core.tick(dt, ctx)
            self._apply_decision(d, dt)
        elif self._pm is None:
            self._apply_decision(self.core.tick(0.0, WorldCtx(stats=self.stats)), 0.0)

        self._stats_accum += dt
        if self._stats_accum >= STATS_TICK_SECONDS:
            self.stats = self.stats.decayed(self._stats_accum)
            self._stats_accum = 0.0
        if self._bubble_left > 0:
            self._bubble_left -= dt
            if self._bubble_left <= 0:
                self._bubble_key, self._bubble_text = None, ""
        self.update()
        self.tick_ms.append((time.perf_counter() - t0) * 1000)
        if len(self.tick_ms) > 600:
            self.tick_ms.pop(0)

    def _apply_decision(self, d, dt: float) -> None:
        if d.slug != self.timeline.spec.slug:
            spec = self.catalog.get(d.slug)
            if spec is not None:
                self.timeline.switch(spec, speed=d.speed)
        else:
            self.timeline.speed = d.speed
        frame = self.timeline.advance(dt)
        pm = self.store.pixmap(d.slug, frame)
        if pm is not None:
            self._pm = pm
        if d.bubble_key:
            self.show_bubble(d.bubble_key)
        if d.state == STATE_WALK and self.body.on_ground:
            b = self._bounds()
            half = self.width() / 2
            self.body = replace(self.body, x=self.body.x + d.walk_dir * WALK_PX_PER_S * dt)
            if self.body.x - half <= b.left or self.body.x + half >= b.right:
                self.core.push("wall")
        elif dt > 0:
            res = step(self.body, dt, self._floor_y(), self._bounds())
            self.body = res.body
            if res.landed:
                self.core.push("landed", hard=res.hard_landing)
                if res.hard_landing:
                    self.stats = apply_delta(self.stats, "thrown")
                    self.save()
        self._place()

    def _reminders(self, dt: float, idle: float) -> None:
        hour = self.chime.tick(datetime.now())
        if hour is not None:
            self.core.push("chime", hungry=self.stats.hungry)
            self.stats = apply_delta(self.stats, "chime")
        if self.sedentary.tick(dt, idle):
            self.core.push("sedentary")
        transition = self.pomodoro.tick(dt)
        if transition == "work_done":
            self.core.push("pomodoro_done")
            self.stats = apply_delta(self.stats, "pomodoro_done")
        elif transition == "break_done":
            self.show_bubble("pomodoro_done")
        self._update_pomodoro_status()

    def _update_pomodoro_status(self) -> None:
        act = self.pomodoro_status_action
        if act is None:
            return
        if self.pomodoro.state == "off":
            act.setText("\u72b6\u6001\uff1a\u672a\u5f00\u542f")
        else:
            mins = max(0, int(self.pomodoro.remaining // 60))
            secs = max(0, int(self.pomodoro.remaining % 60))
            label = "\u4e13\u6ce8" if self.pomodoro.state == "work" else "\u4f11\u606f"
            act.setText(f"\u72b6\u6001\uff1a{label} {mins:02d}:{secs:02d}")

    def show_bubble(self, key: str) -> None:
        self._bubble_key = key
        self._bubble_text = self.lines.pick(key, self.rng)
        self._bubble_left = BUBBLE_SECONDS

    # ------------------------------------------------------------------ input
    def mousePressEvent(self, ev) -> None:
        if ev.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(ev)
        self._press_t = time.perf_counter()
        self._press_pos = ev.globalPosition().toPoint()
        self._samples = [Sample(float(self._press_pos.x()), float(self._press_pos.y()), self._press_t)]
        self._dragging = False

    def mouseMoveEvent(self, ev) -> None:
        if self._press_t is None:
            return
        p = ev.globalPosition().toPoint()
        self._samples.append(Sample(float(p.x()), float(p.y()), time.perf_counter()))
        self._samples = self._samples[-8:]
        if not self._dragging and self._press_pos and \
                (p - self._press_pos).manhattanLength() > DRAG_THRESHOLD:
            self._dragging = True
            self.core.push("grab")
        if self._dragging:
            self.body = Body(x=float(p.x()), y=float(p.y()), vx=0.0, vy=0.0, on_ground=False)
            self._place()

    def mouseReleaseEvent(self, ev) -> None:
        if ev.button() != Qt.MouseButton.LeftButton:
            return super().mouseReleaseEvent(ev)
        held = time.perf_counter() - (self._press_t or time.perf_counter())
        moved = self._dragging
        self._press_t = None
        self._dragging = False
        if moved:
            vx, vy = throw_velocity(self._samples)
            self.core.push("release")
            self.body = replace(self.body, vx=vx, vy=vy, on_ground=False)
            return
        if held <= CLICK_MAX_MS:
            now = time.perf_counter()
            if now - self._last_click_at <= DOUBLE_CLICK_WINDOW:
                self._click_pending = False
                self.pet_now()
            else:
                self._click_pending = True
                self._last_click_at = now
                QTimer.singleShot(int(DOUBLE_CLICK_WINDOW * 1000), self._flush_single_click)

    def _flush_single_click(self) -> None:
        if self._click_pending:
            self._click_pending = False
            self.poke()

    def poke(self) -> None:
        self.core.push("poke")
        annoyed = self.core.slug in cm.POKED_ANNOYED
        self.stats = apply_delta(self.stats, "poke_annoyed" if annoyed else "poke")
        self.save()

    def pet_now(self) -> None:
        self.core.push("pet")
        self.stats = apply_delta(self.stats, "pet")
        self.save()

    def feed(self, food: str) -> None:
        self.core.push("feed")
        self.stats = feed_stats(self.stats, food)
        self.show_bubble("feed")
        self.save()

    def play_clip(self, slug: str) -> bool:
        return self.core.request(slug, priority="reminder")

    def resume_autonomy(self) -> None:
        self.core.resume_autonomy()
        self.update()

    def wheelEvent(self, ev) -> None:
        self.set_scale_index(self.scale_index + (1 if ev.angleDelta().y() > 0 else -1))

    def contextMenuEvent(self, ev) -> None:
        self.show_menu(ev.globalPos())

    # ------------------------------------------------------------------ menu actions
    def show_menu(self, global_pos: QPoint) -> None:
        self._menu = menu_mod.build_menu(self)
        self._menu.exec(global_pos)

    def show_menu_at_cursor(self) -> None:
        self.show_menu(QCursor_pos())

    def set_scale(self, px: int) -> None:
        if px in SCALE_PRESETS:
            self.set_scale_index(SCALE_PRESETS.index(px))

    def set_scale_index(self, index: int) -> None:
        index = min(max(index, 0), len(SCALE_PRESETS) - 1)
        if index == self.scale_index:
            return
        self.scale_index = index
        self.settings.scale_index = index
        self.store.set_target_height(round(self.pet_h * self._dpr()))
        self._apply_size()
        self._place()
        self.save()

    def set_click_through_enabled(self, enabled: bool) -> None:
        self.settings.click_through = bool(enabled)
        set_click_through(int(self.winId()), bool(enabled))
        if self.tray_through_action is not None:
            self.tray_through_action.setChecked(bool(enabled))
        self.save()

    def set_topmost(self, enabled: bool) -> None:
        self.settings.topmost = bool(enabled)
        flags = self.windowFlags()
        if enabled:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        visible = self.isVisible()
        self.setWindowFlags(flags)
        if visible:
            self.show()
        self.save()

    def set_paused(self, paused: bool) -> None:
        self.settings.paused = bool(paused)
        self.save()

    def set_chime_enabled(self, enabled: bool) -> None:
        self.settings.chime_enabled = bool(enabled)
        self.chime.enabled = bool(enabled)
        self.save()

    def set_sedentary_enabled(self, enabled: bool) -> None:
        self.settings.sedentary_enabled = bool(enabled)
        self.sedentary.enabled = bool(enabled)
        self.save()

    def set_sedentary_interval(self, minutes: float) -> None:
        self.settings.sedentary_min = float(minutes)
        self.sedentary.interval_min = float(minutes)
        self.sedentary.reset()
        self.save()

    def set_show_stats(self, on: bool) -> None:
        self._show_stats = bool(on)
        self.update()

    def start_pomodoro(self) -> None:
        self.pomodoro.start()
        self.core.push("pomodoro_start")
        self._update_pomodoro_status()

    def stop_pomodoro(self) -> None:
        self.pomodoro.stop()
        self.core.push("pomodoro_stop")
        self._update_pomodoro_status()

    def reset_position(self) -> None:
        self._park_on_floor()
        self.save()

    def next_screen(self) -> None:
        count = len(QApplication.screens())
        if count < 2:
            return
        self._screen_index = (self._screen_index + 1) % count
        self.store.set_target_height(round(self.pet_h * self._dpr()))
        self._park_on_floor()
        self.save()

    def hide_to_tray(self) -> None:
        self.save()
        self.hide()

    def toggle_visible(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self._place()

    def quit_app(self) -> None:
        self.save()
        QApplication.quit()

    def save(self) -> None:
        if self.on_save is None:
            return
        self.state = SaveState(stats=self.stats, x=self.body.x, y=self.body.y,
                               saved_at=time.time(), last_day=self.state.last_day)
        self.on_save(self.state, self.settings)

    # ------------------------------------------------------------------ paint
    def paintEvent(self, _ev) -> None:
        if self._pm is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        target_h = self.pet_h
        target_w = round(target_h * self._aspect)
        p.drawPixmap(QPoint(round((self.width() - target_w) / 2), self.height() - target_h), self._pm)
        if self._bubble_text:
            self._paint_bubble(p)
        if self._show_stats:
            self._paint_stat_bars(p)
        p.end()

    def _paint_bubble(self, p: QPainter) -> None:
        p.setFont(QFont("Microsoft YaHei", 9))
        fm = p.fontMetrics()
        w = min(self.width() - 4, fm.horizontalAdvance(self._bubble_text) + 18)
        h = BUBBLE_H
        x = max(2.0, (self.width() - w) / 2)
        y = max(0.0, self.height() - self.pet_h - h - 6)
        path = QPainterPath()
        path.addRoundedRect(x, y, w, h, 9, 9)
        p.fillPath(path, QColor(255, 255, 255, 232))
        p.setPen(QColor(60, 60, 60))
        p.drawPath(path)
        p.drawText(QPoint(round(x + 9), round(y + h - 8)), self._bubble_text)

    def _panel_metrics(self) -> tuple[int, int, int, QFont]:
        """(pixel unit, row height, panel height, label font) for the stat panel.

        The row band follows the font rather than the bar, because at the 150 px body size a
        bar-only step clips the labels into the frame above them. The font is capped so the panel
        stays inside the empty band above the head, which is also where the bubble lands.
        """
        px = max(2, round(self.pet_h / 220 * 3))
        font = QFont("Microsoft YaHei", min(11, max(8, round(self.pet_h / 26))))
        row_h = max(px * 5, QFontMetrics(font).height() + px)
        return px, row_h, row_h * 3 + px, font

    def _paint_stat_bars(self, p: QPainter) -> None:
        """Pixel panel: flat pastel blocks on an outlined light frame, no gradients.

        Everything sits on a "pixel" grid that scales with the body size, and each row's name goes in
        the empty left column rather than over the bar, so it stays readable against any wallpaper.
        """
        rows = (("\u9971\u98df", self.stats.satiety, QColor(255, 178, 92), QColor(255, 221, 170)),
                ("\u5fc3\u60c5", self.stats.mood, QColor(255, 127, 168), QColor(255, 190, 212)),
                ("\u4eb2\u5bc6", self.stats.affection, QColor(126, 178, 255), QColor(191, 217, 255)))
        ink = QColor(43, 42, 74)                       # the panel's only dark value: outline + labels
        paper = QColor(244, 241, 255, 226)
        empty = QColor(217, 212, 232)
        empty_foot = QColor(196, 190, 214)
        px, row_h, panel_h, font = self._panel_metrics()
        p.setFont(font)
        fm = p.fontMetrics()
        bar_h = px * 3
        panel = QRectF(px, px, self.width() - px * 2, panel_h)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        p.fillRect(panel, paper)
        p.setPen(ink)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(panel)
        for cx, cy in ((panel.left(), panel.top()), (panel.right() - 1, panel.top()),
                       (panel.left(), panel.bottom() - 1), (panel.right() - 1, panel.bottom() - 1)):
            p.fillRect(QRectF(cx, cy, 1, 1), paper)    # notched corners

        p.setPen(ink)
        label_col = max(fm.horizontalAdvance(row[0]) for row in rows) + px * 2
        bar_x = panel.left() + px + label_col
        segs = 8
        seg_w = max(1.0, (panel.right() - px * 2 - bar_x - px * (segs - 1)) / segs)
        for i, (label, value, fill, highlight) in enumerate(rows):
            band = panel.top() + px + i * row_h
            top = band + (row_h - bar_h) / 2
            p.drawText(QRectF(panel.left() + px, band, label_col, row_h),
                       int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), label)
            filled = round(max(0.0, min(1.0, value / 100)) * segs)
            for s in range(segs):
                sx = bar_x + s * (seg_w + px)
                if s < filled:
                    p.fillRect(QRectF(sx, top, seg_w, bar_h), fill)
                    p.fillRect(QRectF(sx, top, seg_w, px), highlight)
                    p.fillRect(QRectF(sx, top + bar_h - px, seg_w, px), ink)
                else:
                    p.fillRect(QRectF(sx, top, seg_w, bar_h), empty)
                    p.fillRect(QRectF(sx, top + bar_h - px, seg_w, px), empty_foot)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)


def QCursor_pos() -> QPoint:
    from PySide6.QtGui import QCursor
    return QCursor.pos()
