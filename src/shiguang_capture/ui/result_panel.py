"""Local image workbench: source, flattened annotations, and editable text."""
from __future__ import annotations
from pathlib import Path
import json
from PySide6.QtCore import Qt, Signal, QSaveFile, QIODevice, QMimeData
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut, QAction
from PySide6.QtWidgets import (
    QMenu, QButtonGroup, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout, QWidget, QTableWidget, QTableWidgetItem, QHeaderView,
)
from .canvas import ImageCanvas
from .theme import STYLE
from ..structured import table_clipboard, markdown_table, xlsx_bytes, code_block, bounds
from ..clipboard import write_text, write_image


class ResultPanel(QWidget):
    translate_requested = Signal(str)
    record_requested = Signal()
    format_changed = Signal(str, str)
    closed = Signal()
    open_requested = Signal()
    capture_requested = Signal()
    paste_requested = Signal()
    file_dropped = Signal(str)
    image_edited = Signal()
    cancel_requested = Signal()
    save_image_requested = Signal(object)
    pin_requested = Signal(object)

    def __init__(self, delegate=None, parent=None, formats=None):
        super().__init__(parent)
        self._delegate = delegate
        self._formats = dict(formats or {})
        self._image = None
        self._result = self._translation = None
        self._kind = self._mode = 'ocr'
        self.setObjectName('workspace')
        self.setStyleSheet(STYLE)
        self.setWindowTitle('拾光 · 识别')
        self.resize(1080, 700)
        self.setMinimumSize(680, 400)
        self.setAcceptDrops(True)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(8)
        self.canvas = ImageCanvas()
        self.canvas.changed.connect(self._invalidate)
        self.canvas.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(self._image_menu)
        self.splitter.addWidget(self.canvas)
        result_side = QWidget()
        text_layout = QVBoxLayout(result_side)
        text_layout.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        header.addStretch()
        self.translate_button = QPushButton('翻译')
        self.translate_button.clicked.connect(self._translate)
        header.addWidget(self.translate_button)
        text_layout.addLayout(header)
        self.comparison = QSplitter(Qt.Orientation.Vertical)
        self.comparison.setHandleWidth(8)
        original = QWidget()
        original_layout = QVBoxLayout(original)
        original_layout.setContentsMargins(0, 0, 0, 0)
        self.source_edit = QPlainTextEdit()
        self.source_edit.setPlaceholderText('正在识别…')
        self.source_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.source_edit.customContextMenuRequested.connect(self._text_menu)
        original_layout.addWidget(self.source_edit)
        self.table_grid = QTableWidget()
        self.table_grid.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_grid.horizontalHeader().setDefaultSectionSize(120)
        self.table_grid.setAlternatingRowColors(True)
        self.table_grid.currentCellChanged.connect(self._locate_cell)
        self.table_grid.itemChanged.connect(self._table_edited)
        self.table_grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_grid.customContextMenuRequested.connect(lambda pos: self._text_menu(pos, self.table_grid))
        original_layout.addWidget(self.table_grid)
        self.table_grid.hide()
        self.comparison.addWidget(original)
        self.right = QWidget()
        translated = QVBoxLayout(self.right)
        translated.setContentsMargins(0, 0, 0, 0)
        self.target_edit = QPlainTextEdit()
        self.target_edit.setPlaceholderText('译文')
        translated.addWidget(self.target_edit)
        self.comparison.addWidget(self.right)
        text_layout.addWidget(self.comparison, 1)
        self.splitter.addWidget(result_side)
        self.splitter.setSizes([540, 520])
        root.addWidget(self.splitter, 1)
        # Format and block state live in context menus, leaving only the two panes.
        self.mode_combo, self.output_format, self.block_combo = (QComboBox(self) for _ in range(3))
        for title, value in [('文字', 'ocr'), ('代码', 'code'), ('表格', 'table')]:
            self.mode_combo.addItem(title, value)
        for combo in (self.mode_combo, self.output_format, self.block_combo):
            combo.hide()
        self.output_format.currentIndexChanged.connect(self._format_changed)
        self.block_combo.currentIndexChanged.connect(self._locate_block)
        self.head, self.dimensions, self.meta, self.gloss = (QLabel(self) for _ in range(4))
        for label in (self.head, self.dimensions, self.meta, self.gloss):
            label.hide()
        self.feedback = QLabel()
        self.feedback.setWordWrap(True)
        self.feedback.hide()
        root.addWidget(self.feedback)
        actions = [
            ('retry_btn', '重新识别', self._retry),
            ('restore_btn', '恢复原输出', self._restore),
            ('copy_source', '复制识别内容', self._copy_source),
            ('copy_target', '复制译文', self._copy_target),
            ('swap_btn', '交换原文和译文', self._swap),
            ('save_text_btn', '导出文本', self._save_text),
            ('cancel_btn', '取消识别', self.cancel_requested.emit),
            ('copy_image_btn', '复制图片', self._copy_image),
            ('pin_btn', '贴到桌面', lambda: self.pin_requested.emit(self.canvas.image)),
            ('save_image_btn', '保存图片', lambda: self.save_image_requested.emit(self.canvas.image)),
            ('close_btn', '清空会话', self.clear_session),
        ]
        for name, title, callback in actions:
            action = QAction(title, self)
            action.triggered.connect(callback)
            setattr(self, name, action)
        self.source_edit.textChanged.connect(self._source_changed)
        self.target_edit.textChanged.connect(self._update_actions)
        QShortcut(QKeySequence('Ctrl+S'), self, activated=self._save_text)
        QShortcut(QKeySequence('Escape'), self, activated=self.cancel_requested.emit)
        self._busy = False
        self._apply_mode('ocr')
        self._update_actions()

    def _source_changed(self):
        if self._translation and self.source_edit.toPlainText() != self._translation.source_text:
            self._translation = None
            self.target_edit.clear()
            self.target_edit.setPlaceholderText('原文已修改，点击翻译更新')
        self._update_actions()

    def show_error(self, message):
        self.gloss.setText(message)
        self.feedback.setText(message)
        self.feedback.show()

    def _translate(self):
        text = self.source_edit.toPlainText()
        if text.strip() and not self._busy:
            self.right.show()
            self.target_edit.clear()
            self.target_edit.setPlaceholderText('正在翻译…')
            self.comparison.setSizes([300, 300])
            self.translate_requested.emit(text)

    def _image_menu(self, position):
        menu = QMenu(self)
        for action in (self.copy_image_btn, self.save_image_btn, self.pin_btn):
            menu.addAction(action)
        menu.addSeparator()
        menu.addAction('适应窗口', lambda: self.canvas.set_zoom(1))
        menu.addAction('原始大小', self.canvas.actual_size)
        blocks = menu.addMenu('定位文字块')
        for index in range(1, self.block_combo.count()):
            blocks.addAction(self.block_combo.itemText(index), lambda i=index: self._locate_block(i))
        menu.exec(self.canvas.mapToGlobal(position))

    def _select_tool(self, tool):
        self.canvas.tool = tool
        self.canvas.setCursor(Qt.CursorShape.ArrowCursor if tool == 'view' else Qt.CursorShape.CrossCursor)

    def _update_actions(self):
        has_image = not self.canvas.image.isNull()
        for button in (self.retry_btn, self.copy_image_btn, self.pin_btn, self.save_image_btn):
            button.setEnabled(has_image)
        has_text = bool(self.source_edit.toPlainText()) or bool(self._result and self._result.table)
        self.translate_button.setEnabled(has_text and not getattr(self, "_busy", False))
        self.copy_source.setEnabled(has_text)
        self.save_text_btn.setEnabled(has_text)
        self.copy_target.setEnabled(bool(self.target_edit.toPlainText()))
        self.restore_btn.setEnabled(self._result is not None)

    def _invalidate(self):
        self.image_edited.emit()
        self._result = self._translation = None
        self.table_grid.setRowCount(0)
        self.table_grid.setColumnCount(0)
        self.table_grid.hide()
        self.source_edit.show()
        self.block_combo.clear()
        self.block_combo.addItem('文字块定位 · 识别后可用')
        self.canvas.highlight = None
        self.canvas.update()
        self.source_edit.clear()
        self.target_edit.clear()
        self.meta.setText('图像已修改，需重新识别')
        self.gloss.clear()
        self._update_actions()

    def set_image(self, image):
        self.feedback.hide()
        self.right.hide()
        self._image = image
        self.canvas.set_image(image)
        self._invalidate()

        self.dimensions.setText(f'{image.width():,} × {image.height():,} px')
        self.meta.clear()
        self.gloss.clear()

    def show_result(self, kind, result):
        self._kind = kind
        self._result = result
        self._translation = None
        self.source_edit.setPlainText(result.text)
        self.target_edit.clear()
        self._apply_mode(kind)
        self._populate_table()
        self._populate_blocks()
        confidence = getattr(result, 'confidence', None)
        conf = '未提供置信信息' if confidence is None else f'行级平均置信度 {confidence:.0%}'
        self.meta.setText(f'本地识别 · {result.elapsed_ms:,} ms · {len(result.text)} 字 · {conf}')
        low = sum(1 for block in result.blocks if block.get('confidence') is not None and block['confidence'] < .8)
        self.gloss.setText(f'有 {low} 个低置信文字块，请仔细校对。' if low else '识别完成')
        if kind == 'code':
            self.gloss.setText('请核对符号与缩进')
        elif kind == 'table':
            self.gloss.setText('点击单元格定位原图')
        self.retry_btn.setText('重新识别')
        self._update_actions()

    def show_translation(self, result, translation):
        if self._result is None or self.source_edit.toPlainText() != result.text:
            self.show_result(result.mode if result.mode in ('ocr', 'code', 'table') else 'ocr', result)
        self.feedback.hide()
        self._translation = translation
        self.target_edit.setPlainText(translation.target_text)
        self.right.show()
        self.target_edit.setPlaceholderText('译文')
        self.comparison.setSizes([300, 300])
        self.gloss.setText('词典替换模式：仅替换已知术语，不是完整译文。' if translation.degraded
                           else '本地翻译完成，请校对后复制。')
        if translation.degraded:
            self.show_error('尚未安装离线翻译模型；下面仅为词典替换，不是完整译文。')
        self._update_actions()

    def _apply_mode(self, mode):
        self._mode = mode
        self.source_edit.setStyleSheet("QPlainTextEdit { font-family: 'DejaVu Sans Mono', 'Consolas', monospace; }" if mode == 'code' else '')
        self.mode_combo.setCurrentIndex(max(0, self.mode_combo.findData(mode)))
        self.output_format.blockSignals(True)
        self.output_format.clear()
        self.output_format.addItem('纯文本', 'text')
        if mode == 'code':
            self.output_format.addItem('Markdown 代码块', 'code')
        elif mode == 'table':
            self.output_format.addItem('Markdown 表格', 'markdown')
            self.output_format.addItem('表格粘贴 (HTML / TSV)', 'table')
        self.output_format.addItem('JSON', 'json')
        self.output_format.setCurrentIndex(max(0, self.output_format.findData(self._formats.get(mode, 'text'))))
        self.output_format.blockSignals(False)
        self.save_text_btn.setText('导出 XLSX' if mode == 'table' else '导出文本')
        for widget in (self.right, self.copy_target, self.swap_btn):
            widget.setVisible(mode == 'translate')

    def _format_changed(self, *_):
        value = self.output_format.currentData()
        if value is not None:
            self._formats[self._mode] = value
            self.format_changed.emit(self._mode, value)

    def _json_output(self):
        document = {'schema_version': 1, 'mode': self._kind, 'text': self.source_edit.toPlainText()}
        if self._kind == 'table' and self._result and self._result.table:
            document['cells'] = self._table_cells()
            document['rows'] = self.table_grid.rowCount()
            document['columns'] = self.table_grid.columnCount()
        return json.dumps(document, ensure_ascii=False, indent=2)

    def set_busy(self, busy):
        self._busy = busy
        self.translate_button.setText('处理中…' if busy else '翻译')
        self._update_actions()
        self.cancel_btn.setVisible(busy)
        self.retry_btn.setText('重新开始' if busy else ('重新识别' if self._result else '开始识别'))
        if busy:
            self.gloss.setText('正在本地处理… 可以取消；图像不会上传。')

    def _copy_source(self):
        try:
            self._copy_source_checked()
        except RuntimeError as exc:
            self.gloss.setText(str(exc))

    def _copy_source_checked(self):
        output = self.output_format.currentData()
        text = self.source_edit.toPlainText()
        if output == 'json':
            write_text(self._json_output())
            self.gloss.setText('已复制 JSON')
            return
        if self._kind == 'table' and self._result and self._result.table:
            cells = self._table_cells()
            if output == 'table':
                try:
                    plain, rich = table_clipboard(cells)
                except ValueError as exc:
                    self.gloss.setText(str(exc))
                    return
                write_text(plain, rich)
                self.gloss.setText('表格已复制。编号和日期需完全保真时，请优先导出 XLSX。')
                return
            text = markdown_table(cells) if output == 'markdown' else '\n'.join(' | '.join(row) for row in cells)
        elif output == 'code':
            text = code_block(text)
        write_text(text)
        self.gloss.setText('文字已复制。')

    def _copy_target(self):
        try:
            write_text(self.target_edit.toPlainText())
            self.gloss.setText('译文已复制。')
        except RuntimeError as exc:
            self.gloss.setText(str(exc))

    def _copy_image(self):
        try:
            write_image(self.canvas.rendered_image())
            self.gloss.setText('图片已复制')
        except (RuntimeError, ValueError) as exc:
            self.gloss.setText(str(exc))

    def _restore(self):
        if self._result:
            self.source_edit.setPlainText(self._result.text)
            self._populate_table()
            if self._translation:
                self.target_edit.setPlainText(self._translation.target_text)

    def _text_menu(self, position, widget=None):
        widget = widget or self.source_edit
        menu = self.source_edit.createStandardContextMenu() if widget is self.source_edit else QMenu(self)
        menu.addSeparator()
        for action in (self.copy_source, self.save_text_btn, self.restore_btn):
            menu.addAction(action)
        formats = menu.addMenu('复制格式')
        for index in range(self.output_format.count()):
            action = formats.addAction(self.output_format.itemText(index))
            action.setCheckable(True)
            action.setChecked(index == self.output_format.currentIndex())
            action.triggered.connect(lambda checked=False, i=index: self.output_format.setCurrentIndex(i))
        menu.addSeparator()
        clean = menu.addAction('清理选中文字…')
        clean.setEnabled(self.source_edit.textCursor().hasSelection())
        clean.triggered.connect(self._clean_selected_text)
        menu.addAction(self.retry_btn)
        if self._busy:
            menu.addAction(self.cancel_btn)
        if self.right.isVisible():
            menu.addAction('切换左右 / 上下对照', lambda: self.comparison.setOrientation(
                Qt.Orientation.Horizontal if self.comparison.orientation() == Qt.Orientation.Vertical else Qt.Orientation.Vertical))
        menu.exec(widget.mapToGlobal(position))

    def _clean_selected_text(self):
        from .text_cleanup import CleanupDialog
        cursor = self.source_edit.textCursor()
        if not cursor.hasSelection():
            return
        revision = self.source_edit.document().revision()
        dialog = CleanupDialog(cursor.selectedText().replace('\u2029', '\n'), self)
        if dialog.exec() == dialog.DialogCode.Accepted and revision == self.source_edit.document().revision():
            cursor.beginEditBlock()
            cursor.insertText(dialog.result)
            cursor.endEditBlock()

    def _swap(self):
        source, target = self.source_edit.toPlainText(), self.target_edit.toPlainText()
        self.source_edit.setPlainText(target)
        self.target_edit.setPlainText(source)

    def _retry(self):
        if self._delegate and not self.canvas.image.isNull():
            self._delegate(self.canvas.rendered_image(), self.mode_combo.currentData())

    def _save_text(self):
        if self.output_format.currentData() == 'json':
            path, _ = QFileDialog.getSaveFileName(self, '导出 JSON', '识别结果.json', 'JSON (*.json)')
            if path:
                self._write_output(path, self._json_output().encode('utf-8'))
            return
        if self._kind == 'table' and self._result and self._result.table:
            path, _ = QFileDialog.getSaveFileName(self, '导出文本型表格', '识别表格.xlsx', 'Excel 表格 (*.xlsx)')
            if path:
                try:
                    self._write_output(path, xlsx_bytes(self._table_cells()))
                except (OSError, ValueError) as exc:
                    self.gloss.setText('导出失败，请检查单元格内容或另选位置。')
            return
        path, _ = QFileDialog.getSaveFileName(self, '导出校对后的文本', '识别结果.txt', '文本 (*.txt);;Markdown (*.md)')
        if not path:
            return
        data = self.source_edit.toPlainText()
        if Path(path).suffix.lower() == '.md' and self._kind == 'code':
            data = code_block(data)
        self._write_output(path, data.encode('utf-8'))

    def _write_output(self, path, data):
        output = QSaveFile(path)
        if not output.open(QIODevice.OpenModeFlag.WriteOnly):
            self.gloss.setText('无法写入此位置，请重新选择。')
            return
        if output.write(data) != len(data):
            output.cancelWriting()
            self.gloss.setText('导出失败，请检查可用空间。')
            return
        self.gloss.setText('文件已导出。' if output.commit() else '导出失败，请另选位置。')

    def _populate_blocks(self):
        self.block_combo.blockSignals(True)
        self.block_combo.clear()
        self.block_combo.addItem('选择文字块定位原图', None)
        if self._result:
            for index, block in enumerate(self._result.blocks):
                confidence = block.get('confidence')
                score = '未提供' if confidence is None else f'{confidence:.0%}'
                warning = '低置信 · ' if confidence is not None and confidence < .8 else ''
                self.block_combo.addItem(f"{index+1}. {warning}{score} · {block.get('text','')[:22]}", index)
        self.block_combo.blockSignals(False)

    def _locate_block(self, index):
        block_index = self.block_combo.itemData(index)
        if self._result and block_index is not None:
            self.canvas.highlight = bounds(self._result.blocks[block_index])
            self.canvas.update()

    def _populate_table(self):
        table = self._result.table if self._result else None
        self.table_grid.setVisible(table is not None)
        self.source_edit.setVisible(table is None)
        if table is None:
            return
        self.table_grid.blockSignals(True)
        rows, columns = table.shape
        self.table_grid.setRowCount(rows)
        self.table_grid.setColumnCount(columns)
        for r, row in enumerate(table.cells):
            for c, value in enumerate(row):
                self.table_grid.setItem(r, c, QTableWidgetItem(value))
        self.table_grid.blockSignals(False)
        self._table_edited()

    def _table_cells(self):
        return [[self.table_grid.item(r,c).text() if self.table_grid.item(r,c) else ''
                 for c in range(self.table_grid.columnCount())] for r in range(self.table_grid.rowCount())]

    def _table_edited(self, *args):
        if self._result and self._result.table:
            self.source_edit.setPlainText('\n'.join('\t'.join(row) for row in self._table_cells()))

    def _locate_cell(self, row, column, *args):
        if row >= 0 and column >= 0 and self._result and self._result.table:
            self.canvas.highlight = self._result.table.boxes[row][column]
            self.canvas.update()

    def clear_session(self):
        from PySide6.QtGui import QImage
        self.canvas.set_image(QImage())
        self._image = None
        self._invalidate()

        self.dimensions.setText('尚未载入图片')
        self.meta.clear()
        self.gloss.clear()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and len(event.mimeData().urls()) == 1 and event.mimeData().urls()[0].isLocalFile():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile():
            self.file_dropped.emit(urls[0].toLocalFile())
            event.acceptProposedAction()

    def closeEvent(self, event):
        self.cancel_requested.emit()
        self.clear_session()
        self.closed.emit()
        super().closeEvent(event)
