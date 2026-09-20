"""Screen/audio devices and encoding live only in this spawned process."""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RecordingOptions:
    target: str
    screen: str
    region: tuple[int, int, int, int] | None = None
    fps: int = 30
    microphone: str | None = None
    system_audio: str | None = None
    window_title: str | None = None


def probe_windows(connection):
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtMultimedia import QWindowCapture
    app = QGuiApplication([])
    try:
        descriptions = [window.description() for window in QWindowCapture.capturableWindows() if window.isValid()]
        # Qt's Python API exposes descriptions but no portable serializable
        # native window identifier. Never guess between identically named windows.
        unique = sorted(title for title in set(descriptions) if title and descriptions.count(title) == 1)
        connection.send({'type': 'windows', 'windows': unique})
    except Exception as exc:
        connection.send({'type': 'error', 'message': f'无法读取窗口：{exc}'})
    finally:
        connection.close()


def probe_audio(connection):
    try:
        import soundcard
        devices = [{'id': device.id, 'name': device.name, 'loopback': device.isloopback}
                   for device in soundcard.all_microphones(include_loopback=True)]
        connection.send({'type': 'devices', 'devices': devices})
    except Exception as exc:
        connection.send({'type': 'error', 'message': f'无法读取音源：{exc}'})
    finally:
        connection.close()


class AudioCapture:
    def __init__(self, device_ids):
        self.stop = threading.Event()
        self.active = threading.Event()
        self.error = None
        self.queues = [queue.Queue(maxsize=100) for _ in device_ids]
        self.ready = [threading.Event() for _ in device_ids]
        self.threads = []
        for device_id, chunks, ready in zip(device_ids, self.queues, self.ready):
            thread = threading.Thread(target=self._read, args=(device_id, chunks, ready), daemon=True)
            thread.start()
            self.threads.append(thread)

    def _read(self, device_id, chunks, ready):
        try:
            import soundcard
            device = soundcard.get_microphone(device_id, include_loopback=True)
            # Open only during active recording; pause releases the microphone.
            while not self.stop.is_set():
                if not self.active.wait(.05):
                    ready.set()
                    continue
                with device.recorder(samplerate=48000, channels=2, blocksize=960) as recorder:
                    ready.set()
                    while self.active.is_set() and not self.stop.is_set():
                        data = recorder.record(numframes=960)
                        if self.active.is_set():
                            chunks.put_nowait(data)
        except Exception as exc:
            self.error = f'音频录制失败：{exc}'
            ready.set()

    def take(self):
        import numpy as np
        if self.error:
            raise RuntimeError(self.error)
        while self.queues and all(not q.empty() for q in self.queues):
            yield np.clip(sum(q.get_nowait() for q in self.queues), -1, 1)

    def pause(self):
        self.active.clear()
        for chunks in self.queues:
            while not chunks.empty():
                chunks.get_nowait()

    def close(self):
        self.stop.set()
        self.active.clear()
        for thread in self.threads:
            thread.join(timeout=1)


