"""ocr/rapid_backend.py — RapidOCR 本地引擎后端（ONNX Runtime，图像不出本机）。

rapidocr-onnxruntime 的 PP-OCR 系列模型随包分发，无需联网下载。
引擎加载较重（首次约 1-3s），由工厂惰性创建并缓存。
"""
from __future__ import annotations

import logging

from .base import OCRResult

log = logging.getLogger(__name__)


class RapidOCRBackend:
    name = "rapidocr-local"
    is_local = True

    def __init__(self) -> None:
        from rapidocr_onnxruntime import RapidOCR

        self._engine = RapidOCR()
        log.info("RapidOCR 引擎已加载（本地推理）")

    def recognize(self, image: bytes) -> OCRResult:
        if not image:
            raise ValueError("图像字节流为空")
        import time

        t0 = time.perf_counter()
        result, _elapse = self._engine(image)
        elapsed = int((time.perf_counter() - t0) * 1000)

        if not result:
            return OCRResult(text="", confidence=0.0, blocks=[], engine=self.name,
                             elapsed_ms=elapsed)
        lines = [r[1] for r in result]
        confs = [float(r[2]) for r in result]
        blocks = [
            {"type": "line", "text": r[1], "confidence": float(r[2]), "box": r[0]}
            for r in result
        ]
        return OCRResult(
            text="\n".join(lines),
            confidence=sum(confs) / len(confs),
            blocks=blocks,
            engine=self.name,
            elapsed_ms=elapsed,
        )
