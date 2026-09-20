"""Crash-recoverable video writing and lossless MP4 finalization."""
from __future__ import annotations

import os
import locale
import shutil
import tempfile
from fractions import Fraction
from pathlib import Path


def _media_locale():
    # Qt may localize libc error strings. PyAV 16 decodes errno messages as
    # ASCII, even for normal EAGAIN during audio buffering. This module runs in
    # the isolated media process, so changing its diagnostics leaves GUI locale intact.
    locale.setlocale(getattr(locale, 'LC_MESSAGES', locale.LC_ALL), 'C')


def check_space(folder: Path, required: int = 100 * 1024 * 1024):
    if shutil.disk_usage(folder).free < required:
        raise OSError('磁盘空间不足；请释放空间后恢复录制文件。')


def publish_exclusive(source: Path, target: Path) -> Path:
    """Never replace an existing recording, including concurrent name collisions."""
    for index in range(10000):
        candidate = target if not index else target.with_stem(f'{target.stem}-{index}')
        try:
            # Exclusive create also works on FAT/network output folders.
            with candidate.open('xb') as output:
                try:
                    with source.open('rb') as input_file:
                        shutil.copyfileobj(input_file, output, 1024 * 1024)
                    output.flush()
                    os.fsync(output.fileno())
                except BaseException:
                    candidate.unlink(missing_ok=True)
                    raise
            return candidate
        except FileExistsError:
            continue
    raise FileExistsError('同名录制文件过多，请换一个名称。')


def recover_recording(source: Path, target: Path) -> Path:
    _media_locale()
    import av
    check_space(target.parent, source.stat().st_size * 2 + 20 * 1024 * 1024)
    fd, name = tempfile.mkstemp(prefix='.sgc-final-', suffix='.mp4', dir=target.parent)
    os.close(fd)
    temporary = Path(name)
    video_packets = 0
    try:
        with av.open(str(source)) as original, av.open(str(temporary), 'w', format='mp4') as output:
            streams = {s.index: output.add_stream_from_template(s)
                       for s in original.streams if s.type in {'video', 'audio'}}
            for packet in original.demux():
                if packet.dts is None or packet.stream.index not in streams:
                    continue
                if packet.stream.type == 'video':
                    video_packets += 1
                packet.stream = streams[packet.stream.index]
                output.mux(packet)
        if not video_packets:
            raise ValueError('恢复文件中没有完整视频帧。原文件已保留。')
        return publish_exclusive(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


class VideoWriter:
    def __init__(self, target: Path, width: int, height: int, fps: int, audio: bool = False):
        _media_locale()
        import av
        if fps not in (15, 30, 60) or width < 2 or height < 2:
            raise ValueError('无效的帧率或画面尺寸。')
        target.parent.mkdir(parents=True, exist_ok=True)
        check_space(target.parent)
        self.target = target
        fd, name = tempfile.mkstemp(prefix=f'.{target.stem}-', suffix='.sgc-recovery.mkv', dir=target.parent)
        os.close(fd)
        self.recovery = Path(name)
        self.container = av.open(name, 'w', format='matroska', options={
            'cluster_time_limit': '1000', 'flush_packets': '1'})
        self.video = self.container.add_stream('mpeg4', rate=fps)
        self.video.width, self.video.height = width // 2 * 2, height // 2 * 2
        self.video.pix_fmt = 'yuv420p'
        self.video.bit_rate = max(2_000_000, width * height * fps // 5)
        self.video.codec_context.gop_size = fps
        self.video.codec_context.max_b_frames = 0
        self.audio = self.container.add_stream('aac', rate=48000) if audio else None
        if self.audio:
            self.audio.layout = 'stereo'
            self.audio.bit_rate = 192000
        self.fps, self.video_pts, self.audio_pts = fps, -1, 0
        self.closed = False

    def write_video(self, rgb, elapsed: float):
        import av
        pts = max(self.video_pts + 1, round(elapsed * self.fps))
        frame = av.VideoFrame.from_ndarray(rgb, format='rgb24')
        frame = frame.reformat(width=self.video.width, height=self.video.height, format='yuv420p')
        frame.pts, frame.time_base = pts, Fraction(1, self.fps)
        for packet in self.video.encode(frame):
            self.container.mux(packet)
        self.video_pts = pts

    def write_audio(self, stereo):
        import av
        import numpy as np
        if self.audio is None:
            raise ValueError('本次录制未启用音频。')
        frame = av.AudioFrame.from_ndarray(np.ascontiguousarray(stereo.T, dtype='float32'),
                                          format='fltp', layout='stereo')
        frame.sample_rate, frame.time_base, frame.pts = 48000, Fraction(1, 48000), self.audio_pts
        for packet in self.audio.encode(frame):
            self.container.mux(packet)
        self.audio_pts += len(stereo)

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            for stream in (self.video, self.audio):
                if stream is not None:
                    for packet in stream.encode(None):
                        self.container.mux(packet)
        finally:
            self.container.close()

    def finish(self):
        self.close()
        result = recover_recording(self.recovery, self.target)
        self.recovery.unlink()
        return result