def record(connection, options: RecordingOptions):
    from PySide6.QtCore import QObject, Signal, Slot
    from PySide6.QtGui import QGuiApplication, QImage
    from PySide6.QtMultimedia import QMediaCaptureSession, QScreenCapture, QWindowCapture, QVideoSink, QVideoFrame
    import av  # Load the encoder before starting the capture clock.
    import numpy as np
    from .encoder import VideoWriter, check_space
    from .activity import RecordingActivity
    from .frames import rgb_image
    import queue
    import threading

    app = QGuiApplication([])
    screen = next((s for s in app.screens() if s.name() == options.screen), None)
    writer = audio = None
    activity = RecordingActivity()
    metrics = {'frames': 0, 'image_conversion_ms': 0.0, 'encoding_ms': 0.0,
               'max_tick_ms': 0.0, 'max_clock_gap_ms': 0.0, 'active_sleep_ms': 0.0}
    finished = False
    encoder_thread = capture = None
    stop_clock = threading.Event()
    frame_lock = threading.Lock()
    capture_errors = queue.SimpleQueue()
    try:
        if screen is None and not options.window_title:
            raise RuntimeError('所选屏幕已断开，请重新选择。')
        geometry = screen.geometry() if screen else None
        if options.window_title and options.region:
            raise ValueError('窗口录制不能同时指定屏幕区域。')
        if options.region:
            from PySide6.QtCore import QRect
            region = QRect(*options.region)
            if not geometry.contains(region):
                raise ValueError('录屏区域需要位于同一屏幕内。')
        else:
            region = geometry
        session, sink = QMediaCaptureSession(), QVideoSink()
        if options.window_title:
            windows = [window for window in QWindowCapture.capturableWindows()
                       if window.isValid() and window.description() == options.window_title]
            if len(windows) != 1:
                raise RuntimeError('窗口已关闭、标题变化或存在同名窗口，请重新选择，或使用区域录屏。')
            capture = QWindowCapture()
            capture.setWindow(windows[0])
            session.setWindowCapture(capture)
        else:
            capture = QScreenCapture()
            capture.setScreen(screen)
            session.setScreenCapture(capture)
        session.setVideoSink(sink)
        class CaptureControl(QObject):
            requested = Signal(bool)

            @Slot(bool)
            def apply(self, active):
                capture.start() if active else capture.stop()

        control = CaptureControl()
        control.requested.connect(control.apply)
        latest = QVideoFrame()
        started, paused_at, paused_total = None, None, 0.0
        deadline = time.monotonic() + 15
        last_status, last_space_check = 0.0, 0.0
        device_ids = [value for value in (options.microphone, options.system_audio) if value]

        def fail(message):
            nonlocal finished
            if finished:
                return
            finished = True
            try:
                connection.send({'type': 'error', 'message': message,
                                 'recovery': str(writer.recovery) if writer else None})
            finally:
                app.quit()

        def frame_changed(frame):
            nonlocal latest
            if frame.isValid() and paused_at is None:
                with frame_lock:
                    latest = QVideoFrame(frame)

        sink.videoFrameChanged.connect(frame_changed)
        capture.errorOccurred.connect(lambda error, text: capture_errors.put(f'屏幕录制失败：{text}'))
        if not options.window_title:
            screen.geometryChanged.connect(lambda *_: capture_errors.put('屏幕尺寸已改变，录制已停止；可恢复已录内容。'))
            app.screenRemoved.connect(lambda removed: capture_errors.put('录制屏幕已断开；可恢复已录内容。') if removed == screen else None)

        def tick():
            nonlocal writer, audio, started, paused_at, paused_total, last_status, last_space_check, finished, latest, deadline
            if finished:
                return
            try:
                if not capture_errors.empty():
                    raise RuntimeError(capture_errors.get_nowait())
                now = time.monotonic()
                while connection.poll():
                    command = connection.recv()
                    if command == 'stop':
                        finished = True
                        control.requested.emit(False)
                        if audio:
                            audio.close()
                            for chunk in audio.take():
                                writer.write_audio(chunk)
                        connection.send({'type': 'saving'})
                        if writer is None:
                            connection.send({'type': 'cancelled'})
                        else:
                            connection.send({'type': 'finished', 'path': str(writer.finish()), 'metrics': metrics})
                        app.quit()
                        return
                    if command == 'pause' and started is not None and paused_at is None:
                        paused_at = now
                        control.requested.emit(False)
                        activity.stop()
                        if audio:
                            audio.pause()
                        connection.send({'type': 'paused'})
                    if command == 'resume' and paused_at is not None:
                        paused_total += now - paused_at
                        paused_at = None
                        with frame_lock:
                            latest = QVideoFrame()
                        deadline = now + 15
                        activity.start()
                        if audio:
                            audio.active.set()
                        control.requested.emit(True)
                        connection.send({'type': 'recording'})
                if paused_at is not None:
                    return
                with frame_lock:
                    current_frame = QVideoFrame(latest)
                if not current_frame.isValid():
                    if now > deadline:
                        raise RuntimeError('未收到屏幕画面。请检查系统屏幕录制权限后重试。')
                    return
                conversion_start = time.perf_counter()
                if options.window_title:
                    image = rgb_image(current_frame)
                    if writer and (image.width()//2*2, image.height()//2*2) != (writer.video.width, writer.video.height):
                        raise RuntimeError('窗口尺寸已改变，录制已停止；可恢复已录内容。')
                else:
                    from PySide6.QtCore import QRect
                    scale_x, scale_y = current_frame.width()/geometry.width(), current_frame.height()/geometry.height()
                    crop = QRect(round((region.x()-geometry.x())*scale_x), round((region.y()-geometry.y())*scale_y),
                                 round(region.width()*scale_x), round(region.height()*scale_y))
                    image = rgb_image(current_frame, crop)
                if image.isNull():
                    raise RuntimeError('无法读取屏幕帧。请检查系统屏幕录制权限。')
                metrics['image_conversion_ms'] += (time.perf_counter()-conversion_start)*1000
                if writer is None:
                    writer = VideoWriter(Path(options.target), image.width(), image.height(), options.fps, bool(device_ids))
                    audio = AudioCapture(device_ids) if device_ids else None
                    if audio:
                        audio.active.set()
                    started = now = time.monotonic()
                    connection.send({'type': 'recording', 'recovery': str(writer.recovery)})
                elapsed = now - started - paused_total
                array = np.frombuffer(image.constBits(), dtype=np.uint8).reshape(image.height(), image.bytesPerLine())
                if round(elapsed * options.fps) > writer.video_pts:
                    encoding_start = time.perf_counter()
                    writer.write_video(array[:, :image.width()*3].reshape(image.height(), image.width(), 3), elapsed)
                    metrics['encoding_ms'] += (time.perf_counter()-encoding_start)*1000
                    metrics['frames'] += 1
                if audio:
                    for chunk in audio.take():
                        writer.write_audio(chunk)
                if now - last_space_check > 2:
                    check_space(Path(options.target).parent)
                    last_space_check = now
                if now - last_status > .25:
                    connection.send({'type': 'progress', 'seconds': elapsed})
                    last_status = now
            except Exception as exc:
                # Stop failures must still report a recoverable file.
                finished = False
                fail(str(exc))

        def encode_loop():
            # A native GUI event loop can delay timers during window capture,
            # especially on macOS. Keep encoding cadence on its own clock while
            # all capture start/stop operations stay on the Qt main thread.
            previous = time.monotonic()
            while not finished and not stop_clock.is_set():
                began = time.monotonic()
                active_before = started is not None and paused_at is None
                if active_before:
                    metrics['max_clock_gap_ms'] = max(metrics['max_clock_gap_ms'], (began-previous)*1000)
                previous = began
                tick()
                work_time = time.monotonic()-began
                if active_before:
                    metrics['max_tick_ms'] = max(metrics['max_tick_ms'], work_time*1000)
                before_sleep = time.monotonic()
                time.sleep(max(.001, 1/options.fps-work_time))
                if active_before:
                    metrics['active_sleep_ms'] += (time.monotonic()-before_sleep)*1000

        activity.start()
        capture.start()
        encoder_thread = threading.Thread(target=encode_loop, name='screen-encoder', daemon=True)
        encoder_thread.start()
        app.exec()
    except Exception as exc:
        connection.send({'type': 'error', 'message': str(exc), 'recovery': str(writer.recovery) if writer else None})
    finally:
        finished = True
        stop_clock.set()
        if encoder_thread:
            encoder_thread.join()
        if capture:
            capture.stop()
        activity.stop()
        if audio:
            audio.close()
        if writer:
            writer.close()
        connection.close()
