"""Keep user-started macOS recording responsive without changing system settings."""
import sys


def configure_encoder_thread():
    if sys.platform != 'darwin':
        return None
    import ctypes
    system = ctypes.CDLL('/usr/lib/libSystem.B.dylib')
    set_quality = system.pthread_set_qos_class_self_np
    set_quality.argtypes = [ctypes.c_uint, ctypes.c_int]
    set_quality.restype = ctypes.c_int
    # Apple's public sys/qos.h: latency-sensitive, user-interactive thread.
    # This applies only to the recording thread and ends when it exits.
    return set_quality(0x21, 0)


class RecordingActivity:
    def __init__(self):
        self.process = self.token = None

    def start(self):
        if sys.platform != 'darwin' or self.token is not None:
            return
        from Foundation import (NSProcessInfo, NSActivityUserInitiatedAllowingIdleSystemSleep,
                                NSActivityLatencyCritical)
        self.process = NSProcessInfo.processInfo()
        self.token = self.process.beginActivityWithOptions_reason_(
            NSActivityUserInitiatedAllowingIdleSystemSleep | NSActivityLatencyCritical,
            '用户正在录制屏幕')

    def stop(self):
        if self.token is not None:
            self.process.endActivity_(self.token)
            self.token = None
