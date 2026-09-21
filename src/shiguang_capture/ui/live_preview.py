"""Lifecycle and backpressure for the recording panel's live monitor."""
import multiprocessing
import time

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QImage

from ..recording.preview import preview_worker


class LivePreview(QObject):
    frame_ready = Signal(object, object)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = self.connection = None
        self.target = None
        self.pending = False
        self.timer = QTimer(self)
        self.timer.setInterval(67)
        self.timer.timeout.connect(self._poll)

    def start(self, screen_name, region=None, window_title=None):
        target = (screen_name, region, window_title)
        if target == self.target:
            return
        self.stop()
        self.target = target
        context = multiprocessing.get_context('spawn')
        self.connection, child = context.Pipe()
        self.process = context.Process(target=preview_worker, args=(child, *target), daemon=True)
        try:
            self.process.start()
            self.deadline = time.monotonic() + 15
            self.timer.start()
        except Exception as exc:
            self._fail(f'无法启动预览：{exc}')
        finally:
            child.close()

    def stop(self):
        self.timer.stop()
        if self.process is not None:
            if self.process.pid is not None:
                if self.process.is_alive():
                    self.process.terminate()
                self.process.join(timeout=.15)
                if self.process.is_alive():
                    self.process.kill()
                    self.process.join(timeout=.15)
            self.process = None
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        self.target = None
        self.pending = False

    def _fail(self, message):
        # Hold the failed target until the user changes it or reopens the panel.
        target = self.target
        self.stop()
        self.target = target
        self.failed.emit(message)

    def _poll(self):
        if self.process is None:
            return
        try:
            if self.connection.poll():
                event = self.connection.recv()
                self.pending = False
                if event['type'] == 'error':
                    self._fail(event['message'])
                    return
                image = QImage(event['pixels'], event['width'], event['height'], event['stride'],
                               QImage.Format.Format_RGB888).copy()
                self.frame_ready.emit(image, event['source_size'])
                self.deadline = time.monotonic() + 8
            if not self.process.is_alive():
                self._fail('预览已中断，请重新选择范围')
                return
            if time.monotonic() > self.deadline:
                self._fail('预览超时，请检查屏幕录制权限')
                return
            if not self.pending:
                self.connection.send('frame')
                self.pending = True
        except (EOFError, BrokenPipeError, OSError):
            self._fail('预览已中断，请重新选择范围')
