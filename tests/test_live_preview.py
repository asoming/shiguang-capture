import time
from types import SimpleNamespace

import pytest
pytest.importorskip('PySide6')
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest
from shiguang_capture.ui.live_preview import LivePreview
from shiguang_capture.ui.record_panel import RecordPanel


def test_only_one_frame_in_flight_and_failure_stops_process(qt_session):
    monitor = LivePreview()
    sent, replies, killed = [], [], []
    monitor.process = SimpleNamespace(pid=12, is_alive=lambda: not killed,
        terminate=lambda: killed.append(True), join=lambda timeout: None)
    monitor.connection = SimpleNamespace(poll=lambda: bool(replies), recv=lambda: replies.pop(0),
        send=sent.append, close=lambda: None)
    monitor.target = ('screen', (1, 2, 30, 40), None)
    monitor.deadline = time.monotonic()+10
    for _ in range(10):
        monitor._poll()
    assert sent == ['frame']
    images = []
    monitor.frame_ready.connect(lambda image, size: images.append((image, size)))
    replies.append({'type': 'frame', 'width': 1, 'height': 1, 'stride': 3,
                    'pixels': bytes([255, 0, 0]), 'source_size': (100, 100)})
    monitor._poll()
    assert len(sent) == 2 and images[0][0].pixelColor(0, 0).name() == '#ff0000'
    errors = []
    monitor.failed.connect(errors.append)
    replies.append({'type': 'error', 'message': 'permission denied'})
    monitor._poll()
    assert errors == ['permission denied'] and monitor.process is None and killed
    assert monitor.target == ('screen', (1, 2, 30, 40), None)
    monitor.stop()
    assert monitor.target is None


def test_timeout_does_not_keep_stale_image_active(qt_session):
    monitor = LivePreview()
    monitor.process = SimpleNamespace(pid=None, is_alive=lambda: True)
    monitor.connection = SimpleNamespace(poll=lambda: False, close=lambda: None)
    monitor.deadline = time.monotonic()-1
    errors = []
    monitor.failed.connect(errors.append)
    monitor._poll()
    assert errors and monitor.process is None


def test_visibility_selection_and_file_page_control_preview(qt_session, monkeypatch):
    panel = RecordPanel()
    calls = []
    monkeypatch.setattr(QGuiApplication, 'platformName', staticmethod(lambda: 'xcb'))
    monkeypatch.setattr(panel.live_preview, 'start', lambda *target: calls.append(('start', target)))
    monkeypatch.setattr(panel.live_preview, 'stop', lambda: calls.append(('stop',)))
    panel.show()
    qt_session.processEvents()
    assert calls[-1][0] == 'start'
    panel.tabs.setCurrentIndex(1)
    assert calls[-1] == ('stop',)
    panel.tabs.setCurrentIndex(0)
    assert calls[-1][0] == 'start'
    panel.window_title = 'Chosen window'
    panel._sync_preview()
    assert calls[-1][1][2] == 'Chosen window'
    panel.hide()
    assert calls[-1] == ('stop',)
    panel.bar.hide()
    panel.deleteLater()


def test_orb_animation_only_runs_while_visible_and_recording(qt_session):
    from shiguang_capture.ui.record_overlay import RecordingOrb
    orb = RecordingOrb()
    orb.set_state('recording')
    assert not orb.animation.isActive()
    orb.show()
    assert orb.animation.isActive()
    orb.set_state('paused')
    assert not orb.animation.isActive()
    orb.set_state('recording')
    assert orb.animation.isActive()
    orb.hide()
    assert not orb.animation.isActive()
    orb.deleteLater()


def test_preview_retries_are_bounded_and_stop_cancels_retry(qt_session):
    monitor = LivePreview()
    monitor.target = ('screen', None, None)
    for retry in (1, 2):
        monitor._fail('temporary failure')
        assert monitor.retry_timer.isActive()
        assert monitor.retry_timer.interval() == retry * 1000
        assert monitor.retries == retry
    monitor._fail('still unavailable')
    assert not monitor.retry_timer.isActive()
    assert monitor.target == ('screen', None, None)
    monitor.stop()
    monitor._launch()
    assert monitor.target is None and monitor.process is None


def test_same_target_can_restart_after_exhausting_retries(qt_session, monkeypatch):
    monitor = LivePreview()
    monitor.target = ('screen', None, None)
    monitor.retries = 2
    launches = []
    monkeypatch.setattr(monitor, '_launch', lambda: launches.append(monitor.target))
    monitor.start('screen')
    assert launches == [('screen', None, None)]
    assert monitor.retries == 0
    monitor.stop()


def test_docked_orb_stops_animation_and_supports_keyboard(qt_session):
    from shiguang_capture.ui.record_overlay import RecordingOrb
    orb = RecordingOrb()
    orb.set_state('recording')
    orb.show()
    area = QGuiApplication.primaryScreen().availableGeometry()
    orb.move(area.topLeft())
    orb.dock_if_near_edge()
    assert orb.docked == 'left' and not orb.animation.isActive()
    QTest.keyClick(orb, Qt.Key.Key_Space)
    assert orb.expanded and orb.docked is None and orb.animation.isActive()
    QTest.keyClick(orb, Qt.Key.Key_Escape)
    assert not orb.expanded
    orb.hide()
    orb.deleteLater()
