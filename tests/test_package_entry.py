"""Windowed package diagnostics must fail without a blocking traceback dialog."""
import runpy
import sys
from pathlib import Path

import pytest


def test_failed_synthetic_package_check_writes_log_and_exits(monkeypatch, tmp_path):
    from shiguang_capture import __main__ as entry

    def failure():
        raise RuntimeError('synthetic encoder dependency missing')

    log = tmp_path/'package.log'
    monkeypatch.setattr(entry, 'main', failure)
    monkeypatch.setattr(sys, 'argv', ['ShiguangCapture', '--recording-self-test'])
    monkeypatch.setenv('SHIGUANG_SELF_TEST_LOG', str(log))
    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(Path(__file__).parents[1]/'scripts/app_entry.py'), run_name='__main__')
    assert error.value.code == 1
    assert 'synthetic encoder dependency missing' in log.read_text(encoding='utf-8')
