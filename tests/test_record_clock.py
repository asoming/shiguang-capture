"""Clock lifecycle and shutdown; native cadence is verified on macOS CI."""
import threading

from shiguang_capture.recording import clock


def test_portable_wait_wakes_on_stop(monkeypatch):
    monkeypatch.setattr(clock.sys, 'platform', 'linux')
    stop = threading.Event()
    with clock.RecordingClock(stop) as timer:
        thread = threading.Thread(target=timer.wait, args=(30,))
        thread.start()
        stop.set()
        thread.join(timeout=1)
        assert not thread.is_alive()


def test_native_clock_is_closed_even_when_recording_fails(monkeypatch):
    events = []
    class Native:
        def wait(self, seconds):
            events.append(seconds)
        def close(self):
            events.append('closed')
    monkeypatch.setattr(clock.sys, 'platform', 'darwin')
    monkeypatch.setattr(clock, '_DispatchTimer', Native)
    stop = threading.Event()
    try:
        with clock.RecordingClock(stop) as timer:
            timer.wait(.03)
            stop.set()
            timer.wait(.03)
            raise ValueError('encoder failure')
    except ValueError:
        pass
    assert events == [.03, 'closed']
