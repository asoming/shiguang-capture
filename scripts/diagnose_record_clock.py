"""Compare encoder waiting primitives on the actual native CI desktop."""
import json
import statistics
import threading
import time
from pathlib import Path

from PySide6.QtGui import QGuiApplication
from shiguang_capture.recording.activity import RecordingActivity, configure_encoder_thread
from shiguang_capture.recording.clock import RecordingClock

app = QGuiApplication([])
activity = RecordingActivity()
activity.start()
results = {}


def measure():
    results['thread_qos_result'] = configure_encoder_thread()
    with RecordingClock(threading.Event()) as clock:
        for name, wait in [('sleep', time.sleep), ('event', threading.Event().wait), ('recording_clock', clock.wait)]:
            delays = []
            until = time.monotonic()+1.5
            while time.monotonic() < until:
                began = time.monotonic()
                wait(1/30)
                delays.append((time.monotonic()-began)*1000)
            results[name] = {'samples': len(delays), 'mean_ms': statistics.mean(delays),
                             'max_ms': max(delays), 'requested_ms': 1000/30}
    app.quit()


worker = threading.Thread(target=measure)
worker.start()
app.exec()
worker.join()
activity.stop()
output = Path('artifacts/encoder-clock.json')
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(results, indent=2))
print(json.dumps(results, indent=2))
