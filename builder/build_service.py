from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from config.logging_setup import get_logger


@dataclass
class BuildJob:
    task_id: str
    status: str
    log: str


class BuildJobHandle:
    """正在运行的远程编译任务句柄。"""

    def __init__(
        self,
        task_id: str,
        command: str,
        thread: threading.Thread,
        cancel_event: threading.Event,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.task_id = task_id
        self.command = command
        self.status: str = "running"
        self.log: str = ""
        self.exit_code: Optional[int] = None
        self.error: Optional[str] = None

        self._thread = thread
        self._cancel_event = cancel_event
        self._on_log = on_log
        self._lock = threading.Lock()
        self.default_prompt_key: str | None = None

    _MAX_LOG_SIZE = 2 * 1024 * 1024  # 2MB 上限

    def append_log(self, text: str) -> None:
        if not text:
            return
        with self._lock:
            self.log += text
            # 防止日志无限增长：超过上限时截断前半部分
            if len(self.log) > self._MAX_LOG_SIZE:
                half = len(self.log) // 2
                self.log = f"... [日志截断，前 {half} 字节已省略] ..." + self.log[half:]
        if self._on_log:
            try:
                self._on_log(text)
            except Exception:  # noqa: BLE001
                pass

    def cancel(self) -> None:
        self._cancel_event.set()

    def is_running(self) -> bool:
        return self.status == "running"


class BuildService:
    """远程编译服务（通过 SSH 执行构建命令）。"""

    def __init__(self, ssh_client=None, on_log=None) -> None:
        self._ssh = ssh_client
        self._logger = get_logger()
        self._lock = threading.Lock()
        self._job_seq: int = 0
        self._current: Optional[BuildJobHandle] = None
        self._external_on_log = on_log

    def set_ssh_client(self, ssh_client) -> None:
        self._ssh = ssh_client

    def current_handle(self) -> Optional[BuildJobHandle]:
        return self._current

    def set_prompt_key(self, key: str | None) -> None:
        if self._current:
            self._current.default_prompt_key = key

    def submit(self, project_path: str, command: Optional[str] = None) -> BuildJob:
        """提交编译任务。

        若未传入 command，则使用默认 make 命令。
        返回轻量 BuildJob（兼容旧接口），同时启动后台执行。
        """
        effective_command = command or f"cd {project_path} && make -j$(nproc)"

        if self._current and self._current.is_running():
            return BuildJob(
                task_id=self._current.task_id,
                status=self._current.status,
                log=self._current.log,
            )

        with self._lock:
            self._job_seq += 1
            task_id = f"build-{self._job_seq:03d}"

        cancel_event = threading.Event()

        def _on_log(text: str) -> None:
            self._logger.info("构建日志: %s", text.rstrip("\n"))
            if self._external_on_log:
                try:
                    self._external_on_log(text)
                except Exception:
                    pass

        handle = BuildJobHandle(
            task_id=task_id,
            command=effective_command,
            thread=threading.Thread(target=self._run_build, args=(task_id, effective_command, cancel_event), daemon=True),
            cancel_event=cancel_event,
            on_log=_on_log,
        )

        self._current = handle
        handle.append_log(f"已提交编译任务: {project_path}\n命令: {effective_command}\n")
        handle._thread.start()

        return BuildJob(task_id=task_id, status=handle.status, log=handle.log)

    def status(self, task_id: str) -> BuildJob:
        if self._current and self._current.task_id == task_id:
            return BuildJob(task_id=task_id, status=self._current.status, log=self._current.log)
        return BuildJob(task_id=task_id, status="unknown", log="未找到对应编译任务")

    def cancel(self) -> bool:
        if not self._current or not self._current.is_running():
            return False
        self._current.cancel()
        self._current.append_log("\n已请求取消编译，正在等待远程进程结束...\n")
        return True

    def _exec(self, cmd: str) -> tuple[int, str, str]:
        """在远程执行一条命令，返回 (exit_code, stdout, stderr)。"""
        stdin, stdout, stderr = self._ssh.exec_command(cmd)
        try:
            exit_code = stdout.channel.recv_exit_status()
            out = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace")
            return exit_code, out, err
        finally:
            try:
                stdin.close()
                stdout.close()
                stderr.close()
            except Exception:
                pass

    def _run_build(self, task_id: str, command: str, cancel_event: threading.Event) -> None:
        if not self._ssh:
            if self._current and self._current.task_id == task_id:
                self._current.status = "failed"
                self._current.error = "未连接 SSH 客户端"
                self._current.append_log("编译失败: 未连接 SSH 客户端\n")
            return

        session_name = f"ctvbuild-{task_id}"
        log_file = f"/tmp/{session_name}.log"
        marker = f"CTV_BUILD_DONE_{task_id}"
        prompt_key = self._current.default_prompt_key if self._current else "1"

        # 包装命令：写到临时脚本文件执行，避免 shell 注入
        import shlex as _shlex
        script_file = f"/tmp/{session_name}.sh"
        script_content = (
            f"#!/bin/bash\n"
            f"({command}) 2>&1 | tee {log_file}\n"
            f"echo '{marker}:'$? >> {log_file}\n"
        )
        # 用 base64 传递脚本内容，避免转义问题
        import base64 as _b64
        encoded = _b64.b64encode(script_content.encode()).decode()
        setup_cmd = f"echo {encoded} | base64 -d > {script_file} && chmod +x {script_file}"
        tmux_cmd = (
            f"tmux kill-session -t {session_name} 2>/dev/null; "
            f"{setup_cmd}; "
            f"tmux new-session -d -s {session_name} {script_file}"
        )

        try:
            # 启动 tmux 会话
            exit_code, out, err = self._exec(tmux_cmd)
            if exit_code != 0:
                raise RuntimeError(f"启动 tmux 失败: {err.strip() or out.strip()}")

            if self._current and self._current.task_id == task_id:
                self._current.append_log(f"已在 tmux 会话 [{session_name}] 中启动编译\n")
                self._current.append_log(f"（关掉前端后可在服务器执行 tmux attach -t {session_name} 查看）\n\n")

            # 等 tmux 启动，然后用 tail -f 实时读日志
            time.sleep(0.5)

            transport = self._ssh.get_transport()
            if transport is None:
                raise RuntimeError("SSH transport 不可用")

            tail_channel = transport.open_session()
            # 不分配 PTY，避免行缓冲延迟；用 raw 模式读字节流
            tail_channel.settimeout(0.1)
            tail_channel.exec_command(f"tail -f {log_file} 2>/dev/null")

            prompt_sent = False
            while True:
                if cancel_event.is_set():
                    self._exec(f"tmux send-keys -t {session_name} C-c")
                    time.sleep(0.5)
                    self._exec(f"tmux kill-session -t {session_name} 2>/dev/null")
                    if self._current and self._current.task_id == task_id:
                        self._current.status = "failed"
                        self._current.append_log("\n编译已取消\n")
                    try:
                        tail_channel.close()
                    except Exception:  # noqa: BLE001
                        pass
                    return

                # 实时读取输出（非阻塞，settimeout=0.1s）
                try:
                    chunk = tail_channel.recv(2048).decode("utf-8", errors="replace")
                    if chunk and self._current and self._current.task_id == task_id:
                        self._current.append_log(chunk)

                        # 自动应答选单
                        if not prompt_sent and self._current.log.rstrip().endswith("请输入字母或方括号的数字选择："):
                            prompt_sent = True
                            self._exec(f"tmux send-keys -t {session_name} '{prompt_key}' Enter")
                except Exception:
                    pass  # 超时无数据，继续轮询

                # 检查是否编译完成
                if self._current and marker in self._current.log:
                    for line in self._current.log.splitlines():
                        if line.startswith(f"{marker}:"):
                            try:
                                exit_code = int(line.split(":", 1)[1])
                            except ValueError:
                                exit_code = 1
                            break
                    else:
                        exit_code = 0
                    if self._current and self._current.task_id == task_id:
                        self._current.exit_code = exit_code
                        self._current.status = "succeeded" if exit_code == 0 else "failed"
                        self._current.append_log(f"\n编译结束，退出码: {exit_code}\n")
                    break

                # tail channel 断了但编译还没结束 → tmux 会话可能异常
                if tail_channel.exit_status_ready():
                    if self._current and self._current.task_id == task_id:
                        self._current.status = "failed"
                        self._current.append_log("\ntail 通道断开，tmux 会话可能异常退出\n")
                    break

                time.sleep(0.01)

            try:
                tail_channel.close()
            except Exception:  # noqa: BLE001
                pass

            # 清理
            self._exec(f"rm -f {log_file} {script_file}; tmux kill-session -t {session_name} 2>/dev/null")

        except Exception as e:  # noqa: BLE001
            if self._current and self._current.task_id == task_id:
                self._current.status = "failed"
                self._current.error = str(e)
                self._current.append_log(f"\n编译失败: {e}\n")
            # 清理残留 tmux 会话
            try:
                self._exec(f"tmux kill-session -t {session_name} 2>/dev/null")
            except Exception:
                pass
