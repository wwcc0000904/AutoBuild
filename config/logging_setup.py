from __future__ import annotations

import logging
import sys
import threading
import traceback
from pathlib import Path


def setup_logger(name: str = __name__, log_dir: str = "logs") -> logging.Logger:
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # 文件日志 — 保留详细记录
    file_handler = logging.FileHandler(
        log_path / "app.log",
        encoding="utf-8",
        mode="a",
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)

    # 控制台日志 — 同样格式，只显示 INFO 及以上
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# 全局默认日志器
_logger: logging.Logger | None = None


def get_logger() -> logging.Logger:
    global _logger
    if _logger is None:
        _logger = setup_logger("app")
    return _logger

def install_exception_hooks(logger: logging.Logger | None = None) -> None:
    """安装全局异常钩子，把未捕获异常写进文件日志。

    覆盖两类异常：
    - 主线程未捕获异常（sys.excepthook）
    - 后台线程未捕获异常（threading.excepthook，Python 3.8+）

    没有这些钩子时，异常只会打到 stderr，logs/app.log 里看不到，
    PySide6 事件循环甚至可能静默吞掉。
    """
    log = logger or get_logger()

    def _sys_hook(exc_type, exc_value, exc_tb):
        # KeyboardInterrupt 正常退出，不打日志
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        log.error("未捕获异常（主线程）", exc_info=(exc_type, exc_value, exc_tb))
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    def _thread_hook(args):
        # 后台线程崩溃：args.exc_type / args.exc_value / args.exc_traceback
        if issubclass(args.exc_type, KeyboardInterrupt):
            return
        log.error(
            "未捕获异常（线程 %s）",
            args.thread.name if args.thread else "?",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = _sys_hook
    threading.excepthook = _thread_hook
