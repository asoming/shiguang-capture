"""Per-user login startup: Windows Run key and Linux XDG desktop entry."""
from __future__ import annotations

import configparser
import logging
import os
from pathlib import Path
import sys
import tempfile

log = logging.getLogger(__name__)
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "ShiguangCapture"


def _launcher_args() -> list[str]:
    executable = Path(sys.executable)
    if getattr(sys, 'frozen', False):
        # User-local updates move the current symlink, not the login entry.
        current = executable.parent.parent / 'current' / executable.name
        if current.is_file() and current.resolve() == executable.resolve():
            executable = current
        return [str(executable)]
    return [str(executable), '-m', 'shiguang_capture']


def _launcher_command() -> str:
    import subprocess
    return subprocess.list2cmdline(_launcher_args())


def _desktop_command() -> str:
    def quote(argument):
        if any(c in argument for c in '\n\r\x00'):
            raise ValueError('Invalid launcher path')
        # Exec quoting is decoded after desktop-entry string escaping.
        escaped = ''.join('\\' + c if c in '\\"`$' else c for c in argument)
        return '"' + escaped.replace('\\', '\\\\').replace('%', '%%') + '"'
    arguments = _launcher_args()
    if '%' in arguments[0]:
        # GIO checks the executable before expanding %% field escapes. Passing
        # the path as env's argument preserves literal percent signs as well.
        arguments = ['/usr/bin/env', *arguments]
    return ' '.join(quote(argument) for argument in arguments)


def _desktop_path() -> Path:
    configured = Path(os.environ.get('XDG_CONFIG_HOME', ''))
    directory = configured if configured.is_absolute() else Path.home() / '.config'
    return directory / 'autostart' / 'shiguang-capture.desktop'


def is_supported() -> bool:
    return sys.platform == 'win32' or sys.platform.startswith('linux')


def is_enabled() -> bool:
    if sys.platform.startswith('linux'):
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read_string(_desktop_path().read_text(encoding='utf-8'))
            entry = parser['Desktop Entry']
            return (entry.get('Type') == 'Application'
                    and entry.get('Exec') == _desktop_command()
                    and not entry.getboolean('Hidden', fallback=False)
                    and entry.getboolean('X-GNOME-Autostart-enabled', fallback=True))
        except (OSError, ValueError, KeyError, configparser.Error):
            return False
    if sys.platform != 'win32':
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            command, _ = winreg.QueryValueEx(key, _VALUE_NAME)
            return bool(command)
    except OSError:
        return False


def _set_linux_enabled(enabled: bool) -> None:
    path = _desktop_path()
    if not enabled:
        path.unlink(missing_ok=True)
        return
    command = _desktop_command()
    content = ('[Desktop Entry]\nType=Application\nName=Shiguang Capture\n'
               'Name[zh_CN]=拾光 Capture\n'
               f'Exec={command}\nTerminal=false\nHidden=false\n'
               'X-GNOME-Autostart-enabled=true\nStartupWMClass=shiguang-capture\n')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.shiguang-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def set_enabled(enabled: bool) -> bool:
    try:
        if sys.platform.startswith('linux'):
            _set_linux_enabled(enabled)
            return True
        if sys.platform == 'win32':
            import winreg
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                if enabled:
                    winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, _launcher_command())
                else:
                    try:
                        winreg.DeleteValue(key, _VALUE_NAME)
                    except FileNotFoundError:
                        pass
            return True
    except (OSError, ValueError) as exc:
        log.error('设置登录自启动失败: %s', exc)
        return False
    log.warning('当前平台暂不支持登录自启动设置')
    return False
