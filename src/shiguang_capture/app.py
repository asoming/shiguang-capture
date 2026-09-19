"""app.py — 应用装配：托盘 + 热键 + 捕获 + 贴图 + 取色。

设计约束（PRD）：
- 截图链路保持轻量，录屏模块不进入本进程（V2.0 独立入口）。
- 本地识别为默认；云端后端必须显式许可（ocr.assert_privacy_guard）。
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from .capture.grabber import grab_region
from .capture.selector import RegionSelector
from .config import AppConfig
from .geometry import Rect
from .hotkeys import HotkeyManager
from .naming import next_seq, shot_name
from .ocr import MockOCRBackend, OCRBackend, assert_privacy_guard
from .ui.picker import ColorPickerOverlay
from .ui.pin_window import PinWindow
from .ui.tray import TrayIcon

log = logging.getLogger(__name__)


class AppController:
    def __init__(self, qt_app: QApplication, config: AppConfig | None = None,
                 ocr_backend: OCRBackend | None = None) -> None:
        self.app = qt_app
        self.config = config or AppConfig.load()
        self.ocr: OCRBackend = ocr_backend or MockOCRBackend()
        self._pins: list[PinWindow] = []
        self._pins_hidden = False
        self._selector: RegionSelector | None = None
        self._picker: ColorPickerOverlay | None = None

        self.tray = TrayIcon()
        self.tray.action_capture.connect(self.start_region_capture)
        self.tray.action_pick.connect(self.start_color_pick)
        self.tray.action_hide_pins.connect(self.toggle_pins)
        self.tray.action_quit.connect(self.shutdown)
        self.tray.show()

        self.hotkeys = HotkeyManager()
        self.hotkeys.bridge.triggered.connect(self._on_hotkey)
        hk = self.config.hotkeys
        self.hotkeys.register({
            "capture_region": hk.capture_region,
            "capture_fullscreen": hk.capture_fullscreen,
            "pin_last": hk.pin_last,
            "color_picker": hk.color_picker,
            "hide_all_pins": hk.hide_all_pins,
        })
        conflicts = hk.conflicts()
        if conflicts:
            log.warning("热键冲突: %s", conflicts)
            self.tray.notify("拾光 Capture", f"检测到热键冲突：{conflicts[0][0]} 与 {conflicts[0][1]}")

    # ---------- 热键 ----------
    def _on_hotkey(self, action: str) -> None:
        {
            "capture_region": self.start_region_capture,
            "capture_fullscreen": self.capture_fullscreen,
            "pin_last": self.pin_from_clipboard,
            "color_picker": self.start_color_pick,
            "hide_all_pins": self.toggle_pins,
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
        from .capture.grabber import grab_fullscreen, virtual_desktop_rect

        _ = virtual_desktop_rect  # 预留多屏模式选择
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

    # ---------- OCR ----------
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
            img = getattr(self, "_last_image", None)
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
