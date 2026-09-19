"""ui/busy.py — 轻量「处理中」浮层。

识别引擎首次加载 1-3s，用户点了按钮必须有即时反馈，
否则会误判为「按钮没反应 / 功能没用」。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

_STYLE = """
QWidget#busy{background:#1a1f28;border:1px solid #364052;border-radius:10px}
QLabel#msg{color:#e9edf3;font-size:13px}
QLabel#hint{color:#8b96a8;font-size:11px}
"""


class BusyIndicator(QWidget):
    """居中的无模态提示浮层（不抢焦点、不阻塞主线程）。"""

    def __init__(self, message: str = "处理中…",
                 hint: str = "首次识别需加载本地引擎，约 1-3 秒") -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet(_STYLE)

        root = QWidget(objectName="busy")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(root)
        inner = QVBoxLayout(root)
        inner.setContentsMargins(24, 18, 24, 18)
        inner.setSpacing(6)
        self.label = QLabel(message, objectName="msg")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(self.label)
        if hint:
            h = QLabel(hint, objectName="hint")
            h.setAlignment(Qt.AlignmentFlag.AlignCenter)
            inner.addWidget(h)

        self._dots = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._base_msg = message

    def _tick(self) -> None:
        self._dots = (self._dots + 1) % 4
        self.label.setText(self._base_msg + "…" if self._dots == 0
                           else self._base_msg + "…" + "·" * self._dots)

    def showEvent(self, e) -> None:  # noqa: N802
        super().showEvent(e)
        self.adjustSize()
        scr = self.screen().availableGeometry() if self.screen() else None
        if scr is not None:
            self.move(scr.center().x() - self.width() // 2,
                      scr.center().y() - self.height() // 2)
        self._timer.start(320)

    def closeEvent(self, e) -> None:  # noqa: N802
        self._timer.stop()
        super().closeEvent(e)
