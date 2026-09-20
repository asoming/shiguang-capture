"""Verify the shipped, versioned model files before loading ONNX sessions."""
from __future__ import annotations
import hashlib
import json
from importlib.resources import files
from pathlib import Path


def verify_models(directory: Path | None = None) -> dict:
    manifest = json.loads(files('shiguang_capture.ocr').joinpath('models.json').read_text('utf-8'))
    if directory is None:
        directory = Path(str(files('rapidocr_onnxruntime').joinpath('models')))
    for model in manifest['models']:
        path = directory / model['file']
        if not path.is_file() or path.stat().st_size != model['bytes']:
            raise RuntimeError(f"本地模型缺失或损坏：{model['file']}。请重新安装正式版。")
        if hashlib.sha256(path.read_bytes()).hexdigest() != model['sha256']:
            raise RuntimeError(f"本地模型校验失败：{model['file']}。请重新安装正式版。")
    return manifest
