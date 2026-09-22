"""Desktop orchestration. Explicit outputs, frozen captures, cancellable recognition."""
from __future__ import annotations
import logging
import multiprocessing
import sys
import threading
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal, Slot, Qt, QBuffer, QIODevice
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from . import __version__, autostart
from .capture.grabber import grab_fullscreen, grab_region
from .capture.scroller import ScrollCaptureSession
from .capture.selector import RegionSelector
from .config import AppConfig
from .clipboard import write_text, write_image
from .hotkeys import HotkeyManager
from .images import load_image, save_image, validate_size
from .naming import next_seq, shot_name
from .ocr import assert_privacy_guard, create_backend
from .ocr.worker import RecognitionCancelled, RecognitionRunner
from .ui.pin_window import PinWindow
from .ui.result_panel import ResultPanel
from .ui.scroll_preview import ScrollPreviewWindow
from .ui.settings_window import SettingsWindow
from .ui.tray import TrayIcon
from .updater import check_for_update

log = logging.getLogger(__name__)


class _UpdateBridge(QObject):
    finished = Signal(object)


class _RecognitionBridge(QObject):
    ok = Signal(object)
    err = Signal(str)
    done = Signal()

    def __init__(self, on_ok=None, on_err=None, cleanup=None):
        super().__init__()
        self._on_ok, self._on_err, self._cleanup = on_ok, on_err, cleanup
        self.cancel = threading.Event()
        self.ok.connect(self.deliver_ok)
        self.err.connect(self.deliver_error)
        self.done.connect(self.finish)

    @Slot(object)
    def deliver_ok(self, result):
        if not self.cancel.is_set() and self._on_ok:
            self._on_ok(result)

    @Slot(str)
    def deliver_error(self, message):
        if not self.cancel.is_set() and self._on_err:
            self._on_err(message)

    @Slot()
    def finish(self):
        if self._cleanup:
            self._cleanup(self)
        self._on_ok = self._on_err = self._cleanup = None


