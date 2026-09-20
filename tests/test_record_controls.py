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
