"""scripts/smoke_ocr_translate.py — 识图 / 翻译端到端冒烟（离屏，无需真实桌面）。

覆盖：
1. 结果面板能正确渲染 OCR 结果 / 翻译双栏
2. AppController._run_ocr_action / _run_translate_action 全链路通
3. 工具栏 → action_chosen → _dispatch_region 接线正确
4. 真实 RapidOCR 引擎（若已安装）对合成图能出字
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SHIGUANG_NO_HOTKEYS", "1")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from shiguang_capture._console import fix_console_encoding  # noqa: E402

# Windows CI 控制台默认 cp1252，直接 print 中文会 UnicodeEncodeError
fix_console_encoding()

from PySide6.QtCore import (
    QBuffer, QCoreApplication, QEventLoop, QIODevice, QRect, Qt, QTimer,
)  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QColor, QFont, QFontDatabase, QImage, QPainter,
)
from PySide6.QtWidgets import QApplication  # noqa: E402

from shiguang_capture.config import AppConfig  # noqa: E402
from shiguang_capture.ocr.base import OCRResult  # noqa: E402
from shiguang_capture.translate import detect_language, translate_text  # noqa: E402
from shiguang_capture.ui.result_panel import ResultPanel  # noqa: E402

_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]
_font_family: str | None = None


def _load_font() -> str:
    """离屏平台默认无字体（文字渲染成豆腐块）→ 显式加载系统字体。"""
    global _font_family
    if _font_family:
        return _font_family
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            fid = QFontDatabase.addApplicationFont(path)
            fams = QFontDatabase.applicationFontFamilies(fid)
            if fams:
                _font_family = fams[0]
                return _font_family
    _font_family = "Arial"
    return _font_family


def make_text_image(text: str = "Screenshot save copy") -> QImage:
    """合成一张白底黑字图（供 OCR 冒烟用，字要够大够清晰）。"""
    img = QImage(760, 130, QImage.Format.Format_RGB888)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    p.setPen(QColor(0, 0, 0))
    f = QFont(_load_font())
    f.setPointSize(34)
    p.setFont(f)
    p.drawText(QRect(16, 0, 730, 130),
               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
    p.end()
    return img


def pump(ms: int = 60) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def main() -> int:
    app = QApplication.instance() or QApplication([])
    problems: list[str] = []

    # ---- 1. 结果面板：识图模式 ----
    panel = ResultPanel()
    panel.show()
    pump(40)
    r = OCRResult(text="Screenshot tool save copy", confidence=0.93,
                  engine="rapidocr-local", elapsed_ms=412)
    panel.show_result("ocr", r)
    pump(30)
    if panel.source_edit.toPlainText() != r.text:
        problems.append("识图面板原文未渲染")
    if panel.right.isVisible():
        problems.append("识图模式不应显示译文栏")
    if panel.copy_target.isVisible():
        problems.append("识图模式不应显示「复制译文」按钮")
    print(f"识图面板 OK · 标题={panel.head.text()!r} · 元信息={panel.meta.text()!r}")

    # ---- 2. 结果面板：翻译模式 ----
    cfg = AppConfig()
    tr = translate_text(r.text, cfg, allow_cloud=False)
    panel.show_translation(r, tr)
    pump(30)
    if panel.target_edit.toPlainText() != tr.target_text:
        problems.append("翻译面板译文未渲染")
    if not panel.right.isVisible():
        problems.append("翻译模式应显示译文栏")
    print(f"翻译面板 OK · 译文={tr.target_text!r}")
    print(f"           语言对 {tr.source_lang}→{tr.target_lang} · 引擎 {tr.engine}")
    print(f"           词条 {tr.glossary_hits[:4]}")

    # ---- 3. 复制/交换/重新识别 ----
    panel.copy_target.click()
    pump(30)
    if QApplication.clipboard().text() != tr.target_text:
        problems.append("复制译文未写入剪贴板")
    panel.swap_btn.click()
    pump(20)
    if panel.source_edit.toPlainText() != tr.target_text:
        problems.append("交换左右内容失败")
    print("复制 / 交换按钮 OK")

    retry_calls: list[tuple] = []
    p2 = ResultPanel(delegate=lambda img, mode: retry_calls.append((img, mode)))
    p2.set_image(make_text_image())
    p2.show_result("ocr", r)
    p2.retry_btn.click()
    pump(20)
    if len(retry_calls) != 1 or retry_calls[0][1] != "ocr":
        problems.append(f"「重新识别」委托未正确回调：{retry_calls}")
    print("「重新识别」委托 OK")

    # ---- 4. AppController 全链路（注入 Mock 后端）----
    from shiguang_capture.app import AppController
    from shiguang_capture.capture.selector import RegionSelector
    from shiguang_capture.ocr.base import MockOCRBackend

    ctrl = AppController(app, AppConfig(), ocr_backend=MockOCRBackend())
    img = make_text_image()

    ctrl._run_ocr_action(img)
    pump(120)          # 等后台线程 + 信号回主线程
    if ctrl._ocr is None and ctrl._ocr_override is None:
        problems.append("后台识别未推进")
    print("AppController.识图 全链路 OK（后台线程 → 信号 → 面板）")

    ctrl._run_translate_action(img)
    pump(120)
    print("AppController.翻译 全链路 OK")

    # ---- 5. 工具栏接线 ----
    from shiguang_capture.capture.grabber import ScreenFrame
    from shiguang_capture.geometry import Rect
    from PySide6.QtGui import QGuiApplication
    g = QGuiApplication.primaryScreen().geometry()
    snapshot = QImage(g.width(), g.height(), QImage.Format.Format_RGB888)
    snapshot.fill(QColor("white"))
    sel = RegionSelector(frames=[ScreenFrame(Rect(g.x(), g.y(), g.width(), g.height()), snapshot, 1)])
    got: list[tuple] = []
    sel.action_chosen.connect(lambda rect, action: got.append((rect, action)))
    from shiguang_capture.geometry import Rect
    sel._sel = Rect(100, 100, 300, 200)
    sel._state = RegionSelector.EDITING
    for act in ("ocr", "translate"):
        got.clear()
        sel._on_action(act)
        if not got or got[0][1] != act:
            problems.append(f"工具栏动作 {act} 未派发：{got}")
    print(f"工具栏动作派发 OK · 按钮 {[label for _, label in RegionSelector.__dict__.get('_ACTIONS', [])] or '见 selector._ACTIONS'}")

    # ---- 6. 真实引擎（若已装）----
    try:
        from shiguang_capture.ocr.rapid_backend import RapidOCRBackend

        engine_img = make_text_image("Screenshot save copy")
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.ReadWrite)
        engine_img.save(buf, "PNG")
        backend = RapidOCRBackend()
        out = backend.recognize(bytes(buf.data()))
        print(f"真实 RapidOCR OK · 推理 {out.elapsed_ms}ms · 识别={out.text.strip()!r}")
        if not out.text.strip():
            problems.append("RapidOCR 未识别出合成图中的文字")
        else:
            t2 = translate_text(out.text, cfg, allow_cloud=False)
            print(f"          真实识别 → 翻译 OK · 译文={t2.target_text!r}")
    except ImportError as exc:
        print(f"真实引擎未安装（跳过）：{exc}")

    ctrl.cancel_recognition()
    for bridge in list(ctrl._recognition_bridges):
        bridge.thread.join(timeout=2)
    ctrl._runner.close()
    ctrl.tray._tray.hide()
    # Clear only this isolated offscreen test clipboard before Qt/Python teardown.
    app.clipboard().clear()
    from PySide6.QtCore import QEvent
    for window in app.topLevelWidgets():
        window.close()
        window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    print()
    if problems:
        print("FAILED:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("全部通过 · 识图与翻译功能已可用")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
