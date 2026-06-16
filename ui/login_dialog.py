"""登录对话框 — 独立窗口，连接远程服务器。"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Signal, QThread, QSettings, Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QGroupBox,
    QTextEdit,
    QApplication,
    QCheckBox,
)

from config.logging_setup import get_logger


class SSHConnectWorker(QThread):
    """后台线程执行 SSH 连接。"""
    success = Signal(object)
    error = Signal(str)

    def __init__(self, host: str, username: str, password: str, port: int = 22):
        super().__init__()
        self.host = host
        self.username = username
        self.password = password
        self.port = port

    def run(self):
        try:
            import paramiko
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            # 兼容旧版 SSH 服务器
            transport = None
            client.connect(
                self.host, port=self.port,
                username=self.username, password=self.password,
                timeout=10,
                allow_agent=False,
                look_for_keys=False,
            )
            self.success.emit(client)
        except Exception as e:
            self.error.emit(str(e))


class LoginDialog(QDialog):
    """登录对话框：输入服务器信息并连接。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._logger = get_logger()
        self._ssh_client = None
        self._worker = None
        self._settings = QSettings("CtvAuto", "SoftwareOutput")
        self._setup_ui()
        self._load_settings()

    _SS_INPUT = (
        "QLineEdit { background: #ffffff; color: #1a1a2e; border: 1.5px solid #d0d3e0; "
        "border-radius: 8px; padding: 10px 14px; font-size: 14px; min-height: 20px; }"
        "QLineEdit:focus { border: 2px solid #1a1a1a; }"
    )
    _SS_LABEL = "font-size: 13px; color: #3a3b5c; font-weight: 500; min-width: 65px; background: transparent;"
    _SS_GROUP = (
        "QGroupBox { background: #ffffff; border: 1px solid #e0e3ed; border-radius: 12px; "
        "padding: 20px 16px 12px 16px; margin-top: 18px; }"
        "QGroupBox::title { subcontrol-origin: margin; left: 16px; padding: 0 8px; "
        "font-size: 13px; font-weight: bold; color: #1a1a1a; }"
    )

    def _setup_ui(self) -> None:
        self.setWindowTitle("软件输出自动化 — 登录")
        self.setFixedSize(580, 410)
        self.setStyleSheet(
            "QDialog { background: #ffffff; background-image: url(/home/user/Documents/软件输出自动化/static/bg_frosted.png); background-position: center; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(12)

        # 标题
        title = QLabel("🔐 连接远程服务器")
        title.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #1a1a1a; padding: 6px 0 4px 0; background: transparent;"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 表单
        from PySide6.QtWidgets import QGridLayout
        group = QGroupBox("服务器信息")
        group.setStyleSheet(self._SS_GROUP)
        g_layout = QGridLayout(group)
        g_layout.setHorizontalSpacing(16)
        g_layout.setVerticalSpacing(14)

        def _lbl(text):
            l = QLabel(text)
            l.setStyleSheet(self._SS_LABEL)
            return l

        g_layout.addWidget(_lbl("服务器:"), 0, 0)
        self._host_input = QLineEdit()
        self._host_input.setPlaceholderText("IP 地址")
        self._host_input.setStyleSheet(self._SS_INPUT)
        g_layout.addWidget(self._host_input, 0, 1)

        g_layout.addWidget(_lbl("端口:"), 0, 2)
        self._port_input = QLineEdit("22")
        self._port_input.setMaximumWidth(80)
        self._port_input.setStyleSheet(self._SS_INPUT)
        g_layout.addWidget(self._port_input, 0, 3)

        g_layout.addWidget(_lbl("用户名:"), 1, 0)
        self._user_input = QLineEdit()
        self._user_input.setPlaceholderText("SSH 用户名")
        self._user_input.setStyleSheet(self._SS_INPUT)
        g_layout.addWidget(self._user_input, 1, 1)

        g_layout.addWidget(_lbl("密码:"), 1, 2)
        self._pwd_input = QLineEdit()
        self._pwd_input.setPlaceholderText("SSH 密码")
        self._pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._pwd_input.setStyleSheet(self._SS_INPUT)
        g_layout.addWidget(self._pwd_input, 1, 3)

        g_layout.addWidget(_lbl("工程目录:"), 2, 0)
        self._base_path_input = QLineEdit()
        self._base_path_input.setPlaceholderText("填写用户名后自动生成")
        self._base_path_input.setReadOnly(True)
        self._base_path_input.setStyleSheet(
            "QLineEdit { background: #f5f5fa; color: #333; border: 1.5px solid #d0d3e0; "
            "border-radius: 8px; padding: 10px 14px; font-size: 14px; min-height: 20px; }"
        )
        g_layout.addWidget(self._base_path_input, 2, 1, 1, 3)

        g_layout.setColumnStretch(0, 0)
        g_layout.setColumnStretch(1, 1)
        g_layout.setColumnStretch(2, 0)
        g_layout.setColumnStretch(3, 1)

        self._user_input.textChanged.connect(self._update_base_path)
        layout.addWidget(group)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._login_btn = QPushButton("🔗 连接并进入")
        self._login_btn.setFixedHeight(40)
        self._login_btn.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, "
            "stop:0 #1a1a1a, stop:1 #333333); color: white; padding: 10px 40px; "
            "font-size: 14px; font-weight: bold; border: none; border-radius: 8px; }"
            "QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, "
            "stop:0 #000000, stop:1 #1a1a1a); }"
            "QPushButton:disabled { background: #c0c3d0; }"
        )
        self._login_btn.clicked.connect(self._on_login)
        btn_layout.addWidget(self._login_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 状态
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #888; padding: 4px; background: transparent;")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_label)

        # 记住密码
        remember_row = QHBoxLayout()
        remember_row.addStretch()
        self._remember_pwd_cb = QCheckBox("记住密码")
        self._remember_pwd_cb.setChecked(True)
        self._remember_pwd_cb.setStyleSheet("background: transparent;")
        remember_row.addWidget(self._remember_pwd_cb)
        layout.addLayout(remember_row)

        layout.addStretch()
        self._pwd_input.returnPressed.connect(self._on_login)

    def _update_base_path(self, username: str) -> None:
        """根据用户名自动拼接工程目录。"""
        if username.strip():
            self._base_path_input.setText(f"/data/{username.strip()}")
        else:
            self._base_path_input.setText("")

    def _on_login(self) -> None:
        host = self._host_input.text().strip()
        username = self._user_input.text().strip()
        password = self._pwd_input.text()
        port_text = self._port_input.text().strip()

        if not host or not username or not password:
            self._status_label.setText("❌ 请填写完整信息")
            self._status_label.setStyleSheet("color: #e17055; padding: 5px;")
            return

        try:
            port = int(port_text)
        except ValueError:
            self._status_label.setText("❌ 端口必须是数字")
            self._status_label.setStyleSheet("color: #e17055; padding: 5px;")
            return

        self._login_btn.setEnabled(False)
        self._login_btn.setText("连接中…")
        self._status_label.setText(f"正在连接 {host}:{port} …")
        self._status_label.setStyleSheet("color: #888; padding: 5px;")

        self._worker = SSHConnectWorker(host, username, password, port)
        self._worker.success.connect(self._on_connected)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_connected(self, client) -> None:
        self._ssh_client = client
        self._status_label.setText("✅ 连接成功!")
        self._status_label.setStyleSheet("color: #00b894; padding: 5px;")
        self._logger.info("已连接服务器: %s", self._host_input.text())
        self._save_settings()
        self.accept()

    def _on_error(self, error_msg: str) -> None:
        self._status_label.setText(f"❌ {error_msg}")
        self._status_label.setStyleSheet("color: #e17055; padding: 5px;")
        self._login_btn.setEnabled(True)
        self._login_btn.setText("🔗 连接并进入")

    def _load_settings(self) -> None:
        """从 QSettings 恢复上次登录信息。"""
        host = self._settings.value("login/host", "")
        port = self._settings.value("login/port", "22")
        username = self._settings.value("login/username", "")
        password = self._settings.value("login/password", "")
        remember_pwd = self._settings.value("login/remember_password", True, type=bool)

        if host:
            self._host_input.setText(host)
        if port:
            self._port_input.setText(str(port))
        if username:
            self._user_input.setText(username)

        self._remember_pwd_cb.setChecked(bool(remember_pwd))
        if remember_pwd and password:
            self._pwd_input.setText(str(password))
            from PySide6.QtCore import QTimer
            QTimer.singleShot(200, self._on_login)

    def _save_settings(self) -> None:
        """保存登录信息，按选择决定是否保存密码。"""
        self._settings.setValue("login/host", self._host_input.text().strip())
        self._settings.setValue("login/port", self._port_input.text().strip())
        self._settings.setValue("login/username", self._user_input.text().strip())
        self._settings.setValue("login/remember_password", self._remember_pwd_cb.isChecked())

        if self._remember_pwd_cb.isChecked():
            self._settings.setValue("login/password", self._pwd_input.text())
        else:
            self._settings.remove("login/password")

    def get_ssh_client(self):
        return self._ssh_client

    def get_base_path(self) -> str:
        return self._base_path_input.text().strip()

    def get_host(self) -> str:
        return self._host_input.text().strip()
