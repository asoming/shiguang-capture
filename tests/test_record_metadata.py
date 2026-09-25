"""Decoder failures cannot pin a hidden file library or poison unrelated files."""
from types import SimpleNamespace
import time

import pytest
pytest.importorskip('PySide6')
from shiguang_capture.ui.record_metadata import VideoDetails, VideoMetadataLoader


def test_timeout_is_cached_and_remaining_queue_can_continue(qt_session, monkeypatch):
    loader = VideoMetadataLoader(cache_limit=2)
    first = ('/tmp/slow.mp4', 10, 20)
    loader.current = first
    loader.deadline = time.monotonic() - 1
    loader.connection = SimpleNamespace(poll=lambda: False)
    loader.process = SimpleNamespace(is_alive=lambda: True)
    closed = []

    def close():
        closed.append(True)
        loader.current = loader.process = loader.connection = None
    monkeypatch.setattr(loader, '_close_worker', close)
    loader._poll()
    assert closed and '超时' in loader.get(first).error
    loader.request([first])
    assert not loader.queue  # a damaged unchanged file is not decoded on every refresh
    loader.stop()


def test_metadata_cache_is_bounded_and_requested_files_replace_queue(qt_session):
    loader = VideoMetadataLoader(cache_limit=2)
    keys = [(f'/tmp/{i}.mp4', i, i) for i in range(4)]
    for key in keys[:3]:
        loader._remember(key, VideoDetails(duration=1))
    assert len(loader.cache) == 2 and loader.get(keys[0]) is None
    loader.request([keys[0], keys[3]])
    loader.request([keys[3]])
    assert list(loader.queue) == [keys[3]]
    loader.stop()
    assert not loader.queue and not loader.timer.isActive()
