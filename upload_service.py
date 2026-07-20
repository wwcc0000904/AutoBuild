"""WebDAV 上传服务 — 通过 SSH 在远程服务器上执行 curl 上传文件到网盘。"""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from typing import Optional

from config.logging_setup import get_logger


@dataclass
class UploadResult:
    success: bool
    filename: str = ""
    link: str = ""
    size: str = ""
    error: str = ""


class UploadService:
    """通过 SSH 在远程服务器上用 curl 上传文件到 WebDAV 网盘。"""

    DEFAULT_URL = "https://pan.example.com:6443"

    def __init__(self, ssh_client=None) -> None:
        self._ssh = ssh_client
        self._logger = get_logger()

    def set_ssh_client(self, ssh_client) -> None:
        self._ssh = ssh_client

    def _exec(self, cmd: str, timeout: int = 300) -> tuple[int, str, str]:
        """执行远程命令。"""
        stdin, stdout, stderr = self._ssh.exec_command(cmd, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        return exit_code, out, err

    def create_folder(self, remote_dir: str, user: str, password: str,
                      base_url: str = DEFAULT_URL) -> None:
        """逐级创建 WebDAV 文件夹。"""
        parts = [p for p in remote_dir.split("/") if p]
        current = ""
        for part in parts:
            current += f"/{part}"
            url = f"{base_url}/remote.php/webdav{current}"
            cmd = (
                f"curl -k -s -o /dev/null -w '%{{http_code}}' "
                f"-u {shlex.quote(user + ':' + password)} "
                f"-X MKCOL {shlex.quote(url)}"
            )
            self._exec(cmd, timeout=15)

    def upload_file(self, local_path: str, remote_dir: str,
                    user: str, password: str,
                    base_url: str = DEFAULT_URL) -> UploadResult:
        """上传单个文件到 WebDAV 并生成分享链接。

        Args:
            local_path: 远程服务器上的文件路径
            remote_dir: 网盘目标文件夹（如 software/FAE）
            user: WebDAV 用户名
            password: WebDAV 密码
            base_url: WebDAV 服务器地址

        Returns:
            UploadResult 包含成功/失败状态、文件名、分享链接等
        """
        if not self._ssh:
            return UploadResult(success=False, error="未连接 SSH")

        filename = local_path.rsplit("/", 1)[-1] if "/" in local_path else local_path

        # 检查文件是否存在
        exit_code, _, _ = self._exec(f"test -f {shlex.quote(local_path)} && echo YES || echo NO", timeout=10)
        if "YES" not in str(exit_code):
            # 用 stdout 检查
            _, out, _ = self._exec(f"test -f {shlex.quote(local_path)} && echo YES || echo NO", timeout=10)
            if "YES" not in out:
                return UploadResult(success=False, filename=filename, error=f"文件不存在: {local_path}")

        # 获取文件大小
        _, size_out, _ = self._exec(
            f"stat -c%s {shlex.quote(local_path)} 2>/dev/null || stat -f%z {shlex.quote(local_path)} 2>/dev/null",
            timeout=10
        )
        file_size = size_out.strip()
        try:
            size_mb = int(file_size) / 1024 / 1024
            size_display = f"{size_mb:.1f}MB"
        except ValueError:
            size_display = "未知"

        # 创建远程文件夹
        self._logger.info("创建网盘文件夹: %s", remote_dir)
        self.create_folder(remote_dir, user, password, base_url)

        # 上传文件
        remote_path = f"{remote_dir}/{filename}" if remote_dir else filename
        upload_url = f"{base_url}/remote.php/webdav/{remote_path}"
        self._logger.info("上传文件: %s → %s (%s)", filename, remote_path, size_display)

        upload_cmd = (
            f"curl -k -s "
            f"-u {shlex.quote(user + ':' + password)} "
            f"-T {shlex.quote(local_path)} "
            f"{shlex.quote(upload_url)} "
            f"-w '\\n%{{http_code}}\\n%{{time_total}}\\n%{{speed_upload}}' "
            f"-o /dev/null"
        )
        exit_code, out, err = self._exec(upload_cmd, timeout=600)

        # 解析结果
        lines = out.strip().split("\n")
        http_code = lines[-3] if len(lines) >= 3 else ""
        time_total = lines[-2] if len(lines) >= 2 else ""
        speed = lines[-1] if len(lines) >= 1 else ""

        if http_code not in ("200", "201", "204"):
            return UploadResult(
                success=False, filename=filename,
                error=f"上传失败 (HTTP {http_code}): {err[:200]}"
            )

        self._logger.info("上传成功: %s, 耗时 %ss", filename, time_total)

        # 生成分享链接
        share_cmd = (
            f"curl -k -s "
            f"-u {shlex.quote(user + ':' + password)} "
            f"-X POST {shlex.quote(base_url + '/ocs/v2.php/apps/files_sharing/api/v1/shares')} "
            f"-H 'OCS-APIREQUEST: true' "
            f"-d 'path=/{remote_path}&shareType=3'"
        )
        _, share_out, _ = self._exec(share_cmd, timeout=30)

        # 提取链接
        link = ""
        m = re.search(r"<url>([^<]+)</url>", share_out)
        if m:
            link = m.group(1)
        else:
            # 可能已存在分享，查询已有链接
            query_cmd = (
                f"curl -k -s "
                f"-u {shlex.quote(user + ':' + password)} "
                f"'{base_url}/ocs/v2.php/apps/files_sharing/api/v1/shares?path=/{remote_path}' "
                f"-H 'OCS-APIREQUEST: true'"
            )
            _, query_out, _ = self._exec(query_cmd, timeout=15)
            m = re.search(r"<url>([^<]+)</url>", query_out)
            if m:
                link = m.group(1)

        return UploadResult(
            success=True,
            filename=filename,
            link=link,
            size=size_display,
        )

    def find_latest_zip(self, code_dir: str) -> Optional[str]:
        """查找编译产物中最新的 zip 文件。"""
        # 在 out 目录和 code 目录下查找
        cmd = (
            f"find {shlex.quote(code_dir)}/out {shlex.quote(code_dir)} "
            f"-maxdepth 3 -name '*.zip' -type f 2>/dev/null "
            f"| xargs ls -t 2>/dev/null | head -1"
        )
        _, out, _ = self._exec(cmd, timeout=15)
        path = out.strip()
        return path if path else None
