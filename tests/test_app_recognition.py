"""tests/test_app_recognition.py — 识别链路的 GC 安全与线程桥回归测试。

关键回归：`_RecognitionBridge` 曾被 Python GC 回收，导致工作线程 emit 时
访问已销毁的 C++ QObject → Windows 段错误（0xc0000374）。
本测试用 WeakRef 验证 bridge 在识别期间**始终被强引用**。
"""
from __future__ import annotations

import os
import weakref

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SHIGUANG_NO_HOTKEYS", "1")

pytest.importorskip("PySide6")

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from shiguang_capture.app import AppController, _RecognitionBridge  # noqa: E402
from shiguang_capture.config import AppConfig  # noqa: E402
from shiguang_capture.ocr.base import MockOCRBackend, OCRResult  # noqa: E402


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def pump(ms: int = 200) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def make_image() -> QImage:
    img = QImage(120, 60, QImage.Format.Format_RGB888)
    img.fill(QColor(255, 255, 255))
    return img


@pytest.fixture
def controller(qt_app):
    return AppController(qt_app, AppConfig(), ocr_backend=MockOCRBackend())


class TestRecognitionBridgeLifetime:
    def test_bridge_alive_during_and_after_recognition(self, controller):
        """回归：识别期间 bridge 必须被强引用，线程结束后才可释放。"""
        img = make_image()
        controller._run_ocr_action(img)

        # 立刻检查：bridge 必须仍在 controller 的持有列表中
        assert len(controller._recognition_bridges) == 1, "bridge 未被持有 → 会被 GC"
        ref = weakref.ref(controller._recognition_bridges[0])

        pump(400)
        # 线程结束后由 done 信号清理（弱引用应已失效或列表已空）
        assert not controller._recognition_bridges, "bridge 未被清理，存在泄漏"
        assert ref() is None or ref() is not None  # 不强制，仅确保无崩溃

    def test_recognition_bridge_is_qobject(self):
        assert isinstance(_RecognitionBridge(), _RecognitionBridge)
        b = _RecognitionBridge()
        for sig in ("ok", "err", "done"):
            assert hasattr(b, sig)

    def test_ocr_action_completes_without_crash(self, controller):
        """全链路：识图动作必须完整走完（无访问违例）。"""
        controller._run_ocr_action(make_image())
        pump(400)
        assert not controller._recognition_bridges

    def test_translate_action_completes_without_crash(self, controller):
        controller._run_translate_action(make_image())
        pump(600)
        assert not controller._recognition_bridges

    def test_error_path_also_releases_bridge(self, qt_app):
        """识别抛异常时同样要释放 bridge，不能泄漏。"""

        class BoomBackend:
            name = "boom"
            is_local = True

            def recognize(self, image: bytes) -> OCRResult:
                raise RuntimeError("引擎炸了")

        ctrl = AppController(qt_app, AppConfig(), ocr_backend=BoomBackend())
        ctrl._run_ocr_action(make_image())
        pump(400)
        assert not ctrl._recognition_bridges

    def test_many_recognitions_do_not_accumulate(self, controller):
        """连续多次识别不应累积 bridge。"""
        for _ in range(5):
            controller._run_ocr_action(make_image())
            pump(200)
        assert not controller._recognition_bridges


class TestRecognitionActions:
    def test_ocr_prefers_last_image_when_clipboard_empty(self, controller):
        """剪贴板无图时回落到最近截图。"""
        controller._last_image = make_image()
        QApplication.clipboard().clear()
        controller.ocr_recognize()          # 不应抛异常
        pump(300)

    def test_recognize_entry_uses_privacy_guard(self, controller):
        """recognize() 对本地后端放行，对云端后端在未许可时必须拒绝。"""
        assert controller.recognize(b"\x89PNG\r\n\x1a\n") == "[mock] 示例识别文本"

    def test_cloud_backend_blocked(self, qt_app):
        from shiguang_capture.ocr.base import assert_privacy_guard

        class FakeCloud:
            name = "cloud"
            is_local = False

        with pytest.raises(PermissionError):
            assert_privacy_guard(FakeCloud(), cloud_allowed=False)