class AppController:
    def __init__(self, qt_app, config=None, ocr_backend=None):
        self.app = qt_app
        self.config = config or AppConfig.load()
        self._ocr_override = ocr_backend
        self._ocr = None
        self._runner = RecognitionRunner()
        self._recognition_bridges = []
        self._active_task = None
        self._task_id = 0
        self._panel = None
        self._last_image = None
        self._selector = self._picker = self._settings = None
        self._scroll_session = self._scroll_preview = None
        self._record_panel = None
        self._launcher = None
        self._editors = []
        self._quit_after_recording = False
        self._pins = []
        self._pins_hidden = False
        self._color_history = []
        self._closing = False
        self._update_running = False
        self.tray = TrayIcon()
        for signal, callback in [
            (self.tray.action_capture, self.start_region_capture),
            (self.tray.action_record, self.open_recording),
            (self.tray.action_scroll, self.start_scroll_capture),
            (self.tray.action_pick, self.start_color_pick),
            (self.tray.action_ocr, self.ocr_recognize),
            (self.tray.action_hide_pins, self.toggle_pins),
            (self.tray.action_restore_pins, self.restore_pins),
            (self.tray.action_settings, self.open_settings),
            (self.tray.action_open, self.open_image),
            (self.tray.action_workspace, self.open_settings),
            (self.tray.action_quit, self.shutdown),
        ]:
            signal.connect(callback)
        self.tray.action_check_update.connect(lambda: self.check_updates(manual=True))
        self.tray.show()
        self.tray.update_hotkeys(self.config.hotkeys)
        self.hotkeys = HotkeyManager()
        self.hotkeys.bridge.triggered.connect(self._on_hotkey)
        self._register_hotkeys()
        self._update_bridge = _UpdateBridge()
        self._update_bridge.finished.connect(self._on_update_result)
        qt_app.screenRemoved.connect(self._display_changed)
        qt_app.screenAdded.connect(self._screen_added)
        for screen in qt_app.screens():
            self._watch_screen(screen)

    def _watch_screen(self, screen):
        screen.geometryChanged.connect(self._display_changed)
        screen.logicalDotsPerInchChanged.connect(self._display_changed)

    def _screen_added(self, screen):
        self._watch_screen(screen)
        self._display_changed()

    def _display_changed(self, *_):
        if self._picker is not None:
            self._picker.close()
        if self._selector is not None:
            self._selector.close()
            self.tray.notify('拾光 Capture', '显示设置已变化，请重新选择区域。')
        if self._scroll_session and self._scroll_session.is_running:
            self._scroll_session.abort()
        screen = QGuiApplication.primaryScreen()
        if screen:
            available = screen.availableGeometry()
            for pin in self._pins:
                if not any(s.availableGeometry().intersects(pin.frameGeometry()) for s in self.app.screens()):
                    pin.move(available.topLeft())

    def _register_hotkeys(self):
        try:
            if self.config.hotkeys.conflicts():
                raise ValueError('重复快捷键')
        except ValueError:
            self.tray.notify('拾光 Capture', '配置中的快捷键无效或重复，请在设置中修改。托盘菜单仍可使用。')
            return False
        registered = self.hotkeys.register(vars(self.config.hotkeys))
        if not registered:
            self.tray.notify('拾光 Capture', '全局快捷键暂不可用，请检查系统权限。工作台与托盘仍可使用。')
        return registered

    def _on_hotkey(self, action):
        from .ui.hotkey_edit import HotkeyEdit
        if isinstance(self.app.focusWidget(), HotkeyEdit):
            return
        actions = {'capture_region': self.start_region_capture, 'capture_fullscreen': self.capture_fullscreen,
                   'capture_scroll': self.start_scroll_capture, 'pin_last': self.pin_from_clipboard,
                   'color_picker': self.start_color_pick, 'hide_all_pins': self.toggle_pins,
                   'restore_all_pins': self.restore_pins,
                   'ocr_recognize': self.ocr_recognize,
                   'record_toggle': self.toggle_recording, 'record_stop': self.stop_recording}
        actions.get(action, lambda: None)()

    def open_launcher(self):
        if self._launcher is None:
            from .ui.launcher import Launcher
            self._launcher = Launcher()
            self._launcher.capture.connect(self.start_region_capture)
            self._launcher.record.connect(self.open_recording)
            self._launcher.recognize.connect(self.ocr_recognize)
            self._launcher.settings.connect(self.open_settings)
        self._launcher.show()
        self._launcher.raise_()

    def edit_image(self, image):
        from .ui.launcher import ImageEditor
        editor = ImageEditor(image)
        editor.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        editor.save.connect(self.save_as)
        editor.recognize.connect(self._begin_recognition)
        editor.destroyed.connect(lambda: self._editors.remove(editor) if editor in self._editors else None)
        self._editors.append(editor)
        editor.show()

    def open_workspace(self):
        if self._panel is None:
            panel = ResultPanel(delegate=self._recognize_panel, formats=self.config.output_formats)
            panel.translate_requested.connect(lambda text: self._recognize_panel(panel.canvas.image, 'translate_text', text))
            panel.format_changed.connect(self._remember_output_format)
            panel.capture_requested.connect(self.start_region_capture)
            panel.record_requested.connect(self.open_recording)
            panel.open_requested.connect(self.open_image)
            panel.paste_requested.connect(self.paste_image)
            panel.file_dropped.connect(self.open_image)
            panel.image_edited.connect(self._image_changed)
            panel.cancel_requested.connect(self.cancel_recognition)
            panel.save_image_requested.connect(self.save_as)
            panel.pin_requested.connect(self.pin_image)
            self._panel = panel
        self._panel.show()
        self._panel.raise_()
        self._panel.activateWindow()
        return self._panel

    def _remember_output_format(self, mode, output):
        self.config.output_formats[mode] = output
        try:
            self.config.save()
        except OSError:
            self._panel.gloss.setText('格式已在本次会话记住；配置目录暂不可写。')

    def open_recording(self):
        if self._launcher:
            self._launcher.hide()
        if self._record_panel is None:
            from .ui.record_panel import RecordPanel
            self._record_panel = RecordPanel(self.config.record_dir)
            self._record_panel.choose_region.connect(self._choose_record_region)
            self._record_panel.idle.connect(self._recording_idle)
            self._record_panel.folder_changed.connect(self._remember_record_folder)
        self._record_panel.show()
        self._record_panel.raise_()
        self._record_panel.activateWindow()

    def _remember_record_folder(self, folder):
        self.config.record_dir = folder
        try:
            self.config.save()
        except OSError:
            self._record_panel.status.setText('保存位置已在本次会话记住；配置目录暂不可写。')

    def toggle_recording(self):
        if self._record_panel and self._record_panel.active:
            self._record_panel.toggle()
        else:
            self.open_recording()

    def stop_recording(self):
        if self._record_panel:
            self._record_panel.stop()

    def _recording_idle(self):
        if self._quit_after_recording:
            self._quit_after_recording = False
            self.shutdown()

    def _choose_record_region(self):
        if self._selector:
            self._selector.close()
        self._record_panel.hide()
        if self._panel:
            self._panel.hide()
        QTimer.singleShot(150, self._show_record_selector)

    def _show_record_selector(self):
        if self._closing:
            return
        try:
            self._selector = RegionSelector(selection_only=True)
            self._selector.action_chosen.connect(self._record_region_chosen)
            self._selector.cancelled.connect(self._record_selection_cancelled)
            self._selector.show()
            self._selector.activateWindow()
        except (RuntimeError, ValueError) as exc:
            self._record_panel.status.setText(str(exc))
            self._record_panel.show()

    def _record_selection_cancelled(self):
        self._clear_selector()
        self._record_panel.show()

    def _record_region_chosen(self, rect, action):
        self._clear_selector()
        if action == 'copy':
            self._record_panel.set_region(rect)
        self._record_panel.show()

    def _image_changed(self):
        self.cancel_recognition()
        self._last_image = None  # Never retain an unredacted fallback after edits.

    def open_image(self, path=None):
        if not isinstance(path, str):
            path, _ = QFileDialog.getOpenFileName(self._panel, '打开图片', '', '图片 (*.png *.jpg *.jpeg)')
        if not path:
            return
        try:
            image = load_image(path)
        except (ValueError, OSError) as exc:
            self._error(str(exc))
            return
        self.edit_image(image)

    def paste_image(self):
        image = QGuiApplication.clipboard().image()
        try:
            validate_size(image.width(), image.height())
        except ValueError as exc:
            self._error(str(exc))
            return
        self.edit_image(image)

    def start_region_capture(self):
        self._start_selector(False)

    def start_scroll_capture(self):
        self._start_selector(True)

    def _start_selector(self, scroll):
        if self._launcher:
            self._launcher.hide()
        self.cancel_recognition()
        if self._scroll_session and self._scroll_session.is_running:
            self._error('请先完成或停止当前长截图。')
            return
        if self._selector is not None:
            self._selector.close()
        if self._picker is not None:
            self._picker.close()
        if self._panel:
            self._panel.hide()
        if self._settings:
            self._settings.hide()
        QTimer.singleShot(120, lambda: self._show_selector(scroll))

    def _show_selector(self, scroll):
        if self._closing:
            return
        if self._selector is not None:
            self._selector.close()
        try:
            selector = RegionSelector()
        except (ValueError, RuntimeError) as exc:
            self._error(str(exc))
            return
        self._selector = selector
        selector.action_chosen.connect(lambda rect, action: self._dispatch_region(rect, action, scroll))
        selector.cancelled.connect(self._clear_selector)
        selector.show()
        selector.activateWindow()

    def _clear_selector(self):
        if self._selector is not None:
            self._selector.deleteLater()
            self._selector = None

    def _dispatch_region(self, rect, action, long_scroll=False):
        selector = self._selector
        try:
            if action == 'scroll' or (long_scroll and action == 'copy'):
                self._clear_selector()
                QTimer.singleShot(100, lambda: self._start_scroll_session(rect))
                return
            image = selector.selected_image(rect) if selector is not None else grab_region(rect)
            self._last_image = image
            if action == 'copy':
                write_image(image)
                self.tray.notify('拾光 Capture', '已复制')
            elif action == 'save':
                self.save_as(image)
            elif action == 'pin':
                self.pin_image(image)
            elif action in ('ocr', 'translate', 'code', 'table'):
                self._begin_recognition(image, action)
            elif action == 'edit':
                self.edit_image(image)
        except (ValueError, RuntimeError, OSError) as exc:
            self._error(str(exc))
        finally:
            self._clear_selector()

    def _on_region(self, rect):
        self._dispatch_region(rect, 'copy')

    def capture_fullscreen(self):
        try:
            image = grab_fullscreen()
            self._last_image = image
            write_image(image)
            self.tray.notify('拾光 Capture', '当前屏幕已复制，未保存到磁盘。')
        except (ValueError, RuntimeError) as exc:
            self._error(str(exc))

    def _save(self, image):
        directory = Path(self.config.save_dir).expanduser()
        now = datetime.now()
        path = directory / shot_name(now, next_seq(directory, now), self.config.image_format)
        save_image(image, path)
        return path

    def save_as(self, image):
        if image.isNull():
            return
        default = Path(self.config.save_dir).expanduser() / shot_name(datetime.now(), 1, self.config.image_format)
        path, selected = QFileDialog.getSaveFileName(self._panel, '保存当前图片', str(default), 'PNG (*.png);;JPEG (*.jpg)')
        if not path:
            return
        target = Path(path)
        if not target.suffix:
            target = target.with_suffix('.jpg' if selected.startswith('JPEG') else '.png')
            if target.exists() and QMessageBox.question(self._panel, '文件已存在', '替换这个文件？') != QMessageBox.StandardButton.Yes:
                return
        try:
            save_image(image, target)
        except (ValueError, OSError) as exc:
            self._error(str(exc))
            return
        self.tray.notify('拾光 Capture', '图片已保存。')
        if self._panel:
            self._panel.gloss.setText('图片已保存，标注已合并。')

    def _start_scroll_session(self, rect):
        session = ScrollCaptureSession(rect)
        preview = ScrollPreviewWindow()
        session.frame_capturing.connect(preview.hide)
        session.frame_captured.connect(preview.show)
        session.progressed.connect(preview.update_progress)
        session.preview_ready.connect(lambda image: preview.update_progress(image.height(), session._frames, image))
        session.finished.connect(lambda image: self._on_scroll_finished(image, preview))
        session.failed.connect(lambda msg: self._on_scroll_failed(msg, preview))
        preview.abort_requested.connect(session.abort)
        preview.save_requested.connect(session.abort)
        self._scroll_session, self._scroll_preview = session, preview
        # Keep the preview away from the capture when possible.
        screen = QGuiApplication.primaryScreen()
        if screen:
            preview.move(screen.availableGeometry().right() - preview.sizeHint().width(), 30)
        # Capture the first frame before displaying the preview.
        session.start()
        # frame_captured shows it after wheel delivery. Showing it here would
        # cover the pending first wheel target before the scroll timer fires.

    def _on_scroll_finished(self, image, preview):
        preview.close()
        if self._closing:
            return
        self.edit_image(image)


    def _on_scroll_failed(self, message, preview):
        self._error(message)
        if not self._scroll_session or not self._scroll_session.is_running:
            preview.close()

    @property
    def ocr(self):
        if self._ocr_override is not None:
            return self._ocr_override
        if self._ocr is None:
            self._ocr = create_backend(self.config.ocr_engine)
        return self._ocr

    def recognize(self, png_bytes, cloud_allowed=False):
        assert_privacy_guard(self.ocr, cloud_allowed)
        return self.ocr.recognize(png_bytes).text

    def ocr_recognize(self):
        image = QGuiApplication.clipboard().image()
        if image.isNull():
            image = self._last_image
        if image is None or image.isNull():
            self.open_image()
            self._error('打开图片后，点击识别文字。')
            return
        self._begin_recognition(image, 'ocr')

    def _image_to_png_bytes(self, image):
        validate_size(image.width(), image.height())
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(buffer, 'PNG'):
            raise ValueError('无法编码图像，请重新打开图片。')
        return bytes(buffer.data())

    def _ocr_image(self, image):
        self._begin_recognition(image, 'ocr')

    def _run_ocr_action(self, image):
        self._begin_recognition(image, 'ocr')

    def _run_translate_action(self, image):
        self._begin_recognition(image, 'translate')

    def _begin_recognition(self, image, mode):
        panel = self.open_workspace()
        panel.set_image(image)
        self._recognize_panel(image, mode)

    def _recognize_panel(self, image, mode, text=None):
        self.cancel_recognition()
        panel = self.open_workspace()
        try:
            png = self._image_to_png_bytes(image) if text is None else text
        except ValueError as exc:
            self._error(str(exc))
            return
        task_id = self._task_id
        translation_source = deepcopy(panel._result) if text is not None else None
        if translation_source is not None:
            translation_source.text = text
        config = deepcopy(self.config)
        backend_override = self._ocr_override
        panel.set_busy(True)
        def on_ok(payload):
            if self._closing or task_id != self._task_id:
                return
            result, translation = payload
            panel.set_busy(False)
            if translation is not None:
                if text is not None and panel.source_edit.toPlainText() != text:
                    panel.show_error("原文已修改，请再次点击翻译。")
                    return
                panel.show_translation(translation_source or result, translation)
            else:
                panel.show_result(mode, result)
            if not result.text.strip():
                panel.show_error('未识别到文字。请使用更清晰的图片重试。')
        def on_error(message):
            if not self._closing and task_id == self._task_id:
                panel.set_busy(False)
                panel.show_error(message)
        bridge = _RecognitionBridge(on_ok, on_error, self._finish_recognition)
        self._recognition_bridges.append(bridge)
        self._active_task = bridge
        def worker():
            try:
                if backend_override is None or text is not None:
                    payload = self._runner.run(png, mode, config, bridge.cancel)
                else:
                    assert_privacy_guard(backend_override, False)
                    result = backend_override.recognize(png)
                    translation = None
                    if mode == 'translate' and not bridge.cancel.is_set():
                        from .translate import translate_text
                        translation = translate_text(result.text, config, allow_cloud=False)
                    payload = result, translation
                bridge.ok.emit(payload)
            except RecognitionCancelled:
                pass
            except Exception as exc:
                bridge.err.emit(str(exc))
            finally:
                bridge.done.emit()
        thread = threading.Thread(target=worker, daemon=True)
        bridge.thread = thread
        thread.start()

    def _finish_recognition(self, bridge):
        if bridge in self._recognition_bridges:
            self._recognition_bridges.remove(bridge)
        if self._active_task is bridge:
            self._active_task = None

    def cancel_recognition(self):
        self._task_id += 1
        if self._active_task:
            self._active_task.cancel.set()
            self._active_task = None
        if self._panel:
            self._panel.set_busy(False)
            self._panel.gloss.setText('任务已取消。图像仍保留，可再次识别。')

    def pin_image(self, image):
        if image.isNull():
            return
        if len(self._pins) >= 20:
            self._error('已有 20 张贴图，请先关闭一些贴图。')
            return
        pin = PinWindow(image, self.config.pin_default_opacity, self.config.hotkeys.restore_all_pins)
        pin.recognize_requested.connect(self._run_ocr_action)
        pin.edit_requested.connect(self.edit_image)
        pin.closed.connect(lambda item: self._pins.remove(item) if item in self._pins else None)
        self._pins.append(pin)
        self._pins_hidden = False
        for item in self._pins:
            item.show()
        return pin

    def pin_from_clipboard(self):
        image = QGuiApplication.clipboard().image()
        if image.isNull():
            image = self._last_image
        if image is None or image.isNull():
            self._error('剪贴板中没有图片。')
            return
        self.pin_image(image)

    def toggle_pins(self):
        self._pins_hidden = not self._pins_hidden
        for pin in self._pins:
            pin.setVisible(not self._pins_hidden)

    def restore_pins(self):
        self._pins_hidden = False
        screens = self.app.screens()
        for pin in self._pins:
            pin.restore()
            if screens and not any(s.availableGeometry().intersects(pin.frameGeometry()) for s in screens):
                pin.move(screens[0].availableGeometry().topLeft())

    def start_color_pick(self):
        from .ui.picker import ColorPickerOverlay
        if self._picker:
            self._picker.close()
        try:
            self._picker = ColorPickerOverlay(self.config.picker_format, history=self._color_history)
            self._picker.color_picked.connect(self._on_color)
            self._picker.sampled.connect(self._remember_color)
            self._picker.show()
        except (ValueError, RuntimeError) as exc:
            self._error(str(exc))

    def _remember_color(self, r, g, b):
        color = (r, g, b)
        self._color_history = [color, *(item for item in self._color_history if item != color)][:20]

    def _on_color(self, value):
        try:
            write_text(value)
            self.tray.notify('拾光 Capture', f'已复制色值 {value}')
        except RuntimeError as exc:
            self._error(str(exc))

    def open_settings(self):
        if self._settings is not None:
            self._settings.show()
            self._settings.raise_()
            self._settings.activateWindow()
            return
        win = SettingsWindow(self.config)
        win.settings_saved.connect(self.apply_config)
        win.check_update_requested.connect(lambda: self.check_updates(manual=True))
        win.destroyed.connect(lambda: setattr(self, '_settings', None))
        self._settings = win
        win.show()

    def apply_config(self, config):
        previous = self.config
        if config.hotkeys != previous.hotkeys and not self.hotkeys.register(vars(config.hotkeys)):
            self._error('快捷键无法注册，原设置已保留。请检查按键格式和系统权限。')
            return
        try:
            config.save()
        except OSError:
            self.hotkeys.register(vars(previous.hotkeys))
            self._error('设置保存失败，原设置已保留。')
            return
        self.config = config
        self.tray.update_hotkeys(config.hotkeys)
        if config.launch_at_login != autostart.is_enabled() and not autostart.set_enabled(config.launch_at_login):
            self._error('设置已保存，但当前系统未能启用开机启动。')
        if self._settings:
            self._settings.accept()
        self.tray.notify('拾光 Capture', '设置已保存。')

    def check_updates(self, manual=True):
        if self._update_running:
            return
        self._update_running = True
        def worker():
            try:
                result = check_for_update(__version__)
            except Exception:
                result = '无法检查更新，请检查网络后重试。'
            self._update_bridge.finished.emit(result)
        threading.Thread(target=worker, daemon=True).start()

    def _on_update_result(self, info):
        self._update_running = False
        if self._closing:
            return
        message = info if isinstance(info, str) else (f'发现新版本 {info.version}，可从设置页打开发布页。' if info else f'当前已是最新版本 v{__version__}。')
        self.tray.notify('拾光 Capture', message)
        if self._settings:
            self._settings.set_update_result(message)

    def _error(self, message):
        self.tray.notify('拾光 Capture', message)
        if self._panel:
            self._panel.gloss.setText(message)
        if self._settings and self._settings.isVisible():
            self._settings.status.setText(message)

    def shutdown(self):
        if self._record_panel and self._record_panel.active:
            self._quit_after_recording = True
            self._record_panel.stop()
            return
        self._closing = True
        self.cancel_recognition()
        if self._scroll_session:
            self._scroll_session.abort()
        self.hotkeys.unregister()
        # The supervisor sees cancellation within 50ms and terminates its child.
        for bridge in list(self._recognition_bridges):
            bridge.cancel.set()
            bridge.thread.join(timeout=2)
        self._runner.close()
        self.app.quit()


def main(argv=None):
    multiprocessing.freeze_support()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName('shiguang-capture')
    app.setQuitOnLastWindowClosed(False)
    controller = AppController(app)
    controller.open_settings()
    return app.exec()
