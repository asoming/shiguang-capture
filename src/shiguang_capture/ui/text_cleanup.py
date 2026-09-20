"""Preview only selected text, with every cleanup rule initially disabled."""
from difflib import unified_diff
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QCheckBox,
                              QPlainTextEdit, QDialogButtonBox, QLabel)
from ..text_cleanup import clean_selection


class CleanupDialog(QDialog):
    def __init__(self, selected, parent=None):
        super().__init__(parent)
        self.setWindowTitle('清理选中文字')
        self.resize(650, 460)
        self.original = selected
        self.result = selected
        layout = QVBoxLayout(self)
        rules = QHBoxLayout()
        self.numbers = QCheckBox('去编号（如 1. 或 2:）')
        self.join = QCheckBox('换行改为空格')
        rules.addWidget(self.numbers)
        rules.addWidget(self.join)
        layout.addLayout(rules)
        preview = QHBoxLayout()
        for title, value in [('原选区', selected), ('处理后', selected)]:
            column = QVBoxLayout()
            column.addWidget(QLabel(title))
            edit = QPlainTextEdit(value)
            edit.setReadOnly(True)
            column.addWidget(edit)
            preview.addLayout(column)
        self.after = edit
        layout.addLayout(preview, 2)
        layout.addWidget(QLabel('差异'))
        self.diff = QPlainTextEdit()
        self.diff.setReadOnly(True)
        layout.addWidget(self.diff, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel)
        self.apply = buttons.button(QDialogButtonBox.StandardButton.Apply)
        self.apply.setText('仅应用到选区')
        self.apply.setEnabled(False)
        self.apply.clicked.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.numbers.toggled.connect(self._update)
        self.join.toggled.connect(self._update)

    def _update(self):
        self.result = clean_selection(self.original, remove_line_numbers=self.numbers.isChecked(), join_lines=self.join.isChecked())
        self.after.setPlainText(self.result)
        self.diff.setPlainText(''.join(unified_diff(self.original.splitlines(True), self.result.splitlines(True),
                                                  fromfile='原选区', tofile='处理后')))
        self.apply.setEnabled(self.result != self.original)
