"""tests/test_console.py — 控制台编码兼容回归测试。

CI 在 Windows runner 上默认 cp1252 控制台，脚本里 print 中文会抛
`UnicodeEncodeError: 'charmap' codec can't encode characters`，
把本应通过的冒烟 job 打成失败。本测试用子进程强制 PYTHONIOENCODING
复现该场景，断言 fix_console_encoding() 能让中文输出正常通过。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"

_SCRIPT = """
import sys
sys.path.insert(0, {src!r})
from shiguang_capture._console import fix_console_encoding
fix_console_encoding()
print("识图面板 OK · 译文=截图工具保存副本")
print("全部通过 · 识图与翻译功能已可用")
"""


def _run(io_encoding: str, with_fix: bool) -> subprocess.CompletedProcess:
    script = _SCRIPT.format(src=str(SRC))
    if not with_fix:
        script = script.replace("fix_console_encoding()", "pass")
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = io_encoding
    env["PYTHONPATH"] = str(SRC)
    return subprocess.run([sys.executable, "-c", script],
                          env=env, capture_output=True)


class TestConsoleEncoding:
    def test_cp1252_without_fix_fails(self):
        """先确认问题真实存在：不加修复时 cp1252 下必须报错。"""
        r = _run("cp1252", with_fix=False)
        assert r.returncode != 0, "未能复现问题，测试前提已失效"
        assert b"UnicodeEncodeError" in r.stderr or b"charmap" in r.stderr

    def test_cp1252_with_fix_succeeds(self):
        r = _run("cp1252", with_fix=True)
        assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
        assert "识图面板 OK".encode("utf-8") in r.stdout
        assert "全部通过".encode("utf-8") in r.stdout

    def test_cp936_with_fix_succeeds(self):
        """中文 Windows 常见的 cp936（GBK）同样要能过。"""
        r = _run("cp936", with_fix=True)
        assert r.returncode == 0, r.stderr.decode("utf-8", "replace")

    def test_utf8_still_works(self):
        r = _run("utf-8", with_fix=True)
        assert r.returncode == 0

    def test_idempotent(self):
        """重复调用不应抛异常。"""
        from shiguang_capture._console import fix_console_encoding

        fix_console_encoding()
        fix_console_encoding()

    def test_tolerates_stream_without_reconfigure(self, monkeypatch):
        """被 pytest 捕获 / 自定义流没有 reconfigure 时不能崩。"""
        from shiguang_capture import _console

        class FakeStream:
            def write(self, s):  # pragma: no cover
                return len(s)

        monkeypatch.setattr(sys, "stdout", FakeStream())
        monkeypatch.setattr(sys, "stderr", FakeStream())
        _console.fix_console_encoding()   # 不应抛异常
