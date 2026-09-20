import pytest
pytest.importorskip('PySide6')
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage, QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton
from shiguang_capture.capture.grabber import ScreenFrame
from shiguang_capture.geometry import Rect
from shiguang_capture.ui.picker import ColorPickerOverlay


def test_picker_samples_native_frozen_pixel_and_click_position(qt_session):
    image = QImage(600, 400, QImage.Format.Format_RGB888)
    image.fill(QColor('#123456'))
    image.setPixelColor(40, 40, QColor('#ff0000'))
    picker = ColorPickerOverlay('hex', [ScreenFrame(Rect(0, 0, 300, 200), image, 2)])
    picker.show()
    picker._pos = QPoint(25, 25)
    assert picker._sample()[3].name() == '#123456'
    colors = []
    picker.color_picked.connect(colors.append)
    QTest.mouseClick(picker, Qt.MouseButton.LeftButton, pos=QPoint(20,20))
    assert colors == ['#FF0000']
    assert not picker.isVisible()
    picker.close()


def test_history_reformats_only_when_explicitly_clicked(qt_session):
    image = QImage(600,400,QImage.Format.Format_RGB888)
    image.fill(QColor('white'))
    picker = ColorPickerOverlay('hsl', [ScreenFrame(Rect(0,0,600,400),image,1)], [(255,0,0)])
    colors = []
    picker.color_picked.connect(colors.append)
    picker.show()
    assert not colors
    QTest.mouseClick(picker.findChild(QPushButton), Qt.MouseButton.LeftButton)
    assert colors == ['hsl(0, 100%, 50%)']
    picker.close()
