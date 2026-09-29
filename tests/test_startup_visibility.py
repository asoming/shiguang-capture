"""The real CLI and controller distinguish login startup from a manual launch."""
import sys
import pytest

pytest.importorskip('PySide6')
from shiguang_capture import app as application
from shiguang_capture import __main__ as entrypoint
from shiguang_capture.config import AppConfig


@pytest.mark.parametrize('background', [True, False])
def test_startup_mode_preserves_tray_and_manual_settings(qt_session, monkeypatch, background):
    monkeypatch.setenv('SHIGUANG_NO_HOTKEYS', '1')
    monkeypatch.setattr(sys, 'argv', ['shiguang-capture'] + (['--background'] if background else []))
    monkeypatch.setattr(application, 'QApplication', lambda argv: qt_session)
    controllers = []
    original_controller = application.AppController

    def create(app):
        controller = original_controller(app, AppConfig())
        controllers.append(controller)
        return controller

    def event_loop():
        controller = controllers[0]
        qt_session.processEvents()
        assert controller.tray._tray.isVisible()
        if background:
            assert controller._settings is None
            assert controller._panel is None and controller._record_panel is None
        else:
            assert controller._settings.isVisible()
        controller.tray.action_settings.emit()
        qt_session.processEvents()
        assert controller._settings.isVisible()
        return 0

    monkeypatch.setattr(application, 'AppController', create)
    monkeypatch.setattr(qt_session, 'exec', event_loop)
    try:
        assert entrypoint.main() == 0
    finally:
        for controller in controllers:
            if controller._settings is not None:
                controller._settings.close()
            controller.hotkeys.unregister()
            controller.tray._tray.hide()
            controller._runner.close()
