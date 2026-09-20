"""Real local OCR process -> workbench; no screen or real clipboard required."""
from __future__ import annotations
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('SHIGUANG_NO_HOTKEYS', '1')
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QFont
from shiguang_capture.app import AppController
from shiguang_capture.config import AppConfig
from shiguang_capture.selftest import sample_font


def main():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    controller = AppController(app, AppConfig())
    image = QImage(1001, 240, QImage.Format.Format_RGB888)
    image.fill(QColor('white'))
    painter = QPainter(image)
    painter.setPen(QColor('black'))
    painter.setFont(sample_font(36))
    painter.drawText(QRect(30, 40, 940, 150), Qt.AlignmentFlag.AlignLeft, 'Capture 00123\nLocal image review')
    painter.end()
    app.clipboard().setText('keep user content')
    controller._run_ocr_action(image)
    deadline = time.monotonic() + 60
    while controller._active_task and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.01)
    try:
        panel = controller._panel
        result = panel.source_edit.toPlainText()
        assert 'Capture' in result and '00123' in result, (result, panel.gloss.text())
        assert app.clipboard().text() == 'keep user content'
        assert panel._result.engine == 'rapidocr-local'
        print(f'real process OCR OK: {result!r}; {panel._result.elapsed_ms} ms; clipboard preserved')
        # A second task reuses the same process.
        child_pid = controller._runner._process.pid
        controller._run_ocr_action(image)
        deadline = time.monotonic() + 30
        while controller._active_task and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        assert controller._runner._process.pid == child_pid
        assert '00123' in panel.source_edit.toPlainText()
        print('warm process reuse OK')
    finally:
        controller.shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
