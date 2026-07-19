"""编译队列面板 - 可拖拽排序的卡片列表"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QAbstractItemView, QMessageBox,
)
from PySide6.QtGui import QDrag, QPainter, QColor
from PySide6.QtCore import QPoint

from config.logging_setup import get_logger
from executor.build_queue import BuildQueue, QueueItem, QueueItemStatus


STATUS_STYLE = {
    QueueItemStatus.PENDING:   ("待编译", "#0984e3", "#e8f4fd"),
    QueueItemStatus.BUILDING:  ("编译中", "#e17055", "#fdeee8"),
    QueueItemStatus.SUCCEEDED: ("成功",   "#00b894", "#e6f7f1"),
    QueueItemStatus.FAILED:    ("失败",   "#d63031", "#fde8e8"),
    QueueItemStatus.CANCELLED: ("已取消", "#888888", "#eeeeee"),
}


class QueueCard(QFrame):
    """单个队列项卡片。"""
    build_requested = Signal(str)
    build_all_requested = Signal()
    retry_requested = Signal(str)
    remove_requested = Signal(str)

    def __init__(self, item: QueueItem, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._item = item
        self._build_ui()

    def _build_ui(self) -> None:
        item = self._item
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(
            "QueueCard { background: #ffffff; border: 1px solid #e5e5e5;"
            " border-radius: 8px; }"
        )
        outer = QHBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(12)

        # 拖拽手柄（提示可拖）
        grip = QLabel("⋮⋮")
        grip.setStyleSheet("color:#ccc; font-size:16px;")
        grip.setToolTip("拖动调整编译顺序")
        outer.addWidget(grip, 0)

        # 左侧：客户名 + 状态徽章 + 时间
        left = QVBoxLayout()
        left.setSpacing(4)
        name_lbl = QLabel(item.customer_name)
        name_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #1a1a1a;")
        left.addWidget(name_lbl)

        status_text, status_fg, status_bg = STATUS_STYLE.get(
            item.status, ("未知", "#333", "#eee"))
        badge = QLabel(status_text)
        badge.setFixedHeight(20)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background:{status_bg}; color:{status_fg}; border-radius:10px;"
            f" padding:0 10px; font-size:11px; font-weight:bold;"
        )
        if item.created_at:
            time_lbl = QLabel(item.created_at)
            time_lbl.setStyleSheet("color:#aaa; font-size:11px;")
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(badge)
            row.addWidget(time_lbl)
            row.addStretch()
            left.addLayout(row)
        else:
            left.addWidget(badge)
        left.addStretch()
        outer.addLayout(left, 0)

        # 中间：工程路径 + 修改文件 + 需求摘要
        mid = QVBoxLayout()
        mid.setSpacing(3)
        path_lbl = QLabel(str(item.project_path))
        path_lbl.setStyleSheet("color:#555; font-size:12px;")
        path_lbl.setWordWrap(False)
        path_lbl.setTextFormat(Qt.TextFormat.PlainText)
        mid.addWidget(path_lbl)

        if item.modified_files:
            names = ", ".join(Path(f).name for f in item.modified_files)
            files_lbl = QLabel(f"修改文件: {names}")
            files_lbl.setStyleSheet("color:#888; font-size:11px;")
            files_lbl.setWordWrap(True)
            mid.addWidget(files_lbl)

        if item.analysis_summary:
            summary = QLabel(item.analysis_summary)
            summary.setStyleSheet("color:#999; font-size:11px;")
            summary.setWordWrap(True)
            mid.addWidget(summary)
        mid.addStretch()
        outer.addLayout(mid, 1)

        # 右侧：操作按钮
        right = QVBoxLayout()
        right.setSpacing(6)
        qid = item.id

        if item.status == QueueItemStatus.PENDING:
            start_btn = QPushButton("开始编译")
            start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            start_btn.setStyleSheet(
                "QPushButton { background:#4CAF50; color:white; border:none;"
                " padding:6px 16px; font-size:12px; border-radius:6px; min-width:90px; }"
                "QPushButton:hover { background:#43a047; }"
            )
            start_btn.clicked.connect(lambda: self.build_requested.emit(qid))
            right.addWidget(start_btn)
        elif item.status in (QueueItemStatus.CANCELLED, QueueItemStatus.FAILED):
            retry_btn = QPushButton("重新编译")
            retry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            retry_btn.setStyleSheet(
                "QPushButton { background:#0984e3; color:white; border:none;"
                " padding:6px 16px; font-size:12px; border-radius:6px; min-width:90px; }"
                "QPushButton:hover { background:#0773c5; }"
            )
            retry_btn.clicked.connect(lambda: self.retry_requested.emit(qid))
            right.addWidget(retry_btn)

        if item.status != QueueItemStatus.BUILDING:
            remove_btn = QPushButton("移除")
            remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            remove_btn.setStyleSheet(
                "QPushButton { background:transparent; color:#e17055; border:1px solid #e17055;"
                " padding:6px 16px; font-size:12px; border-radius:6px; min-width:90px; }"
                "QPushButton:hover { background:#e17055; color:white; }"
            )
            remove_btn.clicked.connect(lambda: self.remove_requested.emit(qid))
            right.addWidget(remove_btn)
        right.addStretch()
        outer.addLayout(right, 0)


class DraggableQueueList(QListWidget):
    """支持内部拖拽排序的列表，拖拽完成发出 order_changed。"""
    order_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet(
            "QListWidget { background: transparent; border: none; }"
            "QListWidget::item { padding: 0; margin: 0; border: none; }"
            "QListWidget::item:selected { background: rgba(74,144,217,0.08); }"
        )
        self.setUniformItemSizes(False)
        self.setDropIndicatorShown(True)
        self._drop_depth = 0
        self._drop_indicator_pos = None

    def startDrag(self, supportedActions):
        """用卡片截图当拖拽预览，而不是空的方框。"""
        item = self.currentItem()
        if not item:
            return
        card = self.itemWidget(item)
        drag = QDrag(self)
        drag.setMimeData(self.model().mimeData([self.currentIndex()]))
        if card:
            pix = card.grab()
            # 预览半透明，突出"正在拖动"
            pix.setDevicePixelRatio(pix.devicePixelRatio())
            drag.setPixmap(pix)
            drag.setHotSpot(QPoint(40, 30))
        drag.exec(Qt.DropAction.MoveAction)

    def dragMoveEvent(self, event):
        super().dragMoveEvent(event)
        # 记录 drop indicator 位置用于自定义绘制
        self._drop_indicator_pos = self._calc_drop_pos(event.position().toPoint())
        self.viewport().update()

    def dragLeaveEvent(self, event):
        super().dragLeaveEvent(event)
        self._drop_indicator_pos = None
        self.viewport().update()

    def dropEvent(self, event):
        self._drop_depth += 1
        super().dropEvent(event)
        self._drop_depth -= 1
        self._drop_indicator_pos = None
        self.viewport().update()
        if self._drop_depth == 0:
            self.order_changed.emit()

    def _calc_drop_pos(self, pos):
        """返回 drop indicator 应绘制的 y 坐标。"""
        row = self.row(self.itemAt(pos))
        if row < 0:
            # 鼠标在最后一项下方，插入到末尾
            last = self.count() - 1
            if last >= 0:
                rect = self.visualItemRect(self.item(last))
                return rect.bottom() + 1
            return 0
        rect = self.visualItemRect(self.item(row))
        if pos.y() < rect.center().y():
            return rect.top() - 1
        return rect.bottom() + 1

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._drop_indicator_pos is None:
            return
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 粗的彩色插入指示线 + 圆点
        y = self._drop_indicator_pos
        painter.setPen(QColor("#4a90d9"))
        painter.setBrush(QColor("#4a90d9"))
        painter.drawLine(8, y, self.viewport().width() - 8, y)
        painter.drawEllipse(QPoint(8, y), 4, 4)


class QueuePanel(QWidget):
    build_requested = Signal(str)
    build_all_requested = Signal()
    retry_requested = Signal(str)

    def __init__(self, build_queue: BuildQueue, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._build_queue = build_queue
        self._logger = get_logger()
        self._suppress_order = False
        self._build_ui()
        self._build_queue.set_on_change(lambda: QTimer.singleShot(0, self._refresh))
        self._refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        title_row = QHBoxLayout()
        title = QLabel("编译队列")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a1a1a;")
        title_row.addWidget(title)
        title_row.addStretch()
        self._stats_label = QLabel()
        self._stats_label.setStyleSheet("color: #666; font-size: 13px;")
        title_row.addWidget(self._stats_label)
        layout.addLayout(title_row)

        hint = QLabel("提示：拖动卡片左侧手柄 ⋮⋮ 可调整编译顺序")
        hint.setStyleSheet("color:#999; font-size:11px;")
        layout.addWidget(hint)

        self._list = DraggableQueueList()
        self._list.order_changed.connect(self._on_order_changed)
        layout.addWidget(self._list, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._build_all_btn = QPushButton("全部开始编译")
        self._build_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build_all_btn.setStyleSheet(
            "QPushButton { background:#333333; color:white; border:none;"
            " padding:8px 20px; font-size:13px; border-radius:6px; }"
            "QPushButton:hover { background:#444444; }"
            "QPushButton:disabled { background:#bbb; }"
        )
        self._build_all_btn.clicked.connect(self._on_build_all)
        btn_row.addWidget(self._build_all_btn)
        self._clear_btn = QPushButton("清除已完成")
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.setStyleSheet(
            "QPushButton { background:transparent; color:#555; border:1px solid #ccc;"
            " padding:8px 20px; font-size:13px; border-radius:6px; }"
            "QPushButton:hover { background:#f0f0f0; }"
        )
        self._clear_btn.clicked.connect(self._on_clear_completed)
        btn_row.addWidget(self._clear_btn)
        layout.addLayout(btn_row)

    def _refresh(self) -> None:
        self._suppress_order = True
        self._list.clear()
        items = self._build_queue.get_all()
        for item in items:
            lw_item = QListWidgetItem()
            lw_item.setData(Qt.ItemDataRole.UserRole, item.id)
            card = QueueCard(item)
            lw_item.setSizeHint(card.sizeHint())
            self._list.addItem(lw_item)
            self._list.setItemWidget(lw_item, card)
            card.build_requested.connect(self.build_requested.emit)
            card.retry_requested.connect(self._on_retry)
            card.remove_requested.connect(self._on_remove)
        self._suppress_order = False

        pending = len([i for i in items if i.status == QueueItemStatus.PENDING])
        self._stats_label.setText(f"共 {len(items)} 项 · 待编译 {pending}")
        self._build_all_btn.setEnabled(pending > 0)

    def _on_order_changed(self) -> None:
        if self._suppress_order:
            return
        ids = []
        for i in range(self._list.count()):
            lw_item = self._list.item(i)
            if lw_item:
                ids.append(lw_item.data(Qt.ItemDataRole.UserRole))
        if ids:
            self._build_queue.reorder(ids)
            self._logger.info("队列顺序已更新: %s", ids)

    def _styled_question(self, title, text):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setStyleSheet(
            "QMessageBox { background: #ffffff; }"
            "QMessageBox QLabel { color: #1a1a1a; background: transparent; font-size: 13px; }"
            "QMessageBox QPushButton { background: #e0e0e0; color: #1a1a1a; border: none; "
            "border-radius: 6px; padding: 6px 18px; font-size: 13px; min-width: 60px; }"
            "QMessageBox QPushButton:hover { background: #d5d5d5; }"
        )
        return box.exec()

    def _on_build_all(self) -> None:
        pending = self._build_queue.get_pending()
        if not pending:
            return
        reply = self._styled_question("确认", f"确定依次编译 {len(pending)} 项？")
        if reply == QMessageBox.StandardButton.Yes:
            self.build_all_requested.emit()

    def _on_retry(self, queue_id: str) -> None:
        item = self._build_queue.get_by_id(queue_id)
        if item:
            self._build_queue.update_status(queue_id, QueueItemStatus.PENDING)
            self._logger.info("已重置为待编译: %s", item.customer_name)

    def _on_remove(self, queue_id: str) -> None:
        item = self._build_queue.get_by_id(queue_id)
        if item:
            reply = self._styled_question("确认移除", f"确定移除 {item.customer_name}？")
            if reply == QMessageBox.StandardButton.Yes:
                self._build_queue.remove(queue_id)

    def _on_clear_completed(self) -> None:
        count = self._build_queue.clear_completed()
        if count > 0:
            self._logger.info("已清除 %d 个已完成的编译项", count)
