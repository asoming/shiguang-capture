import pytest
pytest.importorskip('PySide6')
from PySide6.QtCore import QPoint
from PySide6.QtGui import QImage, QColor
from shiguang_capture.geometry import Rect
from shiguang_capture.ui.scroll_preview import ScrollPreviewWindow, preview_position


@pytest.mark.parametrize('selection,screen,expected', [
    (Rect(600, 200, 600, 400), Rect(0, 0, 1920, 1080), QPoint(1024, 650)),
    (Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080), QPoint(12, 44)),
    (Rect(50, 200, 600, 400), Rect(0, 0, 1920, 1080), QPoint(474, 650)),
    (Rect(-1200, 200, 600, 400), Rect(-1920, 0, 1920, 1080), QPoint(-776, 650)),
    (Rect(-1920, 0, 1920, 1080), Rect(-1920, 54, 1920, 1000), QPoint(-1908, 98)),
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
    assert preview.thumb.pixmap().width() <= 164
    assert preview.thumb.pixmap().height() <= 212
    assert preview.dimensions.text() == '800 px'
    preview.close()


@pytest.mark.parametrize('selection,screen,inside', [
    (Rect(200, 100, 500, 400), Rect(0, 0, 1920, 1080), False),
    (Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080), True),
    (Rect(-1920, 0, 1920, 1080), Rect(-1920, 0, 1920, 1080), True),
])
def test_capture_border_geometry_and_lifecycle(qt_session, selection, screen, inside):
    from PySide6.QtCore import Qt
    preview = ScrollPreviewWindow()
    try:
        preview.anchor_to(selection, screen)
        frame = preview.selection_frame
        assert all(rect.intersects(selection) == inside for rect in frame.rectangles)
        for rect in frame.rectangles:
            assert screen.x <= rect.x < rect.right <= screen.right
            assert screen.y <= rect.y < rect.bottom <= screen.bottom
        preview.restore_after_capture()
        assert all(edge.isVisible() for edge in frame.edges)
        assert all(edge.windowFlags() & Qt.WindowType.WindowTransparentForInput for edge in frame.edges)
        assert all(edge.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus for edge in frame.edges)
        preview.prepare_capture()
        assert all(edge.isVisible() != inside for edge in frame.edges)
        preview.restore_after_capture()
        assert all(edge.isVisible() for edge in frame.edges)
        preview.close()
        preview.restore_after_capture()
        assert all(not edge.isVisible() for edge in frame.edges)
    finally:
        preview.close()


def test_mask_covers_only_outside_selection_including_other_monitors(qt_session):
    from shiguang_capture.ui.scroll_frame import shade_rectangles
    selection = Rect(200, 150, 500, 400)
    screen = Rect(0, 0, 1200, 800)
    masks = shade_rectangles(selection, screen)
    assert sum(r.area for r in masks) == screen.area-selection.area
    assert all(not r.intersects(selection) for r in masks)
    assert shade_rectangles(screen, screen) == []
    other = Rect(-1200, 0, 1200, 800)
    assert shade_rectangles(selection, other) == [other]
    preview = ScrollPreviewWindow()
    preview.anchor_to(selection, screen, [screen, other])
    preview.restore_after_capture()
    try:
        assert all(s.isVisible() for s in preview.selection_frame.shades)
        assert preview.selection_frame.badge.isVisible()
        assert preview.toolbar.isVisible()
        assert preview.y() > selection.bottom
        preview.update_progress(800, 1)
        assert preview.selection_frame.badge.text == '1000 × 800'
        preview.update_progress(2200, 5)
        assert preview.selection_frame.badge.text == '1000 × 2200'
        preview.prepare_capture()
        assert all(s.isVisible() for s in preview.selection_frame.shades)
    finally:
        preview.close()
    assert not preview.toolbar.isVisible()
    assert not preview.selection_frame.badge.isVisible()
    assert all(not s.isVisible() for s in preview.selection_frame.shades)
