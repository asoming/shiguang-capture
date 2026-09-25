"""Settings navigation must keep real preferences, validation, and tool entry signals."""
from copy import deepcopy

import pytest

pytest.importorskip('PySide6')
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from shiguang_capture.config import AppConfig
from shiguang_capture.ui.settings_window import SettingsWindow


@pytest.fixture
def settings():
    app = QApplication.instance() or QApplication([])
    window = SettingsWindow(AppConfig())
    window.show()
    app.processEvents()
    yield window
    window.close()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_sidebar_saves_every_preference_without_mutating_original(settings):
    original = deepcopy(settings._config)
    saved = []
    settings.settings_saved.connect(saved.append)
    settings._nav_buttons[2].click()
    assert settings.pages.currentIndex() == 2
    settings.opacity_slider.setValue(65)
    settings.picker_combo.setCurrentText('hsl')
    settings._nav_buttons[3].click()
    settings.lang_combo.setCurrentIndex(settings.lang_combo.findData('en'))
    settings._nav_buttons[0].click()
    settings.save_dir_edit.setText('/tmp/screenshots')
    settings.format_combo.setCurrentText('jpg')
    settings.autostart_check.setFocus()
    QTest.keyClick(settings.autostart_check, Qt.Key.Key_Space)
    settings._hotkey_edits['record_stop'].setText('ctrl+f8')
    settings.save_button.click()
    assert len(saved) == 1
    cfg = saved[0]
    assert (cfg.save_dir, cfg.image_format) == ('/tmp/screenshots', 'jpg')
    assert cfg.launch_at_login is True
    assert cfg.pin_default_opacity == .65 and cfg.picker_format == 'hsl'
    assert cfg.target_lang == 'en' and cfg.hotkeys.record_stop == 'ctrl+f8'
    assert cfg.allow_cloud_translate is False
    assert settings._config == original


def test_quick_actions_do_not_save_pending_changes(settings):
    events = []
    settings.capture_requested.connect(lambda: events.append('capture'))
    settings.record_requested.connect(lambda: events.append('record'))
    settings.recognize_requested.connect(lambda: events.append('recognize'))
    settings.settings_saved.connect(lambda _: events.append('saved'))
    settings.save_dir_edit.setText('/tmp/unsaved')
    for label in ['截图', '录屏', '识别']:
        next(b for b in settings.findChildren(QPushButton) if b.text() == label).click()
    assert events == ['capture', 'record', 'recognize']
    assert settings._config.save_dir == '~/Pictures/Shiguang'


def test_hidden_hotkey_conflict_navigates_and_preserves_config(settings):
    settings._nav_buttons[4].click()
    settings._hotkey_edits['record_stop'].setText('f1')
    saved = []
    settings.settings_saved.connect(saved.append)
    settings.save_button.click()
    assert settings.pages.currentIndex() == 1
    assert settings._nav_buttons[1].isChecked()
    assert '区域截图' in settings.hotkey_warn.text()
    assert '停止录屏' in settings.hotkey_warn.text()
    assert settings.status.text() == '设置未保存，原快捷键仍可使用。'
    assert not saved and settings._config.hotkeys.record_stop == 'f7'
