"""Native desktop acceptance using only a synthetic test window as the source.

Fails if native capture is unavailable; offscreen rendering is not acceptance.
The JSON report and resulting video are safe to upload as CI artifacts.
"""
from __future__ import annotations
import json
import multiprocessing
import os
import platform
import sys
import time
from pathlib import Path


def main():
    from PySide6.QtCore import Qt, QPoint
    from PySide6.QtWidgets import QApplication, QWidget
    from shiguang_capture.recording.worker import RecordingOptions, record
    import av
    import numpy as np
    output = Path(sys.argv[1] if len(sys.argv) > 1 else 'artifacts/native-recording')
    output.mkdir(parents=True, exist_ok=True)
    report = {'os': platform.platform(), 'machine': platform.machine(), 'python': platform.python_version(),
              'status': 'failed', 'scope': 'native single-display region, silent recording, pause/resume, MP4 decode'}
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    window = QWidget(None, Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
    window.setWindowTitle('Shiguang synthetic recording test')
    window.resize(400, 260)
    window.move(app.primaryScreen().availableGeometry().topLeft() + QPoint(80, 80))
    window.setStyleSheet('background:#D02020;')
    window.show()
    window.raise_()
    app.processEvents()
    process = parent = None
    events = []
    try:
        if app.platformName() in ('offscreen', 'minimal'):
            raise RuntimeError('Native desktop required; offscreen is not a capture acceptance test.')
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        screen = window.screen()
        location = window.mapToGlobal(QPoint(30, 30))
        rect = (location.x(), location.y(), 320, 180)
        report.update(qt_platform=app.platformName(), screen_dpr=screen.devicePixelRatio(), region=rect)
        context = multiprocessing.get_context('spawn')
        parent, child = context.Pipe()
        options = RecordingOptions(str(output/'native-pause-resume.mp4'), screen.name(), rect, 30)
        process = context.Process(target=record, args=(child, options))
        process.start()
        child.close()
        stage, next_action, path = 'start', None, None
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            app.processEvents()
            while True:
                try:
                    if not parent.poll():
                        break
                    event = parent.recv()
                except (EOFError, OSError):
                    break
                events.append(event)
                if event['type'] == 'error':
                    raise RuntimeError(event['message'])
                if event['type'] == 'recording':
                    stage = 'red' if stage == 'start' else 'blue'
                    next_action = time.monotonic() + 1.2
                elif event['type'] == 'paused':
                    window.setStyleSheet('background:#D020D0;')
                    stage, next_action = 'paused', time.monotonic() + 1.5
                elif event['type'] == 'finished':
                    path = Path(event['path'])
            if path:
                break
            if next_action and time.monotonic() >= next_action:
                next_action = None
                if stage == 'red':
                    parent.send('pause')
                elif stage == 'paused':
                    window.setStyleSheet('background:#2020D0;')
                    # Wait for the desktop compositor, not just the widget's
                    # paint event, before declaring the blue phase resumed.
                    paint_deadline = time.monotonic() + .2
                    while time.monotonic() < paint_deadline:
                        app.processEvents()
                        time.sleep(.01)
                    parent.send('resume')
                elif stage == 'blue':
                    parent.send('stop')
            if not process.is_alive():
                raise RuntimeError(f'Capture process exited: {process.exitcode}')
            time.sleep(.01)
        if path is None:
            raise TimeoutError('Native screen recording did not complete in 45 seconds')
        from shiguang_capture.recording.encoder import _media_locale
        _media_locale()
        with av.open(str(path)) as media:
            frames = list(media.decode(video=0))
        assert len(frames) >= 35, f'Only {len(frames)} frames'
        means = np.array([frame.to_ndarray(format='rgb24').mean(axis=(0, 1)) for frame in frames])
        assert ((means[:, 0] > 150) & (means[:, 2] < 70)).any(), 'Red live desktop content missing'
        assert ((means[:, 2] > 150) & (means[:, 0] < 70)).any(), 'Blue resumed desktop content missing'
        assert not ((means[:, 0] > 150) & (means[:, 2] > 150)).any(), 'Paused magenta content leaked'
        duration = float(frames[-1].time)
        assert 1.8 < duration < 3.3, f'Pause was included or active content missing: {duration}'
        assert frames[0].width == round(320*screen.devicePixelRatio())//2*2
        assert frames[0].height == round(180*screen.devicePixelRatio())//2*2
        report.update(status='passed', frame_count=len(frames), duration=duration,
                      width=frames[0].width, height=frames[0].height, video=path.name)
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        if process:
            if process.is_alive():
                try:
                    parent.send('stop')
                except OSError:
                    pass
                process.join(timeout=3)
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)
        window.close()
        report['events'] = events
        (output/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
