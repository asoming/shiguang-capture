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

from PySide6.QtCore import QPoint, QPointF, QRect, Qt, Signal
from PySide6.QtGui import (
    QColor, QGuiApplication, QImage, QKeyEvent, QMouseEvent, QPainter, QPen,
)
from PySide6.QtWidgets import QHBoxLayout, QToolButton, QWidget

from ..colors import rgb_to_hex
from ..geometry import Rect
from .grabber import virtual_desktop_rect, capture_frames, compose_region
from ..ui.theme import STYLE
from ..ui.tool_icons import tool_icon
from ..ui.selection_canvas import SelectionCanvas
from ..geometry import union

_HANDLE_R = 8           # 手柄命中半径（屏幕像素）
_MIN_W = 8              # 编辑态最小选区
_TOOLBAR_H = 38

_TOOLS = [('view','调整选区'), ('rect','矩形'), ('arrow','箭头'), ('pen','画笔'),
          ('text','文字'), ('redact','实色遮盖'), ('undo','撤销 Ctrl+Z'), ('redo','重做 Ctrl+Y')]
_ACTIONS = [('pin','贴图'), ('ocr','文字识别'), ('code','代码识别'), ('table','表格识别'),
            ('scroll','长截图'), ('save','保存 Ctrl+S'), ('copy','复制 Enter / Ctrl+C'), ('cancel','取消 Esc')]


class _Toolbar(QWidget):
    action_clicked = Signal(str)

    def __init__(self, parent, selection_only=False):
        super().__init__(parent)
        self.setFixedHeight(44)
        self.setStyleSheet(STYLE + "QWidget{background:#FFF;} QToolButton{border:0;border-radius:4px;padding:4px;} QToolButton:hover{background:#E1ECEF;} QToolButton:checked{background:#CFE7E9;}")
        row = QHBoxLayout(self)
        row.setContentsMargins(6,4,6,4)
        row.setSpacing(1)
        self.buttons = {}
        entries = [('copy','确认选区 Enter'), ('cancel','取消 Esc')] if selection_only else _TOOLS+_ACTIONS
        for action, label in entries:
            button = QToolButton()
            button.setIcon(tool_icon(action))
            button.setAccessibleName(label)
            button.setToolTip(label)
            button.setFixedSize(32,34)
            button.setCheckable(action in {'view','rect','arrow','pen','text','redact'})
            button.setChecked(action == 'view')
            button.clicked.connect(lambda checked=False, value=action: self.action_clicked.emit(value))
            row.addWidget(button)
            self.buttons[action] = button
            if action in {'redo','scroll'}:
                line = QWidget()
                line.setFixedWidth(1)
                line.setStyleSheet('background:#D5E1E9;margin:6px 3px;')
                row.addWidget(line)

    def select_tool(self, tool):
        for key, button in self.buttons.items():
            if button.isCheckable():
                button.setChecked(key == tool)


