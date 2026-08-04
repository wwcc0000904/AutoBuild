"""AI 分析器设置对话框 - 配置 API 密钥、模型、开关。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QPushButton, QHBoxLayout, QLabel, QCheckBox, QMessageBox,
)

from config.ai_config import AIConfig, load_ai_config, save_ai_config
from config.logging_setup import get_logger


class AISettingsDialog(QDialog):
    """AI 设置对话框：开关 / provider / 模型 / base_url / 密钥。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._logger = get_logger()
        self.setWindowTitle("AI 分析设置")
        self.setMinimumWidth(460)
        self.setStyleSheet("QDialog { background: #ffffff; }")
        self._setup_ui()
        self._load()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # 说明
        hint = QLabel(
            "启用后，需求分析由 AI 完成（需联网）。\n"
            "未启用或未填密钥时，使用内置规则匹配（Dummy）。"
        )
        hint.setStyleSheet("color: #6b7280; font-size: 12px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)

        self._enabled_chk = QCheckBox("启用 AI 分析")
        form.addRow(self._enabled_chk)

        self._provider_combo = QComboBox()
        self._provider_combo.addItems(["openai", "deepseek", "qwen", "custom"])
        self._provider_combo.currentTextChanged.connect(self._on_provider_changed)
        form.addRow("服务商:", self._provider_combo)

        self._model_input = QLineEdit()
        self._model_input.setPlaceholderText("gpt-4o")
        form.addRow("模型:", self._model_input)

        self._base_url_input = QLineEdit()
        self._base_url_input.setPlaceholderText("留空=官方地址；兼容服务填 https://...")
        form.addRow("Base URL:", self._base_url_input)

        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText("API Key（存入系统钥匙串）")
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("API Key:", self._key_input)

        self._show_key_chk = QCheckBox("显示")
        self._show_key_chk.toggled.connect(
            lambda c: self._key_input.setEchoMode(
                QLineEdit.EchoMode.Normal if c else QLineEdit.EchoMode.Password
            )
        )
        form.addRow("", self._show_key_chk)

        layout.addLayout(form)

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._test_btn = QPushButton("测试连接")
        self._test_btn.setStyleSheet(self._btn_style("#4b5563"))
        self._test_btn.clicked.connect(self._test_connection)
        btn_row.addWidget(self._test_btn)

        self._save_btn = QPushButton("保存")
        self._save_btn.setStyleSheet(self._btn_style("#1a73e8"))
        self._save_btn.clicked.connect(self._save)
        btn_row.addWidget(self._save_btn)

        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.setStyleSheet(self._btn_style("#6b7280"))
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)

        layout.addLayout(btn_row)

    def _btn_style(self, color: str) -> str:
        return (
            f"QPushButton {{ background: {color}; color: white; border: none; "
            f"border-radius: 8px; padding: 8px 20px; font-size: 13px; }}"
            f"QPushButton:hover {{ background: {color}dd; }}"
        )

    def _on_provider_changed(self, provider: str) -> None:
        presets = {
            "openai": ("gpt-4o", ""),
            "deepseek": ("deepseek-chat", "https://api.deepseek.com"),
            "qwen": ("qwen-plus", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            "custom": ("", ""),
        }
        model, url = presets.get(provider, ("", ""))
        if model and not self._model_input.text():
            self._model_input.setText(model)
        if url and not self._base_url_input.text():
            self._base_url_input.setText(url)
        # openai 预设清空自定义 base_url 提示
        if provider == "openai" and not self._base_url_input.text():
            self._base_url_input.setText("")

    def _load(self) -> None:
        cfg = load_ai_config()
        self._enabled_chk.setChecked(cfg.enabled)
        idx = self._provider_combo.findText(cfg.provider)
        if idx >= 0:
            self._provider_combo.setCurrentIndex(idx)
        self._model_input.setText(cfg.model)
        self._base_url_input.setText(cfg.base_url)
        self._key_input.setText(cfg.api_key)

    def _collect(self) -> AIConfig:
        return AIConfig(
            enabled=self._enabled_chk.isChecked(),
            provider=self._provider_combo.currentText(),
            api_key=self._key_input.text().strip(),
            base_url=self._base_url_input.text().strip(),
            model=self._model_input.text().strip() or "gpt-4o",
            timeout=60,
        )

    def _save(self) -> None:
        cfg = self._collect()
        if cfg.enabled and not cfg.api_key:
            QMessageBox.warning(self, "提示", "启用 AI 需要填写 API Key。")
            return
        save_ai_config(cfg)
        # 立即切换分析器
        import ai
        ai.init_analyzer_from_config()
        self._logger.info("AI 配置已保存，分析器已切换: enabled=%s", cfg.enabled)
        self.accept()

    def _test_connection(self) -> None:
        cfg = self._collect()
        if not cfg.api_key:
            QMessageBox.warning(self, "提示", "请先填写 API Key。")
            return
        from pathlib import Path
        from ai.openai_analyzer import OpenAIAnalyzer
        try:
            analyzer = OpenAIAnalyzer(
                skill_path=Path("ai/skills/requirement_analysis.md"),
                api_key=cfg.api_key,
                base_url=cfg.base_url or None,
                model=cfg.model,
                timeout=20,
            )
            result = analyzer.analyze("测试：打开杜比，关闭 miracast")
            QMessageBox.information(
                self, "连接成功",
                f"AI 返回正常。\n客户: {result.customer}\n修改项: {len(result.modifications)} 条",
            )
        except Exception as e:
            QMessageBox.critical(self, "连接失败", str(e))
