"""Exercise the shipped Qt, OCR subprocess and text-only XLSX without user data."""
from __future__ import annotations
import io
import json
import os
import threading


def run():
    os.environ['QT_QPA_PLATFORM']='offscreen'
    os.environ['SHIGUANG_NO_HOTKEYS']='1'
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QBuffer, QIODevice, QRect, Qt
    from PySide6.QtGui import QImage, QPainter, QFont
    from openpyxl import load_workbook
    from .config import AppConfig
    from .ocr.worker import RecognitionRunner
    from .structured import xlsx_bytes, table_clipboard
    from .ui.result_panel import ResultPanel
    app=QApplication.instance() or QApplication([])
    app.clipboard().setText('self-test sentinel')
    image=QImage(900,250,QImage.Format.Format_RGB888)
    image.fill(Qt.GlobalColor.white)
    p=QPainter(image);p.setPen(Qt.GlobalColor.black);p.setFont(QFont('DejaVu Sans',24))
    p.drawText(QRect(30,30,850,150),Qt.AlignmentFlag.AlignLeft,'Capture 00123\nLocal image review');p.end()
    buf=QBuffer();buf.open(QIODevice.OpenModeFlag.WriteOnly);assert image.save(buf,'PNG')
    runner=RecognitionRunner()
    try:
        result,_=runner.run(bytes(buf.data()),'ocr',AppConfig(),threading.Event())
        assert 'Capture' in result.text and '00123' in result.text,result.text
        panel=ResultPanel();panel.set_image(image);panel.show_result('ocr',result)
        assert app.clipboard().text()=='self-test sentinel'
        first_pid=runner._process.pid
        code,_=runner.run(bytes(buf.data()),'code',AppConfig(),threading.Event())
        assert code.mode=='code' and '00123' in code.text
        assert first_pid==runner._process.pid
        # Draw a complete 2 x 2 grid and exercise the production process mode.
        grid=QImage(700,240,QImage.Format.Format_RGB888);grid.fill(Qt.GlobalColor.white)
        p=QPainter(grid);p.setPen(Qt.GlobalColor.black);p.setFont(QFont('DejaVu Sans',22))
        for x in (20,350,680):p.drawLine(x,20,x,220)
        for y in (20,120,220):p.drawLine(20,y,680,y)
        for x,y,text in ((40,80,'ID'),(370,80,'Value'),(40,180,'00123'),(370,180,'128.50')):p.drawText(x,y,text)
        p.end();buf=QBuffer();buf.open(QIODevice.OpenModeFlag.WriteOnly);assert grid.save(buf,'PNG')
        table,_=runner.run(bytes(buf.data()),'table',AppConfig(),threading.Event())
        assert table.table.shape==(2,2),table.table
        assert table.table.cells[1]==['00123','128.50'],table.table.cells
        panel.set_image(grid);panel.show_result('table',table)
        panel.table_grid.item(1,0).setText('00007')
        assert panel._table_cells()[1][0]=='00007'
        assert table.table.cells[1][0]=='00123'
        panel._restore();assert panel._table_cells()[1][0]=='00123'
        panel.table_grid.item(1,0).setText('=2+2')
        panel.output_format.setCurrentIndex(panel.output_format.findData('table'))
        panel._copy_source();assert app.clipboard().text()=='self-test sentinel'
        cells=[['00123','12345678901234567890','2026-09-20','=2+2','+SUM(A1)','@A1','多行\n内容']]
        workbook=load_workbook(io.BytesIO(xlsx_bytes(cells)))
        assert [c.value for c in workbook.active[1]]==cells[0]
        assert all(c.data_type=='s' for c in workbook.active[1])
        plain,rich=table_clipboard([['ID','00123']]);assert plain=='ID\t00123' and '<table>' in rich
        panel.clear_session();assert panel._result is None and panel.canvas.image.isNull()
        print(json.dumps({'self_test':'PASS','engine':result.engine,'text':result.text,'table':table.table.cells,'checks':['model hashes','OCR subprocess','warm reuse','code mode','table mode','cell edit/restore','formula clipboard gate','text XLSX','no automatic clipboard write','session cleanup']},ensure_ascii=False))
        return 0
    finally:
        runner.close()
