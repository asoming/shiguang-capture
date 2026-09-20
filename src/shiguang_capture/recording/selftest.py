"""Standalone package encoding check, entirely synthetic and temporary."""
def run():
    import tempfile
    from pathlib import Path
    import numpy as np
    import av
    from .encoder import VideoWriter
    with tempfile.TemporaryDirectory(prefix='shiguang-record-test-') as folder:
        writer = VideoWriter(Path(folder)/'中文 recording.mp4', 320, 180, 30, True)
        for index in range(60):
            rgb = np.zeros((180,320,3), dtype=np.uint8)
            rgb[:, :, 0 if index < 30 else 2] = 200
            writer.write_video(rgb, index/30)
            samples = np.arange(1600)+index*1600
            tone = .2*np.sin(2*np.pi*440*samples/48000)
            writer.write_audio(np.column_stack((tone,tone)))
        path = writer.finish()
        with av.open(str(path)) as media:
            frames = list(media.decode(video=0))
            assert len(frames)==60
            assert frames[0].to_ndarray(format='rgb24')[:,:,0].mean()>180
            assert frames[-1].to_ndarray(format='rgb24')[:,:,2].mean()>180
            assert abs(frames[-1].time-59/30)<.05
        with av.open(str(path)) as media:
            audio = np.concatenate([frame.to_ndarray() for frame in media.decode(audio=0)],axis=1)
            assert .1 < np.sqrt((audio**2).mean()) < .2
        print('Recording package self-test passed: video, audio, color, duration, Chinese path')
    return 0
