"""naming 单元测试：命名格式、序号推进、跨日清零、录屏共享命名。"""
from datetime import datetime

import pytest

from shiguang_capture.naming import next_seq, recording_name, shot_name

NOW = datetime(2026, 9, 19, 12, 5, 52)


class TestShotName:
    def test_format(self):
        assert shot_name(NOW, 7) == "SG_20260919_120552_0007.png"

    def test_ext_normalized(self):
        assert shot_name(NOW, 1, ".JPG") == "SG_20260919_120552_0001.jpg"

    def test_seq_range(self):
        with pytest.raises(ValueError):
            shot_name(NOW, 10000)

    def test_recording_shares_scheme(self):
        assert recording_name(NOW, 3) == "SG_20260919_120552_0003.mp4"


class TestNextSeq:
    def test_empty_dir(self, tmp_path):
        assert next_seq(tmp_path, NOW) == 1

    def test_increments_same_day(self, tmp_path):
        (tmp_path / "SG_20260919_090000_0001.png").touch()
        (tmp_path / "SG_20260919_100000_0005.png").touch()
        assert next_seq(tmp_path, NOW) == 6

    def test_ignores_other_days(self, tmp_path):
        (tmp_path / "SG_20260918_235959_0009.png").touch()
        assert next_seq(tmp_path, NOW) == 1

    def test_ignores_foreign_files(self, tmp_path):
        (tmp_path / "screenshot.png").touch()
        (tmp_path / "SG_bad.png").touch()
        assert next_seq(tmp_path, NOW) == 1
