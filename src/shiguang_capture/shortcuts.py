"""Shared, platform-independent shortcut spelling and validation."""
import string

MODIFIERS = ('ctrl', 'alt', 'shift', 'cmd')
ALIASES = {'control': 'ctrl', 'meta': 'cmd', 'super': 'cmd', 'win': 'cmd',
           'command': 'cmd', 'option': 'alt', 'escape': 'esc', 'return': 'enter',
           'delete': 'delete', 'pageup': 'page_up', 'pagedown': 'page_down'}
KEYS = set(string.ascii_lowercase + string.digits + "-=[]\\;',./`") | {
    'space', 'tab', 'enter', 'esc', 'backspace', 'delete', 'insert',
    'home', 'end', 'page_up', 'page_down', 'left', 'right', 'up', 'down',
    *(f'f{i}' for i in range(1, 21)),
}


def normalize_shortcut(value: str) -> str:
    """Return one chord; an empty string explicitly disables the shortcut."""
    if not value.strip():
        return ''
    parts = [ALIASES.get(p.strip().lower(), p.strip().lower()) for p in value.split('+')]
    keys = [part for part in parts if part not in MODIFIERS]
    if len(parts) != len(set(parts)) or len(keys) != 1 or keys[0] not in KEYS:
        raise ValueError('请按下一个按键或组合键')
    return '+'.join([m for m in MODIFIERS if m in parts] + keys)


def shortcut_label(value: str) -> str:
    return value.replace('cmd', 'Cmd / Win').upper() if value else '未设置'
