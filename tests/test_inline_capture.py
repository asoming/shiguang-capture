"""Real Qt mouse/key events on frozen, high-DPI selection surfaces."""
import pytest
pytest.importorskip('PySide6')
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from shiguang_capture.capture.grabber import ScreenFrame
from shiguang_capture.capture.selector import RegionSelector
from shiguang_capture.geometry import Rect


@pytest.fixture
def selector():
    app = QApplication.instance() or QApplication([])
    frame = QImage(1600, 1000, QImage.Format.Format_RGB888)
    frame.fill(QColor('white'))
    selector = RegionSelector([ScreenFrame(Rect(0, 0, 800, 500), frame, 2)])
    selector.show()
    QTest.mousePress(selector, Qt.MouseButton.LeftButton, pos=QPoint(40, 40))
    QTest.mouseMove(selector, QPoint(340, 240))
    QTest.mouseRelease(selector, Qt.MouseButton.LeftButton, pos=QPoint(340, 240))
    app.processEvents()
    yield selector
    selector.close()
    selector.deleteLater()
    app.processEvents()


def redact(selector):
    selector._on_action('redact')
    canvas = selector._canvas
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(20, 20))
    QTest.mouseMove(canvas, QPoint(90, 60))
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(90, 60))


def test_direct_redaction_native_pixels_and_undo(selector):
    redact(selector)
    output = selector.selected_image(selector._sel)
    assert (output.width(), output.height()) == (600, 400)
    assert output.pixelColor(80, 80).name() == '#20374b'
    assert output.pixelColor(10, 10).name() == '#ffffff'
    QTest.keyClick(selector, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert selector.selected_image(selector._sel).pixelColor(80, 80).name() == '#ffffff'
    QTest.keyClick(selector, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
    assert selector.selected_image(selector._sel).pixelColor(80, 80).name() == '#20374b'


def test_move_keeps_marks_and_resize_keeps_screen_position(selector):
    redact(selector)
    selector._sel = selector._sel.translated(10, 10)
    selector._sync_canvas(moved=True)
    assert selector.selected_image(selector._sel).pixelColor(80, 80).name() == '#20374b'
    selector._sel = Rect(40, 40, 320, 220)
    selector._sync_canvas()
    assert selector._canvas.marks[0].points[0] == QPoint(60, 60)
    assert selector.selected_image(selector._sel).pixelColor(100, 100).name() == '#20374b'


def test_copy_commits_inline_text_and_returns_flattened_pixels(selector):
    selector._on_action('text')
    QTest.mouseClick(selector._canvas, Qt.MouseButton.LeftButton, pos=QPoint(20, 20))
    selector._canvas.text_input.setText('Inline 123')
    chosen = []
    selector.action_chosen.connect(lambda rect, action: chosen.append((rect, action, selector.selected_image(rect))))
    selector._on_action('copy')
    assert chosen[0][1] == 'copy'
    assert selector._canvas.text_input is None
    assert len(selector._canvas.marks) == 1
    assert chosen[0][2] != selector._canvas.image
    assert not selector.isVisible()


def test_right_click_reselect_then_escape_cancels_without_output(selector):
    redact(selector)
    chosen, cancelled = [], []
    selector.action_chosen.connect(lambda *event: chosen.append(event))
    selector.cancelled.connect(lambda: cancelled.append(True))
    QTest.mouseClick(selector._canvas, Qt.MouseButton.RightButton, pos=QPoint(30, 30))
    assert selector._sel is None and not selector._canvas.marks
    QTest.keyClick(selector, Qt.Key.Key_Escape)
    assert cancelled and not chosen


def test_twenty_annotation_steps_undo_redo_and_new_branch(selector):
    selector._on_action('rect')
    canvas = selector._canvas
    for index in range(20):
        start = QPoint(5 + index * 10, 20)
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(canvas, start + QPoint(8, 50))
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=start + QPoint(8, 50))
    complete = selector.selected_image(selector._sel)
    assert len(canvas.marks) == 20
    for _ in range(20):
        QTest.keyClick(selector, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert not canvas.marks
    for _ in range(20):
        QTest.keyClick(selector, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
    assert selector.selected_image(selector._sel) == complete
    QTest.keyClick(selector, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    redact(selector)
    QTest.keyClick(selector, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
    assert len(canvas.marks) == 20 and canvas.marks[-1].tool == 'redact'


def test_existing_text_can_be_clicked_edited_and_undone(selector):
    canvas = selector._canvas
    selector._on_action('text')
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(25, 25))
    canvas.text_input.setText('Original')
    QTest.keyClick(canvas.text_input, Qt.Key.Key_Return)
    selector._on_action('rect')
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(160, 120))
    QTest.mouseMove(canvas, QPoint(210, 170))
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(210, 170))
    selector._on_action('view')
    center = canvas.text_bounds(canvas.marks[0]).center() * (canvas.width()/canvas.image.width())
    QTest.mouseClick(selector, Qt.MouseButton.LeftButton, pos=canvas.mapTo(selector, center.toPoint()))
    assert canvas.text_input is not None
    assert canvas.text_input.text() == 'Original'
    canvas.text_input.setText('Corrected')
    QTest.keyClick(canvas.text_input, Qt.Key.Key_Return)
    assert [m.text for m in canvas.marks] == ['Corrected', '']
    canvas.undo()
    assert canvas.marks[0].text == 'Original'
    canvas.redo()
    assert canvas.marks[0].text == 'Corrected'
    selector._sel = selector._sel.translated(10, 20)
    selector._sync_canvas(moved=True)
    canvas.undo()
    assert canvas.marks[0].text == 'Original'


def test_dimming_preserves_native_pixel_detail(qt_session):
    from PySide6.QtGui import QPainter
    frame = QImage(400, 240, QImage.Format.Format_RGB32)
    frame.fill(QColor('white'))
    p = QPainter(frame)
    p.setPen(QColor('black'))
    for x in range(0, 400, 2):
        p.drawLine(x, 0, x, 239)
    p.end()
    selector = RegionSelector([ScreenFrame(Rect(0, 0, 200, 120), frame, 2)])
    selector.show()
    qt_session.processEvents()
    output = QImage(400, 240, QImage.Format.Format_ARGB32)
    output.setDevicePixelRatio(2)
    output.fill(0)
    selector.render(output)
    # One physical pixel per stripe must survive the dimming path at DPR 2.
    assert output.pixelColor(40, 40).lightness() < 20
    assert output.pixelColor(41, 40).lightness() > 100
    selector.close()
    selector.deleteLater()
