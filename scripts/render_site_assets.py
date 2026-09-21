"""Render real application widgets with public sample content, never the desktop.

Run with PYTHONPATH=src QT_QPA_PLATFORM=offscreen SHIGUANG_NO_HOTKEYS=1.
These are illustrative UI renders, not OCR or recording acceptance evidence.
"""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

from shiguang_capture.ocr.base import OCRResult
from shiguang_capture.translate import TranslationResult
from shiguang_capture.ui.record_panel import RecordPanel
from shiguang_capture.ui.result_panel import ResultPanel


def main():
    app = QApplication([])
    app.setFont(QFont('Noto Sans CJK SC', 10))
    out = Path(__file__).resolve().parents[1] / 'docs/assets'
    source = QImage(960, 600, QImage.Format.Format_RGB888)
    source.fill(QColor('#FFFFFF'))
    painter = QPainter(source)
    painter.fillRect(0, 0, 14, 600, QColor('#246DEB'))
    painter.setPen(QColor('#246DEB'))
    painter.setFont(QFont('Noto Sans CJK SC', 16))
    painter.drawText(65, 75, 'STUDIO NOTES   /   01')
    painter.setPen(QColor('#122943'))
    painter.setFont(QFont('Noto Sans CJK SC', 38, QFont.Weight.Bold))
    painter.drawText(65, 175, '记录一个好想法。')
    painter.setFont(QFont('Noto Sans CJK SC', 17))
    painter.setPen(QColor('#586C86'))
    painter.drawText(65, 240, '从屏幕上的一瞬，到可以分享的下一步。')
    for i, height in enumerate((54, 92, 70, 126, 108, 162, 142, 185)):
        painter.fillRect(65+i*98, 485-height, 62, height, QColor('#246DEB' if i > 4 else '#DFEAFC'))
    painter.setFont(QFont('Noto Sans CJK SC', 13))
    painter.drawText(65, 550, '项目回顾  ·  示例演示文稿')
    painter.end()

    # Prevent desktop capture: the image is deliberately supplied sample content.
    panel = RecordPanel('~/Videos/Shiguang')
    panel.live_preview.start = lambda *args: None
    panel.resize(1080, 650)
    panel.screen.setItemText(0, '屏幕 1 · 1920 × 1080')
    panel.folder.setText('~/Videos/Shiguang')
    panel.show()
    app.processEvents()
    panel._preview_frame(source, (960, 600))
    panel.grab().save(str(out / 'recording.png'))
    panel.bar.set_state('recording')
    panel.bar.set_expanded(True)
    panel.bar.show()
    app.processEvents()
    panel.bar.grab().save(str(out / 'orb.png'))
    panel.bar.hide()
    panel.hide()
    panel.timer.stop()
    panel.close()

    sample = QImage(820, 560, QImage.Format.Format_RGB888)
    sample.fill(QColor('#FFFFFF'))
    painter = QPainter(sample)
    painter.fillRect(0, 0, 820, 10, QColor('#246DEB'))
    painter.setPen(QColor('#122943'))
    painter.setFont(QFont('DejaVu Sans', 26, QFont.Weight.Bold))
    painter.drawText(45, 95, 'A small idea, worth keeping.')
    painter.setFont(QFont('DejaVu Sans', 18))
    lines = ['Capture the details.', 'Keep your notes close.', 'Make room for the next idea.']
    for i, line in enumerate(lines):
        painter.drawText(45, 200+i*65, line)
    painter.setPen(QColor('#586C86'))
    painter.setFont(QFont('DejaVu Sans', 13))
    painter.drawText(45, 495, 'STUDIO NOTES / SAMPLE CONTENT')
    painter.end()
    text = 'A small idea, worth keeping.\n\n' + '\n'.join(lines)
    result = OCRResult(text, None, engine='sample')
    workbench = ResultPanel()
    workbench.set_image(sample)
    workbench.show_result('ocr', result)
    workbench.show_translation(result, TranslationResult(text, '一个小想法，值得留下。\n\n捕捉细节。\n把笔记留在身边。\n为下一个想法留出空间。', 'en', 'zh', 'sample'))
    workbench.show()
    app.processEvents()
    workbench.grab().save(str(out / 'recognition.png'))
    workbench.close()


if __name__ == '__main__':
    main()
