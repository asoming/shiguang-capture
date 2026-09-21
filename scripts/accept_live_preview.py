"""Native preview acceptance, also included in standalone packages."""
import multiprocessing
import sys
from shiguang_capture.recording.preview_acceptance import verify_live_preview, run

if __name__ == '__main__':
    multiprocessing.freeze_support()
    raise SystemExit(run(sys.argv[1], '--window' in sys.argv))
