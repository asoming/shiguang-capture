"""Saved recordings from the selected folder, with native file actions."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QFile, QFileSystemWatcher, QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMenu,
    QMessageBox, QPushButton, QStackedWidget, QToolButton, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

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
        self.setStyleSheet('''
            QTreeWidget {background:white; border:0; outline:0;}
            QTreeWidget::item {height:56px; border-bottom:1px solid #EDF2F8;}
            QTreeWidget::item:selected {background:#E5F2FF; color:#24394B;}
            QHeaderView::section {background:#F7FAFF; color:#657D8E;
                                  border:0; padding:10px; text-align:left;}
            QToolButton {border:0; border-radius:6px; font-size:24px; background:transparent;}
            QToolButton:hover {background:#DDEEFF; color:#3188F5;}
            QToolButton::menu-indicator {image:none;}
            QMenu {background:white; border:1px solid #DCE7F4; padding:5px;}
            QMenu::item {padding:9px 24px;}
            QMenu::item:selected {background:#E5F2FF;}
        ''')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        header = QHBoxLayout()
        self.location = QLineEdit()
        self.location.setReadOnly(True)
        self.location.setAccessibleName('录屏保存文件夹')
        header.addWidget(self.location, 1)
        open_folder = QPushButton('打开文件夹')
        open_folder.clicked.connect(lambda: self.open_path(self.folder))
        header.addWidget(open_folder)
        refresh = QPushButton('刷新')
        refresh.clicked.connect(self.refresh)
        header.addWidget(refresh)
        layout.addLayout(header)
        self.table = QTreeWidget()
        self.table.setColumnCount(4)
        self.table.setHeaderLabels(['文件名', '大小', '修改时间', ''])
        self.table.setRootIsDecorated(False)
        self.table.setUniformRowHeights(True)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.header().setStretchLastSection(False)
        self.table.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column, width in ((1, 110), (2, 175), (3, 60)):
            self.table.header().setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(column, width)
        self.table.itemDoubleClicked.connect(lambda item, _: self.open_path(Path(item.data(0, Qt.ItemDataRole.UserRole))))
        self.empty = QLabel('还没有录屏文件')
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setStyleSheet('color:#657D8E; font-size:15px;')
        self.content = QStackedWidget()
        self.content.addWidget(self.table)
        self.content.addWidget(self.empty)
        layout.addWidget(self.content, 1)
        self.summary = QLabel()
        self.summary.setObjectName('muted')
        self.summary.setWordWrap(True)
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

    def refresh(self):
        selected = self.table.currentItem()
        selected_path = selected.data(0, Qt.ItemDataRole.UserRole) if selected else None
        self.table.clear()
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
        for path, stat in sorted(records, key=lambda record: (-record[1].st_mtime, record[0].name)):
            item = QTreeWidgetItem([path.name, file_size(stat.st_size),
                                    datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'), ''])
            item.setData(0, Qt.ItemDataRole.UserRole, str(path))
            item.setToolTip(0, path.name)
            self.table.addTopLevelItem(item)
            button = QToolButton()
            button.setText('⋯')
            button.setToolTip('更多操作')
            button.setAccessibleName(f'{path.name} · 更多操作')
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            button.setMenu(self.file_menu(path, button))
            self.table.setItemWidget(item, 3, button)
            if str(path) == selected_path:
                self.table.setCurrentItem(item)
        self.content.setCurrentWidget(self.table if records else self.empty)
        self.empty.setText('无法读取文件夹' if error else '还没有录屏文件')
        self.summary.setText(error or f'{len(records)} 个文件 · {file_size(sum(stat.st_size for _, stat in records))}')

    def file_menu(self, path: Path, parent):
        menu = QMenu(parent)
        menu.addAction('播放', lambda: self.open_path(path))
        menu.addAction('打开所在文件夹', lambda: self.open_path(path.parent))
        menu.addSeparator()
        menu.addAction('删除', lambda: self.delete_file(path))
        return menu

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
        removed = QFile.moveToTrash(str(path))
        self.refresh()
        if not removed:
            self.summary.setText('无法移到回收站，文件已保留。请打开所在文件夹处理。')
