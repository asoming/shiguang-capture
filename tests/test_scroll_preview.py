import pytest
pytest.importorskip('PySide6')
from PySide6.QtCore import QPoint
from PySide6.QtGui import QImage, QColor
from shiguang_capture.geometry import Rect
from shiguang_capture.ui.scroll_preview import ScrollPreviewWindow, preview_position


@pytest.mark.parametrize('selection,screen,expected', [
    (Rect(600, 200, 600, 400), Rect(0, 0, 1920, 1080), QPoint(414, 200)),
    (Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080), QPoint(12, 12)),
    (Rect(50, 200, 600, 400), Rect(0, 0, 1920, 1080), QPoint(12, 12)),
    (Rect(-1200, 200, 600, 400), Rect(-1920, 0, 1920, 1080), QPoint(-1386, 200)),
    (Rect(-1920, 0, 1920, 1080), Rect(-1920, 54, 1920, 1000), QPoint(-1908, 66)),
])
def test_preview_placement(selection, screen, expected):
    assert preview_position(selection, screen, 176, 270) == expected


def test_preview_outside_capture_stays_visible_but_fullscreen_hides(qt_session):
    preview = ScrollPreviewWindow()
    try:
        screen = Rect(0, 0, 1920, 1080)
        preview.anchor_to(Rect(600, 200, 600, 400), screen)
        preview.show()
        preview.prepare_capture()
        assert preview.isVisible()
        preview.anchor_to(screen, screen)
        preview.prepare_capture()
        assert not preview.isVisible()
        preview.restore_after_capture()
        assert preview.isVisible()
        preview.close()
        preview.restore_after_capture()
        assert not preview.isVisible()
    finally:
        preview.close()


def test_long_wide_thumbnail_never_enlarges_window(qt_session):
    preview = ScrollPreviewWindow()
    image = QImage(4000, 800, QImage.Format.Format_RGB32)
    image.fill(QColor('white'))
    before = preview.size()
    preview.update_progress(800, 1, image)
    assert preview.size() == before
    assert preview.thumb.pixmap().width() <= 154
    assert preview.thumb.pixmap().height() <= 184
    assert preview.dimensions.text() == '800 px'
    preview.close()
