"""Recording controls must recover from cancellation, races and worker failure."""
from pathlib import Path
from types import SimpleNamespace
import pytest
pytest.importorskip('PySide6')
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from shiguang_capture.ui.record_panel import RecordPanel


@pytest.fixture
def panel(qt_session):
    panel = RecordPanel()
    panel.timer.stop()
    panel.show()
    yield panel
    panel.state = 'idle'
    panel.bar.hide()
    panel.close()
    panel.bar.deleteLater()
    panel.deleteLater()


def test_cancel_countdown_creates_no_worker_and_preserves_last_video(panel):
    panel.last_path = Path('previous.mp4')
    QTest.mouseClick(panel.start_button, Qt.MouseButton.LeftButton)
    assert panel.state == 'countdown' and not panel.fields.isEnabled()
    QTest.mouseClick(panel.stop_button, Qt.MouseButton.LeftButton)
    assert panel.state == 'idle' and panel.process is None
    assert panel.fields.isEnabled() and panel.open_button.isEnabled()


def test_missing_audio_device_cannot_silently_record_without_audio(panel):
    panel.audio.blockSignals(True)
    panel.audio.setCurrentIndex(panel.audio.findData('mic'))
    panel.toggle()
    assert panel.state == 'idle' and panel.process is None
    assert '未找到' in panel.status.text()


def test_closing_indicator_stops_and_late_pause_ack_cannot_resume_saving(panel):
    sent = []
    panel.process = SimpleNamespace()
    panel.connection = SimpleNamespace(send=sent.append)
    panel.state = 'recording'
    panel.bar.show()
    panel.bar.close()
    assert sent == ['stop'] and panel.state == 'saving'
    assert panel.bar.isVisible()
    panel._event({'type': 'paused'})
    assert panel.state == 'saving' and not panel.pause_button.isEnabled()
    panel._event({'type': 'finished', 'path': 'done.mp4'})
    assert panel.state == 'idle' and not panel.bar.isVisible()
    assert panel.open_button.isEnabled()


def test_dead_worker_restores_controls_and_keeps_recovery_path(panel):
    def broken_pipe():
        raise EOFError
    panel.process = SimpleNamespace(is_alive=lambda: False, join=lambda timeout: None)
    panel.connection = SimpleNamespace(poll=lambda: True, recv=broken_pipe, close=lambda: None)
    panel.state = 'paused'
    panel.recovery = 'saved.sgc-recovery.mkv'
    panel._poll()
    assert panel.state == 'idle' and panel.process is None
    assert 'saved.sgc-recovery.mkv' in panel.status.text()
    assert panel.fields.isEnabled()


def test_countdown_escape_cancels_fullscreen_overlay(panel):
    panel.toggle()
    assert panel.countdown_overlay.isVisible()
    assert not panel.isVisible()
    QTest.keyClick(panel.countdown_overlay, Qt.Key.Key_Escape)
    assert panel.state == 'idle' and panel.process is None
    assert not panel.countdown_overlay.isVisible()
    assert panel.isVisible()


def test_orb_expands_contextual_controls_and_docks(panel):
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QGuiApplication
    orb = panel.bar
    orb.show()
    panel._event({'type': 'recording'})
    QTest.mouseClick(orb, Qt.MouseButton.LeftButton, pos=QPoint(32, 32))
    assert orb.expanded and orb.pause.isEnabled() and not orb.play.isEnabled()
    panel._event({'type': 'paused'})
    assert orb.play.isEnabled() and not orb.pause.isEnabled()
    area = QGuiApplication.primaryScreen().availableGeometry()
    orb.move(area.left(), area.top()+80)
    orb.dock_if_near_edge()
    assert orb.docked == 'left' and orb.width() == 32 and not orb.expanded
    QTest.mouseClick(orb, Qt.MouseButton.LeftButton, pos=QPoint(12, 32))
    assert orb.expanded and orb.docked is None and orb.x() >= area.left()
    orb.move(area.right()-orb.width()+1, area.top()+80)
    orb.dock_if_near_edge()
    assert orb.docked == 'right' and orb.geometry().right() == area.right()
    panel._event({'type': 'saving'})
    assert not orb.play.isEnabled() and not orb.pause.isEnabled() and not orb.stop_button.isEnabled()


def test_scope_selection_tracks_committed_target_and_cancel_keeps_it(panel):
    from shiguang_capture.geometry import Rect
    selected = []
    panel.choose_region.connect(lambda: selected.append(True))
    assert panel.full_button.isChecked()
    QTest.mouseClick(panel.region_button, Qt.MouseButton.LeftButton)
    assert selected and panel.full_button.isChecked()  # choosing/cancelling does not change the target
    panel.set_region(Rect(10, 10, 200, 100))
    assert panel.region_button.isChecked() and '200 × 100' in panel.scope_hint.text()
    QTest.mouseClick(panel.full_button, Qt.MouseButton.LeftButton)
    assert panel.full_button.isChecked() and panel.region is None and panel.window_title is None
    panel.window_title = 'Chosen window'
    panel._sync_scope_buttons()
    assert panel.window_button.isChecked() and panel.scope_hint.text() == 'Chosen window'


def test_audio_devices_expand_without_losing_selection(panel):
    panel.microphone.addItem('Test microphone', 'microphone-1')
    panel.system_audio.addItem('Test system sound', 'system-1')
    panel.audio.setCurrentIndex(panel.audio.findData('both'))
    assert panel.audio_details_button.isVisible() and not panel.audio_details.isVisible()
    QTest.mouseClick(panel.audio_details_button, Qt.MouseButton.LeftButton)
    assert panel.microphone.isVisible() and panel.system_audio.isVisible()
    QTest.mouseClick(panel.audio_details_button, Qt.MouseButton.LeftButton)
    assert not panel.audio_details.isVisible()
    assert panel.microphone.currentData() == 'microphone-1'
    panel.audio.setCurrentIndex(panel.audio.findData('none'))
    assert not panel.audio_details_button.isVisible()


def test_preview_error_offers_reconnect_and_first_frame_clears_it(panel, monkeypatch):
    from PySide6.QtGui import QImage
    calls = []
    monkeypatch.setattr(panel.live_preview, 'restart', lambda: calls.append('restart'))
    panel._preview_failed('屏幕权限不可用')
    assert panel.preview_retry.isVisible()
    QTest.mouseClick(panel.preview_retry, Qt.MouseButton.LeftButton)
    assert calls == ['restart']
    panel._preview_recovering('正在重连')
    assert '重连' in panel.preview_badge.text() and not panel.preview_retry.isVisible()
    image = QImage(16, 9, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.blue)
    panel._preview_frame(image, (1920, 1080))
    assert not panel.preview_retry.isVisible() and '实时' in panel.preview_badge.text()
