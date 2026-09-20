"""Keep user-started macOS recording responsive without changing system settings."""
import sys
import time


def recording_waiter():
    """Use the native absolute clock on macOS; never busy-wait for a frame."""
    if sys.platform != 'darwin':
        return time.sleep
    import ctypes

    class Timebase(ctypes.Structure):
        _fields_ = [('numer', ctypes.c_uint32), ('denom', ctypes.c_uint32)]

    system = ctypes.CDLL('/usr/lib/libSystem.B.dylib')
    info = Timebase()
    system.mach_timebase_info.argtypes = [ctypes.POINTER(Timebase)]
    if system.mach_timebase_info(ctypes.byref(info)) or not info.numer or not info.denom:
        raise RuntimeError('无法初始化录屏时钟。')
    now = system.mach_absolute_time
    now.argtypes = []
    now.restype = ctypes.c_uint64
    wait = system.mach_wait_until
    wait.argtypes = [ctypes.c_uint64]
    wait.restype = ctypes.c_int
    ticks_per_second = 1_000_000_000 * info.denom / info.numer

    def sleep(seconds):
        deadline = now() + max(1, round(seconds*ticks_per_second))
        while True:
            result = wait(deadline)
            if result == 0:
                return
            if result != 14:  # KERN_ABORTED: retry the same deadline after interruption.
                raise RuntimeError(f'录屏时钟等待失败：{result}')

    return sleep


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
