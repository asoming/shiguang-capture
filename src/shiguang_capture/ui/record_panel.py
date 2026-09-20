"""Compact recording controls; native capture runs in a separate process."""
from __future__ import annotations

import multiprocessing
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
                              QPushButton, QComboBox, QFileDialog, QLineEdit)

from ..recording.worker import RecordingOptions, record, probe_audio, probe_windows
from .theme import STYLE


class RecordingBar(QWidget):
    stop_requested = Signal()

    def closeEvent(self, event):
        self.stop_requested.emit()
        event.ignore()  # Keep the indicator visible until the recorder stops.


class RecordPanel(QWidget):
    choose_region = Signal()
    idle = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle('拾光 · 录屏')
        self.setObjectName('workspace')
        self.setStyleSheet(STYLE)
        self.setMinimumWidth(420)
        self.process = self.connection = None
        self.probe = self.probe_connection = None
        self.window_probe = self.window_connection = None
        self.state = 'idle'
        self.region = None
        self.window_title = None
        self.recovery = None
        self.last_path = None
        self.countdown = 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        self.fields = QWidget()
        form = QFormLayout(self.fields)
        self.form = form
        form.setContentsMargins(0, 0, 0, 0)
        self.screen = QComboBox()
        for index, screen in enumerate(QGuiApplication.screens()):
            form_label = f'屏幕 {index + 1} · {screen.geometry().width()} × {screen.geometry().height()}'
            self.screen.addItem(form_label, screen.name())
        self.screen.currentIndexChanged.connect(self._clear_region)
        form.addRow('录制屏幕', self.screen)
        self.region_button = QPushButton('选择区域…')
        self.region_button.clicked.connect(self.choose_region.emit)
        full = QPushButton('全屏')
        full.clicked.connect(self._clear_region)
        bounds = QHBoxLayout()
        bounds.addWidget(self.region_button, 1)
        bounds.addWidget(full)
        choose_window = QPushButton('窗口…')
        choose_window.clicked.connect(self._choose_window)
        bounds.addWidget(choose_window)
        form.addRow('范围', bounds)
        self.audio = QComboBox()
        for text, value in [('不录声音', 'none'), ('麦克风', 'mic'), ('系统声音', 'system'), ('系统声音 + 麦克风', 'both')]:
            self.audio.addItem(text, value)
        self.audio.currentIndexChanged.connect(self._audio_changed)
        form.addRow('声音', self.audio)
        self.microphone, self.system_audio = QComboBox(), QComboBox()
        form.addRow('麦克风', self.microphone)
        form.addRow('系统音源', self.system_audio)
        self.microphone.setEnabled(False)
        self.system_audio.setEnabled(False)
        form.setRowVisible(self.microphone, False)
        form.setRowVisible(self.system_audio, False)
        self.fps = QComboBox()
        for fps in (15, 30, 60):
            self.fps.addItem(f'{fps} fps', fps)
        self.fps.setCurrentIndex(1)
        form.addRow('帧率', self.fps)
        self.folder = QLineEdit(str(Path.home()/'Videos'/'Shiguang'))
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder, 1)
        browse = QPushButton('…')
        browse.clicked.connect(self._choose_folder)
        folder_row.addWidget(browse)
        form.addRow('保存位置', folder_row)
        layout.addWidget(self.fields)
        self.status = QLabel('')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QHBoxLayout()
        self.start_button = QPushButton('开始录制', objectName='primary')
        self.start_button.clicked.connect(self.toggle)
        self.stop_button = QPushButton('停止并保存')
        self.stop_button.clicked.connect(self.stop)
        self.stop_button.setEnabled(False)
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.stop_button)
        layout.addLayout(buttons)
        footer = QHBoxLayout()
        recover = QPushButton('恢复录制…')
        recover.clicked.connect(self._recover)
        self.open_button = QPushButton('打开视频')
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_path))))
        footer.addWidget(recover)
        footer.addWidget(self.open_button)
        layout.addLayout(footer)
        self.recover_button = recover

        self.bar = RecordingBar(None, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.bar.stop_requested.connect(self.stop)
        self.bar.setWindowTitle('拾光 · 录制中')
        self.bar.setStyleSheet(STYLE)
        row = QHBoxLayout(self.bar)
        self.clock = QLabel('● 00:00')
        self.clock.setStyleSheet('color:#B83737;font-weight:bold;')
        row.addWidget(self.clock)
        self.pause_button = QPushButton('暂停')
        self.pause_button.clicked.connect(self.toggle)
        row.addWidget(self.pause_button)
        stop = QPushButton('停止')
        stop.clicked.connect(self.stop)
        row.addWidget(stop)
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self._poll)
        self.timer.start()

    @property
    def active(self):
        return self.state != 'idle'

    def _clear_region(self, *_):
        self.region = None
        self.window_title = None
        self.region_button.setText('选择区域…')

    def _choose_window(self):
        if self.window_probe:
            return
        context = multiprocessing.get_context('spawn')
        self.window_connection, child = context.Pipe()
        self.window_probe = context.Process(target=probe_windows, args=(child,), daemon=True)
        self.window_probe.start()
        child.close()
        self.window_deadline = time.monotonic() + 10
        self.status.setText('正在读取窗口…')

    def set_region(self, rect):
        screen = next((s for s in QGuiApplication.screens()
                       if s.geometry().contains(rect.x, rect.y) and
                       s.geometry().contains(rect.right-1, rect.bottom-1)), None)
        if not screen:
            self.status.setText('请在同一块屏幕内选择录制区域。')
            return
        self.screen.setCurrentIndex(self.screen.findData(screen.name()))
        self.region = (rect.x, rect.y, rect.width, rect.height)
        self.window_title = None
        self.region_button.setText(f'{rect.width} × {rect.height} · 重新选择')

    def _choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, '保存位置', self.folder.text())
        if path:
            self.folder.setText(path)

    def _audio_changed(self):
        mode = self.audio.currentData()
        self.microphone.setEnabled(mode in ('mic', 'both'))
        self.system_audio.setEnabled(mode in ('system', 'both'))
        self.form.setRowVisible(self.microphone, mode in ('mic', 'both'))
        self.form.setRowVisible(self.system_audio, mode in ('system', 'both'))
        self.adjustSize()
        if mode == 'none' or self.probe or self.microphone.count() or self.system_audio.count():
            return
        context = multiprocessing.get_context('spawn')
        self.probe_connection, child = context.Pipe()
        self.probe = context.Process(target=probe_audio, args=(child,), daemon=True)
        self.probe.start()
        child.close()
        self.probe_deadline = time.monotonic() + 10
        self.status.setText('正在读取音源…')

    def toggle(self):
        if self.state in ('recording', 'paused'):
            try:
                self.connection.send('pause' if self.state == 'recording' else 'resume')
            except (BrokenPipeError, OSError):
                self.status.setText('录屏进程已退出，请尝试恢复录制。')
        elif self.state == 'idle':
            if self.process is not None:
                return
            mode = self.audio.currentData()
            if (mode in ('mic', 'both') and self.microphone.currentData() is None or
                    mode in ('system', 'both') and self.system_audio.currentData() is None):
                self.status.setText('未找到所选音源，请连接设备或选择不录声音。')
                return
            self.state = 'countdown'
            self.fields.setEnabled(False)
            self.recover_button.setEnabled(False)
            self.open_button.setEnabled(False)
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.stop_button.setText('取消')
            self.countdown = time.monotonic() + 3
            self.status.setText('3 秒后开始录制')

    def _start(self):
        mode = self.audio.currentData()
        target = Path(self.folder.text()).expanduser()/f'录屏_{datetime.now():%Y%m%d_%H%M%S}.mp4'
        options = RecordingOptions(str(target), self.screen.currentData(), self.region, self.fps.currentData(),
                                   self.microphone.currentData() if mode in ('mic', 'both') else None,
                                   self.system_audio.currentData() if mode in ('system', 'both') else None,
                                   self.window_title)
        context = multiprocessing.get_context('spawn')
        self.connection, child = context.Pipe()
        self.process = context.Process(target=record, args=(child, options), daemon=True)
        try:
            self.process.start()
        except Exception as exc:
            self.status.setText(f'无法启动录屏：{exc}')
            self.connection.close()
            self.process = None
            self._set_idle()
            return
        finally:
            child.close()
        self.state = 'starting'
        self.started_deadline = time.monotonic() + 25
        self.recovery = None
        self.stop_button.setText('停止并保存')
        self.pause_button.setEnabled(False)
        self.clock.setText('● 准备中')
        self.hide()
        self.bar.show()

    def stop(self):
        if self.state == 'countdown':
            self.status.clear()
            self._set_idle()
        elif self.process and self.state not in ('idle', 'saving'):
            try:
                self.connection.send('stop')
                self.state = 'saving'
                self.pause_button.setEnabled(False)
                self.clock.setText('正在保存…')
                self.stop_button.setEnabled(False)
            except (BrokenPipeError, OSError):
                self.status.setText('录屏进程已退出，请尝试恢复录制。')

    def _set_idle(self):
        self.state = 'idle'
        self.fields.setEnabled(True)
        self.recover_button.setEnabled(True)
        self.start_button.setEnabled(True)
        self.start_button.setText('开始录制')
        self.stop_button.setEnabled(False)
        self.stop_button.setText('停止并保存')
        self.bar.hide()
        self.open_button.setEnabled(self.last_path is not None)
        self.show()
        self.idle.emit()

    def _poll(self):
        if self.window_probe:
            try:
                if self.window_connection.poll():
                    event = self.window_connection.recv()
                    probe, self.window_probe = self.window_probe, None
                    self.window_connection.close()
                    probe.join(timeout=.1)
                    if event['type'] == 'windows' and event['windows']:
                        from PySide6.QtWidgets import QInputDialog
                        title, accepted = QInputDialog.getItem(self, '选择录制窗口', '窗口', event['windows'], 0, False)
                        if accepted:
                            self.window_title, self.region = title, None
                            self.region_button.setText('窗口 · ' + title[:20])
                            self.region_button.setToolTip(title)
                        self.status.clear()
                    else:
                        self.status.setText(event.get('message', '没有可单独识别的窗口，请使用区域录屏。'))
            except (EOFError, OSError):
                pass
            if self.window_probe and (not self.window_probe.is_alive() or time.monotonic() > self.window_deadline):
                if self.window_probe.is_alive():
                    self.window_probe.terminate()
                    self.status.setText('读取窗口超时，请使用区域录屏。')
                self.window_probe.join(timeout=.1)
                self.window_probe = None
                self.window_connection.close()
        if self.state == 'countdown':
            seconds = self.countdown - time.monotonic()
            if seconds <= 0:
                self._start()
            else:
                self.status.setText(f'{int(seconds)+1} 秒后开始录制')
                self.clock.setText(f'{int(seconds)+1} 秒后开始')
        if self.probe:
            try:
                if self.probe_connection.poll():
                    event = self.probe_connection.recv()
                    if event['type'] == 'devices':
                        for device in event['devices']:
                            combo = self.system_audio if device['loopback'] else self.microphone
                            combo.addItem(device['name'], device['id'])
                        self.status.clear()
                    else:
                        self.status.setText(event['message'])
            except (EOFError, OSError):
                pass
            if not self.probe.is_alive() or time.monotonic() > self.probe_deadline:
                if self.probe.is_alive():
                    self.probe.terminate()
                    self.status.setText('读取音源超时，请检查系统音频服务。')
                self.probe.join(timeout=.1)
                self.probe = None
                self.probe_connection.close()
        if self.process is None:
            return
        try:
            while self.connection.poll():
                self._event(self.connection.recv())
        except (EOFError, OSError):
            pass
        if self.state == 'starting' and time.monotonic() > self.started_deadline:
            self.process.terminate()
            self.status.setText('屏幕采集启动超时，请检查系统权限。')
            self._set_idle()
        if not self.process.is_alive():
            self.process.join(timeout=.1)
            self.process = None
            self.connection.close()
            if self.active:
                self.status.setText('录制意外中断。' + (f'恢复文件：{self.recovery}' if self.recovery else '请重试。'))
                self._set_idle()

    def _event(self, event):
        kind = event['type']
        if event.get('recovery'):
            self.recovery = event['recovery']
        if kind in ('recording', 'paused'):
            if self.state == 'saving':
                return
            self.state = kind
            self.start_button.setEnabled(True)
            self.pause_button.setEnabled(True)
            text = '继续' if kind == 'paused' else '暂停'
            self.start_button.setText(text)
            self.pause_button.setText(text)
            if kind == 'paused':
                self.clock.setText('Ⅱ 已暂停')
        elif kind == 'progress':
            seconds = int(event['seconds'])
            self.clock.setText(f'● {seconds//60:02d}:{seconds%60:02d}')
        elif kind == 'saving':
            self.state = 'saving'
            self.clock.setText('正在保存…')
        elif kind == 'finished':
            self.last_path = Path(event['path'])
            self.status.setText(f'已保存：{self.last_path.name}')
            self._set_idle()
            self.open_button.setEnabled(True)
        elif kind == 'error':
            self.status.setText(event['message'] + (f'\n恢复文件：{self.recovery}' if self.recovery else ''))
            self._set_idle()
        elif kind == 'cancelled':
            self.status.clear()
            self._set_idle()

    def _recover(self):
        if self.process is not None:
            return
        path, _ = QFileDialog.getOpenFileName(self, '恢复录制', self.recovery or self.folder.text(), '录制恢复文件 (*.sgc-recovery.mkv)')
        if not path:
            return
        # Recovery runs separately too; large files must not freeze controls.
        from ..recording.recovery import recover_worker
        context = multiprocessing.get_context('spawn')
        self.connection, child = context.Pipe()
        target = Path(path).with_name(f'恢复_{datetime.now():%Y%m%d_%H%M%S}.mp4')
        self.process = context.Process(target=recover_worker, args=(child, path, str(target)), daemon=True)
        try:
            self.process.start()
        except Exception as exc:
            self.connection.close()
            self.process = None
            self.status.setText(f'无法启动恢复：{exc}')
            return
        finally:
            child.close()
        self.state = 'saving'
        self.fields.setEnabled(False)
        self.start_button.setEnabled(False)
        self.recover_button.setEnabled(False)
        self.status.setText('正在恢复…')

    def closeEvent(self, event):
        if self.active:
            event.ignore()
            self.hide()
            self.bar.show()
        else:
            super().closeEvent(event)
