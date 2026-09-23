"""Recording-only frame waits; Darwin timers request zero scheduling leeway."""
import sys
import threading


class RecordingClock:
    def __init__(self, stopped):
        self.stopped = stopped
        self.native = _DispatchTimer() if sys.platform == 'darwin' else None

    def wait(self, seconds):
        if not self.stopped.is_set():
            if self.native:
                self.native.wait(seconds)
            else:
                self.stopped.wait(seconds)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if self.native:
            self.native.close()


class _DispatchTimer:
    """One-shot GCD timer; no polling, busy-waiting or system power changes.

    Public source.h specifies DISPATCH_TIMER_STRICT = 1, which requests that
    dispatch_source_set_timer's zero leeway be honored even under power saving.
    All C callbacks stay alive until the cancellation handler has completed.
    """
    def __init__(self):
        import ctypes as c
        self.lib = c.CDLL('/usr/lib/system/libdispatch.dylib')
        self.ready, self.cancelled = threading.Event(), threading.Event()
        handler_type = c.CFUNCTYPE(None, c.c_void_p)
        self.handler = handler_type(lambda _: self.ready.set())
        self.cancel_handler = handler_type(lambda _: self.cancelled.set())
        signatures = {
            'dispatch_get_global_queue': ([c.c_long, c.c_ulong], c.c_void_p),
            'dispatch_source_create': ([c.c_void_p, c.c_size_t, c.c_ulong, c.c_void_p], c.c_void_p),
            'dispatch_source_set_event_handler_f': ([c.c_void_p, handler_type], None),
            'dispatch_source_set_cancel_handler_f': ([c.c_void_p, handler_type], None),
            'dispatch_source_set_timer': ([c.c_void_p, c.c_uint64, c.c_uint64, c.c_uint64], None),
            'dispatch_time': ([c.c_uint64, c.c_int64], c.c_uint64),
            'dispatch_resume': ([c.c_void_p], None),
            'dispatch_source_cancel': ([c.c_void_p], None),
            'dispatch_release': ([c.c_void_p], None),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.lib, name)
            function.argtypes, function.restype = args, result
        source_type = c.c_byte.in_dll(self.lib, '_dispatch_source_type_timer')
        queue = self.lib.dispatch_get_global_queue(0x21, 0)  # QOS_CLASS_USER_INTERACTIVE
        self.source = self.lib.dispatch_source_create(c.byref(source_type), 0, 1, queue)
        if not self.source:
            raise RuntimeError('无法创建 macOS 录屏计时器。')
        self.lib.dispatch_source_set_event_handler_f(self.source, self.handler)
        self.lib.dispatch_source_set_cancel_handler_f(self.source, self.cancel_handler)
        self.lib.dispatch_resume(self.source)

    def wait(self, seconds):
        self.ready.clear()
        deadline = self.lib.dispatch_time(0, max(1, round(seconds*1_000_000_000)))
        self.lib.dispatch_source_set_timer(self.source, deadline, (1 << 64)-1, 0)
        if not self.ready.wait(max(1, seconds*2)):
            raise RuntimeError('macOS 录屏计时器未响应，已停止录制。')

    def close(self):
        if self.source:
            self.lib.dispatch_source_cancel(self.source)
            # Resumed sources deliver cancellation after any event callback.
            self.cancelled.wait()
            self.lib.dispatch_release(self.source)
            self.source = None
