"""Lifecycle and backpressure for the recording panel's live monitor."""
import multiprocessing
import time

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QImage

from ..recording.preview import preview_worker


class LivePreview(QObject):
    frame_ready = Signal(object, object)
    failed = Signal(str)
    recovering = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = self.connection = None
        self.target = None
        self.pending = False
        self.retries = 0
        self.retry_timer = QTimer(self)
        self.retry_timer.setSingleShot(True)
        self.retry_timer.timeout.connect(self._launch)
        self.timer = QTimer(self)
        self.timer.setInterval(67)
        self.timer.timeout.connect(self._poll)

    def start(self, screen_name, region=None, window_title=None):
        target = (screen_name, region, window_title)
        if target == self.target and (self.process is not None or self.retry_timer.isActive()):
            return
        self.stop()
        self.target = target
        self._launch()

    def restart(self):
        target = self.target
        if target is not None:
            self.stop()
            self.start(*target)

    def _launch(self):
        target = self.target
        if target is None:
            return
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
        self.retry_timer.stop()
        self.retries = 0
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
        target, retries = self.target, self.retries
        self.stop()
        self.target, self.retries = target, retries
        self.failed.emit(message)
        # A hidden panel clears its target; never revive a stopped preview.
        if self.target is not None and self.retries < 2:
            self.retries += 1
            self.recovering.emit(f'正在重新连接预览（{self.retries}/2）')
            self.retry_timer.start(self.retries * 1000)

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
