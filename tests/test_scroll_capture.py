"""Manual scroll regressions: user pacing, clean previews and final frames."""
import sys
from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip('PySide6')
from PySide6.QtGui import QCursor
from shiguang_capture.capture import scroller
from shiguang_capture.geometry import Rect


@pytest.fixture
def manual_session(monkeypatch, qt_session):
    rng = np.random.default_rng(8)
    page = np.repeat(rng.integers(20, 230, (3200, 1, 3), dtype=np.uint8), 100, axis=1)
    position = [0]
    session = scroller.ScrollCaptureSession(Rect(-100, 20, 50, 800))
    monkeypatch.setattr(scroller, 'grab_region', lambda rect: scroller.array_to_qimage(page[position[0]:position[0]+1600]))
    results, errors, hints, previews = [], [], [], []
    session.finished.connect(results.append)
    session.failed.connect(errors.append)
    session.hint_changed.connect(hints.append)
    session.preview_ready.connect(previews.append)
    yield session, page, position, results, errors, hints, previews
    session.abort()


def test_idle_capture_never_sends_input_or_finishes(manual_session, monkeypatch):
    session, _, _, results, errors, _, _ = manual_session
    def forbidden(*args, **kwargs):
        pytest.fail('Manual capture must never control user input')
    monkeypatch.setattr(QCursor, 'setPos', forbidden)
    monkeypatch.setitem(sys.modules, 'pynput.mouse', SimpleNamespace(Controller=forbidden))
    session.start()
    for _ in range(100):
        session._capture_step()
    assert session.is_running and session._frames == 1
    assert not results and not errors
    session.complete()
    session._capture_frame()
    assert len(results) == 1 and not session.is_running


def test_manual_high_dpi_scroll_pause_and_final_visible_frame(manual_session):
    session, page, position, results, errors, _, previews = manual_session
    session.start()
    for offset in (240, 480, 720, 800):
        position[0] = offset
        session._capture_frame()
    for _ in range(20):
        session._capture_step()
    assert session.is_running and not results
    # Finish before the next poll: the final visible content must be included.
    position[0] = 1040
    session.complete()
    assert not results and session._frame_timer.isActive()
    session._capture_frame()
    assert not session.is_running and not errors
    np.testing.assert_array_equal(scroller.qimage_to_array(results[0]), page[:2640])
    assert len(previews) == 6
    assert all(image.width() <= 180 and image.height() <= 420 for image in previews)
    assert not session._timer.isActive() and not session._frame_timer.isActive()


def test_reverse_or_too_far_scroll_can_recover(manual_session, monkeypatch):
    session, page, position, results, errors, hints, _ = manual_session
    session.start()
    position[0] = 200
    session._capture_frame()
    accepted = session._acc.copy()
    position[0] = 0
    session._capture_frame()
    assert session.is_running and not results and not errors
    np.testing.assert_array_equal(session._acc, accepted)
    with monkeypatch.context() as patch:
        patch.setattr(scroller, 'grab_region', lambda rect: scroller.array_to_qimage(np.full((1600, 100, 3), 250, np.uint8)))
        session._capture_frame()
    assert session.is_running and not results and not errors
    np.testing.assert_array_equal(session._acc, accepted)
    assert hints[-1] == '稍往回滚'
    position[0] = 400
    session._capture_frame()
    assert session._frames == 3 and hints[-1] == '向下滚动'
    session.abort()
    np.testing.assert_array_equal(scroller.qimage_to_array(results[0]), page[:2000])


def test_preview_changes_do_not_trigger_capture_but_page_changes_do(manual_session, monkeypatch):
    session, page, _, _, _, _, _ = manual_session
    session.start()
    # Logical preview bounds -> physical rectangle [20:60, 200:400] at DPR 2.
    session.excluded_rect = Rect(-90, 120, 20, 100)
    probe = page[:1600].copy()
    probe[200:400, 20:60] = 255
    monkeypatch.setattr(scroller, 'grab_region', lambda rect: scroller.array_to_qimage(probe))
    hidden = []
    session.frame_capturing.connect(lambda: hidden.append(True))
    session._capture_step()
    assert not hidden and not session._frame_timer.isActive()
    probe[500:800] = 0
    session._capture_step()
    assert hidden == [True] and session._frame_timer.isActive()


def test_abort_cancels_pending_capture_and_delivers_once(manual_session):
    session, _, _, results, _, _, _ = manual_session
    session.start()
    session.complete()
    assert session._frame_timer.isActive()
    session.abort()
    session._capture_frame()
    session.abort()
    assert len(results) == 1
    assert not session._timer.isActive() and not session._frame_timer.isActive()
