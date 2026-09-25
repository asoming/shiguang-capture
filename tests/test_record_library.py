"""Saved recordings follow the chosen folder and act on the selected file."""
import os
from pathlib import Path
import time

import pytest

pytest.importorskip('PySide6')
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox

from shiguang_capture.ui.record_library import RecordingLibrary, file_size
from shiguang_capture.ui.record_panel import RecordPanel


@pytest.fixture
def library(qt_session, tmp_path):
    widget = RecordingLibrary()
    widget.resize(900, 480)
    widget.set_folder(str(tmp_path))
    widget.show()
    yield widget
    widget.close()
    widget.deleteLater()


def test_list_sorts_newest_and_skips_incomplete_or_nonvideo_files(library, tmp_path):
    old = tmp_path / '旧录屏.mp4'
    old.write_bytes(b'a' * 1024)
    os.utime(old, (10, 10))
    new = tmp_path / '新录屏.MP4'
    new.write_bytes(b'b' * 2048)
    for name in ['work.sgc-recovery.mkv', 'notes.txt', '.temporary.mp4', 'active.mp4']:
        (tmp_path / name).touch()
    (tmp_path / 'directory.mp4').mkdir()
    library.set_folder(str(tmp_path), tmp_path / 'active.mp4')
    assert library.table.topLevelItemCount() == 2
    assert [library.table.topLevelItem(i).text(0) for i in range(2)] == [new.name, old.name]
    assert library.table.topLevelItem(0).text(1) == '2.0 KiB'
    assert library.summary.text() == '2 个文件 · 3.0 KiB'


def test_menu_opens_exact_file_and_parent_even_with_spaces(library, tmp_path, monkeypatch):
    from shiguang_capture.ui import record_library
    path = tmp_path / '中文 录屏.mp4'
    path.touch()
    library.refresh()
    opened = []
    monkeypatch.setattr(record_library.QDesktopServices, 'openUrl', lambda url: opened.append(url.toLocalFile()) or True)
    item = library.table.topLevelItem(0)
    button = library.table.itemWidget(item, 3)
    actions = [action for action in button.menu().actions() if not action.isSeparator()]
    assert [action.text() for action in actions] == ['播放', '打开所在文件夹', '重命名…', '删除']
    actions[0].trigger()
    actions[1].trigger()
    assert [Path(value) for value in opened] == [path, tmp_path]


@pytest.mark.parametrize('returns_tuple', [False, True])
def test_delete_cancel_failure_and_success_are_safe(library, tmp_path, monkeypatch, returns_tuple):
    from shiguang_capture.ui import record_library
    path = tmp_path / 'delete me.mp4'
    path.touch()
    library.refresh()
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.No)
    library.delete_file(path)
    assert path.exists()
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(record_library.QFile, 'moveToTrash', lambda file: (False, '') if returns_tuple else False)
    library.delete_file(path)
    assert path.exists() and '已保留' in library.summary.text()

    def trash(filename):
        assert filename == str(path)
        Path(filename).unlink()
        return (True, str(path)) if returns_tuple else True

    monkeypatch.setattr(record_library.QFile, 'moveToTrash', trash)
    library.delete_file(path)
    assert not path.exists() and library.table.topLevelItemCount() == 0


def test_external_changes_and_missing_folders_refresh(library, tmp_path):
    (tmp_path / 'created.mp4').touch()
    # Directory notifications are asynchronous and macOS may coalesce them.
    # Wait for the actual refresh, without manually invoking the behavior tested.
    deadline = time.monotonic() + 3
    while library.table.topLevelItemCount() != 1 and time.monotonic() < deadline:
        QTest.qWait(20)
    assert library.table.topLevelItemCount() == 1
    library.set_folder(str(tmp_path / 'not-created'))
    assert library.table.topLevelItemCount() == 0
    assert library.content.currentWidget() == library.empty
    library.set_folder('')
    assert library.folder is None


def test_record_panel_switch_and_save_update_library(qt_session, tmp_path):
    panel = RecordPanel()
    panel.timer.stop()
    panel.folder.setText(str(tmp_path))
    panel.show()
    panel.tabs.setCurrentIndex(1)
    assert panel.pages.currentWidget() is panel.library
    assert panel.library.folder == tmp_path
    path = tmp_path / 'finished.mp4'
    path.touch()
    panel.state = 'saving'
    panel._event({'type': 'finished', 'path': str(path)})
    assert panel.library.table.topLevelItemCount() == 1
    panel.tabs.setCurrentIndex(0)
    assert panel.start_button.isVisible()
    panel.close()
    panel.deleteLater()


def test_directory_refresh_does_not_destroy_an_open_file_menu(library, tmp_path):
    (tmp_path / 'first.mp4').touch()
    library.refresh()
    item = library.table.topLevelItem(0)
    (tmp_path / 'unrelated.png').touch()
    QTest.qWait(650)
    assert library.table.topLevelItem(0) is item
    button = library.table.itemWidget(item, 3)
    menu = button.menu()
    menu.popup(button.mapToGlobal(button.rect().bottomLeft()))
    (tmp_path / 'second.mp4').touch()
    QTest.qWait(650)
    assert menu.isVisible() and item.text(0) == 'first.mp4'
    assert library.table.topLevelItemCount() == 1
    menu.hide()
    QTest.qWait(650)
    assert library.table.topLevelItemCount() == 2