class RegionSelector(QWidget):
    action_chosen = Signal(object, str)   # geometry.Rect, action
    cancelled = Signal()

    IDLE, EDITING = 0, 1
    MAG_SIZE = 120
    MAG_CELLS = 15

    def __init__(self, frames=None, selection_only=False) -> None:
        super().__init__()
        self._frames = capture_frames() if frames is None else frames
        bounds = union([frame.bounds for frame in self._frames])
        self._bounds = bounds
        # Cocoa's utility panels cannot enter fullscreen. Its popup level also
        # sits above the menu bar and Dock without switching desktop Spaces.
        window_type = (Qt.WindowType.Popup if QGuiApplication.platformName() == 'cocoa'
                       else Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | window_type)
        # A managed normal window is constrained to the work area by some WMs,
        # leaving the dock exposed and scaling our full-desktop snapshot.
        # X11 fullscreen spans one monitor; bypass the WM for a multi-screen
        # selection so the virtual-desktop geometry stays intact.
        if QGuiApplication.platformName() == 'xcb' and len(QGuiApplication.screens()) > 1:
            self.setWindowFlag(Qt.WindowType.X11BypassWindowManagerHint)
        self.setGeometry(bounds.x, bounds.y, bounds.width, bounds.height)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

        self._state = self.IDLE
        self._sel: Rect | None = None
        self._drag_origin: QPoint | None = None
        self._drag_mode: str | None = None       # create / move / resize
        self._active_handle: str | None = None
        self._move_offset: QPoint | None = None
        self._cursor: QPoint | None = None
        self._snapshot: QImage | None = compose_region(self._frames, bounds)     # 全屏缓存快照

        self._toolbar = _Toolbar(self, selection_only)
        self._toolbar.action_clicked.connect(self._on_action)
        self._toolbar.hide()
        self._canvas = SelectionCanvas(self)
        self._canvas.hide()
        self._canvas_rect = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.CrossCursor)

    # ---------- 生命周期 ----------
    def show(self):
        screens = QGuiApplication.screens()
        bounds = QRect(self._bounds.x, self._bounds.y, self._bounds.width, self._bounds.height)
        if QGuiApplication.platformName() == 'cocoa':
            super().show()
            self.setGeometry(bounds)
        elif len(screens) == 1 and screens[0].geometry() == bounds:
            self.showFullScreen()
        else:
            super().show()
        self.raise_()
        self.activateWindow()
        if QGuiApplication.platformName() == 'cocoa':
            # Cocoa can still stack system menu/status windows above a Qt
            # popup. Set the native level after Qt has applied its own flags.
            import objc
            from AppKit import NSScreenSaverWindowLevel
            view = objc.objc_object(c_void_p=int(self.winId()))
            window = view.window()
            window.setLevel_(NSScreenSaverWindowLevel)
            window.orderFrontRegardless()

    def showEvent(self, e) -> None:  # noqa: N802
        super().showEvent(e)
        if self._snapshot is None:
            self._snapshot = self._grab_full_snapshot()

    def _grab_full_snapshot(self) -> QImage:
        return compose_region(self._frames, self._bounds)

    def selected_image(self, rect: Rect) -> QImage:
        if self._canvas_rect == rect and not self._canvas.image.isNull():
            self._canvas.commit_text()
            return self._canvas.rendered_image()
        return compose_region(self._frames, rect)

    def closeEvent(self, event):
        self.cancelled.emit()
        super().closeEvent(event)

    def reset_selection(self):
        self._canvas.commit_text()
        self._canvas.hide()
        self._canvas_rect = None
        self._canvas.set_image(QImage())
        self._sel = None
        self._state = self.IDLE
        self._toolbar.hide()
        self._toolbar.select_tool('view')
        self._canvas.set_tool('view')
        self.update()

    def _sync_canvas(self, moved=False):
        if not self._sel or not self._sel.is_valid:
            return
        marks = list(self._canvas.marks)
        undone, history = list(self._canvas.undone), list(self._canvas.history)
        old_rect = self._canvas_rect
        old_density = self._canvas.image.width()/old_rect.width if old_rect else 1
        image = compose_region(self._frames, self._sel)
        density = image.width()/self._sel.width
        self._canvas.set_image(image)
        if old_rect:
            dx = 0 if moved else old_rect.x-self._sel.x
            dy = 0 if moved else old_rect.y-self._sel.y
            versions = marks + [mark for state in history+undone for mark in state]
            for mark in versions:
                mark.points = [QPointF((point.x()/old_density+dx)*density,
                                      (point.y()/old_density+dy)*density) for point in mark.points]
            self._canvas.marks, self._canvas.undone, self._canvas.history = marks, undone, history
        self._canvas_rect = self._sel
        self._canvas.setGeometry(self._local_sel())
        self._canvas.show()
        self._toolbar.raise_()

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
        if e.button() == Qt.MouseButton.RightButton:
            if self._sel:
                self.reset_selection()
            else:
                self._on_action('cancel')
            return
        if e.button() != Qt.MouseButton.LeftButton:
            return
        if self._state == self.EDITING and self._canvas.isVisible():
            point = self._canvas.mapFrom(self, e.position().toPoint())
            if self._canvas.edit_text_at(QPointF(point)):
                return
        self._canvas.commit_text()
        self._canvas.hide()
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
            self._canvas_rect = None
            self._canvas.set_image(QImage())
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
        if mode is not None and self._sel and self._state == self.EDITING:
            self._sync_canvas(moved=mode == 'move')
        self.update()

    def mouseDoubleClickEvent(self, event):
        if self._sel and event.button() == Qt.MouseButton.LeftButton:
            self._on_action('copy')

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
        self._toolbar.move(x, max(4, y))
        self._toolbar.raise_()

    # ---------- 键盘 ----------
    def keyPressEvent(self, e: QKeyEvent) -> None:
        key = e.key()
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            actions = {Qt.Key.Key_C:'copy', Qt.Key.Key_S:'save', Qt.Key.Key_Z:'undo', Qt.Key.Key_Y:'redo'}
            action = actions.get(key)
            if action:
                if action == 'undo' and e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    action = 'redo'
                self._on_action(action)
                return
        if key == Qt.Key.Key_Escape:
            self.hide()
            self.cancelled.emit()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._state == self.EDITING and self._sel:
                self._finish("copy")
            return
        nudge = {
            Qt.Key.Key_Left: (-1, 0), Qt.Key.Key_Right: (1, 0),
            Qt.Key.Key_Up: (0, -1), Qt.Key.Key_Down: (0, 1),
        }.get(key)
        if nudge and self._state == self.EDITING and self._sel:
            self._sel = self._sel.nudged(*nudge, self._bounds)
            self._sync_canvas(moved=True)
            self._reposition_toolbar()
            self.update()

    # ---------- 动作 ----------
    def _on_action(self, action: str) -> None:
        if action in {'view','rect','arrow','pen','text','redact'}:
            self._canvas.set_tool(action)
            self._toolbar.select_tool(action)
            self.setFocus()
            return
        if action in {'undo','redo'}:
            getattr(self._canvas, action)()
            return
        if action == "cancel":
            self.hide()
            self.cancelled.emit()
            return
        if self._sel and self._sel.is_valid:
            self._finish(action)

    def _finish(self, action: str) -> None:
        self._canvas.commit_text()
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
        p.drawImage(self.rect(), self._snapshot)
        p.fillRect(self.rect(), QColor(10, 12, 16, 110))
        s = self._local_sel()
        if s and s.width() > 0:
            # 选区恢复清晰
            p.save()
            p.setClipRect(s)
            p.drawImage(self.rect(), self._snapshot)
            p.restore()
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
        if self._cursor and self._state == self.IDLE:
            self._draw_magnifier(p)
        p.end()

    def _draw_magnifier(self, p: QPainter) -> None:
        local = self._to_local(self._cursor)
        n = self.MAG_CELLS
        density = self._snapshot.width() / self.width()
        pixel = QPoint(round(local.x()*density), round(local.y()*density))
        src = QRect(pixel.x() - n // 2, pixel.y() - n // 2, n, n)
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
            max(0, min(pixel.x(), self._snapshot.width() - 1)),
            max(0, min(pixel.y(), self._snapshot.height() - 1)))
        p.setPen(QColor(233, 237, 243))
        p.drawText(mag_x, mag_y + self.MAG_SIZE + 18,
                   f"({self._cursor.x()}, {self._cursor.y()})  "
                   f"{rgb_to_hex(center.red(), center.green(), center.blue())}")
