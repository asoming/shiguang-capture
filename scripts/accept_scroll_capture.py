"""Native scroll capture acceptance against an opaque synthetic document.

Run on a desktop: PYTHONPATH=src python scripts/accept_scroll_capture.py OUTPUT
Only the test document is captured. Test-only input simulates a person scrolling;
the application must stay idle until that input and wait for explicit completion.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time

import numpy as np
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QCursor, QFont, QPainter
from pynput.mouse import Controller
from PySide6.QtWidgets import QApplication, QWidget

from shiguang_capture.capture.scroller import ScrollCaptureSession, array_to_qimage, qimage_to_array
from shiguang_capture.geometry import Rect
from shiguang_capture.ui.scroll_preview import ScrollPreviewWindow


def main(destination, outside=False):
    app = QApplication([])
    area = app.primaryScreen().availableGeometry()
    density = app.primaryScreen().devicePixelRatio()
    width, height = min(420, area.width()-80), min(640, area.height()-120)
    total = height+1200
    rng = np.random.default_rng(51)
    rows = rng.integers(180, 255, (round(total*density), 1, 3), dtype=np.uint8)
    page = array_to_qimage(np.repeat(rows, round(width*density), axis=1))
    painter = QPainter(page)
    painter.setPen(QColor('#123456'))
    painter.setFont(QFont('DejaVu Sans', 20))
    for y in range(60, total, 70):
        painter.drawText(round(25*density), round(y*density), f'Sample document / line {y//70+1:02d}')
    painter.end()

    class Document(QWidget):
        def __init__(self):
            super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
            self.offset = self.wheels = 0
            self.setWindowTitle('Shiguang synthetic scroll document')
            self.setGeometry(area.x()+min(320, area.width()-width-40), area.y()+60, width, height)

        def paintEvent(self, event):
            painter = QPainter(self)
            painter.drawImage(self.rect(), page, QRect(0, round(self.offset*density), page.width(), round(height*density)))

        def wheelEvent(self, event):
            self.wheels += 1
            self.offset = min(total-height, max(0, self.offset-round(event.angleDelta().y()/120)*65))
            self.update()
            event.accept()

    def pump(seconds):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.005)

    document = Document()
    document.show()
    document.raise_()
    document.activateWindow()
    pump(.6)
    origin = document.mapToGlobal(QPoint(0, 0))
    session = ScrollCaptureSession(Rect(origin.x(), origin.y(), width, height), settle_ms=160)
    preview = ScrollPreviewWindow()
    selection = Rect(origin.x(), origin.y(), width, height)
    preview.anchor_to(selection, Rect(area.x(), area.y(), area.width(), area.height()))
    if not outside:
        # Force the thumbnail inside the selection to verify clean exclusion.
        preview.move(origin.x()+width//2-preview.width()//2, origin.y()+height//2-preview.height()//2)
    session.frame_capturing.connect(preview.prepare_capture)
    session.frame_captured.connect(preview.restore_after_capture)
    session.preview_ready.connect(preview.update_image)
    session.progressed.connect(preview.update_progress)
    session.excluded_rect = Rect(preview.x(), preview.y(), preview.width(), preview.height())
    session.hint_changed.connect(preview.status.setText)
    preview.save_requested.connect(session.complete)
    results, errors = [], []
    session.finished.connect(results.append)
    session.failed.connect(errors.append)
    out = Path(destination)
    out.mkdir(parents=True, exist_ok=True)
    original_cursor = QCursor.pos()
    mouse = Controller()
    report = {'status': 'failed', 'density': density, 'preview': 'left' if outside else 'inside'}
    try:
        session.start()
        first = qimage_to_array(page)[:round(height*density)]
        assert np.array_equal(session._acc, first), 'Test document is obstructed before capture'
        pump(1)
        assert document.wheels == 0 and document.offset == 0
        assert session.is_running and not results
        assert QCursor.pos() == original_cursor, 'Application moved the pointer'
        report['idle_wait_respected'] = True
        target = QPoint(origin.x()+20, origin.y()+height//2)
        QCursor.setPos(target)
        while document.offset < total-height:
            frames = session._frames
            mouse.scroll(0, -2)  # Test-only simulation of the user's wheel.
            deadline = time.monotonic()+3
            while session._frames == frames and time.monotonic() < deadline:
                pump(.02)
            assert session._frames > frames, 'Manual wheel did not update the long image'
            assert QCursor.pos() == target, 'Application moved the pointer after capture'
        pump(1)
        assert session.is_running and not results, 'Capture ended without the user finishing'
        report['bottom_wait_respected'] = True
        preview.save_btn.click()
        deadline = time.monotonic()+3
        while session.is_running and time.monotonic() < deadline:
            pump(.02)
        assert not session.is_running, 'Explicit completion did not finish capture'
        report.update(wheel_events=document.wheels, frames=session._frames, offset=document.offset, errors=errors)
        assert not errors, errors
        assert preview.thumb.pixmap() is not None
        assert preview.thumb.pixmap().width() <= 154
        assert len(results) == 1 and document.offset == total-height
        assert document.wheels > 0 and session._frames > 1
        results[0].save(str(out/'actual.png'))
        page.save(str(out/'expected.png'))
        np.testing.assert_array_equal(qimage_to_array(results[0]), qimage_to_array(page))
        report.update(status='passed', pixel_exact=True, size=[results[0].width(), results[0].height()])
    finally:
        session.abort()
        preview.hide()
        preview.close()
        document.close()
        QCursor.setPos(original_cursor)
        (out/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main(sys.argv[1], '--outside' in sys.argv)