def test_size_uses_readable_binary_units():
    assert file_size(0) == '0 B'
    assert file_size(1536) == '1.5 KiB'
    assert file_size(1024**3) == '1.0 GiB'


def test_record_folder_is_remembered_and_empty_path_cannot_record(qt_session, tmp_path):
    from shiguang_capture.config import AppConfig
    config = AppConfig(record_dir=str(tmp_path / '视频'))
    config_path = tmp_path / 'config.json'
    config.save(config_path)
    panel = RecordPanel(AppConfig.load(config_path).record_dir)
    panel.timer.stop()
    assert panel.folder.text() == config.record_dir
    changed = []
    panel.folder_changed.connect(changed.append)
    panel.folder.setText(str(tmp_path))
    panel._folder_edited()
    assert changed == [str(tmp_path)]
    panel.folder.clear()
    panel.toggle()
    assert panel.state == 'idle' and panel.process is None
    assert '保存位置' in panel.status.text()
    panel.deleteLater()


def test_search_is_case_insensitive_and_survives_directory_refresh(library, tmp_path):
    for name in ['Meeting.mp4', '长截图演示.mp4', '其他.mp4']:
        (tmp_path / name).touch()
    library.refresh()
    library.search.setText('meet')
    visible = lambda: [library.table.topLevelItem(i).text(0)
                       for i in range(library.table.topLevelItemCount())
                       if not library.table.topLevelItem(i).isHidden()]
    assert visible() == ['Meeting.mp4']
    (tmp_path / 'MEETING 2.mp4').touch()
    library.refresh()
    assert set(visible()) == {'Meeting.mp4', 'MEETING 2.mp4'}
    library.search.setText('没有匹配')
    assert library.content.currentWidget() is library.empty
    assert '没有匹配' in library.empty.text()
    library.search.clear()
    assert len(visible()) == 4


def test_rename_preserves_extension_and_never_overwrites(library, tmp_path):
    source = tmp_path / '录屏.mp4'
    target = tmp_path / '已有.mp4'
    source.write_bytes(b'original')
    target.write_bytes(b'existing')
    library.refresh()
    assert not library.rename_file(source, '已有')
    assert source.read_bytes() == b'original' and target.read_bytes() == b'existing'
    assert not library.rename_file(source, '../escape')
    assert not library.rename_file(source, '.hidden')
    assert library.rename_file(source, '新的 文件')
    assert not source.exists() and (tmp_path / '新的 文件.mp4').read_bytes() == b'original'
    assert library.table.topLevelItemCount() == 2
    library.active_path = target
    assert not library.rename_file(target, '不能改名')
    assert target.exists()


def _write_test_video(path):
    av = pytest.importorskip('av')
    import numpy as np
    with av.open(str(path), 'w') as media:
        stream = media.add_stream('mpeg4', rate=10)
        stream.width, stream.height = 160, 90
        stream.pix_fmt = 'yuv420p'
        for _ in range(20):
            frame = av.VideoFrame.from_ndarray(np.full((90, 160, 3), (220, 40, 80), dtype=np.uint8), format='rgb24')
            for packet in stream.encode(frame):
                media.mux(packet)
        for packet in stream.encode():
            media.mux(packet)


def test_real_video_details_are_async_cached_and_stopped_when_hidden(library, tmp_path, monkeypatch):
    path = tmp_path / '真实录屏.mp4'
    _write_test_video(path)
    library.refresh()
    delivered = []
    library.metadata.ready.connect(lambda key, details: delivered.append((key, details)))
    deadline = time.monotonic() + 10
    while not delivered and time.monotonic() < deadline:
        QTest.qWait(20)
    assert delivered, 'Video metadata process did not respond'
    key, details = delivered[0]
    assert details.duration == pytest.approx(2, abs=.15)
    assert (details.width, details.height) == (160, 90)
    assert details.pixels and details.thumbnail_width <= 192
    assert library.table.topLevelItem(0).text(4) == '00:02'
    assert library.metadata.process is not None
    library.hide()
    assert library.metadata.process is None and not library.metadata.timer.isActive()

    def unexpected_decode():
        pytest.fail('unchanged video should use cached metadata')
    monkeypatch.setattr(library.metadata, '_start_worker', unexpected_decode)
    library.show()
    library.refresh()
    QTest.qWait(160)
    assert library.metadata.get(key) == details and len(delivered) == 1


def test_replaced_video_invalidates_cache_key(library, tmp_path):
    from shiguang_capture.ui.record_metadata import VideoDetails
    path = tmp_path / 'same.mp4'
    path.write_bytes(b'first')
    library.refresh()
    old_key = next(iter(library._metadata_items))
    library.metadata._remember(old_key, VideoDetails(duration=20))
    assert library.table.topLevelItem(0).text(4) == '00:20'
    path.write_bytes(b'replaced content')
    library.refresh()
    new_key = next(iter(library._metadata_items))
    assert new_key != old_key
    assert library.table.topLevelItem(0).text(4) == '—'
    library._metadata_ready(old_key, VideoDetails(duration=99))
    assert library.table.topLevelItem(0).text(4) == '—'
