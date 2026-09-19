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

    local：优先 RapidOCR 真引擎；依赖缺失时降级 MockOCR 并记日志
    （应用保持可用，不让识别能力阻塞截图主链路）。
    cloud：暂未开放，同样降级 Mock（隐私守卫已在调用链上把关）。
    """
    if name == "local":
        try:
            from .rapid_backend import RapidOCRBackend

            return RapidOCRBackend()
        except ImportError as exc:
            log.warning("RapidOCR 不可用（%s），降级为 Mock 后端", exc)
            return MockOCRBackend()
    log.info("识别引擎 %r 暂未开放，使用 Mock 后端", name)
    return MockOCRBackend()
