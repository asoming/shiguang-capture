"""Scroll capture regressions: input target, native frame size and partial results."""
import sys
from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip('PySide6')
from PySide6.QtCore import QPoint
from shiguang_capture.capture import scroller
from shiguang_capture.geometry import Rect


def test_scroll_hides_preview_before_moving_qt_cursor(monkeypatch, qt_session):
    events = []
    position = QPoint(9, 13)

    class Cursor:
        @staticmethod
        def pos():
            return position

        @staticmethod
        def setPos(*args):
            events.append(('cursor', args))

    class Mouse:
        def scroll(self, x, y):
            events.append(('wheel', x, y))

        @property
        def position(self):
            raise AssertionError('Never mix native input coordinates with Qt coordinates')

    monkeypatch.setattr(scroller, 'QCursor', Cursor)
    monkeypatch.setitem(sys.modules, 'pynput.mouse', SimpleNamespace(Controller=Mouse))
    session = scroller.ScrollCaptureSession(Rect(900, 100, 400, 600))
    session._running = True
    session.frame_capturing.connect(lambda: events.append('hide'))
    session.frame_captured.connect(lambda: events.append('show'))
    try:
        session._scroll_once()
        assert events == ['hide']
        session._scroll_timer.stop()
        session._send_scroll()
        assert events == ['hide', ('cursor', (1100, 400)), ('wheel', 0, -3), 'show']
        session.abort()
        assert events[-1] == ('cursor', (position,))
        assert not any(timer.isActive() for timer in (session._timer, session._frame_timer, session._scroll_timer))
    finally:
        session.abort()


def test_no_scroll_reports_reason_and_preserves_first_screen(monkeypatch, qt_session):
    session = scroller.ScrollCaptureSession(Rect(0, 0, 100, 200))
    image = scroller.array_to_qimage(np.full((400, 200, 3), 230, np.uint8))
    monkeypatch.setattr(scroller, 'grab_region', lambda rect: image)
    monkeypatch.setattr(session, '_scroll_once', lambda: None)
    results, errors = [], []
    session.finished.connect(results.append)
    session.failed.connect(errors.append)
    session.start()
    session._capture_frame()
    session._capture_frame()
    assert not session.is_running
    assert len(results) == 1 and results[0] == image
    assert len(errors) == 1 and '未检测到内容滚动' in errors[0]


def test_session_uses_full_previous_frame_and_stops_at_bottom(monkeypatch, qt_session):
    rng = np.random.default_rng(8)
    page = np.repeat(rng.integers(20, 230, (2400, 1, 3), dtype=np.uint8), 100, axis=1)
    images = iter(scroller.array_to_qimage(page[offset:offset+1600]) for offset in (0, 240, 480, 720, 800, 800, 800))
    session = scroller.ScrollCaptureSession(Rect(0, 0, 50, 800))
    monkeypatch.setattr(scroller, 'grab_region', lambda rect: next(images))
    monkeypatch.setattr(session, '_scroll_once', lambda: None)
    results, errors = [], []
    session.finished.connect(results.append)
    session.failed.connect(errors.append)
    session.start()
    for _ in range(6):
        session._capture_frame()
    assert not session.is_running
    assert errors == []
    assert len(results) == 1
    np.testing.assert_array_equal(scroller.qimage_to_array(results[0]), page)


def test_abort_during_pending_wheel_does_not_send_input(qt_session):
    session = scroller.ScrollCaptureSession(Rect(0, 0, 100, 200))
    session._running = True
    session._acc = np.full((200, 100, 3), 250, np.uint8)
    session._frames = 1
    results = []
    session.finished.connect(results.append)
    session._scroll_once()
    assert session._scroll_timer.isActive()
    session.abort()
    session._send_scroll()
    assert not session._scroll_timer.isActive()
    assert session._mouse is None
    assert len(results) == 1
