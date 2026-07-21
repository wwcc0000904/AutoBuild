from __future__ import annotations

import shlex
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
        return self.get_status() == "running"

    def set_status(self, status: str) -> None:
        """线程安全地设置编译状态。"""
        with self._lock:
            self.status = status

    def get_status(self) -> str:
        """线程安全地读取编译状态。"""
        with self._lock:
            return self.status

    def get_log(self) -> str:
        """线程安全地读取完整日志。"""
        with self._lock:
            return self.log

    def set_exit_code(self, exit_code: Optional[int]) -> None:
        """线程安全地设置退出码。"""
        with self._lock:
            self.exit_code = exit_code

    def get_exit_code(self) -> Optional[int]:
        """线程安全地读取退出码。"""
        with self._lock:
            return self.exit_code

    def set_error(self, error: Optional[str]) -> None:
        """线程安全地设置错误信息。"""
        with self._lock:
            self.error = error

    def has_log_marker(self, marker: str) -> bool:
        """线程安全地检查日志中是否包含标记。"""
        with self._lock:
            return marker in self.log

    def parse_exit_code_from_log(self, marker: str) -> Optional[int]:
        """线程安全地从日志中解析退出码标记行（取最后一次出现的 marker）。"""
        with self._lock:
            result = None
            for line in self.log.splitlines():
                if line.startswith(f"{marker}:"):
                    try:
                        result = int(line.split(":", 1)[1])
                    except ValueError:
                        result = 1
            return result


