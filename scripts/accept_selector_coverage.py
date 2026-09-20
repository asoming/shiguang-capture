"""Check actual desktop pixels over dock/taskbar areas using synthetic content."""
import json
from pathlib import Path


def verify_selector_coverage(app, destination):
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtTest import QTest
    from shiguang_capture.capture.grabber import ScreenFrame
    from shiguang_capture.capture.selector import RegionSelector
    from shiguang_capture.geometry import Rect

    frames = []
    for screen in app.screens():
        geometry = screen.geometry()
        image = QImage(geometry.size()*screen.devicePixelRatio(), QImage.Format.Format_RGB32)
        image.fill(QColor('#C080E0'))
        frames.append(ScreenFrame(Rect(*geometry.getRect()), image, screen.devicePixelRatio()))
    selector = RegionSelector(frames)
    report = {'status': 'failed', 'screens': []}
    output = Path(destination)
    output.mkdir(parents=True, exist_ok=True)
    try:
        selector.show()
        QTest.qWait(1500)
        bounds = selector._bounds
        report['expected_geometry'] = [bounds.x, bounds.y, bounds.width, bounds.height]
        report['actual_geometry'] = list(selector.geometry().getRect())
        assert selector.geometry() == QRect(*report['expected_geometry']), report
        selector.grab().save(str(output/'selector.png'))
        expected = QColor('#714E86')  # Frozen image plus production dimming color.
        for screen in app.screens():
            capture = screen.grabWindow(0).toImage()
            assert not capture.isNull(), 'Cannot inspect the desktop'
            width, height = capture.width(), capture.height()
            samples = []
            for x, y in [(width//2, 10), (width//2, height-10), (width//2, height-60),
                         (20, height-10), (width-20, height-10)]:
                pixel = capture.pixelColor(x, y)
                samples.append({'x': x, 'y': y, 'color': pixel.name()})
                assert max(abs(a-b) for a, b in zip(pixel.getRgb()[:3], expected.getRgb()[:3])) <= 3, samples
            report['screens'].append({'name': screen.name(), 'samples': samples})
        report['status'] = 'passed'
    finally:
        selector.close()
        selector.deleteLater()
        app.processEvents()
        (output/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication([])
    print(json.dumps(verify_selector_coverage(app, sys.argv[1]), ensure_ascii=False))
