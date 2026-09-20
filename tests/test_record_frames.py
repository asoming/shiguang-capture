import pytest
pytest.importorskip('PySide6')
from PySide6.QtCore import QRect
from PySide6.QtGui import QImage, QColor
from PySide6.QtMultimedia import QVideoFrame
from shiguang_capture.recording.frames import rgb_image


@pytest.mark.parametrize('width', [101, 102, 103, 200])
def test_mapped_frame_crop_preserves_channels_stride_and_buffer_lifetime(qt_session, width):
    source = QImage(width, 100, QImage.Format.Format_ARGB32)
    source.fill(QColor('#2030e0'))
    source.setPixelColor(31, 22, QColor('#c02010'))
    frame = QVideoFrame(source)
    result = rgb_image(frame, QRect(30, 20, 40, 30))
    del frame, source
    assert result.size().toTuple() == (40,30)
    assert result.pixelColor(1,2).name() == '#c02010'
    assert result.pixelColor(0,0).name() == '#2030e0'
