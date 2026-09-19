"""capture/stitch.py — 长截图拼接核心（纯逻辑，numpy，可单元测试）。

算法：逐帧计算「上一帧底部条带」与「当前帧顶部条带」的重叠量，
取平均绝对差（SAD）最小的重叠值，裁掉重复部分后纵向追加。
对应 FR-1.13（重叠区域自动识别与拼接）、FR-1.14（动态元素抑制——
通过容忍带处理小幅差异）、FR-1.16 的终止判据（内容不再变化）。
"""
from __future__ import annotations

import numpy as np

# 重叠搜索上限（像素）：大于典型视口一次滚动的距离
DEFAULT_MAX_OVERLAP = 600
# 两帧整体差异低于该均值差视为「没有滚动」（终止条件）
IDENTICAL_TOLERANCE = 0.5
# 单帧重叠匹配的可接受误差（超出则认为内容动态变化过大，仍取最优但降置信）
MATCH_TOLERANCE = 2.0
# 最优重叠的 SAD 仍高于该值 → 判定两帧无重叠（直接整帧追加）
NO_MATCH_THRESHOLD = 8.0
# 并列容差带：带内取最大重叠（周期/留白内容下避免错位）
TIE_BAND = 1.0
# 匹配阶段的列抽样步长（提速，不影响行对齐精度）
_COL_STEP = 4


def _gray(img: np.ndarray) -> np.ndarray:
    """(H, W, 3|4) uint8 -> (H, W) float32 灰度。"""
    if img.ndim != 3 or img.shape[2] < 3:
        raise ValueError("期望 (H, W, 3|4) 图像数组")
    rgb = img[..., :3].astype(np.float32)
    return rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114


def find_overlap(prev: np.ndarray, curr: np.ndarray,
                 max_overlap: int = DEFAULT_MAX_OVERLAP) -> tuple[int, float]:
    """计算 curr 相对 prev 的重叠像素数。

    返回 (overlap, sad)：overlap∈[0, max_overlap]，sad 为该重叠下的
    平均每像素绝对差（越小越可信）。两帧宽度必须一致。
    所有候选重叠的 SAD 都高于 NO_MATCH_THRESHOLD 时返回 (0, sad)，
    表示两帧无可靠重叠（调用方应整帧追加或终止）。
    """
    if prev.shape[1] != curr.shape[1]:
        raise ValueError("两帧宽度不一致，无法拼接")
    g_prev, g_curr = _gray(prev), _gray(curr)
    upper = min(max_overlap, prev.shape[0], curr.shape[0])
    if upper <= 0:
        return 0, float("inf")

    p = g_prev[:, ::_COL_STEP]
    c = g_curr[:, ::_COL_STEP]
    sads = np.empty(upper + 1, dtype=np.float64)
    sads[0] = np.inf
    for o in range(1, upper + 1):
        sads[o] = float(np.mean(np.abs(p[-o:, :] - c[:o, :])))

    best_o = int(np.argmin(sads[1:])) + 1
    best_sad = float(sads[best_o])
    if best_sad > NO_MATCH_THRESHOLD:
        return 0, best_sad
    # 并列容差带内取最大重叠（周期/留白内容下避免裁掉真实新内容）
    tied = np.where(sads[best_o:] <= best_sad + TIE_BAND)[0]
    if tied.size:
        best_o = best_o + int(tied[-1])
    return best_o, best_sad


def stitch(acc: np.ndarray, curr: np.ndarray, overlap: int) -> np.ndarray:
    """按重叠量把 curr 的非重复部分追加到 acc 下方。"""
    if overlap < 0 or overlap > curr.shape[0]:
        raise ValueError("overlap 超出当前帧高度")
    new_part = curr[overlap:, :]
    if new_part.shape[0] == 0:
        return acc
    return np.concatenate([acc, new_part], axis=0)


def frames_identical(a: np.ndarray, b: np.ndarray,
                     tol: float = IDENTICAL_TOLERANCE) -> bool:
    """两帧是否基本无变化（滚动到底的判据）。"""
    if a.shape != b.shape:
        return False
    return float(np.mean(np.abs(_gray(a) - _gray(b)))) <= tol
