"""Run native capture acceptance from the same implementation shipped in the app."""
import argparse
import multiprocessing
from shiguang_capture.recording.acceptance import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", default="artifacts/native-recording")
    parser.add_argument("--window", action="store_true")
    args = parser.parse_args()
    main(args.output, args.window)
