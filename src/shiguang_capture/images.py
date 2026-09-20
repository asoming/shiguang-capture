"""Validated image inputs and atomic, checked exports."""
from pathlib import Path
from PySide6.QtCore import QSaveFile, QIODevice
from PySide6.QtGui import QImage, QImageReader

MAX_PIXELS = 32_000_000
MAX_SIDE = 32767


def validate_size(width: int, height: int, max_pixels: int = MAX_PIXELS) -> None:
    if width <= 0 or height <= 0:
        raise ValueError("没有可用的图像，请重新截图或打开图片。")
    if max(width, height) > MAX_SIDE or width * height > max_pixels:
        raise ValueError("图像尺寸过大，请先裁剪或分段处理。")


def load_image(path: str) -> QImage:
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    if bytes(reader.format()).lower() not in (b"png", b"jpeg", b"jpg"):
        raise ValueError("请选择 PNG 或 JPEG 图片。")
    size = reader.size()
    validate_size(size.width(), size.height())
    image = reader.read()
    if image.isNull():
        raise ValueError("无法读取这张图片，文件可能已损坏。")
    validate_size(image.width(), image.height())
    return image


def save_image(image: QImage, path: Path) -> None:
    validate_size(image.width(), image.height(), max_pixels=64_000_000)
    suffix = path.suffix.lower().lstrip(".")
    if suffix not in {"png", "jpg", "jpeg"}:
        raise ValueError("保存格式必须为 PNG 或 JPEG。")
    path.parent.mkdir(parents=True, exist_ok=True)
    output = QSaveFile(str(path))
    if not output.open(QIODevice.OpenModeFlag.WriteOnly):
        raise OSError("无法写入此位置，请选择其他目录。")
    if not image.save(output, suffix.upper()):
        output.cancelWriting()
        raise OSError("图像保存失败，原文件没有被修改。")
    if not output.commit():
        raise OSError("保存未完成，请检查可用空间或选择其他目录。")
