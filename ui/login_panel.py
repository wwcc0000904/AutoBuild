"""登录面板 — 连接远程服务器。"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Signal, QThread
import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QGroupBox,
    QTextEdit,
    QComboBox,
)

from config.logging_setup import get_logger


class SSHConnectWorker(QThread):
    """后台线程执行 SSH 连接，避免卡 UI。"""
    success = Signal(object)  # 传回 paramiko client
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
            client.connect(
                self.host, port=self.port,
                username=self.username, password=self.password,
                timeout=10,
            )
            self.success.emit(client)
        except Exception as e:
            self.error.emit(str(e))


class LoginPanel(QWidget):
    """登录面板：输入服务器信息并连接。"""

    login_success = Signal(object, str)  # (ssh_client, base_path)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._logger = get_logger()
        self._ssh_client = None
        self._worker = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("🔐 连接远程服务器")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1976D2;")
        layout.addWidget(title)

        # 服务器信息
        group = QGroupBox("服务器信息")
        g_layout = QVBoxLayout(group)

        # 地址
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("服务器地址:"))
        self._host_input = QLineEdit()
        self._host_input.setPlaceholderText("IP 或域名，如 192.168.1.100")
        row1.addWidget(self._host_input, 1)
        row1.addWidget(QLabel("端口:"))
        self._port_input = QLineEdit("22")
        self._port_input.setMaximumWidth(60)
        row1.addWidget(self._port_input)
        g_layout.addLayout(row1)

        # 账号
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("用户名:"))
        self._user_input = QLineEdit()
        self._user_input.setPlaceholderText("SSH 用户名")
        row2.addWidget(self._user_input, 1)
        g_layout.addLayout(row2)

        # 密码
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("密  码:"))
        self._pwd_input = QLineEdit()
        self._pwd_input.setPlaceholderText("SSH 密码")
        self._pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        row3.addWidget(self._pwd_input, 1)
        g_layout.addLayout(row3)

        # 工程根目录
        row4 = QHBoxLayout()
        row4.addWidget(QLabel("工程根目录:"))
        self._base_path_input = QLineEdit("")
        self._base_path_input.setPlaceholderText("服务器上客户工程的根目录")
        row4.addWidget(self._base_path_input, 1)
        g_layout.addLayout(row4)

        layout.addWidget(group)

        # 连接按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._login_btn = QPushButton("  连接")
        self._login_btn.setIcon(qta.icon("fa5s.plug", color="#1a1a1a"))
        self._login_btn.setStyleSheet(
            "QPushButton { background-color: #1976D2; color: white; padding: 10px 30px; "
            "font-size: 14px; border-radius: 6px; }"
            "QPushButton:hover { background-color: #1565C0; }"
        )
        self._login_btn.clicked.connect(self._on_login)
        btn_layout.addWidget(self._login_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 状态/日志
        layout.addWidget(QLabel("连接日志:"))
        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setMaximumHeight(200)
        layout.addWidget(self._log_edit)

        layout.addStretch()

    def _on_login(self) -> None:
        host = self._host_input.text().strip()
        username = self._user_input.text().strip()
        password = self._pwd_input.text()
        port_text = self._port_input.text().strip()

        if not host or not username or not password:
            self._log_edit.append("❌ 请填写完整的服务器信息")
            return

        try:
            port = int(port_text)
        except ValueError:
            self._log_edit.append("❌ 端口必须是数字")
            return

        self._login_btn.setEnabled(False)
        self._login_btn.setText("连接中…")
        self._log_edit.append(f"正在连接 {host}:{port} …")

        self._worker = SSHConnectWorker(host, username, password, port)
        self._worker.success.connect(self._on_connected)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_connected(self, client) -> None:
        self._ssh_client = client
        self._log_edit.append("✅ 连接成功!")

        # 获取服务器信息
        try:
            stdin, stdout, stderr = client.exec_command('hostname', timeout=5)
            hostname = stdout.read().decode().strip()
            self._log_edit.append(f"   主机名: {hostname}")
        except Exception as e:
            self._logger.debug("获取主机名失败: %s", e)

        base_path = self._base_path_input.text().strip()
        if base_path:
            try:
                from shlex import quote
                stdin, stdout, stderr = client.exec_command(f'ls -d {quote(base_path)}/*/', timeout=5)
                dirs = [d.strip().rstrip('/') for d in stdout.read().decode().strip().split('\n') if d.strip()]
                if dirs:
                    self._log_edit.append(f"   工程目录 ({len(dirs)} 个):")
                    for d in dirs[:10]:
                        self._log_edit.append(f"     - {Path(d).name}")
                    if len(dirs) > 10:
                        self._log_edit.append(f"     ... 还有 {len(dirs)-10} 个")
                else:
                    self._log_edit.append(f"   ⚠ {base_path} 下没有子目录")
            except Exception as e:
                self._log_edit.append(f"   ⚠ 无法列出目录: {e}")

        self._login_btn.setEnabled(True)
        self._login_btn.setText("  连接")

        # 发射成功信号
        self.login_success.emit(client, base_path)

    def _on_error(self, error_msg: str) -> None:
        self._log_edit.append(f"❌ 连接失败: {error_msg}")
        self._login_btn.setEnabled(True)
        self._login_btn.setText("  连接")

    def get_ssh_client(self):
        return self._ssh_client

    def get_base_path(self) -> str:
        return self._base_path_input.text().strip()
