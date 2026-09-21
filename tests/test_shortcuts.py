from copy import deepcopy
import sys
from types import SimpleNamespace

import pytest

from shiguang_capture.config import AppConfig, HotkeyConfig
from shiguang_capture.shortcuts import normalize_shortcut


def test_aliases_and_disabled_shortcuts():
    assert normalize_shortcut(' Shift + Control + A ') == 'ctrl+shift+a'
    assert normalize_shortcut('meta+F9') == 'cmd+f9'
    assert HotkeyConfig(capture_region='', capture_fullscreen='').conflicts() == []
    assert HotkeyConfig(capture_region='win+a', capture_fullscreen='cmd+a').conflicts()


@pytest.mark.parametrize('value', ['ctrl', 'ctrl++a', 'ctrl+a+b', 'ctrl+ctrl+a', 'f99'])
def test_invalid_chords(value):
    with pytest.raises(ValueError):
        normalize_shortcut(value)


@pytest.fixture
def app():
    pytest.importorskip('PySide6')
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_record_clear_cancel_restore_and_conflicts(app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from shiguang_capture.ui.settings_window import SettingsWindow
    win = SettingsWindow(AppConfig())
    win.show()
    win._switch_to_tab(1)
    app.processEvents()
    edit = win._hotkey_edits['capture_region']
    edit.setFocus()
    app.processEvents()
    QTest.keyClick(edit, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    assert edit.text() == ('shift+cmd+a' if sys.platform == 'darwin' else 'ctrl+shift+a')
    QTest.keyClick(edit, Qt.Key.Key_Escape)
    assert edit.text() == 'f1'
    edit.setFocus()
    QTest.keyClick(edit, Qt.Key.Key_Backspace)
    assert edit.text() == ''
    saved = []
    win.settings_saved.connect(saved.append)
    win._on_save()
    assert saved[-1].hotkeys.capture_region == ''
    win._reset_hotkeys()
    assert edit.text() == 'f1'
    QTest.keyClick(edit, Qt.Key.Key_F2)
    win._on_save()
    assert len(saved) == 1
    assert '区域截图' in win.hotkey_warn.text() and '取色器' in win.hotkey_warn.text()
    win.close()
    app.processEvents()


def test_save_rebind_reopen_and_failure_rollback(app, tmp_path, monkeypatch):
    from shiguang_capture.app import AppController
    from PySide6.QtCore import QCoreApplication, QEvent
    controller = AppController(app, AppConfig())
    path = tmp_path/'config.json'
    monkeypatch.setattr(AppConfig, 'default_path', staticmethod(lambda: path))
    monkeypatch.setattr('shiguang_capture.app.autostart.is_enabled', lambda: False)
    calls = []
    monkeypatch.setattr(controller.hotkeys, 'register', lambda keys: calls.append(keys.copy()) or True)
    controller.open_settings()
    controller._settings._hotkey_edits['record_toggle'].setText('ctrl+shift+r')
    controller._settings._hotkey_edits['capture_region'].setText('')
    controller._settings._on_save()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert AppConfig.load(path).hotkeys.record_toggle == 'ctrl+shift+r'
    assert calls[-1]['capture_region'] == ''
    assert 'CTRL+SHIFT+R' in controller.tray._hotkey_actions['record_toggle'][0].text()
    controller.open_settings()
    assert controller._settings._hotkey_edits['record_toggle'].text() == 'ctrl+shift+r'
    previous = deepcopy(controller.config)
    next_config = deepcopy(previous)
    next_config.hotkeys.record_toggle = 'f9'
    monkeypatch.setattr(controller.hotkeys, 'register', lambda keys: False)
    controller.apply_config(next_config)
    assert controller.config == previous and AppConfig.load(path) == previous
    monkeypatch.setattr(controller.hotkeys, 'register', lambda keys: calls.append(keys.copy()) or True)
    def fail_save(self):
        raise OSError('disk unavailable')
    monkeypatch.setattr(AppConfig, 'save', fail_save)
    controller.apply_config(next_config)
    assert calls[-1] == vars(previous.hotkeys)
    assert controller.config == previous and AppConfig.load(path) == previous
    controller._settings.close()
    controller.tray._tray.hide()
    controller._runner.close()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_editing_does_not_trigger_capture(app, monkeypatch):
    from PySide6.QtTest import QTest
    from shiguang_capture.app import AppController
    controller = AppController(app, AppConfig())
    controller.open_settings()
    controller._settings._switch_to_tab(1)
    controller._settings.activateWindow()
    edit = controller._settings._hotkey_edits['capture_region']
    edit.setFocus()
    QTest.qWait(20)
    triggered = []
    monkeypatch.setattr(controller, 'start_region_capture', lambda: triggered.append(True))
    assert app.focusWidget() is edit
    controller._on_hotkey('capture_region')
    assert not triggered
    edit.clearFocus()
    controller._on_hotkey('capture_region')
    assert triggered == [True]
    controller._settings.close()
    controller.tray._tray.hide()
    controller._runner.close()


def test_launch_opens_settings(monkeypatch):
    pytest.importorskip('PySide6')
    import shiguang_capture.app as module
    calls = []
    fake_app = SimpleNamespace(setApplicationName=lambda _: None,
        setQuitOnLastWindowClosed=lambda _: None, exec=lambda: 0)
    monkeypatch.setattr(module, 'QApplication', lambda _: fake_app)
    monkeypatch.setattr(module, 'AppController', lambda _: SimpleNamespace(
        open_settings=lambda: calls.append('settings')))
    assert module.main([]) == 0
    assert calls == ['settings']
