import pytest
pytest.importorskip('PySide6')
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QPushButton
from PySide6.QtTest import QTest
from shiguang_capture.ocr.base import OCRResult
from shiguang_capture.ui.result_panel import ResultPanel
from shiguang_capture.translate import TranslationResult


def test_recognition_has_only_translate_button_and_uses_edited_text(qt_session):
    panel = ResultPanel()
    image = QImage(600, 400, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    panel.set_image(image)
    panel.show_result('ocr', OCRResult('Original text', .95))
    panel.show()
    qt_session.processEvents()
    assert [b.text() for b in panel.findChildren(QPushButton) if b.isVisible()] == ['翻译']
    assert not panel.right.isVisible()
    calls = []
    panel.translate_requested.connect(calls.append)
    panel.source_edit.setPlainText('Corrected text')
    QTest.mouseClick(panel.translate_button, Qt.MouseButton.LeftButton)
    assert calls == ['Corrected text']
    panel.show_translation(OCRResult('Corrected text', .95),
                           TranslationResult('Corrected text', '校对后的文字', 'en', 'zh', 'test'))
    assert panel.right.isVisible()
    assert panel.source_edit.toPlainText() == 'Corrected text'
    assert panel.target_edit.toPlainText() == '校对后的文字'
    panel.close()
    panel.deleteLater()
