from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from builder.build_service import BuildService
from config.logging_setup import get_logger
from customer_project.project_manager import CustomerProjectManager
from review.review_service import ReviewService
from ui.login_dialog import LoginDialog
from ui.main_window import MainWindow


def main() -> int:
    logger = get_logger()
    logger.info("程序启动")

    app = QApplication(sys.argv)

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

    # 打开主窗口
    window = MainWindow(
        project_manager=project_manager,
        review_service=review_service,
        build_service=build_service,
        ssh_client=ssh_client,
        base_path=base_path,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
