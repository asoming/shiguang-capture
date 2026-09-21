"""hotkeys.py — 全局热键（FR-1.1 / FR-1.2）。

pynput 在独立线程监听系统级按键，通过 Qt 信号桥回主线程，
保证界面响应不受监听线程阻塞（唤起 ≤ 200ms 的前提之一）。

pynput 为可选依赖：缺失时热键静默禁用，应用其余功能不受影响。
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal
from .shortcuts import normalize_shortcut

log = logging.getLogger(__name__)


class ChordMatcher:
    """Match the entire held chord, so Shift+F1 cannot also activate F1."""

    def __init__(self, actions):
        self.actions = actions
        self.pressed = set()

    def press(self, key):
        if key in self.pressed:
            return
        self.pressed.add(key)
        callback = self.actions.get(frozenset(self.pressed))
        if callback:
            callback()

    def release(self, key):
        self.pressed.discard(key)


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
        parts = normalize_shortcut(key).split('+')
        return "+".join(f"<{p}>" if len(p) > 1 or p in ("f1", "f2", "f3") else p for p in parts)

    def register(self, mapping: dict[str, str]) -> bool:
        """mapping: {action: key}，如 {'capture_region': 'f1'}。返回是否成功。"""
        import os

        if os.environ.get("SHIGUANG_NO_HOTKEYS"):
            log.info("热键已按环境变量 SHIGUANG_NO_HOTKEYS 禁用")
            return False
        if os.environ.get("QT_QPA_PLATFORM") in ("offscreen", "minimal"):
            # 无头/离屏环境没有可挂的消息循环，启动 pynput 监听会段错误
            log.info("离屏环境，跳过全局热键注册")
            return False
        try:
            from pynput import keyboard
        except ImportError:
            log.warning("pynput 未安装，全局热键不可用（pip install pynput）")
            return False
        try:
            actions = {}
            for action, key in mapping.items():
                if not key.strip():
                    continue
                chord = frozenset(keyboard.HotKey.parse(self._to_pynput(key)))
                if not chord or chord in actions:
                    raise ValueError("快捷键为空或重复")
                actions[chord] = lambda a=action: self.bridge.fire(a)
            matcher = ChordMatcher(actions)
            candidate = keyboard.Listener(
                on_press=lambda key: matcher.press(candidate.canonical(key)),
                on_release=lambda key: matcher.release(candidate.canonical(key)),
            )
            candidate.start()
        except Exception as exc:  # 平台权限不足（如 macOS 辅助功能未授权）
            log.error("全局热键注册失败: %s", exc)
            return False
        self.unregister()
        self._listener = candidate
        return True

    def unregister(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
