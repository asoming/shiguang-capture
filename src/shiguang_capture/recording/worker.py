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
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtGui import QGuiApplication, QImage
    from PySide6.QtMultimedia import QMediaCaptureSession, QScreenCapture, QWindowCapture, QVideoSink, QVideoFrame
    import av  # Load the encoder before starting the capture clock.
    import numpy as np
    from .encoder import VideoWriter, check_space
    from .activity import RecordingActivity

    app = QGuiApplication([])
    screen = next((s for s in app.screens() if s.name() == options.screen), None)
    writer = audio = None
    activity = RecordingActivity()
    metrics = {'frames': 0, 'image_conversion_ms': 0.0, 'encoding_ms': 0.0}
    finished = False
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
            connection.send({'type': 'error', 'message': message,
                             'recovery': str(writer.recovery) if writer else None})
            app.quit()

        def frame_changed(frame):
            nonlocal latest
            if frame.isValid() and paused_at is None:
                latest = QVideoFrame(frame)

        sink.videoFrameChanged.connect(frame_changed)
        capture.errorOccurred.connect(lambda error, text: fail(f'屏幕录制失败：{text}'))
        if not options.window_title:
            screen.geometryChanged.connect(lambda *_: fail('屏幕尺寸已改变，录制已停止；可恢复已录内容。'))
            app.screenRemoved.connect(lambda removed: fail('录制屏幕已断开；可恢复已录内容。') if removed == screen else None)

        def tick():
            nonlocal writer, audio, started, paused_at, paused_total, last_status, last_space_check, finished, latest, deadline
            if finished:
                return
            try:
                now = time.monotonic()
                while connection.poll():
                    command = connection.recv()
                    if command == 'stop':
                        finished = True
                        capture.stop()
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
                        capture.stop()
                        activity.stop()
                        if audio:
                            audio.pause()
                        connection.send({'type': 'paused'})
                    if command == 'resume' and paused_at is not None:
                        paused_total += now - paused_at
                        paused_at = None
                        latest = QVideoFrame()
                        deadline = now + 15
                        activity.start()
                        if audio:
                            audio.active.set()
                        capture.start()
                        connection.send({'type': 'recording'})
                if paused_at is not None:
                    return
                if not latest.isValid():
                    if now > deadline:
                        raise RuntimeError('未收到屏幕画面。请检查系统屏幕录制权限后重试。')
                    return
                conversion_start = time.perf_counter()
                full_image = latest.toImage()
                if full_image.isNull():
                    raise RuntimeError('无法读取屏幕帧。请检查系统屏幕录制权限。')
                if options.window_title:
                    image = full_image
                    if writer and (image.width()//2*2, image.height()//2*2) != (writer.video.width, writer.video.height):
                        raise RuntimeError('窗口尺寸已改变，录制已停止；可恢复已录内容。')
                else:
                    scale_x, scale_y = full_image.width()/geometry.width(), full_image.height()/geometry.height()
                    image = full_image.copy(round((region.x()-geometry.x())*scale_x),
                                        round((region.y()-geometry.y())*scale_y),
                                        round(region.width()*scale_x), round(region.height()*scale_y))
                image = image.convertToFormat(QImage.Format.Format_RGB888)
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

        timer = QTimer()
        timer.setTimerType(Qt.TimerType.PreciseTimer)
        timer.setInterval(max(1, round(1000/options.fps)))
        timer.timeout.connect(tick)
        timer.start()
        activity.start()
        capture.start()
        app.exec()
    except Exception as exc:
        connection.send({'type': 'error', 'message': str(exc), 'recovery': str(writer.recovery) if writer else None})
    finally:
        activity.stop()
        if audio:
            audio.close()
        if writer:
            writer.close()
        connection.close()
