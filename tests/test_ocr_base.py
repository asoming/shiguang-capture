"""ocr.base 单元测试：后端协议、Mock 后端、隐私红线守卫。"""
import pytest

from shiguang_capture.ocr import MockOCRBackend, OCRBackend
from shiguang_capture.ocr.base import OCRResult, assert_privacy_guard


class TestMockBackend:
    def test_satisfies_protocol(self):
        assert isinstance(MockOCRBackend(), OCRBackend)

    def test_deterministic_result(self):
        r = MockOCRBackend().recognize(b"\x89PNG fake")
        assert isinstance(r, OCRResult)
        assert r.confidence == 0.99
        assert r.engine == "mock"

    def test_empty_image_rejected(self):
        with pytest.raises(ValueError):
            MockOCRBackend().recognize(b"")


class _FakeCloudBackend:
    name = "cloud-fake"
    is_local = False

    def recognize(self, image: bytes) -> OCRResult:  # pragma: no cover
        return OCRResult(text="", confidence=0.0, engine=self.name)


class TestPrivacyGuard:
    def test_local_always_allowed(self):
        assert_privacy_guard(MockOCRBackend(), cloud_allowed=False)  # 不抛异常即通过

    def test_cloud_blocked_without_consent(self):
        with pytest.raises(PermissionError):
            assert_privacy_guard(_FakeCloudBackend(), cloud_allowed=False)

    def test_cloud_allowed_with_consent(self):
        assert_privacy_guard(_FakeCloudBackend(), cloud_allowed=True)
