"""ui/scroll_preview.py — 滚动长截图实时预览窗（FR-1.16）。

显示拼接进度（高度、帧数、缩略图），用户可随时中止并保留已拼接部分。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .icon import make_icon

_MAX_PREVIEW_H = 420


class ScrollPreviewWindow(QWidget):
    abort_requested = Signal()
    save_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("拾光 Capture · 滚动长截图")
        self.setWindowIcon(make_icon())
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setMinimumWidth(300)

        lay = QVBoxLayout(self)
        self.status = QLabel("正在捕获第 1 帧…")
        lay.addWidget(self.status)

        self.thumb = QLabel("（拼接预览）")
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setMinimumHeight(200)
        self.thumb.setStyleSheet("background:#12151b;color:#69727f;border-radius:8px")
        lay.addWidget(self.thumb, 1)

        row = QHBoxLayout()
        self.abort_btn = QPushButton("中止并保留")
        self.abort_btn.clicked.connect(self.abort_requested.emit)
        self.save_btn = QPushButton("完成并保存")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self.save_requested.emit)
        row.addWidget(self.abort_btn)
        row.addWidget(self.save_btn)
        lay.addLayout(row)

    def closeEvent(self, event) -> None:
        self.abort_requested.emit()
        super().closeEvent(event)

    def update_progress(self, height: int, frames: int, image: QImage | None = None) -> None:
        self.status.setText(f"已拼接 {height:,} px · 第 {frames} 帧（滚动中…）")
        if image is not None and not image.isNull():
            pix = QPixmap.fromImage(image)
            if pix.height() > _MAX_PREVIEW_H:
                pix = pix.scaledToHeight(_MAX_PREVIEW_H, Qt.TransformationMode.SmoothTransformation)
            self.thumb.setPixmap(pix)

    def mark_done(self, height: int, frames: int) -> None:
        self.status.setText(f"✅ 完成：{height:,} px · 共 {frames} 帧")
        self.abort_btn.setEnabled(False)
        self.save_btn.setText("保存")
