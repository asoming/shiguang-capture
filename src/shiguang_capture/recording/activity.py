"""Keep user-started macOS recording responsive without changing system settings."""
import sys


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
