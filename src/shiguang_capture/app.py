"""app.py — 应用装配：托盘 + 热键 + 捕获 + 贴图 + 取色 + 设置 + 更新。

设计约束（PRD）：
- 截图链路保持轻量，录屏模块不进入本进程（V2.0 独立入口）。
- 本地识别为默认；云端后端必须显式许可（ocr.assert_privacy_guard）。
"""
from __future__ import annotations

import logging
import sys
import threading
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from . import __version__
from . import autostart
from .capture.grabber import grab_region
from .capture.scroller import ScrollCaptureSession
from .capture.selector import RegionSelector
from .config import AppConfig
from .geometry import Rect
from .hotkeys import HotkeyManager
from .naming import next_seq, shot_name
from .ocr import OCRBackend, assert_privacy_guard, create_backend
from .ui.picker import ColorPickerOverlay
from .ui.pin_window import PinWindow
from .ui.scroll_preview import ScrollPreviewWindow
from .ui.settings_window import SettingsWindow
from .ui.tray import TrayIcon
from .updater import RELEASES_PAGE, UpdateInfo, check_for_update

log = logging.getLogger(__name__)


class _UpdateBridge(QObject):
    """工作线程 → Qt 主线程的结果桥。"""

    finished = Signal(object)  # UpdateInfo | None


