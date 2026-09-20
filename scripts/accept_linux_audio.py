"""PulseAudio loopback/mixing acceptance using private virtual sinks only.

Never reads the user's real microphone, changes default devices or plays sound
through physical speakers. Every created PulseAudio module is unloaded on exit.
"""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
import numpy as np
from shiguang_capture.recording.worker import AudioCapture


def main():
    import soundcard
    output = Path(sys.argv[1] if len(sys.argv)>1 else 'artifacts/audio')
    output.mkdir(parents=True, exist_ok=True)
    modules, devices, players = [], [], []
    done = threading.Event()
    capture = None
    report = {'status':'failed', 'scope':'Linux virtual PulseAudio loopback and two-source mixing; no physical microphone'}
    try:
        for index in range(2):
            name = f'shiguang_accept_{os.getpid()}_{index}'
            module = subprocess.check_output(['pactl','load-module','module-null-sink',f'sink_name={name}',
                                              'rate=48000','channels=2'], text=True).strip()
            modules.append(module)
            devices.append(name)
        capture = AudioCapture([name+'.monitor' for name in devices])
        capture.active.set()

        def play(name, frequency):
            speaker = soundcard.get_speaker(name)
            with speaker.player(samplerate=48000, channels=2, blocksize=960) as player:
                offset = 0
                while not done.is_set():
                    sample = np.arange(960)+offset
                    tone = .15*np.sin(2*np.pi*frequency*sample/48000)
                    player.play(np.column_stack([tone,tone]))
                    offset += 960

        for name, frequency in zip(devices, (440, 880)):
            thread = threading.Thread(target=play, args=(name,frequency), daemon=True)
            thread.start()
            players.append(thread)
        chunks = []
        deadline = time.monotonic()+4
        while time.monotonic()<deadline:
            chunks.extend(capture.take())
            time.sleep(.02)
        capture.pause()
        time.sleep(.15)
        assert not list(capture.take()), 'Audio continued during pause'
        capture.active.set()
        deadline = time.monotonic()+1
        resumed = []
        while time.monotonic()<deadline:
            resumed.extend(capture.take())
            time.sleep(.02)
        assert resumed, 'Audio failed to resume'
        audio = np.concatenate(chunks)
        assert len(audio)>48000, 'Too few captured samples'
        signal = audio[-48000:,0]
        spectrum = abs(np.fft.rfft(signal))
        assert spectrum[440]>100 and spectrum[880]>100, 'One audio source missing from mix'
        assert abs(signal).max()<=1, 'Mix clipped outside valid range'
        report.update(status='passed', samples=len(audio), tone_440=float(spectrum[440]),
                      tone_880=float(spectrum[880]), resumed_samples=sum(len(chunk) for chunk in resumed))
        capture.close()
        capture = None
        from shiguang_capture.recording.acceptance import main as record_desktop
        record_desktop(output/'native-mixed', audio_devices=[name+'.monitor' for name in devices])
    except Exception as exc:
        report['error']=str(exc)
        raise
    finally:
        done.set()
        if capture:
            capture.close()
        for thread in players:
            thread.join(timeout=2)
        for module in reversed(modules):
            subprocess.run(['pactl','unload-module',module], check=True)
        (output/'report.json').write_text(json.dumps(report,indent=2), encoding='utf-8')
        print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
