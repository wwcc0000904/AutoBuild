from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from builder.build_service import BuildService
from config.logging_setup import get_logger, install_exception_hooks
import ai
from customer_project.project_manager import CustomerProjectManager
from executor.build_queue import BuildQueue
from review.review_service import ReviewService
from ui.login_dialog import LoginDialog
from ui.main_window import MainWindow


def main() -> int:
    logger = get_logger()
    install_exception_hooks(logger)
    ai.init_analyzer_from_config()
    logger.info("程序启动")

    # 禁用原生对话框，强制用 Qt 渲染（否则 macOS 深色模式下 QMessageBox 黑底）
    from PySide6.QtCore import Qt
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)

    app = QApplication(sys.argv)

    # 全局弹窗样式（防止 QMessageBox 等继承系统深色主题）
    app.setStyleSheet("""
        QMessageBox {
            background: #ffffff;
        }
        QMessageBox QLabel {
            color: #1a1a1a;
            background: transparent;
        }
        QMessageBox QPushButton {
            background: #e0e0e0;
            color: #1a1a1a;
            border: none;
            border-radius: 6px;
            padding: 6px 18px;
            font-size: 13px;
            min-width: 60px;
        }
        QMessageBox QPushButton:hover {
            background: #d5d5d5;
        }
        QDialog {
            background: #ffffff;
        }
        QDialog QLabel {
            color: #1a1a1a;
            background: transparent;
        }
        QToolTip {
            background: #ffffff;
            color: #1a1a1a;
            border: 1px solid #d0d0d0;
        }
    """)

    # 先弹登录对话框
    login = LoginDialog()
    if login.exec() != LoginDialog.DialogCode.Accepted:
        logger.info("用户取消登录，退出")
        return 0

    ssh_client = login.get_ssh_client()
    base_path = login.get_base_path()
    host = login.get_host()

    logger.info("登录成功: %s, 工程目录: %s", host, base_path)

    # 全局服务
    project_manager = CustomerProjectManager(root=Path(base_path))
    review_service = ReviewService()
    build_service = BuildService(ssh_client=ssh_client)
    build_queue = BuildQueue(ssh_client=ssh_client)

    # 打开主窗口
    window = MainWindow(
        project_manager=project_manager,
        review_service=review_service,
        build_service=build_service,
        build_queue=build_queue,
        ssh_client=ssh_client,
        base_path=base_path,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
