"""config 单元测试：默认值、读写往返、损坏文件回落、热键冲突检测。"""
import json

from shiguang_capture.config import AppConfig, HotkeyConfig


class TestDefaults:
    def test_default_hotkeys(self):
        hk = HotkeyConfig()
        assert hk.capture_region == "f1"
        assert hk.color_picker == "f2"

    def test_default_privacy_local_first(self):
        assert AppConfig().ocr_engine == "local"

    def test_no_conflict_by_default(self):
        assert HotkeyConfig().conflicts() == []


class TestConflicts:
    def test_detects_duplicate(self):
        hk = HotkeyConfig(capture_region="f1", color_picker="f1")
        pairs = hk.conflicts()
        assert len(pairs) == 1
        assert set(pairs[0]) == {"capture_region", "color_picker"}

    def test_case_insensitive(self):
        hk = HotkeyConfig(capture_region="F1", color_picker=" f1 ")
        assert len(hk.conflicts()) == 1


class TestPersistence:
    def test_json_cannot_replace_hotkey_methods(self, tmp_path):
        path = tmp_path / "cfg.json"
        path.write_text('{"hotkeys":{"conflicts":"bad","capture_region":null}}')
        cfg = AppConfig.load(path)
        assert cfg.hotkeys.conflicts() == []
        assert cfg.hotkeys.capture_region == "f1"

    def test_roundtrip(self, tmp_path):
        p = tmp_path / "cfg.json"
        cfg = AppConfig(image_format="jpg", pin_default_opacity=0.8)
        cfg.hotkeys.capture_region = "f5"
        cfg.save(p)
        loaded = AppConfig.load(p)
        assert loaded.image_format == "jpg"
        assert loaded.pin_default_opacity == 0.8
        assert loaded.hotkeys.capture_region == "f5"

    def test_missing_file_returns_defaults(self, tmp_path):
        cfg = AppConfig.load(tmp_path / "nope.json")
        assert cfg == AppConfig()

    def test_corrupt_file_returns_defaults(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{not json", encoding="utf-8")
        cfg = AppConfig.load(p)
        assert cfg == AppConfig()

    def test_unknown_keys_ignored(self, tmp_path):
        p = tmp_path / "cfg.json"
        p.write_text(json.dumps({"image_format": "webp", "unknown_key": 1,
                                 "hotkeys": {"capture_region": "f9", "bogus": "x"}}),
                     encoding="utf-8")
        cfg = AppConfig.load(p)
        assert cfg.image_format == "webp"
        assert cfg.hotkeys.capture_region == "f9"
        assert not hasattr(cfg, "unknown_key")
