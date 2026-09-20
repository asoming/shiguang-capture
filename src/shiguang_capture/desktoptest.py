"""Actual X11 capture/hotkey checks against a synthetic topmost test window."""
import json
import os
import time
from pathlib import Path
from PySide6.QtCore import Qt, QPoint, QMimeData
from PySide6.QtGui import QPainter, QColor, QImage
from PySide6.QtWidgets import QApplication, QWidget
from shiguang_capture.capture.grabber import capture_frames, compose_region
from shiguang_capture.geometry import Rect
from shiguang_capture.hotkeys import HotkeyManager, HotkeyBridge
from shiguang_capture.ui.pin_window import PinWindow


class Pattern(QWidget):
    def paintEvent(self,event):
        p=QPainter(self);p.fillRect(self.rect(),QColor('#123456'))
        p.fillRect(40,40,120,80,QColor('#dc7020'))
        p.setPen(Qt.GlobalColor.white);p.drawText(20,180,'Shiguang synthetic capture test')


def main():
    assert os.environ.get('XDG_SESSION_TYPE')=='x11','This test requires X11'
    app=QApplication([])
    def pump(seconds=.3):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:app.processEvents();time.sleep(.01)
    window=Pattern();window.setWindowFlags(Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint)
    window.resize(520,280);window.move(160,160);window.show();window.activateWindow();pump(.6)
    manager=HotkeyManager(HotkeyBridge());pin=None
    try:
        origin=window.mapToGlobal(QPoint(0,0))
        rect=Rect(origin.x(),origin.y(),window.width(),window.height())
        frames=capture_frames();image=compose_region(frames,rect)
        density=max(f.dpr for f in frames if f.bounds.intersects(rect))
        assert image.width()==round(window.width()*density)
        for x,y,color in ((10,10,'#123456'),(80,70,'#dc7020')):
            assert image.pixelColor(round(x*density),round(y*density)).name()==color,(image.pixelColor(round(x*density),round(y*density)).name(),color)
        # Frozen capture is unchanged even after the test window disappears.
        window.hide();pump();assert compose_region(frames,rect)==image
        pin=PinWindow(image);pin.show();pump();assert pin.isVisible();pin.hide();pump();assert not pin.isVisible()
        window.show();window.activateWindow();pump()
        hits=[];manager.bridge.triggered.connect(hits.append)
        assert manager.register({'test':'ctrl+shift+f12'})
        manager._listener.wait()
        from pynput.keyboard import Controller,Key
        keyboard=Controller()
        with keyboard.pressed(Key.ctrl):
            with keyboard.pressed(Key.shift):keyboard.press(Key.f12);keyboard.release(Key.f12)
        pump(.5);assert hits==['test'],hits
        # Copy/read an image via the real Qt/X11 clipboard, restoring prior formats.
        clipboard=app.clipboard();previous=QMimeData();current=clipboard.mimeData()
        if current:
            for name in current.formats():previous.setData(name,current.data(name))
        clipboard.setImage(image);pump(.1)
        assert clipboard.image().size()==image.size()
        clipboard.setMimeData(previous);pump(.1)
        print(json.dumps({'x11':'PASS','screen_pixels':[image.width(),image.height()],'density':density,'checks':['live screen crop colors','native capture size','frozen snapshot','pin show/hide','real ctrl+shift+F12','image clipboard and restore']},ensure_ascii=False))
    finally:
        manager.unregister();window.close()
        if pin:pin.close()

if __name__=='__main__':main()