class AppController:
    def __init__(self, qt_app: QApplication, config: AppConfig | None = None,
                 ocr_backend: OCRBackend | None = None) -> None:
        self.app = qt_app
        self.config = config or AppConfig.load()
        self._ocr_override = ocr_backend          # 测试注入；None 则惰性工厂创建
        self._ocr: OCRBackend | None = None       # 首次使用时加载（引擎初始化重）
        self._pins: list[PinWindow] = []
        self._pins_hidden = False
        self._selector: RegionSelector | None = None
        self._picker: ColorPickerOverlay | None = None
        self._settings: SettingsWindow | None = None
        self._scroll_session: ScrollCaptureSession | None = None
        self._scroll_preview: ScrollPreviewWindow | None = None
        self._last_image = None

        self.tray = TrayIcon()
        self.tray.action_capture.connect(self.start_region_capture)
        self.tray.action_scroll.connect(self.start_scroll_capture)
        self.tray.action_pick.connect(self.start_color_pick)
        self.tray.action_ocr.connect(self.ocr_recognize)
        self.tray.action_hide_pins.connect(self.toggle_pins)
        self.tray.action_settings.connect(self.open_settings)
        self.tray.action_check_update.connect(lambda: self.check_updates(manual=True))
        self.tray.action_quit.connect(self.shutdown)
        self.tray.show()

        self.hotkeys = HotkeyManager()
        self.hotkeys.bridge.triggered.connect(self._on_hotkey)
        self._register_hotkeys()

        self._update_bridge = _UpdateBridge()
        self._update_bridge.finished.connect(self._on_update_result)
        self._update_manual = False
        # 启动 3 秒后静默检查一次更新（仅发现新版本时打扰用户）
        QTimer.singleShot(3000, lambda: self.check_updates(manual=False))

    # ---------- 热键 ----------
    def _register_hotkeys(self) -> None:
        hk = self.config.hotkeys
        ok = self.hotkeys.register({
            "capture_region": hk.capture_region,
            "capture_fullscreen": hk.capture_fullscreen,
            "capture_scroll": hk.capture_scroll,
            "pin_last": hk.pin_last,
            "color_picker": hk.color_picker,
            "hide_all_pins": hk.hide_all_pins,
            "ocr_recognize": hk.ocr_recognize,
        })
        conflicts = hk.conflicts()
        if conflicts:
            log.warning("热键冲突: %s", conflicts)
            self.tray.notify("拾光 Capture", f"检测到热键冲突：{conflicts[0][0]} 与 {conflicts[0][1]}")
        if not ok:
            log.warning("全局热键未生效（pynput 缺失或系统权限不足）")

    def _on_hotkey(self, action: str) -> None:
        {
            "capture_region": self.start_region_capture,
            "capture_fullscreen": self.capture_fullscreen,
            "capture_scroll": self.start_scroll_capture,
            "pin_last": self.pin_from_clipboard,
            "color_picker": self.start_color_pick,
            "hide_all_pins": self.toggle_pins,
            "ocr_recognize": self.ocr_recognize,
        }.get(action, lambda: log.warning("未知热键动作: %s", action))()

    # ---------- 截图 ----------
    def start_region_capture(self) -> None:
        self._selector = RegionSelector()
        self._selector.region_selected.connect(self._on_region)
        self._selector.show()

    def _on_region(self, rect: Rect) -> None:
        image = grab_region(rect)
        if self.config.copy_to_clipboard:
            QGuiApplication.clipboard().setImage(image)
        path = self._save(image)
        self.tray.notify("拾光 Capture", f"截图已保存：{path.name}（已复制到剪贴板）")
        self._last_image = image

    def capture_fullscreen(self) -> None:
        from .capture.grabber import grab_fullscreen

        image = grab_fullscreen()
        if self.config.copy_to_clipboard:
            QGuiApplication.clipboard().setImage(image)
        path = self._save(image)
        self.tray.notify("拾光 Capture", f"全屏截图已保存：{path.name}")
        self._last_image = image

    def _save(self, image) -> Path:
        save_dir = Path(self.config.save_dir).expanduser()
        save_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        name = shot_name(now, next_seq(save_dir, now), self.config.image_format)
        path = save_dir / name
        image.save(str(path))
        return path

    def start_scroll_capture(self) -> None:
        if self._scroll_session is not None and self._scroll_session.is_running:
            self.tray.notify("拾光 Capture", "已有长截图任务进行中")
            return
        self._selector = RegionSelector()
        self._selector.region_selected.connect(self._start_scroll_session)
        self._selector.show()

    def _start_scroll_session(self, rect: Rect) -> None:
        session = ScrollCaptureSession(rect)
        preview = ScrollPreviewWindow()
        session.progressed.connect(
            lambda h, n: preview.update_progress(h, n))
        session.preview_ready.connect(
            lambda img: preview.update_progress(
                img.height(), session._frames, img))  # noqa: SLF001（同装配层读取）
        session.finished.connect(lambda img: self._on_scroll_finished(img, preview))
        session.failed.connect(lambda msg: self._on_scroll_failed(msg, preview))
        preview.abort_requested.connect(session.abort)
        preview.save_requested.connect(session.abort)
        self._scroll_session = session
        self._scroll_preview = preview
        preview.show()
        session.start()

    def _on_scroll_finished(self, image, preview: ScrollPreviewWindow) -> None:
        frames = self._scroll_session._frames if self._scroll_session else 0  # noqa: SLF001
        preview.mark_done(image.height(), frames)
        preview.update_progress(image.height(), frames, image)
        path = self._save(image)
        self._last_image = image
        self.tray.notify("拾光 Capture", f"长截图已保存：{path.name}（{image.height():,} px）")
        preview.save_btn.setText("关闭")
        preview.save_btn.clicked.connect(preview.close)

    def _on_scroll_failed(self, msg: str, preview: ScrollPreviewWindow) -> None:
        preview.close()
        self.tray.notify("拾光 Capture", f"长截图失败：{msg}")

    # ---------- OCR ----------
    @property
    def ocr(self) -> OCRBackend:
        """惰性创建识别后端（RapidOCR 首次加载 1-3s，不阻塞启动）。"""
        if self._ocr_override is not None:
            return self._ocr_override
        if self._ocr is None:
            self._ocr = create_backend(self.config.ocr_engine)
        return self._ocr

    def ocr_recognize(self) -> None:
        img = QGuiApplication.clipboard().image()
        if img.isNull():
            img = self._last_image
        if img is None or img.isNull():
            self.tray.notify("拾光 Capture", "剪贴板中没有图像，也没有最近截图")
            return
        from PySide6.QtCore import QBuffer, QIODevice

        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.ReadWrite)
        img.save(buf, "PNG")
        try:
            result = self.ocr.recognize(bytes(buf.data()))
        except Exception as exc:
            self.tray.notify("拾光 Capture", f"识别失败：{exc}")
            return
        if not result.text.strip():
            self.tray.notify("拾光 Capture", "未识别到文字内容")
            return
        QGuiApplication.clipboard().setText(result.text)
        preview = result.text.strip().splitlines()[0][:30]
        self.tray.notify(
            "拾光 Capture · OCR",
            f"{len(result.text)} 字 · {result.elapsed_ms}ms · {result.engine}（已复制）「{preview}…」",
        )

    def recognize(self, png_bytes: bytes, cloud_allowed: bool = False) -> str:
        """识别入口：隐私守卫在前，任何云端后端未获许可不得调用。"""
        assert_privacy_guard(self.ocr, cloud_allowed)
        return self.ocr.recognize(png_bytes).text

    # ---------- 贴图 ----------
    def pin_image(self, image) -> PinWindow:
        pin = PinWindow(image, self.config.pin_default_opacity)
        pin.closed.connect(lambda w: self._pins.remove(w) if w in self._pins else None)
        self._pins.append(pin)
        pin.show()
        return pin

    def pin_from_clipboard(self) -> None:
        img = QGuiApplication.clipboard().image()
        if img.isNull():
            img = self._last_image
        if img is None or img.isNull():
            self.tray.notify("拾光 Capture", "剪贴板中没有图像")
            return
        self.pin_image(img)

    def toggle_pins(self) -> None:
        self._pins_hidden = not self._pins_hidden
        for pin in self._pins:
            pin.setVisible(not self._pins_hidden)

    # ---------- 取色 ----------
    def start_color_pick(self) -> None:
        self._picker = ColorPickerOverlay(self.config.picker_format)
        self._picker.color_picked.connect(self._on_color)
        self._picker.show()

    def _on_color(self, value: str) -> None:
        QGuiApplication.clipboard().setText(value)
        self.tray.notify("拾光 Capture", f"已复制色值 {value}")

    # ---------- 设置 ----------
    def open_settings(self) -> None:
        if self._settings is not None:
            self._settings.raise_()
            self._settings.activateWindow()
            return
        win = SettingsWindow(self.config)
        win.settings_saved.connect(self.apply_config)
        win.check_update_requested.connect(lambda: self.check_updates(manual=True))
        win.destroyed.connect(lambda: setattr(self, "_settings", None))
        self._settings = win
        win.show()

    def apply_config(self, cfg: AppConfig) -> None:
        """设置保存：落盘 + 热键重注册 + 自启动同步，一次完成。"""
        self.config = cfg
        cfg.save()
        self._register_hotkeys()
        if cfg.launch_at_login != autostart.is_enabled():
            if autostart.set_enabled(cfg.launch_at_login):
                log.info("开机自启动已%s", "开启" if cfg.launch_at_login else "关闭")
            elif cfg.launch_at_login:
                self.tray.notify("拾光 Capture", "当前平台暂不支持设置开机自启动")
        self.tray.notify("拾光 Capture", "设置已保存并生效")

    # ---------- 更新 ----------
    def check_updates(self, manual: bool) -> None:
        self._update_manual = manual

        def worker() -> None:
            info = check_for_update(__version__)
            self._update_bridge.finished.emit(info)

        threading.Thread(target=worker, daemon=True).start()

    def _on_update_result(self, info: UpdateInfo | None) -> None:
        if info is not None:
            text = f"发现新版本 {info.version}"
            self.tray.notify("拾光 Capture · 有更新", f"{text}，前往 Releases 下载")
            QGuiApplication.clipboard().setText(info.url)
            log.info("%s: %s（链接已复制）", text, info.url)
        elif self._update_manual:
            self.tray.notify("拾光 Capture", f"已是最新版本 v{__version__}")
        if self._settings is not None:
            if info is not None:
                self._settings.set_update_result(f"发现新版本 {info.version}（链接已复制到剪贴板）")
            else:
                self._settings.set_update_result(f"已是最新 v{__version__} · 更新发布于 {RELEASES_PAGE}")

    # ---------- 生命周期 ----------
    def shutdown(self) -> None:
        self.hotkeys.unregister()
        self.config.save()
        self.app.quit()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("shiguang-capture")
    app.setQuitOnLastWindowClosed(False)  # 托盘常驻
    controller = AppController(app)
    _ = controller  # 防 GC
    return app.exec()
