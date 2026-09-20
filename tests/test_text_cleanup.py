from shiguang_capture.text_cleanup import clean_selection


def test_cleanup_is_opt_in_and_does_not_remove_ids_dates_or_code():
    text = '00123\n2026-09-20\n1. print("hello")\n2:     return 0\nv1.2.3'
    assert clean_selection(text) == text
    assert clean_selection(text, remove_line_numbers=True) == '00123\n2026-09-20\nprint("hello")\n    return 0\nv1.2.3'
    assert clean_selection(' a\n  b', join_lines=True) == ' a   b'


def test_apply_changes_only_selected_range_and_undo_keeps_raw_output(qt_session, monkeypatch):
    import pytest
    pytest.importorskip('PySide6')
    from PySide6.QtGui import QTextCursor
    from shiguang_capture.ocr.base import OCRResult
    from shiguang_capture.ui.result_panel import ResultPanel
    from shiguang_capture.ui.text_cleanup import CleanupDialog
    original = 'keep\n1. first\n2. second\nkeep'
    panel = ResultPanel()
    panel.show_result('ocr', OCRResult(original, .9))
    cursor = panel.source_edit.textCursor()
    cursor.setPosition(5)
    cursor.setPosition(len(original)-5, QTextCursor.MoveMode.KeepAnchor)
    panel.source_edit.setTextCursor(cursor)
    def accept(dialog):
        assert not dialog.numbers.isChecked() and not dialog.join.isChecked()
        assert not dialog.apply.isEnabled()
        dialog.numbers.setChecked(True)
        assert dialog.diff.toPlainText()
        return dialog.DialogCode.Accepted
    monkeypatch.setattr(CleanupDialog, 'exec', accept)
    panel._clean_selected_text()
    assert panel.source_edit.toPlainText() == 'keep\nfirst\nsecond\nkeep'
    assert panel._result.text == original
    panel.source_edit.undo()
    assert panel.source_edit.toPlainText() == original
    panel.close()
