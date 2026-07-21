"""代码提交面板 — 客户目录上传到 Gerrit"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTextEdit, QLineEdit, QGroupBox, QCheckBox,
    QScrollArea, QFrame,
)


class GerritPanel(QWidget):
    """客户目录 Gerrit 提交页面。"""

    # 信号：请求同步 / 请求提交
    sync_requested = Signal(str)       # project_path
    submit_requested = Signal(str, str, str)  # project_path, commit_msg, branch

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # ── 项目选择卡片 ──
        proj_card = self._card("项目选择")
        proj_lay = proj_card.layout()

        proj_row = QHBoxLayout()
        proj_row.setSpacing(10)
        proj_lbl = QLabel("项目目录:")
        proj_lbl.setStyleSheet("font-size: 12px; color: #666;")
        proj_row.addWidget(proj_lbl)

        self._project_combo = QComboBox()
        self._project_combo.setMinimumWidth(300)
        self._project_combo.setStyleSheet(
            "QComboBox { background: #fff; border: 1px solid #d5d8e0; border-radius: 6px;"
            " padding: 6px 12px; font-size: 12px; }"
        )
        proj_row.addWidget(self._project_combo, 1)

        self._sync_btn = QPushButton("  同步代码 (repo sync)")
        self._sync_btn.setStyleSheet(
            "QPushButton { background: #4a90d9; color: white; border: none;"
            " padding: 8px 16px; font-size: 12px; border-radius: 6px; }"
            "QPushButton:hover { background: #3a7bc8; }"
        )
        proj_row.addWidget(self._sync_btn)
        proj_lay.addLayout(proj_row)
        layout.addWidget(proj_card)

        # ── 改动文件卡片 ──
        files_card = self._card("改动文件")
        files_lay = files_card.layout()

        files_header = QHBoxLayout()
        self._select_all_cb = QCheckBox("全选")
        self._select_all_cb.setChecked(True)
        self._select_all_cb.setStyleSheet("font-size: 12px; color: #666;")
        files_header.addWidget(self._select_all_cb)
        files_header.addStretch()
        self._files_count_lbl = QLabel("暂无改动")
        self._files_count_lbl.setStyleSheet("font-size: 12px; color: #999;")
        files_header.addWidget(self._files_count_lbl)
        files_lay.addLayout(files_header)

        # 文件列表区域
        self._files_container = QWidget()
        self._files_container.setStyleSheet("background: transparent;")
        self._files_layout = QVBoxLayout(self._files_container)
        self._files_layout.setContentsMargins(0, 0, 0, 0)
        self._files_layout.setSpacing(2)

        files_scroll = QScrollArea()
        files_scroll.setWidgetResizable(True)
        files_scroll.setWidget(self._files_container)
        files_scroll.setFixedHeight(180)
        files_scroll.setStyleSheet("QScrollArea { border: 1px solid #e0e0e0; border-radius: 6px; background: #fafafa; }")
        files_lay.addWidget(files_scroll)

        # 空状态提示
        self._files_empty_lbl = QLabel("请先同步代码或选择项目目录")
        self._files_empty_lbl.setStyleSheet("font-size: 12px; color: #bbb; padding: 20px;")
        self._files_empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._files_layout.addWidget(self._files_empty_lbl)

        layout.addWidget(files_card)

        # ── 提交信息卡片 ──
        commit_card = self._card("提交信息")
        commit_lay = commit_card.layout()

        # 目标分支
        branch_row = QHBoxLayout()
        branch_row.setSpacing(10)
        branch_lbl = QLabel("目标分支:")
        branch_lbl.setStyleSheet("font-size: 12px; color: #666;")
        branch_row.addWidget(branch_lbl)
        self._branch_combo = QComboBox()
        self._branch_combo.setEditable(True)
        self._branch_combo.addItems(["master", "main"])
        self._branch_combo.setStyleSheet(
            "QComboBox { background: #fff; border: 1px solid #d5d8e0; border-radius: 6px;"
            " padding: 6px 12px; font-size: 12px; }"
        )
        branch_row.addWidget(self._branch_combo, 1)
        commit_lay.addLayout(branch_row)

        # Commit message
        msg_lbl = QLabel("Commit Message:")
        msg_lbl.setStyleSheet("font-size: 12px; color: #666; margin-top: 6px;")
        commit_lay.addWidget(msg_lbl)
        self._commit_msg = QTextEdit()
        self._commit_msg.setPlaceholderText("请输入提交说明…")
        self._commit_msg.setFixedHeight(100)
        self._commit_msg.setStyleSheet(
            "QTextEdit { background: #fff; border: 1px solid #d5d8e0; border-radius: 6px;"
            " padding: 8px; font-size: 12px; }"
        )
        commit_lay.addWidget(self._commit_msg)
        layout.addWidget(commit_card)

        # ── 操作按钮 ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._submit_btn = QPushButton("  提交并推送 (commit + push)")
        self._submit_btn.setStyleSheet(
            "QPushButton { background: #4CAF50; color: white; border: none;"
            " padding: 10px 24px; font-size: 13px; font-weight: bold; border-radius: 8px; }"
            "QPushButton:hover { background: #43a047; }"
            "QPushButton:disabled { background: #ccc; }"
        )
        btn_row.addWidget(self._submit_btn)
        layout.addLayout(btn_row)

        # ── 执行日志卡片 ──
        log_card = self._card("执行日志")
        log_lay = log_card.layout()

        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setFixedHeight(200)
        self._log_view.setStyleSheet(
            "QTextEdit { background: #1e1e1e; color: #d4d4d4; border: 1px solid #333;"
            " border-radius: 6px; padding: 8px; font-family: 'Consolas', 'Menlo', monospace;"
            " font-size: 12px; }"
        )
        self._log_view.setPlainText("等待操作…")
        log_lay.addWidget(self._log_view)
        layout.addWidget(log_card)

        layout.addStretch()

    def _card(self, title: str) -> QGroupBox:
        """创建统一样式的卡片。"""
        card = QGroupBox(title)
        card.setStyleSheet(
            "QGroupBox { background-color: #ffffff; border: 1px solid #e5e5e5;"
            " border-radius: 12px; padding: 16px 12px 8px 12px; margin-top: 16px;"
            " font-size: 13px; font-weight: bold; color: #1a1a1a; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 16px; padding: 0 8px; }"
        )
        lay = QVBoxLayout(card)
        lay.setSpacing(10)
        return card

    # ── 公共接口 ──

    def set_projects(self, projects: list[str]) -> None:
        """设置项目目录列表。"""
        self._project_combo.clear()
        self._project_combo.addItems(projects)

    def set_file_list(self, files: list[dict]) -> None:
        """设置改动文件列表。files: [{"path": "...", "status": "M/A/D"}]"""
        # 清空旧列表
        while self._files_layout.count():
            child = self._files_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._file_checkboxes: list[QCheckBox] = []

        if not files:
            self._files_empty_lbl = QLabel("无改动文件")
            self._files_empty_lbl.setStyleSheet("font-size: 12px; color: #bbb; padding: 20px;")
            self._files_empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._files_layout.addWidget(self._files_empty_lbl)
            self._files_count_lbl.setText("暂无改动")
            return

        status_colors = {"M": "#e67e22", "A": "#27ae60", "D": "#e74c3c", "??": "#999"}
        for f in files:
            row = QHBoxLayout()
            cb = QCheckBox(f["path"])
            cb.setChecked(True)
            cb.setStyleSheet("font-size: 12px;")
            row.addWidget(cb, 1)
            self._file_checkboxes.append(cb)

            status = f.get("status", "M")
            tag = QLabel(status)
            tag.setStyleSheet(
                f"color: {status_colors.get(status, '#999')}; font-size: 11px;"
                " font-weight: bold; padding: 2px 6px;")
            row.addWidget(tag)

            container = QWidget()
            container.setStyleSheet("background: transparent;")
            container.setLayout(row)
            self._files_layout.addWidget(container)

        self._files_count_lbl.setText(f"共 {len(files)} 个文件")
        self._select_all_cb.stateChanged.connect(self._toggle_all_files)

    def _toggle_all_files(self, state: int) -> None:
        """全选/取消全选。"""
        if not hasattr(self, '_file_checkboxes'):
            return
        for cb in self._file_checkboxes:
            cb.setChecked(state == Qt.CheckState.Checked.value)

    def get_selected_files(self) -> list[str]:
        """获取用户勾选的文件列表。"""
        if not hasattr(self, '_file_checkboxes'):
            return []
        return [cb.text() for cb in self._file_checkboxes if cb.isChecked()]

    def get_commit_message(self) -> str:
        return self._commit_msg.toPlainText().strip()

    def get_branch(self) -> str:
        return self._branch_combo.currentText().strip()

    def get_project(self) -> str:
        return self._project_combo.currentText().strip()

    def append_log(self, text: str) -> None:
        """追加日志。"""
        cursor = self._log_view.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._log_view.setTextCursor(cursor)
        self._log_view.insertPlainText(text)
        sb = self._log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def clear_log(self) -> None:
        self._log_view.clear()

    def set_submitting(self, submitting: bool) -> None:
        """设置提交中状态。"""
        self._submit_btn.setEnabled(not submitting)
        self._submit_btn.setText("  提交中…" if submitting else "  提交并推送 (commit + push)")
