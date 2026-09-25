"""Local image workbench: source, flattened annotations, and editable text."""
from __future__ import annotations
from pathlib import Path
import json
from PySide6.QtCore import Qt, Signal, QSaveFile, QIODevice, QTimer, QPoint
from PySide6.QtGui import QKeySequence, QShortcut, QAction
from PySide6.QtWidgets import (
    QMenu, QComboBox, QFileDialog, QHBoxLayout, QLabel, QToolButton,
    QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout, QWidget, QTableWidget,
    QTableWidgetItem, QHeaderView,
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
        self._result_kind = 'ocr'
        self._busy = False
        self._pending_translation = None
        self._accept_results = True
        self._active_menu = None
        self.setObjectName('workspace')
        self.setStyleSheet(STYLE)
        self.setWindowTitle('拾光 · 识别')
        self.resize(1080, 700)
        self.setMinimumSize(680, 400)
        self.setAcceptDrops(True)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)
        imports = QHBoxLayout()
        self.open_button = QToolButton()
        self.open_button.setText('打开图片')
        self.open_button.setToolTip('打开本地图片，也可直接拖入窗口 · Ctrl+O')
        self.open_button.clicked.connect(self.open_requested.emit)
        self.paste_button = QToolButton()
        self.paste_button.setText('粘贴图片')
        self.paste_button.setToolTip('读取剪贴板中的图片')
        self.paste_button.clicked.connect(self.paste_requested.emit)
        for button in (self.open_button, self.paste_button):
            button.setObjectName('quietTool')
            imports.addWidget(button)
        imports.addStretch()
        root.addLayout(imports)
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
        self.more_button = QToolButton()
        self.more_button.setText('⋯')
        self.more_button.setObjectName('moreTool')
        self.more_button.setAccessibleName('识别结果更多操作')
        self.more_button.setToolTip('识别模式、复制、导出与对照')
        self.more_button.setFixedSize(34, 34)
        self.more_button.clicked.connect(self._show_more_menu)
        header.addWidget(self.more_button)
        text_layout.addLayout(header)
        self.comparison = QSplitter(Qt.Orientation.Vertical)
        self.comparison.setHandleWidth(8)
        original = QWidget()
        original_layout = QVBoxLayout(original)
        original_layout.setContentsMargins(0, 0, 0, 0)
        self.source_edit = QPlainTextEdit()
        self.source_edit.setPlaceholderText('打开、粘贴或拖入图片后开始识别')
        self.source_edit.setAccessibleName('识别内容，可编辑')
        self.source_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.source_edit.customContextMenuRequested.connect(self._text_menu)
        original_layout.addWidget(self.source_edit)
        self.table_grid = QTableWidget()
        self.table_grid.setAccessibleName('识别表格，编辑单元格并定位原图')
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
        self.target_edit.setAccessibleName('译文，可编辑')
        self.target_edit.setPlaceholderText('译文')
        self.target_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.target_edit.customContextMenuRequested.connect(self._target_menu)
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
        self.feedback.setObjectName('muted')
        self.feedback.setAccessibleName('识别操作反馈')
        self.feedback.setWordWrap(True)
        self.feedback.hide()
        root.addWidget(self.feedback)
        self.feedback_timer = QTimer(self)
        self.feedback_timer.setSingleShot(True)
        self.feedback_timer.timeout.connect(self.feedback.hide)
        actions = [
            ('retry_btn', '重新识别', self._retry),
            ('restore_btn', '恢复原输出', self._restore),
            ('copy_source', '复制识别内容', self._copy_source),
            ('copy_target', '复制译文', self._copy_target),
            ('swap_btn', '交换原文和译文', self._swap),
            ('save_text_btn', '导出文本', self._save_text),
            ('cancel_btn', '取消识别', self._cancel),
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
        QShortcut(QKeySequence('Ctrl+O'), self, activated=self.open_requested.emit)
        QShortcut(QKeySequence('Escape'), self, activated=self._cancel)
        self._apply_mode('ocr')
        self._update_actions()

    def _source_changed(self):
        text = self.source_edit.toPlainText()
        if self._busy and self._pending_translation is None:
            # Editing while OCR is running is an explicit choice to keep the edit.
            self._accept_results = False
            self.cancel_requested.emit()
            self.set_busy(False)
            self._notify('内容已修改，已取消识别。')
        pending_changed = self._pending_translation is not None and text != self._pending_translation
        translated_changed = self._translation is not None and text != self._translation.source_text
        swapped_changed = (self._translation is None and not self.right.isHidden()
                           and bool(self.target_edit.toPlainText()))
        if pending_changed or translated_changed or swapped_changed:
            if pending_changed:
                self._pending_translation = None
                self.cancel_requested.emit()
                self.set_busy(False)
            self._translation = None
            self.target_edit.clear()
            self.target_edit.setPlaceholderText('原文已修改，点击翻译更新')
            self._notify('原文已修改，请重新翻译。')
        self._update_actions()

    def _notify(self, message, timeout=3500):
        """Keep feedback visible long enough to read without adding a permanent bar."""
        self.gloss.setText(message)
        self.feedback_timer.stop()
        self.feedback.setText(message)
        self.feedback.show()
        if timeout:
            self.feedback_timer.start(timeout)

    def show_error(self, message):
        self._notify(message, timeout=0)

    def _dismiss_menus(self):
        if self._active_menu is not None:
            self._active_menu.close()

    def _exec_menu(self, menu, position):
        self._active_menu = menu
        try:
            menu.exec(position)
        finally:
            self._active_menu = None
            menu.deleteLater()

    def _cancel(self):
        if not self._busy and self._pending_translation is None:
            return
        self._pending_translation = None
        self.cancel_requested.emit()
        self.set_busy(False)
        self._notify('已取消，原有内容已保留。')

    def _translate(self):
        text = self.source_edit.toPlainText()
        if text.strip() and not self._busy:
            self._pending_translation = text
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
        self._exec_menu(menu, self.canvas.mapToGlobal(position))

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
        self.swap_btn.setEnabled(bool(self.target_edit.toPlainText()) and not self._busy)
        self.restore_btn.setEnabled(self._result is not None)
        self.close_btn.setEnabled(has_image or has_text or self._busy)
        self.cancel_btn.setEnabled(self._busy)

    def _has_table(self):
        return bool(self._result and self._result.table and not self.table_grid.isHidden())

    def _invalidate(self):
        self._pending_translation = None
        if self._busy:
            self.cancel_requested.emit()
            self.set_busy(False)
        self.image_edited.emit()
        self._result = self._translation = None
        self.right.hide()
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
        self.feedback_timer.stop()
        self.feedback.hide()
        self._update_actions()

    def set_image(self, image):
        self._accept_results = True
        self.feedback.hide()
        self.right.hide()
        self._image = image
        self.canvas.set_image(image)
        self._invalidate()

        self.dimensions.setText(f'{image.width():,} × {image.height():,} px')
        self.meta.clear()
        self.gloss.clear()

    def show_result(self, kind, result):
        if not self._accept_results:
            return
        self.set_busy(False)
        self._dismiss_menus()
        self._pending_translation = None
        kind = kind if kind in ('ocr', 'code', 'table') else 'ocr'
        self._kind = kind
        self._result_kind = kind
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
        if low:
            self._notify(f'{low} 处文字建议校对，可右键原图定位。', timeout=7000)
        elif kind == 'code':
            self._notify('请对照原图核对符号与缩进。', timeout=5000)
        elif kind == 'table':
            self._notify('点击单元格可定位原图，直接修改内容。', timeout=5000)
        else:
            self._notify('识别完成')
        self.retry_btn.setText('重新识别')
        self._update_actions()

    def show_translation(self, result, translation):
        if not self._accept_results:
            return
        self.set_busy(False)
        self._dismiss_menus()
        if self._result is not None and self.source_edit.toPlainText() != result.text:
            self._pending_translation = None
            self._notify('原文已修改，请再次点击翻译。')
            return
        if self._result is None:
            self.show_result(result.mode if result.mode in ('ocr', 'code', 'table') else 'ocr', result)
        self._pending_translation = None
        self._translation = translation
        self.target_edit.setPlainText(translation.target_text)
        self.right.show()
        self.target_edit.setPlaceholderText('译文')
        self.comparison.setSizes([300, 300])
        if translation.degraded:
            self.show_error('当前仅替换已知术语，不是完整译文。')
        else:
            self._notify('翻译完成，可右键切换对照方向。')
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
        self.right.hide()

    def _format_changed(self, *_):
        value = self.output_format.currentData()
        if value is not None:
            self._formats[self._mode] = value
            self.format_changed.emit(self._mode, value)

    def _json_output(self):
        document = {'schema_version': 1, 'mode': self._kind, 'text': self.source_edit.toPlainText()}
        if self._has_table():
            document['cells'] = self._table_cells()
            document['rows'] = self.table_grid.rowCount()
            document['columns'] = self.table_grid.columnCount()
        return json.dumps(document, ensure_ascii=False, indent=2)

    def set_busy(self, busy):
        self._dismiss_menus()
        self._busy = busy
        if busy and not self.canvas.image.isNull():
            self._accept_results = True
        self.translate_button.setText('处理中…' if busy else '翻译')
        self._update_actions()
        self.cancel_btn.setVisible(busy)
        self.retry_btn.setText('重新开始' if busy else ('重新识别' if self._result else '开始识别'))
        if busy:
            self._notify('正在本地处理… Esc 取消', timeout=0)
        elif self.feedback.text() == '正在本地处理… Esc 取消':
            self.feedback.hide()

    def _copy_source(self):
        try:
            self._copy_source_checked()
        except RuntimeError as exc:
            self.show_error(str(exc))

    def _copy_source_checked(self):
        output = self.output_format.currentData()
        text = self.source_edit.toPlainText()
        if output == 'json':
            write_text(self._json_output())
            self._notify('已复制 JSON')
            return
        if self._has_table():
            cells = self._table_cells()
            if output == 'table':
                try:
                    plain, rich = table_clipboard(cells)
                except ValueError as exc:
                    self.show_error(str(exc))
                    return
                write_text(plain, rich)
                self._notify('已复制表格；保留编号与日期请导出 XLSX。', timeout=5000)
                return
            text = markdown_table(cells) if output == 'markdown' else '\n'.join(' | '.join(row) for row in cells)
        elif output == 'code':
            text = code_block(text)
        write_text(text)
        self._notify('已复制识别内容')

    def _copy_target(self):
        try:
            write_text(self.target_edit.toPlainText())
            self._notify('已复制译文')
        except RuntimeError as exc:
            self.show_error(str(exc))

    def _copy_image(self):
        try:
            write_image(self.canvas.rendered_image())
            self._notify('已复制图片')
        except (RuntimeError, ValueError) as exc:
            self.show_error(str(exc))

    def _restore(self):
        if self._result:
            self._cancel()
            self._translation = None
            self._kind = self._result_kind
            self._apply_mode(self._kind)
            self.source_edit.setPlainText(self._result.text)
            self._populate_table()
            self.target_edit.clear()
            self._notify('已恢复原输出')
            self._update_actions()

    def _choose_mode(self, mode):
        self._mode = mode
        self.mode_combo.setCurrentIndex(self.mode_combo.findData(mode))
        self._retry()

    def _switch_comparison(self):
        direction = (Qt.Orientation.Horizontal if self.comparison.orientation() == Qt.Orientation.Vertical
                     else Qt.Orientation.Vertical)
        self.comparison.setOrientation(direction)
        self.comparison.setSizes([300, 300])

    def _hide_translation(self):
        self._cancel()
        self._translation = None
        self.target_edit.clear()
        self.right.hide()
        self._update_actions()

    def _add_comparison_actions(self, menu):
        if self.right.isHidden():
            return
        menu.addSeparator()
        label = ('左右对照' if self.comparison.orientation() == Qt.Orientation.Vertical else '上下对照')
        menu.addAction(label, self._switch_comparison)
        menu.addAction(self.swap_btn)
        menu.addAction(self.copy_target)
        menu.addAction('收起译文', self._hide_translation)

    def _populate_result_menu(self, menu):
        modes = menu.addMenu('识别模式')
        for label, mode in (('文字', 'ocr'), ('代码', 'code'), ('表格', 'table')):
            action = modes.addAction(label)
            action.setCheckable(True)
            action.setChecked(self._mode == mode)
            action.setEnabled(not self.canvas.image.isNull() and self._delegate is not None)
            action.triggered.connect(lambda checked=False, selected=mode: self._choose_mode(selected))
        menu.addSeparator()
        menu.addAction(self.copy_source)
        formats = menu.addMenu('复制格式')
        for index in range(self.output_format.count()):
            action = formats.addAction(self.output_format.itemText(index))
            action.setCheckable(True)
            action.setChecked(index == self.output_format.currentIndex())
            action.triggered.connect(lambda checked=False, i=index: self.output_format.setCurrentIndex(i))
        exports = menu.addMenu('导出')
        options = [('纯文本 · TXT', 'txt'), ('Markdown · MD', 'md'), ('JSON', 'json')]
        if self._has_table():
            options.append(('Excel 表格 · XLSX', 'xlsx'))
        for label, extension in options:
            action = exports.addAction(label)
            action.setEnabled(self.save_text_btn.isEnabled())
            action.triggered.connect(lambda checked=False, ext=extension: self._export_output(ext))
        menu.addAction(self.restore_btn)
        clean = menu.addAction('清理选中文字…')
        clean.setEnabled(not self.source_edit.isHidden() and self.source_edit.textCursor().hasSelection())
        clean.triggered.connect(self._clean_selected_text)
        menu.addSeparator()
        menu.addAction(self.retry_btn)
        if self._busy:
            menu.addAction(self.cancel_btn)
        self._add_comparison_actions(menu)
        menu.addSeparator()
        menu.addAction(self.close_btn)

    def _show_more_menu(self):
        menu = QMenu(self)
        self._populate_result_menu(menu)
        self._exec_menu(menu, self.more_button.mapToGlobal(QPoint(0, self.more_button.height())))

    def _text_menu(self, position, widget=None):
        widget = widget or self.source_edit
        menu = self.source_edit.createStandardContextMenu() if widget is self.source_edit else QMenu(self)
        menu.addSeparator()
        self._populate_result_menu(menu)
        self._exec_menu(menu, widget.mapToGlobal(position))

    def _target_menu(self, position):
        menu = self.target_edit.createStandardContextMenu()
        self._add_comparison_actions(menu)
        self._exec_menu(menu, self.target_edit.mapToGlobal(position))

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
        if not self.target_edit.toPlainText() or self._busy:
            return
        source, target = self.source_edit.toPlainText(), self.target_edit.toPlainText()
        self._translation = None
        self._pending_translation = None
        if self._has_table():
            self.table_grid.hide()
            self.source_edit.show()
            self._kind = 'ocr'
            self._apply_mode('ocr')
        self.source_edit.setPlainText(target)
        self.target_edit.setPlainText(source)
        self.right.show()
        self._notify('已交换原文和译文')
        self._update_actions()

    def _retry(self):
        if self._delegate and not self.canvas.image.isNull():
            self._pending_translation = None
            self._delegate(self.canvas.rendered_image(), self.mode_combo.currentData())

    def _save_text(self):
        extension = ('json' if self.output_format.currentData() == 'json' else
                     'xlsx' if self._has_table() else None)
        self._export_output(extension)

    def _export_output(self, extension=None):
        if not self.save_text_btn.isEnabled():
            return
        filters = {'txt': '文本 (*.txt)', 'md': 'Markdown (*.md)',
                   'json': 'JSON (*.json)', 'xlsx': 'Excel 表格 (*.xlsx)'}
        file_filter = filters[extension] if extension else '文本 (*.txt);;Markdown (*.md)'
        filename = f'识别结果.{extension or "txt"}'
        path, _ = QFileDialog.getSaveFileName(self, '导出校对后的内容', filename, file_filter)
        if not path:
            return
        extension = extension or Path(path).suffix.lower().lstrip('.')
        try:
            if extension == 'xlsx':
                data = xlsx_bytes(self._table_cells())
            else:
                text = self.source_edit.toPlainText()
                if extension == 'json':
                    text = self._json_output()
                elif extension == 'md' and self._has_table():
                    text = markdown_table(self._table_cells())
                elif extension == 'md' and self._kind == 'code':
                    text = code_block(text)
                data = text.encode('utf-8')
            self._write_output(path, data)
        except (OSError, ValueError):
            self.show_error('导出失败，请检查内容或另选位置。')

    def _write_output(self, path, data):
        output = QSaveFile(path)
        if not output.open(QIODevice.OpenModeFlag.WriteOnly):
            self.show_error('无法写入此位置，请重新选择。')
            return
        if output.write(data) != len(data):
            output.cancelWriting()
            self.show_error('导出失败，请检查可用空间。')
            return
        if output.commit():
            self._notify('文件已导出')
        else:
            self.show_error('导出失败，请另选位置。')

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
        self._accept_results = False
        self._pending_translation = None
        self.cancel_requested.emit()
        self.set_busy(False)
        self._dismiss_menus()
        self.canvas.set_image(QImage())
        self._image = None
        self._invalidate()

        self.dimensions.setText('尚未载入图片')
        self.meta.clear()
        self.gloss.clear()
        self.source_edit.setPlaceholderText('打开、粘贴或拖入图片后开始识别')

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and len(event.mimeData().urls()) == 1 and event.mimeData().urls()[0].isLocalFile():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile():
            self.file_dropped.emit(urls[0].toLocalFile())
            event.acceptProposedAction()

    def closeEvent(self, event):
        self.clear_session()
        self.closed.emit()
        super().closeEvent(event)
