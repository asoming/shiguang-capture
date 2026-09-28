"""User-local login entries stay accurate and survive app updates."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from shiguang_capture import autostart


@pytest.fixture
def linux(monkeypatch, tmp_path):
    monkeypatch.setattr(autostart.sys, 'platform', 'linux')
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'config'))
    monkeypatch.setattr(autostart.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(autostart.sys, 'executable', str(tmp_path / 'App Folder' / 'ShiguangCapture'))
    return autostart._desktop_path()


def test_enable_disable_and_external_disabled_state(linux):
    assert not autostart.is_enabled()
    assert autostart.set_enabled(True)
    assert autostart.is_enabled()
    text = linux.read_text(encoding='utf-8')
    assert 'Type=Application' in text and 'Exec="' in text
    linux.write_text(text.replace('Hidden=false', 'Hidden=true'), encoding='utf-8')
    assert not autostart.is_enabled()
    assert autostart.set_enabled(True)
    assert autostart.is_enabled()
    assert autostart.set_enabled(False)
    assert not linux.exists() and not autostart.is_enabled()
    assert autostart.set_enabled(False)


def test_failed_atomic_update_preserves_previous_file(linux, monkeypatch):
    assert autostart.set_enabled(True)
    original = linux.read_bytes()
    def fail(*args):
        raise PermissionError('read only')
    monkeypatch.setattr(autostart.os, 'replace', fail)
    assert not autostart.set_enabled(True)
    assert linux.read_bytes() == original
    assert list(linux.parent.iterdir()) == [linux]


def test_broken_entry_is_not_enabled(linux):
    linux.parent.mkdir(parents=True)
    linux.write_text('broken entry', encoding='utf-8')
    assert not autostart.is_enabled()
    assert autostart.set_enabled(True)
    linux.write_text(linux.read_text(encoding='utf-8').replace('ShiguangCapture"', 'missing-app"'), encoding='utf-8')
    assert not autostart.is_enabled()


def test_current_symlink_is_used_across_updates(linux, tmp_path, monkeypatch):
    if autostart.os.name == 'nt':
        pytest.skip('POSIX user-local installer symlink')
    root = tmp_path / 'installed'
    executable = root / '1.5.0b2' / 'ShiguangCapture'
    executable.parent.mkdir(parents=True)
    executable.touch()
    (root / 'current').symlink_to(executable.parent, target_is_directory=True)
    monkeypatch.setattr(autostart.sys, 'executable', str(executable))
    assert autostart._launcher_args() == [str(root / 'current' / 'ShiguangCapture')]
    assert autostart.set_enabled(True)
    assert 'current' in linux.read_text(encoding='utf-8')


def test_desktop_exec_escapes_literal_field_codes_and_shell_characters(linux, monkeypatch):
    monkeypatch.setattr(autostart, '_launcher_args', lambda: ['/tmp/a b%f"$`\\app'])
    assert autostart._desktop_command() == '"/usr/bin/env" "/tmp/a b%%f\\\\"\\\\$\\\\`\\\\\\\\app"'


def test_windows_creates_missing_run_key_and_preserves_command(monkeypatch):
    monkeypatch.setattr(autostart.sys, 'platform', 'win32')
    monkeypatch.setattr(autostart, '_launcher_args', lambda: ['C:\\Program Files\\Shiguang\\app.exe'])
    values = {}
    class Key:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    def delete(key, name):
        if name not in values:
            raise FileNotFoundError(name)
        del values[name]
    registry = SimpleNamespace(HKEY_CURRENT_USER=1, KEY_SET_VALUE=2, REG_SZ=3,
        CreateKeyEx=lambda *args: Key(), OpenKey=lambda *args: Key(),
        SetValueEx=lambda key, name, reserved, kind, value: values.update({name: value}),
        QueryValueEx=lambda key, name: (values.get(name, ''), 3), DeleteValue=delete)
    monkeypatch.setitem(autostart.sys.modules, 'winreg', registry)
    assert autostart.set_enabled(True) and autostart.is_enabled()
    assert values['ShiguangCapture'] == '"C:\\Program Files\\Shiguang\\app.exe"'
    assert autostart.set_enabled(False) and not autostart.is_enabled()
    assert autostart.set_enabled(False)
