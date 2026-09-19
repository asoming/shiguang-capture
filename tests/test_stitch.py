"""stitch 单元测试：用合成图像验证重叠检测、拼接与终止判据。"""
import numpy as np
import pytest

from shiguang_capture.capture.stitch import (
    frames_identical, find_overlap, stitch,
)


def make_page(height: int, width: int = 80, seed: int = 0) -> np.ndarray:
    """合成一页「内容」：每行一个确定性灰度条，模拟文档。"""
    rng = np.random.default_rng(seed)
    rows = rng.integers(40, 220, size=(height, 1, 1), dtype=np.uint8)
    page = np.repeat(np.repeat(rows, width, axis=1), 3, axis=2)
    return page


def slice_frames(page: np.ndarray, view: int, step: int) -> list[np.ndarray]:
    """把长页按视口高 view、滚动步长 step 切成连续帧（帧间有 view-step 重叠）。"""
    return [page[y:y + view] for y in range(0, page.shape[0] - view + 1, step)]


class TestFindOverlap:
    def test_exact_overlap(self):
        page = make_page(1000)
        f1, f2 = slice_frames(page, view=300, step=180)[:2]
        overlap, sad = find_overlap(f1, f2)
        assert overlap == 120          # 300 - 180
        assert sad < 1.0

    def test_no_overlap(self):
        page = make_page(1000)
        f1 = page[0:300]
        f2 = page[300:600]             # 紧接但不重叠
        overlap, _ = find_overlap(f1, f2, max_overlap=100)
        assert overlap <= 8            # 允许边界误差，不得误判出大重叠

    def test_width_mismatch_rejected(self):
        with pytest.raises(ValueError):
            find_overlap(np.zeros((10, 80, 3), np.uint8), np.zeros((10, 60, 3), np.uint8))


class TestStitch:
    def test_full_scroll_reconstructs_page(self):
        page = make_page(1000)
        frames = slice_frames(page, view=300, step=180)
        acc = frames[0]
        for f in frames[1:]:
            o, sad = find_overlap(acc[-300:], f)
            acc = stitch(acc, f, o)
        # 拼接结果应与原页一致（末尾不足一屏的部分按帧覆盖范围对齐）
        assert acc.shape[0] == 300 + 180 * (len(frames) - 1)
        np.testing.assert_array_equal(acc, page[:acc.shape[0]])

    def test_zero_new_content(self):
        f = make_page(300)
        acc = stitch(f.copy(), f.copy(), overlap=300)
        assert acc.shape[0] == 300

    def test_invalid_overlap(self):
        f = make_page(100)
        with pytest.raises(ValueError):
            stitch(f, f, overlap=101)


class TestIdentical:
    def test_same_frame(self):
        f = make_page(300)
        assert frames_identical(f, f.copy())

    def test_small_noise_tolerated(self):
        f = make_page(300).astype(np.int16)
        noisy = np.clip(f + 1, 0, 255).astype(np.uint8)  # 全局 ±1 噪声（模拟光标闪烁）
        assert frames_identical(f.astype(np.uint8), noisy, tol=2.0)

    def test_different_frames(self):
        a = make_page(300, seed=1)
        b = make_page(300, seed=2)
        assert not frames_identical(a, b)

    def test_shape_mismatch(self):
        assert not frames_identical(make_page(300), make_page(200))
