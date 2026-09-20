"""ocr 子包：识别引擎抽象与后端实现。"""
from __future__ import annotations

import logging

from .base import MockOCRBackend, OCRBackend, OCRResult, assert_privacy_guard

log = logging.getLogger(__name__)

__all__ = [
    "OCRBackend", "OCRResult", "MockOCRBackend", "assert_privacy_guard",
    "create_backend",
]


def create_backend(name: str = "local") -> OCRBackend:
    """按配置创建识别后端。

    缺少引擎时明确报错；Mock 仅允许由测试显式注入。
    """
    if name == "local":
        try:
            from .rapid_backend import RapidOCRBackend

            return RapidOCRBackend()
        except ImportError as exc:
            raise RuntimeError("本地 OCR 未安装。请安装 OCR 组件后重试；截图、标注和保存仍可使用。") from exc
    raise ValueError("此识别引擎尚未开放，请选择本地 OCR。")
