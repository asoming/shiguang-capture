"""Saved recordings from the selected folder, with native file actions."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QFile, QFileSystemWatcher, QTimer, Qt, QUrl, QSize
from PySide6.QtGui import QDesktopServices, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMenu,
    QMessageBox, QPushButton, QStackedWidget, QToolButton, QTreeWidget, QInputDialog,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .record_metadata import VideoMetadataLoader
from .record_style import LIBRARY_STYLE
from .tool_icons import tool_icon

VIDEO_SUFFIXES = {'.mp4', '.mkv', '.mov', '.avi', '.webm', '.m4v'}


def file_size(size: int) -> str:
    value = float(size)
    for unit in ('B', 'KiB', 'MiB', 'GiB', 'TiB'):
        if value < 1024 or unit == 'TiB':
            return f'{value:.0f} {unit}' if unit == 'B' else f'{value:.1f} {unit}'
        value /= 1024


class RecordingLibrary(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.folder: Path | None = None
        self.active_path: Path | None = None
        self._listing_key = None
        self._menu_open = False
        self._metadata_items = {}
        self._read_error = ''
        self._total_bytes = 0
        self.setStyleSheet(LIBRARY_STYLE)
        self.metadata = VideoMetadataLoader(self)
        self.metadata.ready.connect(self._metadata_ready)
        self.metadata_timer = QTimer(self)
        self.metadata_timer.setSingleShot(True)
        self.metadata_timer.setInterval(80)
        self.metadata_timer.timeout.connect(self._request_metadata)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        header = QHBoxLayout()
        self.location = QLineEdit()
        self.location.setReadOnly(True)
        self.location.setAccessibleName('录屏保存文件夹')
        self.search = QLineEdit()
        self.search.setPlaceholderText('搜索录屏文件')
        self.search.setAccessibleName('搜索录屏文件')
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        header.addWidget(self.search, 1)
        open_folder = QPushButton('打开文件夹')
        open_folder.clicked.connect(lambda: self.open_path(self.folder))
        header.addWidget(open_folder)
        refresh = QPushButton('刷新')
        refresh.clicked.connect(self.refresh)
        header.addWidget(refresh)
        layout.addLayout(header)
        self.table = QTreeWidget()
        self.table.setColumnCount(5)
        self.table.setHeaderLabels(['名称', '大小', '录制时间', '', '时长'])
        # Keep existing logical columns stable for native acceptance/file actions.
        self.table.header().moveSection(4, 1)
        self.table.setIconSize(QSize(96, 54))
        self.table.setRootIsDecorated(False)
        self.table.setUniformRowHeights(True)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.header().setStretchLastSection(False)
        self.table.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column, width in ((1, 108), (2, 170), (3, 48), (4, 80)):
            self.table.header().setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(column, width)
        self.table.verticalScrollBar().valueChanged.connect(lambda _: self.metadata_timer.start())
        self.table.itemDoubleClicked.connect(lambda item, _: self.open_path(Path(item.data(0, Qt.ItemDataRole.UserRole))))
        self.empty = QLabel('还没有录屏文件')
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setStyleSheet('color:#8B9AAF; font-size:14px;')
        self.content = QStackedWidget()
        self.content.addWidget(self.table)
        self.content.addWidget(self.empty)
        layout.addWidget(self.content, 1)
        self.summary = QLabel()
        self.summary.setObjectName('muted')
        self.summary.setWordWrap(True)
        layout.addWidget(self.location)
        layout.addWidget(self.summary)
        self.watcher = QFileSystemWatcher(self)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.setInterval(300)
        self.refresh_timer.timeout.connect(self.refresh)
        self.watcher.directoryChanged.connect(lambda _: self.refresh_timer.start())

    def set_folder(self, folder: str, active_path: Path | None = None):
        self.folder = Path(folder).expanduser().absolute() if folder.strip() else None
        self.active_path = active_path.absolute() if active_path else None
        self.location.setText(str(self.folder) if self.folder else '')
        self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()
        self.metadata_timer.start()

    def hideEvent(self, event):
        self.metadata_timer.stop()
        self.metadata.stop()
        super().hideEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'metadata_timer'):
            self.metadata_timer.start()

    def refresh(self):
        if self._menu_open:
            return  # The menu's hide signal schedules the deferred refresh.
        records = []
        error = ''
        if self.folder:
            try:
                for path in self.folder.iterdir():
                    if (path.suffix.lower() not in VIDEO_SUFFIXES or path.name.startswith('.')
                            or path.name.endswith('.sgc-recovery.mkv') or path == self.active_path
                            or path.is_symlink()):
                        continue
                    try:
                        if path.is_file():
                            records.append((path, path.stat()))
                    except FileNotFoundError:
                        continue  # An external file operation can race the refresh.
            except FileNotFoundError:
                pass  # The default folder is created on the first recording.
            except OSError as exc:
                error = f'无法读取文件夹：{exc}'
        watched = self.watcher.directories()
        desired = [str(self.folder)] if self.folder and self.folder.is_dir() else []
        if watched != desired:
            if watched:
                self.watcher.removePaths(watched)
            if desired:
                self.watcher.addPaths(desired)
        records.sort(key=lambda record: (-record[1].st_mtime, record[0].name))
        key = (self.folder, error, tuple((path, stat.st_size, stat.st_mtime_ns) for path, stat in records))
        self._read_error = error
        self._total_bytes = sum(stat.st_size for _, stat in records)
        if key == self._listing_key:
            self._apply_filter()
            return  # Unrelated files should not disturb selection or menus.
        self._listing_key = key
        selected = self.table.currentItem()
        selected_path = selected.data(0, Qt.ItemDataRole.UserRole) if selected else None
        self.table.clear()
        self._metadata_items.clear()
        for path, stat in records:
            item = QTreeWidgetItem([path.name, file_size(stat.st_size),
                                    datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'), '', '—'])
            item.setData(0, Qt.ItemDataRole.UserRole, str(path))
            item.setToolTip(0, path.name)
            item.setIcon(0, tool_icon('play', '#A4BADC'))
            metadata_key = (str(path), stat.st_size, stat.st_mtime_ns)
            self._metadata_items[metadata_key] = item
            self.table.addTopLevelItem(item)
            cached = self.metadata.get(metadata_key)
            if cached is not None:
                self._metadata_ready(metadata_key, cached)
            button = QToolButton()
            button.setText('⋯')
            button.setToolTip('更多操作')
            button.setAccessibleName(f'{path.name} · 更多操作')
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            button.setMenu(self.file_menu(path, button))
            self.table.setItemWidget(item, 3, button)
            if str(path) == selected_path:
                self.table.setCurrentItem(item)
        self._apply_filter()

    def _apply_filter(self):
        query = self.search.text().strip().casefold()
        count = 0
        total = self.table.topLevelItemCount()
        for index in range(total):
            item = self.table.topLevelItem(index)
            match = query in item.text(0).casefold()
            item.setHidden(not match)
            count += match
        self.content.setCurrentWidget(self.table if count else self.empty)
        message = ('无法读取文件夹' if self._read_error else
                   '没有匹配的录屏文件' if query and total else '还没有录屏文件')
        self.empty.setText(message)
        summary = f'{total} 个文件 · {file_size(self._total_bytes)}'
        if query:
            summary = f'找到 {count} / {total} 个文件'
        self.summary.setText(self._read_error or summary)
        self.metadata_timer.start()

    def _request_metadata(self):
        if not self.isVisible():
            return
        visible = self.table.viewport().rect().adjusted(0, -160, 0, 160)
        keys = [key for key, item in self._metadata_items.items()
                if not item.isHidden() and self.table.visualItemRect(item).intersects(visible)]
        self.metadata.request(keys)

    def _metadata_ready(self, key, details):
        item = self._metadata_items.get(key)
        if item is None:
            return
        if details.duration is not None:
            seconds = round(details.duration)
            hours, rest = divmod(seconds, 3600)
            minutes, seconds = divmod(rest, 60)
            value = f'{hours}:{minutes:02d}:{seconds:02d}' if hours else f'{minutes:02d}:{seconds:02d}'
            item.setText(4, value)
        item.setToolTip(4, details.error or '')
        if details.width and details.height:
            item.setToolTip(0, f'{Path(key[0]).name}\n{details.width} × {details.height}')
        if details.pixels:
            image = QImage(details.pixels, details.thumbnail_width, details.thumbnail_height,
                           details.thumbnail_width * 3, QImage.Format.Format_RGB888).copy()
            item.setIcon(0, QIcon(QPixmap.fromImage(image)))

    def rename_file(self, path: Path, new_name: str | None = None):
        if path == self.active_path or path.is_symlink():
            self.summary.setText('这个文件当前不能重命名。')
            return False
        if new_name is None:
            new_name, accepted = QInputDialog.getText(self, '重命名录屏', '文件名', text=path.name)
            if not accepted:
                return False
        name = new_name.strip()
        if (not name or name.startswith('.') or name.endswith('.') or
                any(char in name for char in '/\\\x00<>:"|?*') or any(ord(char) < 32 for char in name)):
            self.summary.setText('请输入有效文件名，不要包含路径或特殊字符。')
            return False
        if not name.lower().endswith(path.suffix.lower()):
            name += path.suffix
        target = path.with_name(name)
        if target == path:
            return True
        self.metadata.stop()  # Release the decoder's file handle before renaming on Windows.
        file = QFile(str(path))
        # QFile.rename refuses existing targets, including a race after validation.
        if not file.rename(str(target)):
            self.summary.setText('无法重命名，请检查同名文件、权限或文件是否正在使用。')
            self.metadata_timer.start()
            return False
        previous_key = next((key for key in self._metadata_items if key[0] == str(path)), None)
        cached = self.metadata.get(previous_key) if previous_key else None
        if cached is not None:
            self.metadata.cache.pop(previous_key, None)
            self.metadata._remember((str(target), *previous_key[1:]), cached)
        self.refresh()
        self.summary.setText(f'已重命名为 {target.name}')
        return True

    def file_menu(self, path: Path, parent):
        menu = QMenu(parent)
        menu.aboutToShow.connect(self._menu_opened)
        menu.aboutToHide.connect(self._menu_closed)
        menu.addAction('播放', lambda: self.open_path(path))
        menu.addAction('打开所在文件夹', lambda: self.open_path(path.parent))
        menu.addAction('重命名…', lambda: self.rename_file(path))
        menu.addSeparator()
        menu.addAction('删除', lambda: self.delete_file(path))
        return menu

    def _menu_opened(self):
        self._menu_open = True

    def _menu_closed(self):
        self._menu_open = False
        self.refresh_timer.start()

    def open_path(self, path: Path | None):
        if path is None or not path.exists():
            self.summary.setText('文件或文件夹不存在，请刷新列表。')
        elif not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            self.summary.setText('无法打开，请检查系统默认播放器或文件管理器。')

    def delete_file(self, path: Path):
        if path == self.active_path:
            self.summary.setText('录制中的文件不能删除。')
            return
        if not path.is_file():
            self.refresh()
            self.summary.setText('文件已不存在。')
            return
        answer = QMessageBox.question(self, '删除录屏', f'将“{path.name}”移到回收站？',
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        # Never fall back to permanent deletion if the platform has no trash.
        self.metadata.stop()
        result = QFile.moveToTrash(str(path))
        # PySide versions expose the optional output path differently.
        removed = result[0] if isinstance(result, tuple) else result
        self.refresh()
        if not removed:
            self.summary.setText('无法移到回收站，文件已保留。请打开所在文件夹处理。')
