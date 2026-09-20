"""Crop CPU-mappable capture frames before full-screen color conversion."""
from PySide6.QtGui import QImage
from PySide6.QtMultimedia import QVideoFrame, QVideoFrameFormat


def rgb_image(frame, crop=None):
    image_format = QVideoFrameFormat.imageFormatFromPixelFormat(frame.pixelFormat())
    if image_format != QImage.Format.Format_Invalid and frame.map(QVideoFrame.MapMode.ReadOnly):
        try:
            mapped = QImage(frame.bits(0), frame.width(), frame.height(), frame.bytesPerLine(0), image_format)
            # Detach while mapped: neither the crop nor returned image may retain
            # a pointer into a buffer after QVideoFrame.unmap().
            image = mapped.copy(crop) if crop is not None else mapped.copy()
            return image.convertToFormat(QImage.Format.Format_RGB888)
        finally:
            frame.unmap()
    image = frame.toImage()
    if crop is not None:
        image = image.copy(crop)
    return image.convertToFormat(QImage.Format.Format_RGB888)
