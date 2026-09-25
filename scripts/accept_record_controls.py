"""Exercise the production countdown and floating controls on a native desktop."""
from pathlib import Path
import json
import multiprocessing
import platform
import sys
import time


def main(destination):
    from PySide6.QtCore import Qt, QPoint
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QApplication, QWidget
    from PySide6.QtTest import QTest
    from shiguang_capture.geometry import Rect
    from shiguang_capture.ui.record_panel import RecordPanel
    import av
    import numpy as np
    output = Path(destination).resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = {'os': platform.platform(), 'status': 'failed', 'scope': 'native recording UI; synthetic content only'}
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    source = QWidget(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
    source.setWindowTitle('Shiguang UI acceptance source')
    source.resize(400, 260)
    source.move(app.primaryScreen().availableGeometry().topLeft()+QPoint(60, 60))
    source.setStyleSheet('background:#D02020;')
    source.show()
    panel = RecordPanel()
    panel.folder.setText(str(output))

    def pump(seconds):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)

    def until(predicate, seconds=30):
        deadline = time.monotonic()+seconds
        while not predicate():
            if time.monotonic() > deadline:
                raise AssertionError(f'Timed out in {panel.state}: {panel.status.text()}')
            pump(.02)

    try:
        assert app.platformName() not in ('offscreen', 'minimal'), 'Native desktop required'
        from accept_live_preview import verify_live_preview
        report['live_preview'] = verify_live_preview(app, output/'live-preview')
        from accept_selector_coverage import verify_selector_coverage
        report['selector'] = verify_selector_coverage(app, output/'selector-coverage')
        pump(.5)
        location = source.mapToGlobal(QPoint(25, 25))
        panel.set_region(Rect(location.x(), location.y(), 320, 180))
        panel.preview_image = source.grab()
        panel.show()
        panel._fit_preview()
        pump(.2)
        panel.grab().save(str(output/'recording-panel.png'))
        # First cancellation must neither spawn a worker nor produce a video.
        QTest.mouseClick(panel.start_button, Qt.MouseButton.LeftButton)
        assert panel.countdown_overlay.isVisible()
        QTest.keyClick(panel.countdown_overlay, Qt.Key.Key_Escape)
        assert panel.state == 'idle' and panel.process is None
        started = time.monotonic()
        QTest.mouseClick(panel.start_button, Qt.MouseButton.LeftButton)
        panel.countdown_overlay.grab().save(str(output/'countdown.png'))
        until(lambda: panel.state != 'countdown', 5)
        report['countdown_seconds'] = round(time.monotonic()-started, 2)
        assert report['countdown_seconds'] >= 2.9
        assert not panel.countdown_overlay.isVisible()
        until(lambda: panel.state == 'recording')
        pump(1.6)
        orb = panel.bar
        QTest.mouseClick(orb, Qt.MouseButton.LeftButton, pos=QPoint(32, 32))
        assert orb.expanded
        QTest.mouseClick(orb.pause, Qt.MouseButton.LeftButton)
        until(lambda: panel.state == 'paused')
        source.setStyleSheet('background:#D020D0;')
        orb.grab().save(str(output/'paused-orb.png'))
        pump(1.2)
        source.setStyleSheet('background:#2040D0;')
        pump(.1)
        QTest.mouseClick(orb.play, Qt.MouseButton.LeftButton)
        until(lambda: panel.state == 'recording')
        pump(1.6)
        area = source.screen().availableGeometry()
        orb.move(area.left(), area.top()+400)
        orb.dock_if_near_edge()
        assert orb.docked == 'left' and orb.width() == 32
        orb.grab().save(str(output/'docked-orb.png'))
        QTest.mouseClick(orb, Qt.MouseButton.LeftButton, pos=QPoint(12, 32))
        assert orb.expanded
        QTest.mouseClick(orb.stop_button, Qt.MouseButton.LeftButton)
        until(lambda: panel.state == 'idle' and panel.process is None)
        assert panel.last_path and panel.last_path.is_file(), panel.status.text()
        panel.tabs.setCurrentIndex(1)
        pump(.2)
        library = panel.library
        assert library.table.topLevelItemCount() >= 1
        item = next(library.table.topLevelItem(index) for index in range(library.table.topLevelItemCount())
                    if library.table.topLevelItem(index).text(0) == panel.last_path.name)
        from shiguang_capture.ui.record_library import file_size
        assert item.text(1) == file_size(panel.last_path.stat().st_size)
        report['file_library'] = {'name': item.text(0), 'size': item.text(1), 'modified': item.text(2)}
        panel.grab().save(str(output/'recording-files.png'))
        menu = library.table.itemWidget(item, 3).menu()
        button = library.table.itemWidget(item, 3)
        menu.popup(button.mapToGlobal(button.rect().bottomLeft()))
        pump(.2)
        menu.grab().save(str(output/'recording-file-menu.png'))
        assert [action.text() for action in menu.actions() if not action.isSeparator()] == ['播放', '打开所在文件夹', '重命名…', '删除']
        menu.hide()
        frames = []
        with av.open(str(panel.last_path)) as media:
            for frame in media.decode(video=0):
                pixels = frame.to_ndarray(format='rgb24')
                frames.append(pixels[pixels.shape[0]//2, pixels.shape[1]//2].astype(int))
        red = sum(r > 130 and b < 90 for r, g, b in frames)
        blue = sum(b > 130 and r < 90 for r, g, b in frames)
        magenta = sum(r > 130 and b > 130 for r, g, b in frames)
        assert red and blue and magenta == 0, (red, blue, magenta)
        report.update(status='passed', frames=len(frames), red=int(red), blue=int(blue), paused_frames=int(magenta),
                      video=panel.last_path.name, controls=['countdown cancel', 'three seconds', 'pause', 'resume', 'dock', 'expand', 'stop'])
    finally:
        (output/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        if panel.process and panel.process.is_alive():
            panel.process.terminate()
            panel.process.join(timeout=2)
        panel.timer.stop()
        panel.state = 'idle'
        panel.bar.hide()
        panel.countdown_overlay.hide()
        panel.close()
        source.close()
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    multiprocessing.freeze_support()
    main(sys.argv[1] if len(sys.argv)>1 else 'artifacts/record-controls')
