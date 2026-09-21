"""Record one shortcut without requiring users to type its syntax."""
import sys

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QLineEdit

from ..shortcuts import normalize_shortcut


class HotkeyEdit(QLineEdit):
    def __init__(self, value, parent=None):
        super().__init__(value, parent)
        self.setReadOnly(True)
        self.setPlaceholderText('未设置 · 点击后按下快捷键')
        self.setAccessibleName('快捷键，点击后按下组合键')
        self.setToolTip('直接按下组合键；Backspace 清除，Esc 取消此次修改')
        self._before_edit = value

    def focusInEvent(self, event):
        self._before_edit = self.text()
        super().focusInEvent(event)
        self.selectAll()

    def event(self, event):
        if event.type() == QEvent.Type.ShortcutOverride:
            event.accept()
            return True
        if (event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Tab
                and event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier)):
            self.keyPressEvent(event)
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        event.accept()
        if event.isAutoRepeat():
            return
        key, modifiers = event.key(), event.modifiers()
        if key == Qt.Key.Key_Escape and not modifiers:
            self.setText(self._before_edit)
            self.clearFocus()
            return
        if key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete) and not modifiers:
            self.clear()
            return
        names = {Qt.Key.Key_Tab: 'tab', Qt.Key.Key_Space: 'space', Qt.Key.Key_Return: 'enter',
                 Qt.Key.Key_Enter: 'enter', Qt.Key.Key_Escape: 'esc',
                 Qt.Key.Key_Backspace: 'backspace', Qt.Key.Key_Delete: 'delete',
                 Qt.Key.Key_Insert: 'insert', Qt.Key.Key_Home: 'home', Qt.Key.Key_End: 'end',
                 Qt.Key.Key_PageUp: 'page_up', Qt.Key.Key_PageDown: 'page_down',
                 Qt.Key.Key_Left: 'left', Qt.Key.Key_Right: 'right',
                 Qt.Key.Key_Up: 'up', Qt.Key.Key_Down: 'down'}
        if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F20:
            name = f'f{key - Qt.Key.Key_F1 + 1}'
        else:
            name = names.get(key, chr(key).lower() if 32 <= key < 127 else '')
        if not name:
            return
        # Qt swaps Control and Meta on macOS; pynput uses physical names.
        ctrl, meta = ('cmd', 'ctrl') if sys.platform == 'darwin' else ('ctrl', 'cmd')
        parts = [name for flag, name in ((Qt.KeyboardModifier.ControlModifier, ctrl),
                 (Qt.KeyboardModifier.AltModifier, 'alt'),
                 (Qt.KeyboardModifier.ShiftModifier, 'shift'),
                 (Qt.KeyboardModifier.MetaModifier, meta)) if modifiers & flag]
        try:
            self.setText(normalize_shortcut('+'.join(parts + [name])))
        except ValueError:
            pass
