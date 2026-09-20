"""autostart.py — 开机自启动（Windows 注册表实现；其他平台降级为日志）。"""
from __future__ import annotations

import logging
import os
import sys

log = logging.getLogger(__name__)

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "ShiguangCapture"


def _launcher_command() -> str:
    """指向当前解释器 + 模块的启动命令（开发态）；打包后替换为 exe 路径。"""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{sys.executable}" -m shiguang_capture'


def is_supported() -> bool:
    return os.name == "nt"


def is_enabled() -> bool:
    if not is_supported():
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _VALUE_NAME)
            return True
    except OSError:
        return False


def set_enabled(enabled: bool) -> bool:
    """返回是否设置成功。非 Windows 平台记录日志并返回 False。"""
    if not is_supported():
        log.warning("当前平台暂不支持开机自启动设置")
        return False
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enabled:
                winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, _launcher_command())
            else:
                try:
                    winreg.DeleteValue(key, _VALUE_NAME)
                except OSError:
                    pass
        return True
    except OSError as exc:
        log.error("写入自启动失败: %s", exc)
        return False
