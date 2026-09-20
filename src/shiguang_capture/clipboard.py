"""User-triggered clipboard writes with read-back, no background retries."""
from uuid import uuid4
from PySide6.QtCore import QMimeData
from PySide6.QtGui import QGuiApplication

TOKEN_FORMAT = 'application/x-shiguang-copy-token'


def write_mime(mime):
    clipboard = QGuiApplication.clipboard()
    token = uuid4().hex.encode('ascii')
    mime.setData(TOKEN_FORMAT, token)
    clipboard.setMimeData(mime)
    current = clipboard.mimeData()
    if current is None or bytes(current.data(TOKEN_FORMAT)) != token:
        raise RuntimeError('剪贴板写入失败或被其他程序占用，请重试复制。')


def write_text(text, html=None):
    mime = QMimeData()
    mime.setText(text)
    if html is not None:
        mime.setHtml(html)
    write_mime(mime)


def write_image(image):
    if image.isNull():
        raise ValueError('没有可复制的图片。')
    mime = QMimeData()
    mime.setImageData(image)
    write_mime(mime)
