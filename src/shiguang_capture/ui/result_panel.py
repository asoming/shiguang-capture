"""Local image workbench: source, flattened annotations, and editable text."""
from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import Qt, Signal, QSaveFile, QIODevice, QMimeData
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout, QWidget, QTableWidget, QTableWidgetItem, QHeaderView,
)
from .canvas import ImageCanvas
from .theme import STYLE
from ..structured import table_clipboard, markdown_table, xlsx_bytes, code_block, bounds


class ResultPanel(QWidget):
    closed = Signal()
    open_requested = Signal()
    capture_requested = Signal()
    paste_requested = Signal()
    file_dropped = Signal(str)
    image_edited = Signal()
    cancel_requested = Signal()
    save_image_requested = Signal(object)
    pin_requested = Signal(object)

    def __init__(self, delegate=None, parent=None):
        super().__init__(parent)
        self._delegate = delegate
        self._image = None
        self._result = self._translation = None
        self._kind = self._mode = 'ocr'
        self.setObjectName('workspace')
        self.setStyleSheet(STYLE)
        self.setWindowTitle('拾光 Capture · 图片工作台')
        self.resize(1160, 780)
        self.setMinimumSize(900, 650)
        self.setAcceptDrops(True)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 20)
        root.setSpacing(18)
        brand_row = QHBoxLayout()
        brand_row.addWidget(QLabel('拾光  /  CAPTURE', objectName='brand'))
        brand_row.addStretch()
        brand_row.addWidget(QLabel('本地处理 · 不自动保存', objectName='status'))
        root.addLayout(brand_row)
        heading = QHBoxLayout()
        title = QVBoxLayout()
        self.head = QLabel('把画面，留给下一步。', objectName='title')
        title.addWidget(self.head)
        self.meta = QLabel('打开图片或截取屏幕，标注、校对，然后带走。', objectName='muted')
        self.meta.setWordWrap(True)
        title.addWidget(self.meta)
        heading.addLayout(title)
        heading.addStretch()
        for label, signal in [('截图', self.capture_requested), ('粘贴图片', self.paste_requested), ('打开图片', self.open_requested)]:
            button = QPushButton(label)
            button.clicked.connect(signal.emit)
            heading.addWidget(button)
        root.addLayout(heading)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(18)
        source = QFrame(objectName='paper')
        source_layout = QVBoxLayout(source)
        source_layout.setContentsMargins(14, 14, 14, 14)
        source_header = QHBoxLayout()
        source_header.addWidget(QLabel('原图与标注', objectName='section'))
        source_header.addStretch()
        self.dimensions = QLabel('尚未载入图片', objectName='muted')
        source_header.addWidget(self.dimensions)
        source_layout.addLayout(source_header)
        tools = QHBoxLayout()
        tools.setSpacing(4)
        self.tool_group = QButtonGroup(self)
        for tool, label in [('view','查看'), ('arrow','箭头'), ('rect','矩形'), ('pen','画笔'), ('text','文字'), ('redact','遮盖')]:
            button = QPushButton(label)
            button.setCheckable(True)
            button.setChecked(tool == 'view')
            button.setStyleSheet('padding:6px 8px;')
            button.clicked.connect(lambda checked=False, value=tool: self._select_tool(value))
            self.tool_group.addButton(button)
            tools.addWidget(button)
        source_layout.addLayout(tools)
        self.canvas = ImageCanvas()
        self.canvas.changed.connect(self._invalidate)
        source_layout.addWidget(self.canvas, 1)
        edit_bar = QHBoxLayout()
        for label, callback in [('撤销', self.canvas.undo), ('重做', self.canvas.redo)]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            edit_bar.addWidget(button)
        edit_bar.addStretch()
        edit_bar.addWidget(QLabel('遮盖区域不会进入新识别结果', objectName='muted'))
        source_layout.addLayout(edit_bar)
        navigation = QHBoxLayout()
        self.block_combo = QComboBox()
        self.block_combo.setMinimumWidth(160)
        self.block_combo.addItem('文字块定位 · 识别后可用')
        self.block_combo.currentIndexChanged.connect(self._locate_block)
        navigation.addWidget(self.block_combo, 1)
        for label, callback in [('适应', lambda: self.canvas.set_zoom(1)), ('100%', lambda: self.canvas.actual_size())]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            navigation.addWidget(button)
        source_layout.addLayout(navigation)
        self.splitter.addWidget(source)

        text_card = QFrame(objectName='paper')
        text_layout = QVBoxLayout(text_card)
        text_layout.setContentsMargins(14, 14, 14, 14)
        text_header = QHBoxLayout()
        text_header.addWidget(QLabel('识别与校对', objectName='section'))
        text_header.addStretch()
        self.mode_combo = QComboBox()
        self.mode_combo.addItem('提取文字', 'ocr')
        self.mode_combo.addItem('代码 / 日志', 'code')
        self.mode_combo.addItem('简单表格', 'table')
        self.mode_combo.addItem('离线翻译 · 实验', 'translate')
        text_header.addWidget(self.mode_combo)
        self.retry_btn = QPushButton('开始识别', objectName='primary')
        self.retry_btn.clicked.connect(self._retry)
        text_header.addWidget(self.retry_btn)
        text_layout.addLayout(text_header)
        self.source_edit = QPlainTextEdit()
        self.source_edit.setPlaceholderText('识别结果会出现在这里。\n请对照左侧原图校对，再点击复制。')
        text_layout.addWidget(self.source_edit, 1)
        self.table_grid = QTableWidget()
        self.table_grid.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_grid.horizontalHeader().setDefaultSectionSize(120)
        self.table_grid.setAlternatingRowColors(True)
        self.table_grid.setStyleSheet("QTableWidget {background:white; alternate-background-color:#F0F6F8; gridline-color:#D5E1E9;} QHeaderView::section {background:#E0F0EF; padding:7px; border:0;}")
        self.table_grid.currentCellChanged.connect(self._locate_cell)
        self.table_grid.itemChanged.connect(self._table_edited)
        text_layout.addWidget(self.table_grid, 1)
        self.table_grid.hide()
        self.right = QWidget()
        translation_layout = QVBoxLayout(self.right)
        translation_layout.setContentsMargins(0, 0, 0, 0)
        translation_layout.addWidget(QLabel('译文 · 请核对词典模式的完整性', objectName='muted'))
        self.target_edit = QPlainTextEdit()
        translation_layout.addWidget(self.target_edit)
        text_layout.addWidget(self.right, 1)
        format_row = QHBoxLayout()
        format_row.addWidget(QLabel('复制格式', objectName='muted'))
        self.output_format = QComboBox()
        self.output_format.addItem('纯文本', 'text')
        format_row.addWidget(self.output_format, 1)
        text_layout.addLayout(format_row)
        actions = QHBoxLayout()
        self.restore_btn = QPushButton('恢复原输出')
        self.restore_btn.clicked.connect(self._restore)
        self.copy_source = QPushButton('复制文字', objectName='primary')
        self.copy_source.clicked.connect(self._copy_source)
        self.copy_target = QPushButton('复制译文')
        self.copy_target.clicked.connect(self._copy_target)
        self.swap_btn = QPushButton('交换')
        self.swap_btn.clicked.connect(self._swap)
        self.save_text_btn = QPushButton('导出文本')
        self.save_text_btn.clicked.connect(self._save_text)
        for button in (self.restore_btn, self.save_text_btn, self.copy_source, self.copy_target, self.swap_btn):
            actions.addWidget(button)
        text_layout.addLayout(actions)
        self.splitter.addWidget(text_card)
        self.splitter.setSizes([540, 520])
        root.addWidget(self.splitter, 1)

        footer = QHBoxLayout()
        self.gloss = QLabel('内容仅保留在本次会话中。', objectName='muted')
        self.gloss.setWordWrap(True)
        footer.addWidget(self.gloss, 1)
        self.cancel_btn = QPushButton('取消识别')
        self.cancel_btn.clicked.connect(self.cancel_requested.emit)
        self.cancel_btn.hide()
        footer.addWidget(self.cancel_btn)
        self.copy_image_btn = QPushButton('复制图片')
        self.copy_image_btn.clicked.connect(self._copy_image)
        self.pin_btn = QPushButton('贴到桌面')
        self.pin_btn.clicked.connect(lambda: self.pin_requested.emit(self.canvas.rendered_image()))
        self.save_image_btn = QPushButton('保存图片')
        self.save_image_btn.clicked.connect(lambda: self.save_image_requested.emit(self.canvas.rendered_image()))
        self.close_btn = QPushButton('清空会话')
        self.close_btn.clicked.connect(self.clear_session)
        for button in (self.copy_image_btn, self.pin_btn, self.save_image_btn, self.close_btn):
            footer.addWidget(button)
        root.addLayout(footer)
        self.source_edit.textChanged.connect(self._update_actions)
        self.target_edit.textChanged.connect(self._update_actions)
        for key, callback in [('Ctrl+Z', self.canvas.undo), ('Ctrl+Shift+Z', self.canvas.redo)]:
            shortcut = QShortcut(QKeySequence(key), self.canvas)
            shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
            shortcut.activated.connect(callback)
        self.canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._apply_mode('ocr')
        self._update_actions()

    def _select_tool(self, tool):
        self.canvas.tool = tool
        self.canvas.setCursor(Qt.CursorShape.ArrowCursor if tool == 'view' else Qt.CursorShape.CrossCursor)

    def _update_actions(self):
        has_image = not self.canvas.image.isNull()
        for button in (self.retry_btn, self.copy_image_btn, self.pin_btn, self.save_image_btn):
            button.setEnabled(has_image)
        has_text = bool(self.source_edit.toPlainText()) or bool(self._result and self._result.table)
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
        self.meta.setText('图像已修改 · 请重新识别当前可见内容')
        self.gloss.setText('已清除旧识别结果。复制、保存和识别均使用当前标注图。')
        self._update_actions()

    def set_image(self, image):
        self._image = image
        self.canvas.set_image(image)
        self._invalidate()
        self.head.setText('看清原图，再带走内容。')
        self.dimensions.setText(f'{image.width():,} × {image.height():,} px')
        self.meta.setText('图片已就绪 · 可以标注，也可以提取文字')

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
        self.gloss.setText(f'有 {low} 个低置信文字块，请仔细校对。' if low else '识别完成。校对后点击复制，剪贴板不会自动改变。')
        if kind == 'code':
            self.gloss.setText('按可见位置恢复缩进，不补写代码。请核对标点和缩进后使用。')
        elif kind == 'table':
            self.gloss.setText('点击单元格可定位原图。XLSX 按文本保存编号、日期和公式样式内容。')
        self.retry_btn.setText('重新识别')
        self._update_actions()

    def show_translation(self, result, translation):
        self.show_result('translate', result)
        self._translation = translation
        self.target_edit.setPlainText(translation.target_text)
        self._apply_mode('translate')
        self.gloss.setText('词典替换模式：仅替换已知术语，不是完整译文。' if translation.degraded
                           else '本地翻译完成，请校对后复制。')
        self._update_actions()

    def _apply_mode(self, mode):
        self._mode = mode
        self.mode_combo.setCurrentIndex(max(0, self.mode_combo.findData(mode)))
        self.output_format.clear()
        self.output_format.addItem('纯文本', 'text')
        if mode == 'code':
            self.output_format.addItem('Markdown 代码块', 'code')
        elif mode == 'table':
            self.output_format.addItem('Markdown 表格', 'markdown')
            self.output_format.addItem('表格粘贴 (HTML / TSV)', 'table')
        self.save_text_btn.setText('导出 XLSX' if mode == 'table' else '导出文本')
        for widget in (self.right, self.copy_target, self.swap_btn):
            widget.setVisible(mode == 'translate')

    def set_busy(self, busy):
        self.cancel_btn.setVisible(busy)
        self.retry_btn.setText('重新开始' if busy else ('重新识别' if self._result else '开始识别'))
        if busy:
            self.gloss.setText('正在本地处理… 可以取消；图像不会上传。')

    def _copy_source(self):
        output = self.output_format.currentData()
        text = self.source_edit.toPlainText()
        if self._kind == 'table' and self._result and self._result.table:
            cells = self._table_cells()
            if output == 'table':
                try:
                    plain, rich = table_clipboard(cells)
                except ValueError as exc:
                    self.gloss.setText(str(exc))
                    return
                mime = QMimeData()
                mime.setText(plain)
                mime.setHtml(rich)
                QGuiApplication.clipboard().setMimeData(mime)
                self.gloss.setText('表格已复制。编号和日期需完全保真时，请优先导出 XLSX。')
                return
            text = markdown_table(cells) if output == 'markdown' else '\n'.join(' | '.join(row) for row in cells)
        elif output == 'code':
            text = code_block(text)
        QGuiApplication.clipboard().setText(text)
        self.gloss.setText('文字已复制。')

    def _copy_target(self):
        QGuiApplication.clipboard().setText(self.target_edit.toPlainText())
        self.gloss.setText('译文已复制。')

    def _copy_image(self):
        QGuiApplication.clipboard().setImage(self.canvas.rendered_image())
        self.gloss.setText('图片已复制，标注已合并。')

    def _restore(self):
        if self._result:
            self.source_edit.setPlainText(self._result.text)
            self._populate_table()
            if self._translation:
                self.target_edit.setPlainText(self._translation.target_text)

    def _swap(self):
        source, target = self.source_edit.toPlainText(), self.target_edit.toPlainText()
        self.source_edit.setPlainText(target)
        self.target_edit.setPlainText(source)

    def _retry(self):
        if self._delegate and not self.canvas.image.isNull():
            self._delegate(self.canvas.rendered_image(), self.mode_combo.currentData())

    def _save_text(self):
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
        self.head.setText('把画面，留给下一步。')
        self.dimensions.setText('尚未载入图片')
        self.meta.setText('会话已清空 · 已保存的文件和系统剪贴板不受影响')
        self.gloss.setText('打开图片或截取屏幕开始。')

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
