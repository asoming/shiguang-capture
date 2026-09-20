"""Check actual desktop pixels over dock/taskbar areas using synthetic content."""
import json
from pathlib import Path


def verify_selector_coverage(app, destination):
    from PySide6.QtCore import QPoint, QRect, Qt
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
        report['visible'] = selector.isVisible()
        report['window_flags'] = int(selector.windowFlags())
        if app.platformName() == 'cocoa':
            import objc
            native = objc.objc_object(c_void_p=int(selector.winId())).window()
            report['native_level'] = int(native.level())
            report['native_visible'] = bool(native.isVisible())
        assert selector.geometry() == QRect(*report['expected_geometry']), report
        selector.grab().save(str(output/'selector.png'))
        expected = QColor('#714E86')  # Frozen image plus production dimming color.
        for screen in app.screens():
            capture = screen.grabWindow(0).toImage()
            assert not capture.isNull(), 'Cannot inspect the desktop'
            width, height = capture.width(), capture.height()
            samples = []
            entry = {'name': screen.name(), 'samples': samples}
            report['screens'].append(entry)
            for x, y in [(width//2, 10), (width//2, height-10), (width//2, height-60),
                         (20, height-10), (width-20, height-10)]:
                pixel = capture.pixelColor(x, y)
                samples.append({'x': x, 'y': y, 'color': pixel.name()})
                assert max(abs(a-b) for a, b in zip(pixel.getRgb()[:3], expected.getRgb()[:3])) <= 3, samples
        # The overlay must still accept selection, text input and Escape at its
        # native window level (especially Cocoa's popup rather than utility).
        QTest.mousePress(selector, Qt.MouseButton.LeftButton, pos=QPoint(40, 40))
        QTest.mouseMove(selector, QPoint(400, 250))
        QTest.mouseRelease(selector, Qt.MouseButton.LeftButton, pos=QPoint(400, 250))
        selector._on_action('text')
        QTest.mouseClick(selector._canvas, Qt.MouseButton.LeftButton, pos=QPoint(30, 30))
        selector._canvas.text_input.setText('Overlay input')
        QTest.keyClick(selector._canvas.text_input, Qt.Key.Key_Return)
        assert selector.isVisible() and selector._canvas.marks[0].text == 'Overlay input'
        QTest.keyClick(selector, Qt.Key.Key_Escape)
        assert not selector.isVisible()
        report['interaction'] = 'selection, text confirmation and Escape passed'
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
