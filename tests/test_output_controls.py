import json
from types import SimpleNamespace
import pytest
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QMimeData
from shiguang_capture.ui.result_panel import ResultPanel
from shiguang_capture.ocr.base import OCRResult
from shiguang_capture.structured import TableData
from shiguang_capture.config import AppConfig


@pytest.fixture
def app():
    app = QApplication.instance() or QApplication([])
    yield app
    # Offscreen Qt has no system clipboard manager to consume transferred MIME
    # ownership before interpreter teardown.
    app.clipboard().clear()


def test_json_keeps_table_strings_and_mode_format(app):
    panel = ResultPanel(formats={'table': 'json', 'code': 'code'})
    result = OCRResult(text='00123', confidence=.9, table=TableData([['00123', '=2+2', '']], [[(0,0,20,20)]*3]))
    panel.show_result('table', result)
    assert panel.output_format.currentData() == 'json'
    panel._copy_source()
    saved = json.loads(app.clipboard().text())
    assert saved == {'schema_version':1, 'mode':'table', 'text':'00123\t=2+2\t',
                     'cells': [['00123', '=2+2', '']], 'rows':1, 'columns':3}
    panel.show_result('code', OCRResult(text='if True:\n    pass', confidence=.9))
    assert panel.output_format.currentData() == 'code'
    panel.show_result('table', result)
    assert panel.output_format.currentData() == 'json'
    panel.close()


def test_clipboard_busy_is_not_reported_as_success(app, monkeypatch):
    import shiguang_capture.clipboard as module
    old = QMimeData()
    old.setText('newer user content')
    busy = SimpleNamespace(setMimeData=lambda mime: None, mimeData=lambda: old)
    monkeypatch.setattr(module, 'QGuiApplication', SimpleNamespace(clipboard=lambda: busy))
    panel = ResultPanel()
    panel.source_edit.setPlainText('recognition')
    panel._copy_source()
    assert '失败' in panel.gloss.text()
    assert old.text() == 'newer user content'
    panel.close()


def test_saved_format_settings_validate_and_roundtrip(tmp_path):
    path = tmp_path/'config.json'
    config = AppConfig(output_formats={'ocr':'json','code':'code','table':'table'})
    config.save(path)
    assert AppConfig.load(path).output_formats == config.output_formats
    path.write_text(json.dumps({'output_formats':{'ocr':[], 'bad':'json', 'table':'markdown'}}))
    assert AppConfig.load(path).output_formats == {'table':'markdown'}
