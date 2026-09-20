"""Cancellation, timeout, and recovery of the actual process boundary."""
import threading
import time
import pytest
from shiguang_capture.config import AppConfig
from shiguang_capture.ocr.worker import RecognitionRunner, RecognitionCancelled
import shiguang_capture.ocr.worker as worker_module


def delayed_worker(connection):
    try:
        while connection.poll(3):
            image, mode, config = connection.recv()
            if image == b'slow':
                time.sleep(10)
            connection.send(('ok', ('recognized', None)))
    except (EOFError, OSError):
        pass
    finally:
        connection.close()


def test_cancel_kills_worker_and_next_job_recovers(monkeypatch):
    monkeypatch.setattr(worker_module, '_serve', delayed_worker)
    runner = RecognitionRunner()
    cancel = threading.Event()
    timer = threading.Timer(.25, cancel.set)
    timer.start()
    try:
        with pytest.raises(RecognitionCancelled):
            runner.run(b'slow', 'ocr', AppConfig(), cancel)
        assert runner._process is None
        assert runner.run(b'fast', 'ocr', AppConfig(), threading.Event())[0] == 'recognized'
    finally:
        timer.cancel()
        runner.close()


def test_timeout_releases_worker(monkeypatch):
    monkeypatch.setattr(worker_module, '_serve', delayed_worker)
    runner = RecognitionRunner()
    try:
        with pytest.raises(TimeoutError):
            runner.run(b'slow', 'ocr', AppConfig(), threading.Event(), timeout=.2)
        assert runner._process is None
    finally:
        runner.close()