class BuildService:
    """远程编译服务（通过 SSH 执行构建命令）。"""

    def __init__(self, ssh_client=None, on_log=None, on_finished=None) -> None:
        self._ssh = ssh_client
        self._logger = get_logger()
        self._lock = threading.Lock()
        self._job_seq: int = 0
        self._current: Optional[BuildJobHandle] = None
        self._external_on_log = on_log
        self._external_on_finished = on_finished

    def set_ssh_client(self, ssh_client) -> None:
        self._ssh = ssh_client

    def current_handle(self) -> Optional[BuildJobHandle]:
        return self._current

    def set_prompt_key(self, key: str | None) -> None:
        if self._current:
            self._current.default_prompt_key = key

    def set_callbacks(self, on_log=None, on_finished=None) -> None:
        """设置日志和完成回调（公开接口，替代直接修改私有属性）。"""
        if on_log is not None:
            self._external_on_log = on_log
        if on_finished is not None:
            self._external_on_finished = on_finished

    def _fire_finished(self, task_id: str, status: str, exit_code: int) -> None:
        """触发编译完成回调。"""
        if self._external_on_finished:
            try:
                self._external_on_finished(status, exit_code)
            except Exception:
                pass

    def submit(self, project_path: str, command: Optional[str] = None) -> BuildJob:
        """提交编译任务。

        若未传入 command，则使用默认 make 命令。
        返回轻量 BuildJob（兼容旧接口），同时启动后台执行。
        """
        effective_command = command or f"cd {shlex.quote(project_path)} && make -j$(nproc)"

        if self._current and self._current.is_running():
            return BuildJob(
                task_id=self._current.task_id,
                status=self._current.get_status(),
                log=self._current.get_log(),
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

        return BuildJob(task_id=task_id, status=handle.get_status(), log=handle.get_log())

    def status(self, task_id: str) -> BuildJob:
        if self._current and self._current.task_id == task_id:
            return BuildJob(task_id=task_id, status=self._current.get_status(), log=self._current.get_log())
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
                self._current.set_status("failed")
                self._current.set_error("未连接 SSH 客户端")
                self._current.append_log("编译失败: 未连接 SSH 客户端\n")
                self._fire_finished(task_id, "failed", 1)
            return

        try:
            self._run_build_inner(task_id, command, cancel_event)
        except Exception as e:
            self._logger.error("编译异常: %s", e, exc_info=True)
            if self._current and self._current.task_id == task_id:
                self._current.set_status("failed")
                self._current.append_log(f"\n编译异常: {e}\n")
            self._fire_finished(task_id, "failed", 1)

    def _run_build_inner(self, task_id: str, command: str, cancel_event: threading.Event) -> None:
        if not self._ssh:
            if self._current and self._current.task_id == task_id:
                self._current.set_status("failed")
                self._current.set_error("未连接 SSH 客户端")
                self._current.append_log("编译失败: 未连接 SSH 客户端\n")
            return

        # 从命令中提取订单名（最后一个参数），用于精确应答选单
        import shlex as _shlex2
        # 同一套代码用同一个 tmux 会话：会话名用项目目录名，如 tmux_352_AN12_MP3
        _code_path = ''
        try:
            _parts = _shlex2.split(command)
            if 'cd' in _parts:
                _cd_idx = _parts.index('cd')
                if _cd_idx + 1 < len(_parts):
                    _code_path = _parts[_cd_idx + 1]
        except Exception:
            pass
        # /home/user/352_AN12_MP3/code -> 352_AN12_MP3
        _proj_name = 'ctvbuild'
        if _code_path:
            _path_parts = [p for p in _code_path.replace('/', ' ').split() if p]
            if len(_path_parts) >= 2:
                _proj_name = _path_parts[-2]  # code 的上一层就是项目名
            elif _path_parts:
                _proj_name = _path_parts[-1]
        session_name = f"tmux_{_proj_name}"
        log_file = f"/tmp/ctvbuild-{task_id}.log"
        marker = f"CTV_BUILD_DONE_{task_id}"
        # 包装命令：写到临时脚本文件执行，避免 shell 注入
        script_file = f"/tmp/ctvbuild-{task_id}.sh"
        # 编译成功后自动执行 ctvbuild usb 打包，最后 exec bash 保持 tmux 会话
        cd_cmd = f"cd {shlex.quote(_code_path)}" if _code_path else ""
        script_content = (
            f"#!/bin/bash\n"
            f"({command}) 2>&1 | tee {log_file}\n"
            f"_BUILD_EXIT=${{PIPESTATUS[0]}}\n"
            f"echo '{marker}:'$_BUILD_EXIT >> {log_file}\n"
            f"if [ $_BUILD_EXIT -eq 0 ]; then\n"
            f"    echo '=== 编译成功，开始打包 (EXACT_MATCH=1 ctvbuild usb) ===' | tee -a {log_file}\n"
            f"    ({cd_cmd} && EXACT_MATCH=1 ctvbuild usb) 2>&1 | tee -a {log_file}\n"
            f"    _USB_EXIT=${{PIPESTATUS[0]}}\n"
            f"    echo '{marker}:'$_USB_EXIT >> {log_file}\n"
            f"else\n"
            f"    echo '=== 编译失败，跳过打包 ===' | tee -a {log_file}\n"
            f"fi\n"
            f"echo '{marker}_ALL_DONE' >> {log_file}\n"
            f"exec bash\n"
        )
        # 用 base64 传递脚本内容，避免转义问题
        import base64 as _b64
        encoded = _b64.b64encode(script_content.encode()).decode()
        setup_cmd = f"echo {shlex.quote(encoded)} | base64 -d > {shlex.quote(script_file)} && chmod +x {shlex.quote(script_file)}"
        # 检查 tmux 会话是否已存在（同一套代码不允许同时多个 tmux 编译）
        check_exit, _, _ = self._exec(f"tmux has-session -t {shlex.quote(session_name)} 2>&1")
        if check_exit == 0:
            # 会话存在，检查是否还有编译进程在跑
            ps_exit, ps_out, _ = self._exec(
                f"tmux capture-pane -t {shlex.quote(session_name)} -p 2>/dev/null | tail -5"
            )
            # 检查 tmux 会话内是否还有活跃的子进程（make/ctvbuild 等）
            pane_pid_exit, pane_pid_out, _ = self._exec(
                f"tmux list-panes -t {shlex.quote(session_name)} -F '#{{pane_pid}}' 2>/dev/null"
            )
            is_busy = False
            if pane_pid_exit == 0 and pane_pid_out.strip():
                # 检查该 pane 的子进程中是否有 make/ctvbuild 在跑
                for pid_line in pane_pid_out.strip().splitlines():
                    pid = pid_line.strip()
                    if pid:
                        child_exit, child_out, _ = self._exec(
                            f"pgrep -P {shlex.quote(pid)} 2>/dev/null"
                        )
                        if child_exit == 0 and child_out.strip():
                            is_busy = True
                            break
            if is_busy:
                # 检查是否有实际的编译进程（make/ctvbuild），而不只是 shell
                has_build = False
                for pid_line in pane_pid_out.strip().splitlines():
                    pid = pid_line.strip()
                    if pid:
                        _, build_check, _ = self._exec(
                            f"ps -o comm= -P {shlex.quote(pid)} 2>/dev/null"
                        )
                        if any(p in build_check for p in ("make", "ctvbuild", "gcc", "g++")):
                            has_build = True
                            break
                if has_build:
                    raise RuntimeError(f"tmux 会话 [{session_name}] 正在编译中，请等待完成或先取消")
                else:
                    # 旧会话空闲，杀掉重建
                    self._logger.info("清理旧 tmux 会话: %s", session_name)
                    self._exec(f"tmux kill-session -t {shlex.quote(session_name)} 2>/dev/null")
                    is_busy = False
            # 会话空闲，复用已有会话，在里面执行新编译
            self._exec(setup_cmd)  # 先写脚本文件
            self._exec(f"tmux send-keys -t {shlex.quote(session_name)} {shlex.quote(script_file)} Enter")
            tmux_cmd = None  # 标记已复用
        else:
            tmux_cmd = (
                f"{setup_cmd}; "
                f"tmux new-session -d -s {shlex.quote(session_name)} {shlex.quote(script_file)}"
            )

        try:
            # 启动 tmux 会话（新建或复用）
            if tmux_cmd:
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
            tail_channel.exec_command(f"tail -f {shlex.quote(log_file)} 2>/dev/null")

            last_prompt_log_len = 0  # 上次应答选单时的日志长度，避免重复应答
            check_counter = 0
            while True:
                if cancel_event.is_set():
                    self._exec(f"tmux send-keys -t {shlex.quote(session_name)} C-c")
                    time.sleep(0.5)
                    # 不杀 tmux 会话，保留给用户 attach 查看
                    if self._current and self._current.task_id == task_id:
                        self._current.set_status("failed")
                        self._current.append_log("\n编译已取消\n")
                    try:
                        tail_channel.close()
                    except Exception:  # noqa: BLE001
                        pass
                    self._fire_finished(task_id, "failed", 1)
                    self._current = None
                    return

                # 实时读取输出（非阻塞，settimeout=0.1s）
                try:
                    chunk = tail_channel.recv(2048).decode("utf-8", errors="replace")
                    if chunk and self._current and self._current.task_id == task_id:
                        self._current.append_log(chunk)

                        # 自动应答选单（支持多次，编译和打包各可能弹一次）
                        # usb 走 -z（上次记录），选单提示 z/回车=默认上次，直接发回车确认
                        current_log = self._current.get_log()
                        if current_log.rstrip().endswith("请输入字母或方括号的数字选择：") and len(current_log) > last_prompt_log_len:
                            last_prompt_log_len = len(current_log)
                            self._current.append_log("[自动应答选单: 回车（使用上次记录）]\n")
                            self._exec(f"tmux send-keys -t {shlex.quote(session_name)} Enter")
                except Exception:
                    pass  # 超时无数据，继续轮询

               # 检查是否编译+打包全部完成（等待 ALL_DONE 标记）
                if self._current and self._current.has_log_marker(f"{marker}_ALL_DONE"):
                    parsed = self._current.parse_exit_code_from_log(marker)
                    exit_code = parsed if parsed is not None else 0
                    if self._current and self._current.task_id == task_id:
                        self._current.set_exit_code(exit_code)
                        self._current.set_status("succeeded" if exit_code == 0 else "failed")
                        self._current.append_log(f"\n编译+打包结束，退出码: {exit_code}\n")
                    break

                # tail channel 断了但编译还没结束 → tmux 会话可能异常
                if tail_channel.exit_status_ready():
                    if self._current and self._current.task_id == task_id:
                        self._current.set_status("failed")
                        self._current.append_log("\ntail 通道断开，tmux 会话可能异常退出\n")
                    break

                # 定期检查 tmux 会话是否还存在（每2秒检查一次）
                check_counter += 1
                if check_counter % 200 == 0:  # 约2秒检查一次
                    try:
                        exit_code, out, _ = self._exec(f"tmux has-session -t {shlex.quote(session_name)} 2>&1")
                        if exit_code != 0:
                            if self._current and self._current.task_id == task_id:
                                self._current.set_status("failed")
                                self._current.append_log("\ntmux 会话已终止（可能被手动停止）\n")
                            try:
                                tail_channel.close()
                            except Exception:
                                pass
                            self._fire_finished(task_id, "failed", 1)
                            self._current = None
                            return
                    except Exception:
                        pass

                time.sleep(0.01)

            try:
                tail_channel.close()
            except Exception:  # noqa: BLE001
                pass

            # 只清理日志文件，不杀 tmux 会话，不删脚本（复用时需要）
            self._exec(f"rm -f {shlex.quote(log_file)}")
            self._fire_finished(
                task_id,
                self._current.get_status() if self._current else "failed",
                self._current.get_exit_code() if self._current else 1,
            )
            self._current = None

        except Exception as e:  # noqa: BLE001
            if self._current and self._current.task_id == task_id:
                self._current.set_status("failed")
                self._current.set_error(str(e))
                self._current.append_log(f"\n编译失败: {e}\n")
            self._fire_finished(task_id, "failed", 1)
            self._current = None
            # 异常时也不杀 tmux 会话，保留现场
