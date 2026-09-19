"""updater 单元测试：版本解析、比较、Release 响应解析。"""
import pytest

from shiguang_capture.updater import is_newer, parse_release_payload, parse_version


class TestParseVersion:
    def test_plain(self):
        assert parse_version("1.2.3") == (1, 2, 3)

    def test_v_prefix(self):
        assert parse_version("v2.0.0") == (2, 0, 0)

    def test_prerelease_suffix_ignored(self):
        assert parse_version("1.3.0-beta.2") == (1, 3, 0)

    def test_invalid(self):
        with pytest.raises(ValueError):
            parse_version("abc")
        with pytest.raises(ValueError):
            parse_version("1.2")


class TestIsNewer:
    def test_major(self):
        assert is_newer("2.0.0", "1.9.9")

    def test_minor(self):
        assert is_newer("1.1.0", "1.0.9")

    def test_patch(self):
        assert is_newer("v1.0.1", "1.0.0")

    def test_same_is_not_newer(self):
        assert not is_newer("1.0.0", "1.0.0")

    def test_older_is_not_newer(self):
        assert not is_newer("0.9.9", "1.0.0")


class TestParseReleasePayload:
    def test_full(self):
        info = parse_release_payload({
            "tag_name": "v1.1.0",
            "html_url": "https://github.com/x/y/releases/tag/v1.1.0",
            "body": "更新内容",
            "published_at": "2026-09-19T00:00:00Z",
        })
        assert info.version == "v1.1.0"
        assert "v1.1.0" in info.url
        assert info.notes == "更新内容"

    def test_missing_keys_safe(self):
        info = parse_release_payload({})
        assert info.version == "0.0.0"
        assert info.url.endswith("/releases")

    def test_long_notes_truncated(self):
        info = parse_release_payload({"body": "x" * 1000})
        assert len(info.notes) == 500
