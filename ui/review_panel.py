from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Signal
import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QGroupBox,
)

import ai
from config.logging_setup import get_logger
from review.review_service import ReviewDecision


class ReviewPanel(QWidget):
    """人工审核面板：展示自动分析结果，提供通过/拒绝操作。"""

    review_completed = Signal(ReviewDecision)

    def __init__(self, analysis: ai.AnalysisResult, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._analysis = analysis
        self._logger = get_logger()
        self._build_ui()
        self._populate(analysis)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 标题
        title = QLabel("📋 人工审核 — 请确认以下分析结果")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1a1a1a; background: transparent;")
        layout.addWidget(title)

        # ======== 基本信息 ========
        info_group = QGroupBox("基本信息")
        info_layout = QVBoxLayout(info_group)
        self._info_labels: dict[str, QLabel] = {}
        for key, label in [
            ("project", "项目"),
            ("platform", "版型"),
            ("region", "区域"),
            ("customer", "客户"),
            ("customer_dir", "客户目录"),
            ("target_dir", "目标目录"),
            ("operation", "操作模式"),
        ]:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{label}："))
            val = QLabel()
            val.setStyleSheet("font-weight: bold;")
            val.setWordWrap(True)
            row.addWidget(val, 1)
            info_layout.addLayout(row)
            self._info_labels[key] = val
        layout.addWidget(info_group)

        # ======== 修改项列表 ========
        mods_group = QGroupBox("待执行的修改项")
        mods_layout = QVBoxLayout(mods_group)
        self._mods_text = QTextEdit()
        self._mods_text.setReadOnly(True)
        self._mods_text.setMaximumHeight(250)
        self._mods_text.setStyleSheet(
            "font-family: 'Menlo', 'Courier New', monospace; font-size: 12px; "
            "background: rgba(255,255,255,0.6); color: #2d3047; border: 1px solid rgba(200,205,220,0.4); border-radius: 8px; padding: 6px;"
        )
        mods_layout.addWidget(self._mods_text)
        layout.addWidget(mods_group)

        # ======== 校验警告 ========
        self._warnings_group = QGroupBox("⚠ 校验警告")
        self._warnings_group.setVisible(False)
        warnings_layout = QVBoxLayout(self._warnings_group)
        self._warnings_text = QLabel()
        self._warnings_text.setWordWrap(True)
        self._warnings_text.setStyleSheet("color: #e17055; background: transparent;")
        warnings_layout.addWidget(self._warnings_text)
        layout.addWidget(self._warnings_group)

        # ======== 备注 ========
        notes_group = QGroupBox("备注")
        notes_layout = QVBoxLayout(notes_group)
        self._notes_text = QTextEdit()
        self._notes_text.setReadOnly(True)
        self._notes_text.setMaximumHeight(100)
        notes_layout.addWidget(self._notes_text)
        layout.addWidget(notes_group)

        # ======== 拒绝理由输入 ========
        reject_group = QGroupBox("拒绝理由（拒绝时必填）")
        reject_layout = QVBoxLayout(reject_group)
        self._reject_reason = QTextEdit()
        self._reject_reason.setPlaceholderText("说明拒绝原因，以便修改需求后重新提交…")
        self._reject_reason.setMaximumHeight(60)
        reject_layout.addWidget(self._reject_reason)
        layout.addWidget(reject_group)

        # ======== 按钮区 ========
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._reject_btn = QPushButton("  拒绝")
        self._reject_btn.setIcon(qta.icon("fa5s.times-circle", color="#e17055"))
        self._reject_btn.setStyleSheet(
            "QPushButton { background-color: transparent; color: #e17055; padding: 8px 24px; "
            "font-size: 13px; border-radius: 6px; border: 1px solid rgba(225,112,85,0.5); }"
            "QPushButton:hover { background: rgba(225,112,85,0.1); }"
        )
        self._reject_btn.clicked.connect(self._on_reject)
        btn_layout.addWidget(self._reject_btn)

        self._approve_btn = QPushButton("  通过，开始执行")
        self._approve_btn.setIcon(qta.icon("fa5s.check-circle", color="#1a1a1a"))
        self._approve_btn.setStyleSheet(
            "QPushButton { background: #1a1a1a; color: white; padding: 8px 24px; "
            "font-size: 13px; border-radius: 6px; font-weight: bold; border: none; }"
            "QPushButton:hover { background: #000000; }"
        )
        self._approve_btn.clicked.connect(self._on_approve)
        btn_layout.addWidget(self._approve_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

    def _describe_mod(self, mod: dict) -> str:
        """把一条修改项翻译成人话，说明改了什么文件、什么地方。"""
        t = mod.get("type", "?")

        if t == "build_config":
            file = mod.get("file", "?")
            key = mod.get("key", "?")
            val = mod.get("value", "?")
            mode = mod.get("mode", "value")
            if mode == "value_part":
                return f"修改 {file} → {key} 中的数值部分为 {val}"
            return f"修改 {file} → {key} = {val}"

        if t == "preinstall":
            app = mod.get("app", "ESharePlus")
            if mod.get("enabled"):
                return f"修改 build_ctv_app.txt → {app} = Y（设为预装）"
            return f"修改 build_ctv_app.txt → {app} = n（取消预装）"

        if t == "whitelist":
            pkg = mod.get("package", "?")
            action = "添加" if mod.get("action") == "add" else "移除"
            return f"修改 etc/whiteList.conf → {action} {pkg}"

        if t == "whitelist_remove":
            return f"修改 etc/whiteList.conf → 移除 {mod.get('package', '?')}"

        if t == "prop":
            return f"修改 {mod.get('file')} → {mod.get('key')} = {mod.get('value')}"

        if t == "ctv_data":
            v = mod.get('value', '?')
            if mod.get('default_value') and mod.get('after_name'):
                return f"检查 ctv_data.xml → {mod.get('name')}：如不存在则添加到 customized 区域（默认值 {v}）"
            return f"修改 ctv_data.xml → {mod.get('name')} = {v}"

        if t == "country_list_first":
            return f"修改 ctv_data.xml → CountryList 默认国家 {mod.get('country_code')} 移到首位并去重"

        if t == "language_first":
            return f"修改 CtvLanguage.ini → 默认语言 {mod.get('target')} 移到第一行"

        if t == "color_temp":
            values = mod.get("values", [])
            if len(values) == 6:
                return f"修改 configs/db.ini → 所有 nature 白平衡前6值 = {','.join(values)}"
            elif len(values) == 3:
                return f"修改 configs/db.ini → 所有 nature 白平衡前3值 = {','.join(values)}"
            return f"修改 configs/db.ini → 白平衡(R/G/B Gain/Offset) = {','.join(values)}"

        if t == "nla":
            param = mod.get('param', '?')
            val = mod.get('value', '?')
            pos = mod.get('position', 2)
            pos_names = {0: "最小值", 1: "1/4值", 2: "中间值", 3: "3/4值", 4: "最大值"}
            pos_name = pos_names.get(pos, f"第{pos+1}个")
            return f"修改 configs/db.ini → NlaInfo_{param} 的{pos_name}为 {val}"

        if t == "sat_gain":
            vals = mod.get('values', [])
            return f"修改 configs/db.ini → 所有 SatGain 行前7值 = {','.join(vals)}"

        if t == "gain":
            name = mod.get('name', '?')
            vals = mod.get('values', [])
            return f"修改 configs/db.ini → 所有 {name} 行前7值 = {','.join(vals)}"

        if t == "db_ini":
            return f"修改 {mod.get('file')} → {mod.get('key')} = {mod.get('value')}"

        if t == "ctv_setting":
            action = "隐藏" if mod.get("enable") == "hide" else "显示"
            return f"修改 configs/ctvsetting.xml → {action} {mod.get('name')}"

        # 兜底
        return f"{mod}"

    def _populate(self, analysis: ai.AnalysisResult) -> None:
        self._info_labels["project"].setText(analysis.project)
        self._info_labels["platform"].setText(analysis.platform)
        self._info_labels["region"].setText(getattr(analysis, "region", ""))
        self._info_labels["customer"].setText(analysis.customer)
        self._info_labels["customer_dir"].setText(analysis.target_customer_dir)
        self._info_labels["target_dir"].setText(getattr(analysis, "target_dir", "") or "（直接修改源目录）")
        self._info_labels["operation"].setText(
            "复制并修改" if analysis.operation == "copy_and_modify" else "直接修改"
        )

        # 修改项列表 — 按文件分组
        file_groups: dict[str, list[str]] = {}
        for mod in analysis.modifications:
            desc = self._describe_mod(mod)
            # 提取文件路径作为分组 key
            file_key = mod.get("file", mod.get("type", "其他"))
            if file_key not in file_groups:
                file_groups[file_key] = []
            file_groups[file_key].append(desc)

        lines = []
        idx = 1
        for file_key, descs in file_groups.items():
            for desc in descs:
                lines.append(f"  {idx}. {desc}")
                idx += 1

        self._mods_text.setPlainText("\n".join(lines) if lines else "  无修改项")

        # 校验警告
        if analysis.notes and "警告" in analysis.notes:
            import re
            m = re.search(r"警告: (.+)", analysis.notes)
            if m:
                self._warnings_text.setText(m.group(1))
                self._warnings_group.setVisible(True)

        # 备注
        self._notes_text.setPlainText(analysis.notes if analysis.notes else "无")

    def _on_approve(self) -> None:
        self._logger.info("审核通过")
        self.review_completed.emit(ReviewDecision(approved=True, reason="人工审核通过"))

    def _on_reject(self) -> None:
        reason = self._reject_reason.toPlainText().strip()
        if not reason:
            self._reject_reason.setPlaceholderText("⚠ 拒绝时必须填写理由！")
            self._reject_reason.setStyleSheet("border: 1px solid #E53935;")
            return
        self._logger.info("审核拒绝: %s", reason)
        self.review_completed.emit(ReviewDecision(approved=False, reason=reason))
