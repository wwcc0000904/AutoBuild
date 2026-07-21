"""编译队列管理"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Callable
from enum import Enum

from config.logging_setup import get_logger


class QueueItemStatus(str, Enum):
    PENDING = "pending"
    BUILDING = "building"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class QueueItem:
    id: str
    customer_name: str
    project_path: str
    modified_files: List[str]
    analysis_summary: str
    status: QueueItemStatus = QueueItemStatus.PENDING
    created_at: str = ""
    started_at: str = ""
    finished_at: str = ""
    build_log: str = ""
    exit_code: Optional[int] = None
    task_id: str = ""
    build_output: str = ""  # 编译产物 zip 路径
    kind: str = "build"     # "build" | "command"
    command: str = ""       # kind="command" 时要执行的命令


class BuildQueue:

    def __init__(self, persist_path: Optional[Path] = None, ssh_client=None) -> None:
        self._items: List[QueueItem] = []
        self._logger = get_logger()
        self._persist_path = persist_path or Path("config/build_queue.json")
        self._on_change_callback: Optional[Callable[[], None]] = None
        self._ssh = ssh_client
        self._load()

    def set_ssh_client(self, ssh_client) -> None:
        self._ssh = ssh_client

    def set_on_change(self, callback: Callable[[], None]) -> None:
        self._on_change_callback = callback

    def _notify_change(self) -> None:
        if self._on_change_callback:
            try:
                self._on_change_callback()
            except Exception:
                pass

    def add(self, customer_name: str, project_path: str, 
            modified_files: List[str], analysis_summary: str) -> QueueItem:
        item = QueueItem(
            id=uuid.uuid4().hex[:12],
            customer_name=customer_name,
            project_path=project_path,
            modified_files=modified_files,
            analysis_summary=analysis_summary,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        self._items.append(item)
        self._save()
        self._notify_change()
        self._logger.info("已添加到编译队列: %s (%s)", customer_name, item.id)
        return item

    def add_command(self, command: str, label: str = "") -> QueueItem:
        """添加一条命令到队列（如 ctvbuild clean）。"""
        item = QueueItem(
            id=uuid.uuid4().hex[:12],
            customer_name=label or command,
            project_path="",
            modified_files=[],
            analysis_summary="",
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            kind="command",
            command=command,
        )
        self._items.append(item)
        self._save()
        self._notify_change()
        self._logger.info("已添加命令到队列: %s (%s)", command, item.id)
        return item

    def remove(self, item_id: str) -> bool:
        for i, item in enumerate(self._items):
            if item.id == item_id:
                self._items.pop(i)
                self._save()
                self._notify_change()
                return True
        return False

    def reorder(self, item_ids: List[str]) -> None:
        """按给定的 id 顺序重排队列。"""
        by_id = {it.id: it for it in self._items}
        new_items = [by_id[i] for i in item_ids if i in by_id]
        # 补上不在列表里的（防御性）
        for it in self._items:
            if it.id not in item_ids:
                new_items.append(it)
        self._items = new_items
        self._save()
        self._notify_change()

    def move_up(self, item_id: str) -> bool:
        """把指定项上移一位。"""
        for i, item in enumerate(self._items):
            if item.id == item_id and i > 0:
                self._items[i], self._items[i - 1] = self._items[i - 1], self._items[i]
                self._save()
                self._notify_change()
                return True
        return False

    def move_down(self, item_id: str) -> bool:
        """把指定项下移一位。"""
        for i, item in enumerate(self._items):
            if item.id == item_id and i < len(self._items) - 1:
                self._items[i], self._items[i + 1] = self._items[i + 1], self._items[i]
                self._save()
                self._notify_change()
                return True
        return False

    def get_pending(self) -> List[QueueItem]:
        return [item for item in self._items if item.status == QueueItemStatus.PENDING]

    def get_all(self) -> List[QueueItem]:
        return list(self._items)

    def get_by_id(self, item_id: str) -> Optional[QueueItem]:
        for item in self._items:
            if item.id == item_id:
                return item
        return None

    def update_status(self, item_id: str, status,
                      task_id: str = "", build_log: str = "",
                      exit_code: Optional[int] = None,
                      build_output: str = "") -> bool:
        item = self.get_by_id(item_id)
        if not item:
            return False
        # 支持字符串或枚举
        if isinstance(status, str):
            status = QueueItemStatus(status)
        self._logger.info("更新队列状态: %s -> %s", item.customer_name, status.value)
        item.status = status
        if task_id:
            item.task_id = task_id
        if build_log:
            item.build_log = build_log
        if exit_code is not None:
            item.exit_code = exit_code
        if build_output:
            item.build_output = build_output
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if status == QueueItemStatus.PENDING:
            # 重试时清除之前的编译信息
            item.started_at = ""
            item.finished_at = ""
            item.task_id = ""
            item.build_log = ""
            item.exit_code = None
            item.build_output = ""
        elif status == QueueItemStatus.BUILDING and not item.started_at:
            item.started_at = now
        elif status in (QueueItemStatus.SUCCEEDED, QueueItemStatus.FAILED, QueueItemStatus.CANCELLED):
            item.finished_at = now
        self._save()
        self._notify_change()
        return True

    def check_tmux_sessions(self) -> None:
        """检查所有 building 状态的项，如果 tmux 会话不存在则标记为失败。"""
        if not self._ssh:
            return
        
        for item in self._items:
            if item.status != QueueItemStatus.BUILDING:
                continue
            
            if not item.task_id:
                continue
            
            session_name = f"ctvbuild-{item.task_id}"
            try:
                stdin, stdout, stderr = self._ssh.exec_command(
                    f"tmux has-session -t {session_name} 2>&1"
                )
                exit_code = stdout.channel.recv_exit_status()
                if exit_code != 0:
                    self._logger.warning("tmux 会话不存在，标记为失败: %s", item.customer_name)
                    self.update_status(item.id, QueueItemStatus.FAILED, 
                                      build_log=item.build_log + "\n[检测] tmux 会话已终止\n")
            except Exception as e:
                self._logger.error("检查 tmux 会话失败: %s", e)

    def clear_completed(self) -> int:
        before = len(self._items)
        self._items = [item for item in self._items 
                       if item.status in (QueueItemStatus.PENDING, QueueItemStatus.BUILDING)]
        self._save()
        self._notify_change()
        return before - len(self._items)

    def _save(self) -> None:
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            data = []
            for item in self._items:
                d = asdict(item)
                d["status"] = item.status.value
                data.append(d)
            # 原子写入：先写临时文件，再 rename，防止崩溃导致数据丢失
            tmp = self._persist_path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            tmp.replace(self._persist_path)
        except Exception as e:
            self._logger.error("保存编译队列失败: %s", e)

    def _load(self) -> None:
        try:
            if not self._persist_path.exists():
                return
            data = json.loads(self._persist_path.read_text(encoding="utf-8"))
            self._items = []
            for d in data:
                try:
                    d["status"] = QueueItemStatus(d["status"])
                    self._items.append(QueueItem(**d))
                except Exception as e:
                    self._logger.warning("跳过损坏的队列项: %s", e)
            # 重置卡在 building 状态的项
            dirty = False
            for item in self._items:
                if item.status == QueueItemStatus.BUILDING:
                    item.status = QueueItemStatus.PENDING
                    item.task_id = ""
                    dirty = True
                    self._logger.warning("重置队列项状态: %s -> pending", item.customer_name)
            if dirty:
                self._save()
            self._logger.info("已加载编译队列: %d 项", len(self._items))
        except Exception as e:
            self._logger.error("加载编译队列失败: %s", e)
            self._items = []
