"""Native changing-pixel evidence for the live recording monitor."""
import json
import multiprocessing
from pathlib import Path
import sys
import time


def verify_live_preview(app, destination, window=False):
    from PySide6.QtCore import Qt, QPoint
    from PySide6.QtWidgets import QWidget
    from ..geometry import Rect
    from ..ui.record_panel import RecordPanel

    out = Path(destination)
    out.mkdir(parents=True, exist_ok=True)
    source = QWidget(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
    source.setWindowTitle('Shiguang live preview test source')
    source.setGeometry(app.primaryScreen().availableGeometry().x()+30,
                       app.primaryScreen().availableGeometry().y()+30, 220, 160)
    source.setStyleSheet('background:#D02020;')
    source.show()
    panel = RecordPanel(str(out))
    frames = []
    panel.live_preview.frame_ready.connect(lambda image, size: frames.append((time.monotonic(), image.pixelColor(image.width()//2, image.height()//2).name(), size)))

    def pump(seconds):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)

    def until(predicate, seconds=18):
        deadline = time.monotonic()+seconds
        while not predicate():
            if time.monotonic() > deadline:
                raise AssertionError(f'Live preview timed out: {panel.preview.text()}, frames={frames[-4:]}')
            pump(.02)

    def matches(color):
        return bool(frames) and all(abs(int(frames[-1][1][i:i+2], 16)-int(color[i:i+2], 16)) <= 12 for i in (1, 3, 5))

    report = {'status': 'failed', 'mode': 'window' if window else 'region'}
    try:
        pump(.2)
        location = source.mapToGlobal(QPoint(10, 10))
        panel.set_region(Rect(location.x(), location.y(), 180, 120))
        if window:
            panel.region = None
            panel.window_title = source.windowTitle()
        panel.show()
        source.raise_()
        until(lambda: matches('#d02020'))
        first_process = panel.live_preview.process
        started = time.monotonic()
        source.setStyleSheet('background:#2040D0;')
        until(lambda: matches('#2040d0'), 3)
        report['change_latency_seconds'] = round(time.monotonic()-started, 3)
        assert panel.isVisible(), 'Live preview must never hide the panel'
        if not window:
            assert frames[-1][2] == (round(180*source.devicePixelRatioF()), round(120*source.devicePixelRatioF()))
        before = len(frames)
        pump(.7)
        report['frames_in_700ms'] = len(frames)-before
        assert report['frames_in_700ms'] >= 3, 'Monitor is not continuously receiving frames'
        panel.grab().save(str(out/'recording-live.png'))
        panel.tabs.setCurrentIndex(1)
        assert panel.live_preview.process is None and not first_process.is_alive()
        panel.tabs.setCurrentIndex(0)
        until(lambda: panel.live_preview.process is not None and panel.preview_badge.text() == '● 实时预览')
        assert panel.live_preview.process is not first_process
        panel.hide()
        assert panel.live_preview.process is None
        source.setStyleSheet('background:#D02020;')
        panel.show()
        until(lambda: matches('#d02020'))
        report.update(status='passed', source_size=frames[-1][2], hidden_process_stopped=True,
                      file_page_process_stopped=True, resumed_with_fresh_frame=True)
        panel.bar.set_state('recording')
        panel.bar.set_expanded(True)
        panel.bar.show()
        pump(.1)
        panel.bar.grab().save(str(out/'orb-expanded.png'))
        panel.bar.set_expanded(False)
        panel.bar.grab().save(str(out/'orb.png'))
        panel.bar.move(app.primaryScreen().availableGeometry().left(), 200)
        panel.bar.dock_if_near_edge()
        panel.bar.grab().save(str(out/'orb-docked.png'))
        return report
    finally:
        panel.hide()
        panel.bar.hide()
        panel.timer.stop()
        panel.close()
        source.close()
        (out/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


def run(destination, window=False):
    from PySide6.QtWidgets import QApplication
    app = QApplication([])
    print(json.dumps(verify_live_preview(app, destination, window)))
    return 0
