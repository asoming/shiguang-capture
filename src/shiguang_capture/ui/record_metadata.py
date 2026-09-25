"""On-demand video details, isolated from the GUI and cached only in memory."""
from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass
import math
import multiprocessing
from pathlib import Path
import time

from PySide6.QtCore import QCoreApplication, QObject, QTimer, Signal


@dataclass(frozen=True)
class VideoDetails:
    duration: float | None = None
    width: int = 0
    height: int = 0
    pixels: bytes = b''
    thumbnail_width: int = 0
    thumbnail_height: int = 0
    error: str = ''


def video_details(path: str) -> VideoDetails:
    """Read the header and one frame; never decode a whole recording for its duration."""
    import av

    with av.open(path, options={'protocol_whitelist': 'file'}) as media:
        if not media.streams.video:
            return VideoDetails(error='没有视频画面')
        stream = media.streams.video[0]
        width, height = stream.codec_context.width, stream.codec_context.height
        if not 0 < width <= 32767 or not 0 < height <= 32767 or width * height > 64_000_000:
            return VideoDetails(error='视频尺寸超出预览范围')
        duration = float(media.duration / av.time_base) if media.duration is not None else None
        if duration is None and stream.duration is not None and stream.time_base is not None:
            duration = float(stream.duration * stream.time_base)
        if duration is not None and (not math.isfinite(duration) or duration < 0):
            duration = None
        # The first decodable frame needs no index/seek and works with large files.
        # The supervising process also enforces a wall-clock deadline.
        for index, packet in enumerate(media.demux(stream)):
            if index >= 96:
                break
            for frame in packet.decode():
                scale = min(192 / width, 108 / height, 1)
                w, h = max(1, round(width * scale)), max(1, round(height * scale))
                pixels = frame.reformat(width=w, height=h, format='rgb24').to_ndarray().tobytes()
                return VideoDetails(duration, width, height, pixels, w, h)
        return VideoDetails(duration=duration, width=width, height=height, error='暂无可用缩略图')


def _metadata_worker(connection):
    """A bad decoder can be terminated without blocking or taking down the app."""
    from ..recording.encoder import _media_locale
    _media_locale()
    try:
        while True:
            key = connection.recv()
            try:
                path = Path(key[0])
                stat = path.stat()
                if (stat.st_size, stat.st_mtime_ns) != key[1:]:
                    details = VideoDetails(error='文件已变化')
                else:
                    details = video_details(str(path))
            except Exception:
                # Decoder/import failures are scoped to this file. No content is logged.
                details = VideoDetails(error='无法读取视频信息')
            connection.send((key, details))
    except (EOFError, BrokenPipeError, OSError):
        return
    finally:
        connection.close()


class VideoMetadataLoader(QObject):
    ready = Signal(object, object)

    def __init__(self, parent=None, *, cache_limit=128):
        super().__init__(parent)
        self.cache_limit = cache_limit
        self.cache = OrderedDict()
        self.process = self.connection = None
        self.current = None
        self.queue = deque()
        self.deadline = 0
        self.idle_since = 0
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self._poll)
        if parent is not None:
            parent.destroyed.connect(self.stop)
        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.stop)

    def get(self, key):
        details = self.cache.get(key)
        if details is not None:
            self.cache.move_to_end(key)
        return details

    def request(self, keys):
        """Keep work limited to rows visible now; scrolling replaces the pending queue."""
        keys = list(dict.fromkeys(keys))
        if self.current is not None and self.current not in keys:
            self._close_worker()
        self.queue = deque(key for key in keys if key not in self.cache and key != self.current)
        if self.queue or self.current is not None:
            self.timer.start()

    def _remember(self, key, details):
        self.cache[key] = details
        self.cache.move_to_end(key)
        while len(self.cache) > self.cache_limit:
            self.cache.popitem(last=False)
        self.ready.emit(key, details)

    def _start_worker(self):
        context = multiprocessing.get_context('spawn')
        self.connection, child = context.Pipe()
        self.process = context.Process(target=_metadata_worker, args=(child,), daemon=True)
        try:
            self.process.start()
        except (OSError, RuntimeError):
            self.connection.close()
            self.process = self.connection = None
            return False
        finally:
            child.close()
        return True

    def _poll(self):
        if self.current is not None:
            try:
                if self.connection.poll():
                    key, details = self.connection.recv()
                    expected, self.current = self.current, None
                    if key == expected:
                        self._remember(key, details)
                    self.idle_since = time.monotonic()
                elif not self.process.is_alive() or time.monotonic() > self.deadline:
                    key = self.current
                    self._close_worker()
                    self._remember(key, VideoDetails(error='视频信息读取超时'))
            except (EOFError, BrokenPipeError, OSError):
                key = self.current
                self._close_worker()
                self._remember(key, VideoDetails(error='无法读取视频信息'))
        if self.current is not None:
            return
        if not self.queue:
            if self.process is None or time.monotonic() - self.idle_since > 3:
                self._close_worker()
                self.timer.stop()
            return
        key = self.queue.popleft()
        if self.process is None and not self._start_worker():
            self._remember(key, VideoDetails(error='无法读取视频信息'))
            return
        try:
            self.connection.send(key)
        except (BrokenPipeError, OSError):
            self._close_worker()
            self._remember(key, VideoDetails(error='无法读取视频信息'))
            return
        self.current = key
        self.deadline = time.monotonic() + 8

    def _close_worker(self):
        process, self.process = self.process, None
        connection, self.connection = self.connection, None
        self.current = None
        if connection is not None:
            connection.close()
        if process is not None and process.pid is not None:
            if process.is_alive():
                process.terminate()
            process.join(timeout=.05)
            if process.is_alive():
                process.kill()
                process.join(timeout=.05)
            if not process.is_alive():
                process.close()

    def stop(self):
        self.timer.stop()
        self.queue.clear()
        self._close_worker()
