"""Regression coverage for user-visible failures found in the PRD audit."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('SHIGUANG_NO_HOTKEYS', '1')
import threading
import time
from types import SimpleNamespace
from pathlib import Path
import pytest
pytest.importorskip('PySide6')
from PySide6.QtCore import QPointF, QEventLoop, QTimer
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication
from shiguang_capture.app import AppController
from shiguang_capture.config import AppConfig, HotkeyConfig
from shiguang_capture.images import load_image, save_image
from shiguang_capture.ocr import create_backend
from shiguang_capture.ocr.base import OCRResult, MockOCRBackend
from shiguang_capture.capture.grabber import compose_region, ScreenFrame
from shiguang_capture.capture.scroller import qimage_to_array
from shiguang_capture.geometry import Rect
from shiguang_capture.ui.canvas import Mark
from shiguang_capture.ui.result_panel import ResultPanel
from shiguang_capture.ui.settings_window import SettingsWindow


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def pump(ms=100):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def image(width=101, height=60):
    result = QImage(width, height, QImage.Format.Format_RGB888)
    result.fill(QColor('white'))
    return result


@pytest.fixture
def controller(app):
    ctrl = AppController(app, AppConfig(), ocr_backend=MockOCRBackend())
    yield ctrl
    ctrl.cancel_recognition()
    for bridge in list(ctrl._recognition_bridges):
        bridge.thread.join(timeout=2)
    pump(20)
    if ctrl._panel:
        ctrl._panel.close()
    ctrl._runner.close()
    ctrl.tray._tray.hide()


@pytest.mark.parametrize('width', [1, 100, 101, 102, 103, 104, 719])
def test_padded_rgb_rows(width):
    data = qimage_to_array(image(width))
    assert data.shape == (60, width, 3)
    assert (data == 255).all()


def test_null_image_does_not_claim_saved(tmp_path):
    with pytest.raises(ValueError):
        save_image(QImage(), tmp_path/'none.png')
    assert not (tmp_path/'none.png').exists()


def test_atomic_image_export_and_import(tmp_path):
    path = tmp_path/'中文 图.png'
    save_image(image(), path)
    loaded = load_image(str(path))
    assert loaded.size() == image().size()
    assert loaded.pixelColor(0, 0) == QColor('white')


def test_corrupt_image_refused(tmp_path):
    path = tmp_path/'bad.png'
    path.write_bytes(b'not an image')
    with pytest.raises(ValueError):
        load_image(str(path))


def test_save_failure_preserves_existing_image(tmp_path):
    path = tmp_path/'keep.png'
    save_image(image(), path)
    original = path.read_bytes()
    with pytest.raises(ValueError):
        save_image(QImage(), path)
    assert path.read_bytes() == original


def test_native_dpi_and_negative_origin():
    frozen = image(200, 120)
    frozen.setPixelColor(0, 0, QColor('red'))
    frame = ScreenFrame(Rect(-100, 0, 100, 60), frozen, 2)
    result = compose_region([frame], Rect(-100, 0, 100, 60))
    assert (result.width(), result.height()) == (200, 120)
    assert result.pixelColor(0, 0) == QColor('red')


def test_unknown_backend_never_returns_mock():
    with pytest.raises(ValueError):
        create_backend('cloud')


def test_malformed_configuration_recovers(tmp_path):
    path = tmp_path/'config.json'
    path.write_text('{"hotkeys":null,"pin_default_opacity":"bad","save_dir":42}')
    assert AppConfig.load(path) == AppConfig()


def test_modifier_order_conflicts():
    assert HotkeyConfig(capture_region='ctrl+shift+a', color_picker='shift+ctrl+a').conflicts()


def test_conflicting_form_does_not_modify_original(app):
    cfg = AppConfig()
    win = SettingsWindow(cfg)
    win._hotkey_edits['capture_region'].setText('f2')
    win._on_save()
    assert cfg.hotkeys.capture_region == 'f1'
    assert '冲突' in win.hotkey_warn.text()
    win.close()


def test_settings_can_reopen(controller):
    controller.open_settings()
    controller._settings.close()
    pump(30)
    controller.open_settings()
    assert controller._settings.isVisible()
    controller._settings.close()
    pump(20)


def test_no_auto_clipboard_and_async_entry(controller, app):
    release = threading.Event()
    finished = threading.Event()
    class Slow:
        is_local = True
        def recognize(self, data):
            release.wait(2)
            finished.set()
            return OCRResult('late text', .9)
    controller._ocr_override = Slow()
    controller._ocr_image(image())
    assert not finished.is_set(), "UI entry waited for inference"
    app.clipboard().setText('new user content')
    release.set()
    pump(250)
    assert app.clipboard().text() == 'new user content'
    assert controller._panel.source_edit.toPlainText() == 'late text'


def test_cancelled_result_cannot_replace_new_result(controller):
    release = threading.Event()
    started = threading.Event()
    class First:
        is_local = True
        def recognize(self, data):
            started.set()
            release.wait(2)
            return OCRResult('obsolete A', .9)
    controller._ocr_override = First()
    controller._run_ocr_action(image())
    assert started.wait(1)
    controller.cancel_recognition()
    controller._ocr_override = MockOCRBackend()
    controller._run_ocr_action(image())
    pump(100)
    release.set()
    pump(100)
    assert controller._panel.source_edit.toPlainText() == '[mock] 示例识别文本'


def test_redaction_invalidates_text_and_flattens(app):
    panel = ResultPanel()
    panel.set_image(image())
    panel.show_result('ocr', OCRResult('SECRET123', .99))
    panel.canvas.marks.append(Mark('redact', [QPointF(5, 5), QPointF(40, 40)]))
    panel.canvas.changed.emit()
    assert not panel.source_edit.toPlainText()
    assert panel._result is None
    assert panel.canvas.rendered_image().pixelColor(20, 20) == QColor('#20374B')
    panel.canvas.undo()
    assert panel.canvas.rendered_image().pixelColor(20, 20) == QColor('white')
    assert panel._result is None
    panel.close()


def test_edit_during_recognition_discards_old_output(controller):
    release = threading.Event()
    class Slow:
        is_local = True
        def recognize(self, data):
            release.wait(2)
            return OCRResult('SECRET', .99)
    controller._ocr_override = Slow()
    controller._run_ocr_action(image())
    controller._panel.canvas.changed.emit()
    release.set()
    pump(100)
    assert not controller._panel.source_edit.toPlainText()


def test_update_does_not_change_clipboard(controller, app):
    app.clipboard().setText('keep this')
    controller._on_update_result(SimpleNamespace(version='2.0', url='https://example.com'))
    assert app.clipboard().text() == 'keep this'


def test_session_clear_drops_original_and_derived(controller):
    panel = controller.open_workspace()
    panel.set_image(image())
    panel.show_result('ocr', OCRResult('SECRET', .9))
    panel.clear_session()
    assert panel.canvas.image.isNull()
    assert panel._image is None
    assert panel._result is None
    assert controller._last_image is None


def test_selected_frame_used_without_recapture(controller, monkeypatch, app):
    import shiguang_capture.app as app_module
    frozen = image()
    frozen.fill(QColor('red'))
    controller._selector = SimpleNamespace(selected_image=lambda rect: frozen, deleteLater=lambda: None)
    def unexpected_capture(rect):
        raise AssertionError('Must crop the frozen frame')
    monkeypatch.setattr(app_module, 'grab_region', unexpected_capture)
    controller._dispatch_region(Rect(0, 0, 101, 60), 'copy')
    assert app.clipboard().image().pixelColor(0, 0) == QColor('red')


def test_preview_close_stops_capture_and_preserves_image(app):
    from shiguang_capture.capture.scroller import ScrollCaptureSession
    from shiguang_capture.ui.scroll_preview import ScrollPreviewWindow
    session = ScrollCaptureSession(Rect(0, 0, 101, 60))
    session._running = True
    session._frames = 1
    session._acc = qimage_to_array(image())
    images = []
    session.finished.connect(images.append)
    preview = ScrollPreviewWindow()
    preview.abort_requested.connect(session.abort)
    preview.show()
    preview.close()
    assert not session.is_running
    assert len(images) == 1 and images[0].width() == 101


def test_translation_degraded_warning_visible(app):
    from shiguang_capture.translate import LocalDictBackend
    panel = ResultPanel()
    panel.show_translation(OCRResult('save', .9), LocalDictBackend().translate('save', 'en', 'zh'))
    assert '不是完整译文' in panel.gloss.text()
    panel.close()


def test_modifier_chord_does_not_fire_bare_function_key():
    from shiguang_capture.hotkeys import ChordMatcher
    fired = []
    matcher = ChordMatcher({
        frozenset({'f1'}): lambda: fired.append('region'),
        frozenset({'shift', 'f1'}): lambda: fired.append('screen'),
    })
    matcher.press('shift')
    matcher.press('f1')
    matcher.press('f1')  # Key repeat should not repeat a capture.
    matcher.release('shift')
    matcher.release('f1')
    assert fired == ['screen']
    matcher.press('f1')
    assert fired == ['screen', 'region']


def test_ten_pins_restore_visible_and_exit_passthrough(controller, app):
    for _ in range(10):
        controller.pin_image(image(20, 20))
    first = controller._pins[0]
    first.set_passthrough(True)
    first.move(-100000, -100000)
    controller.toggle_pins()
    assert all(not pin.isVisible() for pin in controller._pins)
    controller.restore_pins()
    assert len(controller._pins) == 10
    assert all(pin.isVisible() and not pin._passthrough for pin in controller._pins)
    assert app.primaryScreen().availableGeometry().intersects(first.frameGeometry())
    for pin in list(controller._pins):
        pin.close()
    assert not controller._pins
