"""smoke_ocr.py — OCR 引擎集成冒烟（CI / 本机共用）。

渲染一张含文字的图像，走 create_backend 全链路识别，
断言识别结果包含预期文本（空白规范化后比对）。
"""
from __future__ import annotations

import io
import sys


def main() -> int:
    from shiguang_capture._console import fix_console_encoding
    fix_console_encoding()
    from PIL import Image, ImageDraw

    from shiguang_capture.ocr import create_backend

    img = Image.new("RGB", (640, 160), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((30, 30), "Q3 Revenue Report", fill=(20, 20, 20))
    d.text((30, 90), "Total: 1,240,000", fill=(20, 20, 20))
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    backend = create_backend("local")
    result = backend.recognize(buf.getvalue())
    norm = result.text.replace(" ", "")
    ok = "Q3RevenueReport" in norm and "1,240,000" in norm
    print(f"engine={result.engine} elapsed={result.elapsed_ms}ms "
          f"conf={result.confidence:.2f} text={result.text!r}")
    print("smoke-ocr", "OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
