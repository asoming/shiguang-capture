"""capture/selector.py — 全屏取景框（FR-1.5 ~ FR-1.10 + QQ 截图式编辑态）。

性能设计：showEvent 时抓取一次全屏快照并缓存，遮罩 / 放大镜 / 选区
显示全部从缓存绘制——鼠标移动零系统调用，拖拽不卡。

交互状态机：
- IDLE：拖拽创建选区（实时尺寸 + 放大镜）
- EDITING（松开创建后）：八向手柄缩放、内部拖动移动、方向键逐像素微调；
  选区下方工具栏：✓确认 / 📌贴图 / 🔍识图 / 🌐翻译 / ✗取消；
  Enter=确认，Esc=取消。
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QColor, QGuiApplication, QImage, QKeyEvent, QMouseEvent, QPainter, QPen,
)
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from ..colors import rgb_to_hex
from ..geometry import Rect
from .grabber import virtual_desktop_rect

_HANDLE_R = 8           # 手柄命中半径（屏幕像素）
_MIN_W = 8              # 编辑态最小选区
_TOOLBAR_H = 38

# QQ 截图式工具栏：左侧编辑工具，右侧动作。当前版本先落地动作区
# （确认/贴图/识图/翻译/长截图/取消），标注工具（矩形/箭头/马赛克/文字）
# 属 V1.3 独立模块，此处留位不占 UI。
_ACTIONS = [
    ("save", "✓", "确认并复制（Enter）"),
    ("scroll", "⇕", "滚动长截图"),
    ("pin", "📌", "贴到桌面"),
    ("ocr", "文", "屏幕识图（提取文字）"),
    ("translate", "译", "翻译选区文字"),
    ("cancel", "✕", "取消（Esc）"),
]


class _Toolbar(QWidget):
    """选区下方的动作工具栏（子窗口部件，自动处理自身事件）。

    QQ 截图的工具栏是「一排图标 + 悬停提示」的形态，这里照搬：
    图标按钮 + tooltip，确认按钮高亮为主色。
    """

    action_clicked = Signal(str)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedHeight(_TOOLBAR_H)
        self.setStyleSheet(
            "QWidget{background:#1a1f28;border:1px solid #364052;border-radius:8px}"
            "QPushButton{color:#e9edf3;background:transparent;border:none;"
            "padding:4px 8px;font-size:14px;border-radius:6px;min-width:26px}"
            "QPushButton:hover{background:#364052}"
            "QPushButton#primary{background:#5f80f5;color:#ffffff;font-weight:600}"
            "QPushButton#primary:hover{background:#7190ff}"
            "QPushButton#danger:hover{background:#7a2b2e}"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 4, 6, 4)
        row.setSpacing(2)
        for action, label, tip in _ACTIONS:
            btn = QPushButton(label)
            btn.setToolTip(tip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if action == "save":
                btn.setObjectName("primary")
            elif action == "cancel":
                btn.setObjectName("danger")
            btn.clicked.connect(lambda _=False, a=action: self.action_clicked.emit(a))
            row.addWidget(btn)
            if action in ("pin", "ocr"):
                # 分组视觉分隔（对齐 QQ 截图：编辑 / 识别 / 输出 三段）
                sep = QWidget()
                sep.setFixedWidth(1)
                sep.setStyleSheet(
                    "background:#364052;margin-top:6px;margin-bottom:6px")
                row.addWidget(sep)


class RegionSelector(QWidget):
    action_chosen = Signal(object, str)   # geometry.Rect, action
    cancelled = Signal()

    IDLE, EDITING = 0, 1
    MAG_SIZE = 120
    MAG_CELLS = 15

    def __init__(self) -> None:
        super().__init__()
        bounds = virtual_desktop_rect()
        self._bounds = bounds
        self.setGeometry(bounds.x, bounds.y, bounds.width, bounds.height)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

        self._state = self.IDLE
        self._sel: Rect | None = None
        self._drag_origin: QPoint | None = None
        self._drag_mode: str | None = None       # create / move / resize
        self._active_handle: str | None = None
        self._move_offset: QPoint | None = None
        self._cursor: QPoint | None = None
        self._snapshot: QImage | None = None     # 全屏缓存快照

        self._toolbar = _Toolbar(self)
        self._toolbar.action_clicked.connect(self._on_action)
        self._toolbar.hide()
        self.setCursor(Qt.CursorShape.CrossCursor)

    # ---------- 生命周期 ----------
    def showEvent(self, e) -> None:  # noqa: N802
        super().showEvent(e)
        if self._snapshot is None:
            self._snapshot = self._grab_full_snapshot()

    def _grab_full_snapshot(self) -> QImage:
        """打开时一次性抓取虚拟桌面（之后的所有绘制都读这份缓存）。"""
        b = self._bounds
        img = QImage(b.width, b.height, QImage.Format.Format_RGB888)
        img.fill(QColor(20, 22, 26))
        p = QPainter(img)
        for screen in QGuiApplication.screens():
            g = screen.geometry()
            pix = screen.grabWindow(0).toImage()
            p.drawImage(g.x() - b.x, g.y() - b.y, pix)
        p.end()
        return img

    # ---------- 坐标换算 ----------
    def _to_local(self, global_pos: QPoint) -> QPoint:
        return QPoint(global_pos.x() - self._bounds.x,
                      global_pos.y() - self._bounds.y)

    def _local_sel(self) -> QRect | None:
        if not self._sel:
            return None
        return QRect(self._sel.x - self._bounds.x, self._sel.y - self._bounds.y,
                     self._sel.width, self._sel.height)

    # ---------- 手柄命中 ----------
    def _handles(self) -> dict[str, QPoint]:
        s = self._local_sel()
        if not s:
            return {}
        cx, cy = s.center().x(), s.center().y()
        l, t, r, b = s.left(), s.top(), s.right(), s.bottom()
        return {
            "nw": QPoint(l, t), "n": QPoint(cx, t), "ne": QPoint(r, t),
            "e": QPoint(r, cy), "se": QPoint(r, b), "s": QPoint(cx, b),
            "sw": QPoint(l, b), "w": QPoint(l, cy),
        }

    def _zone_at(self, local: QPoint) -> tuple[str, str | None]:
        if self._state == self.EDITING and self._sel:
            for name, hp in self._handles().items():
                if (hp - local).manhattanLength() <= _HANDLE_R * 2:
                    return "handle", name
            s = self._local_sel()
            if s and s.adjusted(-4, -4, 4, 4).contains(local):
                return "inside", None
        return "outside", None

    def _cursor_for(self, zone: str, handle: str | None) -> Qt.CursorShape:
        if zone == "handle":
            return {
                "nw": Qt.CursorShape.SizeFDiagCursor, "se": Qt.CursorShape.SizeFDiagCursor,
                "ne": Qt.CursorShape.SizeBDiagCursor, "sw": Qt.CursorShape.SizeBDiagCursor,
                "n": Qt.CursorShape.SizeVerCursor, "s": Qt.CursorShape.SizeVerCursor,
                "e": Qt.CursorShape.SizeHorCursor, "w": Qt.CursorShape.SizeHorCursor,
            }[handle or "nw"]
        if zone == "inside":
            return Qt.CursorShape.SizeAllCursor
        return Qt.CursorShape.CrossCursor

    # ---------- 鼠标 ----------
    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() != Qt.MouseButton.LeftButton:
            return
        gp = e.globalPosition().toPoint()
        local = self._to_local(gp)
        zone, handle = self._zone_at(local)
        if self._state == self.EDITING and zone == "handle":
            self._drag_mode, self._active_handle = "resize", handle
        elif self._state == self.EDITING and zone == "inside":
            self._drag_mode = "move"
            s = self._local_sel()
            self._move_offset = local - s.topLeft()
        else:
            # 空白处按下：开始创建新选区
            self._drag_mode = "create"
            self._drag_origin = gp
            self._sel = None
            self._state = self.IDLE
            self._toolbar.hide()
        self.update()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        gp = e.globalPosition().toPoint()
        local = self._to_local(gp)
        self._cursor = gp
        if self._drag_mode is None:
            zone, handle = self._zone_at(local)
            self.setCursor(self._cursor_for(zone, handle))
        elif self._drag_mode == "create" and self._drag_origin is not None:
            self._sel = Rect.from_corners(
                self._drag_origin.x(), self._drag_origin.y(), gp.x(), gp.y())
        elif self._drag_mode == "move" and self._sel is not None:
            s = self._local_sel()
            new_tl = local - self._move_offset
            nx = max(0, min(new_tl.x(), self._bounds.width - s.width()))
            ny = max(0, min(new_tl.y(), self._bounds.height - s.height()))
            self._sel = Rect(nx + self._bounds.x, ny + self._bounds.y,
                             s.width(), s.height())
            self._reposition_toolbar()
        elif self._drag_mode == "resize" and self._sel is not None:
            self._resize_to(gp)
            self._reposition_toolbar()
        self.update()

    def _resize_to(self, gp: QPoint) -> None:
        s = self._sel
        l, t, r, b = s.x, s.y, s.right, s.bottom
        h = self._active_handle
        if "w" in h:
            l = min(gp.x(), r - _MIN_W)
        if "e" in h:
            r = max(gp.x(), l + _MIN_W)
        if "n" in h:
            t = min(gp.y(), b - _MIN_W)
        if "s" in h:
            b = max(gp.y(), t + _MIN_W)
        self._sel = Rect.from_corners(l, t, r, b).clamp(self._bounds)

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if e.button() != Qt.MouseButton.LeftButton:
            return
        mode, self._drag_mode = self._drag_mode, None
        self._active_handle = None
        if mode == "create":
            self._drag_origin = None
            if self._sel and self._sel.is_valid:
                self._state = self.EDITING
                self._reposition_toolbar()
                self._toolbar.show()
            else:
                self._sel = None
        self.update()

    def _reposition_toolbar(self) -> None:
        s = self._local_sel()
        if not s:
            return
        self._toolbar.adjustSize()
        tw, th = self._toolbar.width(), self._toolbar.height()
        x = max(4, min(s.right() - tw, self._bounds.width - tw - 4))
        y = s.bottom() + 8
        if y + th > self._bounds.height - 4:      # 底部放不下 → 放到选区上方
            y = s.top() - th - 8
        if y < 4:                                  # 上方也放不下 → 放进选区内部
            y = s.bottom() - th - 8
        self._toolbar.move(x, y)

    # ---------- 键盘 ----------
    def keyPressEvent(self, e: QKeyEvent) -> None:
        key = e.key()
        if key == Qt.Key.Key_Escape:
            self.hide()
            self.cancelled.emit()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._state == self.EDITING and self._sel:
                self._finish("save")
            return
        nudge = {
            Qt.Key.Key_Left: (-1, 0), Qt.Key.Key_Right: (1, 0),
            Qt.Key.Key_Up: (0, -1), Qt.Key.Key_Down: (0, 1),
        }.get(key)
        if nudge and self._state == self.EDITING and self._sel:
            self._sel = self._sel.nudged(*nudge, self._bounds)
            self._reposition_toolbar()
            self.update()

    # ---------- 动作 ----------
    def _on_action(self, action: str) -> None:
        if action == "cancel":
            self.hide()
            self.cancelled.emit()
            return
        if self._sel and self._sel.is_valid:
            self._finish(action)

    def _finish(self, action: str) -> None:
        rect = self._sel
        self._toolbar.hide()
        self.hide()
        self.action_chosen.emit(rect, action)

    # ---------- 绘制 ----------
    def paintEvent(self, _e) -> None:  # noqa: N802
        if self._snapshot is None:
            return
        p = QPainter(self)
        # 遮罩：快照 + 半透明压暗
        p.drawImage(0, 0, self._snapshot)
        p.fillRect(self.rect(), QColor(10, 12, 16, 110))
        s = self._local_sel()
        if s and s.width() > 0:
            # 选区恢复清晰
            p.drawImage(s, self._snapshot, s)
            p.setPen(QPen(QColor(125, 155, 255), 2))
            p.drawRect(s)
            p.setPen(QColor(233, 237, 243))
            label_y = s.top() - 8 if s.top() > 24 else s.bottom() + 18
            p.drawText(s.left() + 4, label_y,
                       f"{self._sel.width} × {self._sel.height}")
            if self._state == self.EDITING:
                # 手柄
                p.setPen(QPen(QColor(125, 155, 255), 1))
                p.setBrush(QColor(255, 255, 255))
                for hp in self._handles().values():
                    p.drawEllipse(hp, 4, 4)
        if self._cursor:
            self._draw_magnifier(p)
        p.end()

    def _draw_magnifier(self, p: QPainter) -> None:
        local = self._to_local(self._cursor)
        n = self.MAG_CELLS
        src = QRect(local.x() - n // 2, local.y() - n // 2, n, n)
        src = src.intersected(self._snapshot.rect())
        mag_x = min(local.x() + 24, self.width() - self.MAG_SIZE - 8)
        mag_y = min(local.y() + 24, self.height() - self.MAG_SIZE - 44)
        mag_x = max(4, mag_x)
        mag_y = max(4, mag_y)
        dest = QRect(mag_x, mag_y, self.MAG_SIZE, self.MAG_SIZE)
        p.drawImage(dest, self._snapshot, src)
        p.setPen(QPen(QColor(125, 155, 255), 2))
        p.drawRect(dest)
        mid = self.MAG_SIZE // 2
        p.setPen(QPen(QColor(255, 107, 110), 1))
        p.drawLine(mag_x + mid, mag_y, mag_x + mid, mag_y + self.MAG_SIZE)
        p.drawLine(mag_x, mag_y + mid, mag_x + self.MAG_SIZE, mag_y + mid)
        center = self._snapshot.pixelColor(
            max(0, min(local.x(), self._snapshot.width() - 1)),
            max(0, min(local.y(), self._snapshot.height() - 1)))
        p.setPen(QColor(233, 237, 243))
        p.drawText(mag_x, mag_y + self.MAG_SIZE + 18,
                   f"({self._cursor.x()}, {self._cursor.y()})  "
                   f"{rgb_to_hex(center.red(), center.green(), center.blue())}")
