"""ocr/base.py — OCR 引擎抽象（纯逻辑，不依赖 Qt / 具体引擎）。

设计要点（对应 PRD L2/L3 与商业化红线）：
- 引擎可插拔：本地引擎为默认且永久免费；云端引擎必须显式启用。
- 任何后端实现都不得隐式上传图像——`is_local` 为 False 的后端在调用前
  必须经过用户确认（由上层 AppController 把关）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class OCRResult:
    text: str
    confidence: float | None               # unknown is not a numeric confidence
    blocks: list[dict] = field(default_factory=list)  # 版面块（表格/代码/段落）
    engine: str = "unknown"
    elapsed_ms: int = 0
    mode: str = "ocr"
    table: object | None = None
    model_version: str = "PP-OCRv4 / RapidOCR 1.4.4"


@runtime_checkable
class OCRBackend(Protocol):
    """识别后端协议。实现方：RapidOCR（本地 ONNX）、云端增强（付费额度）。"""

    name: str
    is_local: bool

    def recognize(self, image: bytes) -> OCRResult:
        """对 PNG/JPEG 字节流执行识别。"""
        ...


@dataclass
class MockOCRBackend:
    """开发与 CI 用的确定性后端：返回固定结果，不做任何 IO。"""

    name: str = "mock"
    is_local: bool = True

    def recognize(self, image: bytes) -> OCRResult:
        if not image:
            raise ValueError("图像字节流为空")
        return OCRResult(
            text="[mock] 示例识别文本",
            confidence=0.99,
            blocks=[{"type": "paragraph", "text": "[mock] 示例识别文本"}],
            engine=self.name,
            elapsed_ms=1,
        )


def assert_privacy_guard(backend: OCRBackend, cloud_allowed: bool) -> None:
    """隐私红线守卫：云端后端未获明确许可时直接拒绝（FR 不默认上传）。"""
    if not backend.is_local and not cloud_allowed:
        raise PermissionError(
            f"识别后端 {backend.name!r} 需要上传图像，但用户未开启云端识别"
        )
