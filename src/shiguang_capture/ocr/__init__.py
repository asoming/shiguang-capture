"""ocr 子包：识别引擎抽象与后端实现。"""
from .base import MockOCRBackend, OCRBackend, OCRResult, assert_privacy_guard

__all__ = ["OCRBackend", "OCRResult", "MockOCRBackend", "assert_privacy_guard"]
