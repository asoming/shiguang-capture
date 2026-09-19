"""_argos_compat.py — 让 Argos Translate 在没有 torch/stanza 的环境下可用。

背景：argostranslate.sbd 顶层 `import stanza`，而 stanza 会连带拉入
torch（Windows 轮子约 2GB）——对一个截图工具完全不可接受。
好在 argos 真正需要的只是一句 sentence-splitting，而它已内置
MiniSBD（纯 ONNX，几十 MB），根本用不到 stanza。

本模块做两件事：
1. 注入一个 stanza 桩模块（满足 import，不参与任何计算）；
2. 把 argos 的 chunk_type 固定为 MINISBD，确保永远走轻量路径。
"""
from __future__ import annotations

import sys
import types

_APPLIED = False


def _install_stanza_stub() -> None:
    """若 stanza 未安装，注入最小桩模块（argos 的 MiniSBD 路径不会调用它）。"""
    try:
        import stanza  # noqa: F401

        return
    except ImportError:
        pass

    stub = types.ModuleType("stanza")
    stub.__version__ = "0.0.0-shim"

    class _UnavailablePipeline:  # pragma: no cover - 仅在误用时报错
        def __init__(self, *a, **kw) -> None:
            raise RuntimeError(
                "stanza 未被安装（拾光使用 MiniSBD 轻量切分）。"
                "如需 stanza 路径，请安装 stanza 与 torch"
            )

    stub.Pipeline = _UnavailablePipeline  # type: ignore[attr-defined]
    sys.modules.setdefault("stanza", stub)


def apply() -> None:
    """幂等地应用兼容层（argos 导入前调用）。"""
    global _APPLIED
    if _APPLIED:
        return
    _install_stanza_stub()
    try:
        from argostranslate import settings

        # 固定走 MiniSBD（纯 ONNX），彻底绕开 stanza/torch
        settings.chunk_type = settings.ChunkType.MINISBD
    except Exception:  # noqa: BLE001
        pass
    _APPLIED = True
