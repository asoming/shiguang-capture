"""ui/result_panel.py — 识图 / 翻译结果面板（QQ 截图同款交互）。

QQ 截图点「屏幕识图 / 翻译」后，不会只弹个通知，而是弹出一个
可复制、可编辑的结果窗口。本模块实现该窗口：

- 左：原文（OCR 结果，可选中复制）
- 右：译文（翻译模式；识图模式隐藏）
- 底：重新识别 / 复制原文 / 复制译文 / 交换 / 关闭
- 状态栏：引擎、耗时、字符数、语言对
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication, QTextOption
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QSplitter,
    QVBoxLayout, QWidget,
)

_STYLE = """
QWidget#root{background:#141821}
QLabel#head{color:#e9edf3;font-size:13px;font-weight:600}
QLabel#meta{color:#8b96a8;font-size:11px}
QLabel#colhead{color:#8b96a8;font-size:11px;font-weight:600}
QPlainTextEdit{background:#1a1f28;color:#e9edf3;border:1px solid #2b3342;
  border-radius:6px;padding:8px;font-size:13px;
  selection-background-color:#364052}
QPushButton{color:#e9edf3;background:#2b3342;border:none;border-radius:6px;
  padding:6px 14px;font-size:12px}
QPushButton:hover{background:#364052}
QPushButton#primary{background:#5f80f5}
QPushButton#primary:hover{background:#7190ff}
QPushButton#ghost{background:transparent;color:#8b96a8}
QPushButton#ghost:hover{background:#2b3342;color:#e9edf3}
"""


class ResultPanel(QWidget):
    """识别 / 翻译结果窗口。"""

    closed = Signal()

    def __init__(self, delegate=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._delegate = delegate
        self._image = None
        self._mode = "ocr"
        self._kind = "ocr"
        self._result = None
        self._translation = None

        self.setWindowTitle("拾光 Capture · 识别结果")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowMinMaxButtonsHint
        )
        self.setStyleSheet(_STYLE)
        self.resize(720, 420)

        root = QWidget(objectName="root")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)
        box = QVBoxLayout(root)
        box.setContentsMargins(16, 14, 16, 14)
        box.setSpacing(10)

        # 标题行
        head_row = QHBoxLayout()
        self.head = QLabel("识别结果", objectName="head")
        self.meta = QLabel("", objectName="meta")
        head_row.addWidget(self.head)
        head_row.addStretch(1)
        head_row.addWidget(self.meta)
        box.addLayout(head_row)

        # 正文区：原文 | 译文
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(10)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(6)
        lv.addWidget(QLabel("原文", objectName="colhead"))
        self.source_edit = QPlainTextEdit()
        self.source_edit.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        lv.addWidget(self.source_edit)
        self.splitter.addWidget(left)

        self.right = QWidget()
        rv = QVBoxLayout(self.right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(6)
        rv.addWidget(QLabel("译文", objectName="colhead"))
        self.target_edit = QPlainTextEdit()
        self.target_edit.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        rv.addWidget(self.target_edit)
        self.splitter.addWidget(self.right)
        self.splitter.setSizes([360, 360])
        box.addWidget(self.splitter, 1)

        # 术语/提示行
        self.gloss = QLabel("", objectName="meta")
        self.gloss.setWordWrap(True)
        box.addWidget(self.gloss)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.copy_source = QPushButton("复制原文")
        self.copy_target = QPushButton("复制译文")
        self.swap_btn = QPushButton("⇄ 交换")
        self.retry_btn = QPushButton("重新识别", objectName="ghost")
        self.close_btn = QPushButton("关闭", objectName="ghost")
        for b in (self.copy_source, self.copy_target, self.swap_btn):
            b.setObjectName("primary")
        btn_row.addWidget(self.retry_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self.swap_btn)
        btn_row.addWidget(self.copy_source)
        btn_row.addWidget(self.copy_target)
        btn_row.addWidget(self.close_btn)
        box.addLayout(btn_row)

        self.copy_source.clicked.connect(self._copy_source)
        self.copy_target.clicked.connect(self._copy_target)
        self.swap_btn.clicked.connect(self._swap)
        self.retry_btn.clicked.connect(self._retry)
        self.close_btn.clicked.connect(self.close)

        self._apply_mode("ocr")

    # ---------------- 对外 API ----------------
    def show_result(self, kind: str, result) -> None:
        """识图模式：只显示原文。kind ∈ {ocr, translate}。"""
        self._kind = kind
        self._result = result
        self._translation = None
        self.head.setText("识别结果" if kind == "ocr" else "翻译结果")
        self.source_edit.setPlainText(result.text)
        if kind == "translate":
            self._apply_mode("translate")
        else:
            self._apply_mode("ocr")
        conf = getattr(result, "confidence", 0.0)
        self.meta.setText(
            f"{result.engine} · {result.elapsed_ms}ms · {len(result.text)} 字 "
            f"· 置信度 {conf * 100:.0f}%")
        self.gloss.setText("原文已自动复制到剪贴板。可直接在左侧选中任意段落复制。")

    def show_translation(self, result, translation) -> None:
        """翻译模式：原文 + 译文双栏。"""
        self._kind = "translate"
        self._result = result
        self._translation = translation
        self.head.setText("翻译结果")
        self.source_edit.setPlainText(result.text)
        self.target_edit.setPlainText(translation.target_text)
        self._apply_mode("translate")
        lang = f"{translation.source_lang} → {translation.target_lang}"
        self.meta.setText(
            f"{translation.engine} · {translation.elapsed_ms}ms · {lang} "
            f"· 识别 {result.elapsed_ms}ms")
        if translation.glossary_hits:
            pairs = "、".join(f"{a}→{b}" for a, b in translation.glossary_hits[:8])
            self.gloss.setText(f"命中词条：{pairs}　（译文已复制到剪贴板）")
        elif getattr(translation, "degraded", False):
            self.gloss.setText(
                "⚠️ 术语词典模式：译文为逐词替换，完整性有限。"
                "在「设置 → 识别」中安装离线神经翻译模型可获得完整译文。")
        else:
            self.gloss.setText("离线神经翻译完成，译文已复制到剪贴板。")

    # ---------------- 内部 ----------------
    def _apply_mode(self, mode: str) -> None:
        self._mode = mode
        is_tr = mode == "translate"
        self.right.setVisible(is_tr)
        self.copy_target.setVisible(is_tr)
        self.swap_btn.setVisible(is_tr)

    def _copy_source(self) -> None:
        QGuiApplication.clipboard().setText(self.source_edit.toPlainText())
        self.gloss.setText("原文已复制到剪贴板。")

    def _copy_target(self) -> None:
        QGuiApplication.clipboard().setText(self.target_edit.toPlainText())
        self.gloss.setText("译文已复制到剪贴板。")

    def _swap(self) -> None:
        s, t = self.source_edit.toPlainText(), self.target_edit.toPlainText()
        self.source_edit.setPlainText(t)
        self.target_edit.setPlainText(s)
        self.gloss.setText("已交换左右内容。")

    def _retry(self) -> None:
        if self._delegate and self._image is not None:
            self._delegate(self._image, self._kind)

    def closeEvent(self, e) -> None:  # noqa: N802
        self.closed.emit()
        super().closeEvent(e)

    # ---------------- 供委托调用 ----------------
    def set_image(self, image) -> None:
        self._image = image


class _PanelHost(QWidget):
    """保留：给后续多结果标签页用（V1.2）。"""
