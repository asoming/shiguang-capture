import hashlib
import json
import pytest
from shiguang_capture.ocr.models import verify_models


def test_missing_model_fails_without_download(tmp_path):
    with pytest.raises(RuntimeError, match='缺失或损坏'):
        verify_models(tmp_path)


def test_hash_tampering_is_rejected(tmp_path, monkeypatch):
    from shiguang_capture.ocr import models
    model = tmp_path/'fake.onnx'
    model.write_bytes(b'bad')
    manifest = tmp_path/'models.json'
    manifest.write_text(json.dumps({'models':[{'file':'fake.onnx','bytes':3,'sha256':hashlib.sha256(b'yes').hexdigest()}]}))
    monkeypatch.setattr(models,'files',lambda name:tmp_path)
    with pytest.raises(RuntimeError,match='校验失败'):
        verify_models(tmp_path)
    model.write_bytes(b'yes')
    assert verify_models(tmp_path)['models'][0]['file']=='fake.onnx'
