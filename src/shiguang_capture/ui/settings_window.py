"""ui/settings_window.py — 设置主界面（五页签，保存即生效）。

常规 / 热键 / 贴图与取色 / 识别 / 关于与更新。
保存后通过 settings_saved 信号把新配置交回 AppController 统一应用。
"""
from __future__ import annotations
from copy import deepcopy
from .theme import STYLE

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSlider, QTabWidget, QVBoxLayout, QWidget,
)

from .. import __app_name__, __version__
from ..config import AppConfig
from ..updater import RELEASES_PAGE
from .icon import make_icon

_HOTKEY_FIELDS = [
    ("capture_region", "区域截图"),
    ("capture_fullscreen", "全屏截图"),
    ("capture_scroll", "滚动长截图"),
    ("pin_last", "贴图（剪贴板图像）"),
    ("color_picker", "取色器"),
    ("hide_all_pins", "隐藏 / 恢复全部贴图"),
    ("ocr_recognize", "OCR 识别（剪贴板 / 上次截图）"),
]


class SettingsWindow(QDialog):
    settings_saved = Signal(object)        # AppConfig
    check_update_requested = Signal()

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = deepcopy(config)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setStyleSheet(STYLE)
        self.setWindowTitle(f"{__app_name__} · 设置")
        self.setWindowIcon(make_icon())
        self.setMinimumWidth(680)
        self.resize(740, 560)
        self.setModal(False)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 20)
        root.setSpacing(18)
        root.addWidget(QLabel("拾光  /  偏好设置", objectName="brand"))
        root.addWidget(QLabel("让工具适应你的习惯。", objectName="title"))
        tabs = QTabWidget()
        tabs.addTab(self._build_general(), "常规")
        tabs.addTab(self._build_hotkeys(), "热键")
        tabs.addTab(self._build_pin_picker(), "贴图与取色")
        tabs.addTab(self._build_ocr(), "识别")
        tabs.addTab(self._build_about(), "关于与更新")
        root.addWidget(tabs)

        self.status = QLabel("设置仅在保存成功后生效。", objectName="muted")
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.close)
        save = QPushButton("保存", objectName="primary")
        save.setDefault(True)
        save.clicked.connect(self._on_save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

    # ================= 常规 =================
    def _build_general(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        dir_row = QHBoxLayout()
        self.save_dir_edit = QLineEdit(self._config.save_dir)
        browse = QPushButton("浏览…")
        browse.clicked.connect(self._pick_dir)
        dir_row.addWidget(self.save_dir_edit, 1)
        dir_row.addWidget(browse)
        form.addRow("截图保存目录", dir_row)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["png", "jpg"])
        self.format_combo.setCurrentText(self._config.image_format)
        form.addRow("图像格式", self.format_combo)

        self.clipboard_check = QCheckBox("截图后自动复制到剪贴板")
        self.clipboard_check.setChecked(self._config.copy_to_clipboard)
        self.clipboard_check.hide()
        form.addRow(QLabel("截图默认只复制；只有点击保存才会写入文件。", objectName="muted"))

        self.sound_check = QCheckBox("截图时播放快门声")
        self.sound_check.setChecked(self._config.play_shutter_sound)
        self.sound_check.hide()

        self.autostart_check = QCheckBox("开机自动启动")
        self.autostart_check.setChecked(self._config.launch_at_login)
        form.addRow(self.autostart_check)
        return w

    def _pick_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择截图保存目录", self.save_dir_edit.text())
        if d:
            self.save_dir_edit.setText(d)

    # ================= 热键 =================
    def _build_hotkeys(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self._hotkey_edits: dict[str, QLineEdit] = {}
        for attr, label in _HOTKEY_FIELDS:
            edit = QLineEdit(getattr(self._config.hotkeys, attr))
            edit.setPlaceholderText("如 f1 / ctrl+f1 / shift+alt+a")
            self._hotkey_edits[attr] = edit
            form.addRow(label, edit)
        self.hotkey_warn = QLabel("")
        self.hotkey_warn.setStyleSheet("color:#ff6b6e")
        self.hotkey_warn.setWordWrap(True)
        form.addRow(self.hotkey_warn)
        hint = QLabel("修饰键：ctrl / shift / alt；功能键：f1-f12；用 + 连接。保存时自动检测冲突。")
        hint.setStyleSheet("color:#888")
        hint.setWordWrap(True)
        form.addRow(hint)
        return w

    # ================= 贴图与取色 =================
    def _build_pin_picker(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(round(self._config.pin_default_opacity * 100))
        self.opacity_label = QLabel(f"{self.opacity_slider.value()}%")
        self.opacity_slider.valueChanged.connect(lambda v: self.opacity_label.setText(f"{v}%"))
        row = QHBoxLayout()
        row.addWidget(self.opacity_slider, 1)
        row.addWidget(self.opacity_label)
        form.addRow("贴图默认透明度", row)

        self.picker_combo = QComboBox()
        self.picker_combo.addItems(["hex", "rgb", "hsv"])
        self.picker_combo.setCurrentText(self._config.picker_format)
        form.addRow("取色复制格式", self.picker_combo)
        return w

    # ================= 识别 =================
    def _build_ocr(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self.ocr_combo = QComboBox()
        self.ocr_combo.addItem("本地引擎（默认 · 永久免费 · 图像不出本机）", "local")
        self.ocr_combo.setEnabled(False)
        idx = self.ocr_combo.findData(self._config.ocr_engine)
        self.ocr_combo.setCurrentIndex(max(idx, 0))
        form.addRow("识别引擎", self.ocr_combo)

        self.lang_combo = QComboBox()
        self.lang_combo.addItem("自动判定（中↔英互译）", "auto")
        self.lang_combo.addItem("翻译为中文", "zh")
        self.lang_combo.addItem("翻译为英文", "en")
        li = self.lang_combo.findData(getattr(self._config, "target_lang", "auto"))
        self.lang_combo.setCurrentIndex(max(li, 0))
        form.addRow("翻译目标语言", self.lang_combo)

        self.cloud_translate_check = QCheckBox("允许云端翻译（默认关闭 · 文本将离开本机）")
        self.cloud_translate_check.setChecked(
            getattr(self._config, "allow_cloud_translate", False))
        self.cloud_translate_check.hide()

        # 离线翻译模型状态
        self.translate_status = QLabel("")
        self.translate_status.setWordWrap(True)
        refresh = QPushButton("检测离线翻译能力")
        refresh.clicked.connect(self._refresh_translate_status)
        row = QHBoxLayout()
        row.addWidget(refresh)
        row.addWidget(self.translate_status, 1)
        form.addRow("翻译引擎", row)

        note = QLabel(
            "隐私红线：选择本地引擎时，识别与翻译全程在本机完成，不上传任何图像或文本。\n"
            "翻译为实验能力。未单独安装 Argos 和语言模型时，只提供术语替换；本界面不会自动下载模型。"
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#888")
        form.addRow(note)
        self._refresh_translate_status()
        return w

    def _refresh_translate_status(self) -> None:
        """检测翻译后端可用性并回显。"""
        try:
            from ..translate import argos_available

            if argos_available():
                self.translate_status.setText("✅ 离线神经翻译已就绪（argos-local）")
                return
        except Exception:  # noqa: BLE001
            pass
        self.translate_status.setText("⚠️ 未检测到离线模型，当前使用术语词典兜底")

    # ================= 关于与更新 =================
    def _build_about(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        title = QLabel(f"<b>{__app_name__}</b> v{__version__}")
        lay.addWidget(title)
        lay.addWidget(QLabel("屏幕信息捕获与再利用工具 · MIT License"))
        lay.addWidget(QLabel(f'<a href="{RELEASES_PAGE}">GitHub Releases</a>'))
        for lbl in w.findChildren(QLabel):
            lbl.setOpenExternalLinks(True)

        row = QHBoxLayout()
        self.update_btn = QPushButton("检查更新")
        self.update_btn.clicked.connect(self._on_check_update)
        self.update_status = QLabel("尚未检查")
        row.addWidget(self.update_btn)
        row.addWidget(self.update_status, 1)
        lay.addLayout(row)
        lay.addStretch(1)
        return w

    def _on_check_update(self) -> None:
        self.update_btn.setEnabled(False)
        self.update_status.setText("正在检查…")
        self.check_update_requested.emit()

    def set_update_result(self, text: str) -> None:
        """由 AppController 回填检查结论。"""
        self.update_btn.setEnabled(True)
        self.update_status.setText(text)

    # ================= 保存 =================
    def _on_save(self) -> None:
        cfg = deepcopy(self._config)
        cfg.save_dir = self.save_dir_edit.text().strip() or cfg.save_dir
        cfg.image_format = self.format_combo.currentText()
        cfg.copy_to_clipboard = self.clipboard_check.isChecked()
        cfg.play_shutter_sound = self.sound_check.isChecked()
        cfg.launch_at_login = self.autostart_check.isChecked()
        cfg.pin_default_opacity = self.opacity_slider.value() / 100
        cfg.picker_format = self.picker_combo.currentText()
        cfg.ocr_engine = self.ocr_combo.currentData()
        cfg.target_lang = self.lang_combo.currentData()
        cfg.allow_cloud_translate = False
        for attr, edit in self._hotkey_edits.items():
            setattr(cfg.hotkeys, attr, edit.text().strip().lower() or getattr(cfg.hotkeys, attr))

        conflicts = cfg.hotkeys.conflicts()
        if conflicts:
            names = "、".join(f"{a} ↔ {b}" for a, b in conflicts)
            self.hotkey_warn.setText(f"热键冲突：{names}。请修改后重新保存。")
            self.status.setText("设置未保存，原快捷键仍可使用。")
            self._switch_to_tab(1)
            return
        self.settings_saved.emit(cfg)

    def _switch_to_tab(self, index: int) -> None:
        tabs = self.findChild(QTabWidget)
        if tabs:
            tabs.setCurrentIndex(index)
