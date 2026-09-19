"""geometry 单元测试：选区归一化、夹取、微调、并集。"""
from datetime import datetime

import pytest

from shiguang_capture.geometry import MIN_SELECTION, Rect, union


class TestFromCorners:
    def test_forward_drag(self):
        r = Rect.from_corners(10, 20, 110, 220)
        assert r == Rect(10, 20, 100, 200)

    def test_reverse_drag_normalized(self):
        r = Rect.from_corners(110, 220, 10, 20)
        assert r == Rect(10, 20, 100, 200)

    def test_negative_coords_multi_monitor(self):
        r = Rect.from_corners(-1920, 0, -1820, 100)
        assert (r.x, r.y, r.width, r.height) == (-1920, 0, 100, 100)


class TestValidity:
    def test_min_selection_boundary(self):
        assert Rect(0, 0, MIN_SELECTION, MIN_SELECTION).is_valid
        assert not Rect(0, 0, MIN_SELECTION - 1, MIN_SELECTION).is_valid

    def test_zero_area_invalid(self):
        assert not Rect(5, 5, 0, 100).is_valid


class TestClampAndNudge:
    BOUNDS = Rect(0, 0, 1920, 1080)

    def test_clamp_inside(self):
        r = Rect(-50, -50, 200, 200).clamp(self.BOUNDS)
        assert (r.x, r.y, r.width, r.height) == (0, 0, 150, 150)

    def test_nudge_moves_by_pixel(self):
        r = Rect(100, 100, 50, 50).nudged(1, 0, self.BOUNDS)
        assert r.x == 101 and r.y == 100

    def test_nudge_blocked_at_edge(self):
        r = Rect(0, 0, 50, 50).nudged(-1, 0, self.BOUNDS)
        assert r.x == 0


class TestAspect:
    def test_locked_aspect(self):
        r = Rect(0, 0, 160, 90).with_locked_aspect(320, 16 / 9)
        assert r.height == 180

    def test_invalid_ratio(self):
        with pytest.raises(ValueError):
            Rect(0, 0, 10, 10).with_locked_aspect(10, 0)


class TestUnion:
    def test_two_monitors(self):
        u = union([Rect(0, 0, 1920, 1080), Rect(1920, 0, 2560, 1440)])
        assert (u.x, u.y, u.width, u.height) == (0, 0, 4480, 1440)

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            union([])
