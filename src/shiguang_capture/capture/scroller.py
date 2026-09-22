"""capture/scroller.py — 滚动长截图会话（FR-1.11 ~ FR-1.18）。

流程：选区确认 → 抓首帧 → 模拟滚轮 → 等内容稳定 → 抓帧拼接 →
重复直到「连续两帧无变化」（滚到底）/ 达到帧数上限 / 用户中止。

pynput 控制真实鼠标：把光标移到选区中心再滚轮——与 PixPin 等工具同构。
帧处理（拼接）在 Qt 主线程以轻量方式完成（numpy 毫秒级），
滚轮等待用 QTimer 链式驱动，不阻塞 UI。
"""
from __future__ import annotations

import logging

import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QCursor, QGuiApplication, QImage

from ..geometry import Rect
from .grabber import grab_region
from .stitch import find_overlap, frames_identical, stitch

log = logging.getLogger(__name__)


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
    """一次滚动长截图。用法：构造 → start() → 监听 finished/aborted。"""

    frame_capturing = Signal()
    frame_captured = Signal()
    progressed = Signal(int, int)     # 已拼接总高度, 帧数
    preview_ready = Signal(object)    # 阶段性拼接图（QImage，每 3 帧一次）
    finished = Signal(object)         # QImage 长图
    aborted = Signal()
    failed = Signal(str)

    def __init__(self, rect: Rect, max_frames: int = 60,
                 scroll_clicks: int = 5, settle_ms: int = 380) -> None:
        super().__init__()
        self._rect = rect
        self._max_frames = max_frames
        # A fixed five-notch step can skip a small selection entirely.
        self._scroll_clicks = min(scroll_clicks, max(1, rect.height // 160))
        self._settle_ms = settle_ms
        self._acc: np.ndarray | None = None
        self._prev_frame: np.ndarray | None = None
        self._frames = 0
        self._still_count = 0
        self._running = False
        self._mouse = None
        self._original_mouse = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._capture_step)
        self._frame_timer = QTimer(self)
        self._frame_timer.setSingleShot(True)
        self._frame_timer.timeout.connect(self._capture_frame)
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.timeout.connect(self._send_scroll)

    # ---------- 生命周期 ----------
    def start(self) -> None:
        try:
            first = qimage_to_array(grab_region(self._rect))
        except Exception as exc:
            self.failed.emit(f"首帧抓取失败：{exc}")
            return
        self._acc = first
        self._prev_frame = first
        self._frames = 1
        self._running = True
        self.progressed.emit(first.shape[0], 1)
        self._scroll_once()

    def abort(self) -> None:
        """用户中止：保留已拼接部分（FR-1.16）。"""
        if not self._running:
            return
        self._running = False
        self._timer.stop()
        self._frame_timer.stop()
        self._scroll_timer.stop()
        self._restore_mouse()
        if self._acc is not None and self._frames > 0:
            self.finished.emit(array_to_qimage(self._acc))
        else:
            self.aborted.emit()

    @property
    def is_running(self) -> bool:
        return self._running

    # ---------- 内部 ----------
    def _scroll_once(self) -> None:
        if not self._running:
            return
        # The preview may cover the wheel target. Let the compositor hide it
        # before sending input, just as we do before taking a screenshot.
        self.frame_capturing.emit()
        self._scroll_timer.start(80)

    def _send_scroll(self) -> None:
        if not self._running:
            return
        try:
            from pynput.mouse import Controller

            if self._mouse is None:
                self._mouse = Controller()
                self._original_mouse = QCursor.pos()
            # Rect uses Qt logical coordinates. pynput uses native coordinates
            # on X11/Windows, so assigning the same numbers misses the selection
            # on scaled displays. Let Qt perform its native-screen conversion.
            QCursor.setPos(self._rect.x + self._rect.width // 2,
                           self._rect.y + self._rect.height // 2)
            QGuiApplication.sync()
            if not self._running:
                return
            self._mouse.scroll(0, -self._scroll_clicks)
        except Exception:
            self.failed.emit("无法控制滚动；已保留当前图像。请检查系统权限。")
            self.abort()
            return
        self.frame_captured.emit()
        # 等内容滚动并稳定后再抓帧
        self._timer.start(self._settle_ms)

    def _capture_step(self) -> None:
        if self._running:
            self.frame_capturing.emit()
            # Allow the desktop compositor to finish hiding the preview.
            self._frame_timer.start(250)

    def _capture_frame(self) -> None:
        if not self._running or self._acc is None:
            return
        try:
            frame = qimage_to_array(grab_region(self._rect))
        except Exception:
            self.failed.emit("捕获中断，已保留此前内容。请检查屏幕是否发生变化。")
            self.abort()
            return

        self.frame_captured.emit()
        if frame.shape != self._prev_frame.shape:
            self.failed.emit("屏幕尺寸已变化，已停止并保留此前内容。")
            self.abort()
            return
        if frames_identical(frame, self._prev_frame):
            self._still_count += 1
            if self._still_count >= 2:
                if self._frames == 1:
                    self.failed.emit("未检测到内容滚动，已保留首屏。请框选可滚动的正文区域，避开固定侧栏和工具栏后重试。")
                self._finish()
                return
            self._scroll_once()
            return
        else:
            self._still_count = 0

        overlap, sad = find_overlap(self._prev_frame, frame)
        if overlap == 0 or sad > 2.0:
            self.failed.emit("画面无法可靠拼接，已停止并保留此前内容。")
            self.abort()
            return
        new_height = self._acc.shape[0] + frame.shape[0] - overlap
        if new_height > 32767 or new_height * frame.shape[1] > 64_000_000:
            self.failed.emit("已达到长图尺寸上限。请保存当前部分，再继续截取。")
            self.abort()
            return
        if overlap >= frame.shape[0]:
            # 整帧都被覆盖（滚动距离过小），多滚一点再试，不计入帧数
            log.info("帧被完全覆盖（sad=%.2f），继续滚动", sad)
            self._scroll_once()
            return

        self._acc = stitch(self._acc, frame, overlap)
        self._prev_frame = frame
        self._frames += 1
        self.progressed.emit(self._acc.shape[0], self._frames)
        if self._frames % 3 == 0:
            self.preview_ready.emit(array_to_qimage(self._acc))

        if self._frames >= self._max_frames:
            log.info("达到帧数上限 %d，收尾", self._max_frames)
            self._finish()
            return
        self._scroll_once()

    def _finish(self) -> None:
        self._running = False
        self._timer.stop()
        self._frame_timer.stop()
        self._scroll_timer.stop()
        self._restore_mouse()
        assert self._acc is not None
        self.finished.emit(array_to_qimage(self._acc))

    def _restore_mouse(self):
        if self._mouse is not None and self._original_mouse is not None:
            try:
                QCursor.setPos(self._original_mouse)
            except Exception:
                pass  # Input permission may have been revoked mid-capture.
            self._original_mouse = None
