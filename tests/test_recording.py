"""Decode actual encoded media; verify recovery, duration and output isolation."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
av = pytest.importorskip('av')
from shiguang_capture.recording.encoder import VideoWriter, recover_recording, check_space


def write_sample(target, seconds=2, audio=True):
    writer = VideoWriter(target, 160, 96, 30, audio)
    for frame_no in range(seconds * 30):
        frame = np.zeros((96, 160, 3), np.uint8)
        frame[:, :, frame_no // 30 % 3] = 200
        writer.write_video(frame, frame_no / 30)
        if audio:
            sample = np.arange(1600) + frame_no * 1600
            tone = .2 * np.sin(2 * np.pi * 440 * sample/48000)
            writer.write_audio(np.column_stack([tone, tone]))
    return writer


def test_mp4_decodes_video_and_audio_without_overwriting(tmp_path):
    original = tmp_path/'中文 recording.mp4'
    original.write_bytes(b'existing file')
    writer = write_sample(original)
    output = writer.finish()
    assert original.read_bytes() == b'existing file'
    assert output != original and not writer.recovery.exists()
    with av.open(str(output)) as media:
        video = list(media.decode(video=0))
        assert len(video) == 60
        assert video[0].width == 160 and video[0].height == 96
        assert abs(float(video[-1].time) - 59/30) < .05
        assert video[0].to_ndarray(format='rgb24')[:, :, 0].mean() > 180
    with av.open(str(output)) as media:
        audio = np.concatenate([frame.to_ndarray() for frame in media.decode(audio=0)], axis=1)
        assert .10 < np.sqrt((audio**2).mean()) < .20
        assert 1.95 < audio.shape[1]/48000 < 2.1


def test_disk_failure_keeps_recoverable_source(tmp_path, monkeypatch):
    writer = write_sample(tmp_path/'video.mp4', audio=False)
    from shiguang_capture.recording import encoder
    monkeypatch.setattr(encoder, 'check_space', lambda *args: (_ for _ in ()).throw(OSError('disk full')))
    with pytest.raises(OSError, match='disk full'):
        writer.finish()
    assert writer.recovery.exists()
    with av.open(str(writer.recovery)) as media:
        assert len(list(media.decode(video=0))) == 60


def test_abrupt_exit_can_recover_completed_clusters(tmp_path):
    script = '''
import os, sys
from pathlib import Path
import numpy as np
from shiguang_capture.recording.encoder import VideoWriter
w = VideoWriter(Path(sys.argv[1]), 160, 96, 30)
for i in range(150):
    w.write_video(np.full((96, 160, 3), i % 255, dtype=np.uint8), i/30)
Path(sys.argv[2]).write_text(str(w.recovery), encoding='utf-8')
os._exit(23)
'''
    manifest = tmp_path/'recovery-path.txt'
    child = subprocess.run([sys.executable, '-c', script, str(tmp_path/'crashed.mp4'), str(manifest)], timeout=30)
    assert child.returncode == 23
    recovery = Path(manifest.read_text(encoding='utf-8'))
    output = recover_recording(recovery, tmp_path/'recovered.mp4')
    with av.open(str(output)) as media:
        frames = list(media.decode(video=0))
        assert len(frames) >= 60  # Last unfinished cluster may be lost.
        assert float(frames[-1].time) > 2
    assert recovery.exists()  # Explicit recovery preserves the original.
