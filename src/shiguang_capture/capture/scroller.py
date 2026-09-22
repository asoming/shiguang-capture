"""Manual scrolling capture: observe content, never move the pointer or scroll."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QImage

from ..geometry import Rect
from .grabber import grab_region
from .stitch import find_overlap, frames_identical, stitch


def qimage_to_array(img: QImage) -> np.ndarray:
    """QImage -> (H, W, 3) uint8 RGB 数组。"""
    converted = img.convertToFormat(QImage.Format.Format_RGB888)
    w, h = converted.width(), converted.height()
    ptr = converted.bits()
    arr = np.frombuffer(ptr, dtype=np.uint8, count=converted.sizeInBytes())
    return arr.reshape(h, converted.bytesPerLine())[:, :w * 3].reshape(h, w, 3).copy()


def array_to_qimage(arr: np.ndarray) -> QImage:
    """(H, W, 3) uint8 -> QImage（拷贝持有数据）。"""
    h, w, _ = arr.shape
    return QImage(arr.tobytes(), w, h, w * 3, QImage.Format.Format_RGB888).copy()


class ScrollCaptureSession(QObject):
    frame_capturing = Signal()
    frame_captured = Signal()
    progressed = Signal(int, int)
    preview_ready = Signal(object)
    hint_changed = Signal(str)
    finished = Signal(object)
    aborted = Signal()
    failed = Signal(str)

    def __init__(self, rect: Rect, max_frames: int | None = None,
                 settle_ms: int = 180) -> None:
        super().__init__()
        self._rect = rect
        self._max_frames = max_frames
        self._settle_ms = settle_ms
        self.excluded_rect: Rect | None = None
        self.excluded_borders: list[Rect] = []
        self._acc = self._prev_frame = None
        self._frames = 0
        self._running = False
        self._completing = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._capture_step)
        self._frame_timer = QTimer(self)
        self._frame_timer.setSingleShot(True)
        self._frame_timer.timeout.connect(self._capture_frame)

    @property
    def is_running(self):
        return self._running

    def start(self):
        try:
            first = qimage_to_array(grab_region(self._rect))
        except Exception as exc:
            self.failed.emit(f'首帧抓取失败：{exc}')
            return
        self._acc = self._prev_frame = first
        self._frames = 1
        self._running = True
        self.progressed.emit(first.shape[0], 1)
        self._emit_preview()
        self.hint_changed.emit('向下滚动')
        self.frame_captured.emit()
        self._schedule()

    def _schedule(self):
        if self._running and not self._completing:
            self._timer.start(self._settle_ms)

    def abort(self):
        """Stop immediately and retain the last successfully stitched content."""
        if self._running:
            self._finish()

    def complete(self):
        """Collect the final visible frame before delivering the long image."""
        if not self._running or self._completing:
            return
        self._completing = True
        self._timer.stop()
        self.frame_capturing.emit()
        self._frame_timer.start(250)

    def _same_content(self, frame):
        """Ignore the preview and border footprints when detecting user movement.

        Idle polling leaves the preview visible. A changed page triggers a clean
        capture with the overlapping preview hidden; thumbnails never enter the
        stitched image. Comparison uses the last accepted clean frame.
        """
        previous = self._prev_frame
        if frame.shape != previous.shape:
            return False
        excluded = [rect for rect in [self.excluded_rect, *self.excluded_borders]
                    if rect is not None and rect.intersects(self._rect)]
        if not excluded:
            return frames_identical(frame, previous, tol=.1)
        height, width = frame.shape[:2]
        sx, sy = width/self._rect.width, height/self._rect.height
        # Split the comparison into uncovered areas, retaining the original
        # pixels for stitching. This also handles clipped/fullscreen borders.
        regions = [(0, 0, width, height)]
        for rect in excluded:
            # Some desktop compositors add a shadow outside the preview window.
            pad_x, pad_y = (int(12*sx)+4, int(12*sy)+4) if rect == self.excluded_rect else (4, 4)
            left = max(0, min(width, int((rect.x-self._rect.x)*sx)-pad_x))
            top = max(0, min(height, int((rect.y-self._rect.y)*sy)-pad_y))
            right = max(0, min(width, int((rect.right-self._rect.x)*sx)+pad_x))
            bottom = max(0, min(height, int((rect.bottom-self._rect.y)*sy)+pad_y))
            uncovered = []
            for x1, y1, x2, y2 in regions:
                l, t, r, b = max(x1, left), max(y1, top), min(x2, right), min(y2, bottom)
                if l >= r or t >= b:
                    uncovered.append((x1, y1, x2, y2))
                else:
                    uncovered.extend((a, c, d, e) for a, c, d, e in
                                     [(x1, y1, x2, t), (x1, b, x2, y2),
                                      (x1, t, l, b), (r, t, x2, b)] if a < d and c < e)
            regions = uncovered
        return bool(regions) and all(frames_identical(frame[y1:y2, x1:x2], previous[y1:y2, x1:x2], tol=.1)
                                     for x1, y1, x2, y2 in regions)

    def _capture_step(self):
        if not self._running:
            return
        try:
            probe = qimage_to_array(grab_region(self._rect))
        except Exception:
            self.failed.emit('捕获中断，已保留此前内容。请检查屏幕是否发生变化。')
            self.abort()
            return
        if self._same_content(probe):
            self._schedule()
            return
        self.frame_capturing.emit()
        # Finish the preview's native hide animation before a clean capture.
        self._frame_timer.start(250)

    def _capture_frame(self):
        if not self._running:
            return
        try:
            frame = qimage_to_array(grab_region(self._rect))
        except Exception:
            self.failed.emit('捕获中断，已保留此前内容。')
            self.abort()
            return
        self.frame_captured.emit()
        if frame.shape != self._prev_frame.shape:
            self.failed.emit('屏幕尺寸已变化，已停止并保留此前内容。')
            self.abort()
            return
        if frames_identical(frame, self._prev_frame):
            if self._completing:
                self._finish()
            else:
                self._schedule()
            return

        overlap, sad = find_overlap(self._prev_frame, frame)
        if not overlap or sad > 2.0:
            if self._completing:
                self.failed.emit('最后一屏无法可靠拼接，已保留此前内容。')
                self._finish()
            else:
                # Never append guessed content or end because the user paused,
                # scrolled upward, or briefly moved too far. They can scroll back.
                self.hint_changed.emit('稍往回滚')
                self._schedule()
            return
        if overlap < frame.shape[0]:
            height = self._acc.shape[0]+frame.shape[0]-overlap
            if height > 32767 or height*frame.shape[1] > 64_000_000:
                self.failed.emit('已达到长图尺寸上限，请保存当前部分。')
                self.abort()
                return
            self._acc = stitch(self._acc, frame, overlap)
            self._prev_frame = frame
            self._frames += 1
            self.progressed.emit(height, self._frames)
            self._emit_preview()
            self.hint_changed.emit('向下滚动')
        if self._completing or (self._max_frames is not None and self._frames >= self._max_frames):
            self._finish()
        else:
            self._schedule()

    def _emit_preview(self):
        height, width = self._acc.shape[:2]
        step = max(1, (height+419)//420, (width+179)//180)
        self.preview_ready.emit(array_to_qimage(self._acc[::step, ::step]))

    def _finish(self):
        self._running = False
        self._timer.stop()
        self._frame_timer.stop()
        if self._acc is not None:
            self.finished.emit(array_to_qimage(self._acc))
        else:
            self.aborted.emit()
