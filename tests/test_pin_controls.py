"""Pin controls keep visibility and position recoverable."""
import pytest
pytest.importorskip('PySide6')
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from shiguang_capture.ui.pin_window import PinWindow


def test_locked_pin_does_not_start_drag_and_can_unlock(qt_session):
    pin = PinWindow(QImage(100, 80, QImage.Format.Format_RGB888))
    pin.show()
    pin.set_locked(True)
    QTest.mousePress(pin, Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
    assert pin._drag_pos is None
    pin.set_locked(False)
    QTest.mousePress(pin, Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
    assert pin._drag_pos is not None
    QTest.mouseRelease(pin, Qt.MouseButton.LeftButton)
    assert pin._drag_pos is None
    pin.close()


def test_pin_scale_presets_are_bounded(qt_session):
    pin = PinWindow(QImage(100, 80, QImage.Format.Format_RGB888))
    pin.set_scale(2)
    assert pin.size().width() == 200
    pin.set_scale(50)
    assert pin.size().width() == 400
    pin.set_scale(0)
    assert pin.size().width() == 20
    pin.close()
