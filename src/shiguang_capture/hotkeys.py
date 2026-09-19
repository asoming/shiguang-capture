"""hotkeys.py — 全局热键（FR-1.1 / FR-1.2）。

pynput 在独立线程监听系统级按键，通过 Qt 信号桥回主线程，
保证界面响应不受监听线程阻塞（唤起 ≤ 200ms 的前提之一）。

pynput 为可选依赖：缺失时热键静默禁用，应用其余功能不受影响。
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

log = logging.getLogger(__name__)


class HotkeyBridge(QObject):
    """把 pynput 的回调桥接为 Qt 信号（线程安全）。"""

    triggered = Signal(str)  # action 名

    def fire(self, action: str) -> None:
        self.triggered.emit(action)


class HotkeyManager:
    """注册/注销全局热键。映射：pynput 热键串 -> action 名。"""

    def __init__(self, bridge: HotkeyBridge | None = None) -> None:
        self.bridge = bridge or HotkeyBridge()
        self._listener = None

    @staticmethod
    def _to_pynput(key: str) -> str:
        """'ctrl+f1' -> '<ctrl>+<f1>'"""
        parts = [p.strip() for p in key.lower().split("+") if p.strip()]
        return "+".join(f"<{p}>" if len(p) > 1 or p in ("f1", "f2", "f3") else p for p in parts)

    def register(self, mapping: dict[str, str]) -> bool:
        """mapping: {action: key}，如 {'capture_region': 'f1'}。返回是否成功。"""
        try:
            from pynput import keyboard
        except ImportError:
            log.warning("pynput 未安装，全局热键不可用（pip install pynput）")
            return False
        self.unregister()
        hotkeys = {
            self._to_pynput(key): (lambda a=action: self.bridge.fire(a))
            for action, key in mapping.items()
        }
        try:
            self._listener = keyboard.GlobalHotKeys(hotkeys)
            self._listener.start()
        except Exception as exc:  # 平台权限不足（如 macOS 辅助功能未授权）
            log.error("全局热键注册失败: %s", exc)
            self._listener = None
            return False
        return True

    def unregister(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
