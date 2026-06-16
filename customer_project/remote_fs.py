"""远程文件系统抽象：通过 SSH 模拟 pathlib.Path 接口。

所有文件操作（exists, read_text, write_text）都通过 SSH 执行，
使得规则引擎可以直接操作远程服务器上的文件。
"""
from __future__ import annotations

import base64
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import paramiko


class RemoteCommandError(RuntimeError):
    """远程命令执行失败。"""

class RemotePath:
    """通过 SSH 操作远程文件路径，接口兼容 pathlib.Path 的常用方法。"""

    def __init__(self, ssh_client: paramiko.SSHClient, path_str: str) -> None:
        self._ssh = ssh_client
        self._path = str(path_str).rstrip("/")

    # ── 路径运算 ──

    def __truediv__(self, other: str) -> "RemotePath":
        return RemotePath(self._ssh, f"{self._path}/{other}")

    def __str__(self) -> str:
        return self._path

    def __repr__(self) -> str:
        return f"RemotePath({self._path!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, RemotePath):
            return self._path == other._path
        if isinstance(other, str):
            return self._path == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._path)

    def __bool__(self) -> bool:
        return bool(self._path)

    @property
    def name(self) -> str:
        return self._path.rsplit("/", 1)[-1] if "/" in self._path else self._path

    @property
    def parent(self) -> "RemotePath":
        idx = self._path.rfind("/")
        if idx <= 0:
            return RemotePath(self._ssh, "/")
        return RemotePath(self._ssh, self._path[:idx])

    @property
    def suffix(self) -> str:
        n = self.name
        dot = n.rfind(".")
        return n[dot:] if dot >= 0 else ""

    def is_absolute(self) -> bool:
        return self._path.startswith("/")

    # ── 文件操作 ──

    def _exec(self, cmd: str, encoding: str = "utf-8") -> str:
        """在远程执行命令并返回 stdout；若命令失败则抛出异常。"""
        stdin, stdout, stderr = self._ssh.exec_command(cmd)
        exit_status = stdout.channel.recv_exit_status()
        out = stdout.read().decode(encoding)
        err = stderr.read().decode(encoding)
        if exit_status != 0:
            raise RemoteCommandError(
                f"Remote command failed (exit={exit_status}): {cmd}\n{err}"
            )
        return out

    def exists(self) -> bool:
        try:
            out = self._exec(
                f'test -e "{self._path}" && echo YES || echo NO'
            )
            return out.strip() == "YES"
        except RemoteCommandError:
            return False

    def is_dir(self) -> bool:
        try:
            out = self._exec(
                f'test -d "{self._path}" && echo YES || echo NO'
            )
            return out.strip() == "YES"
        except RemoteCommandError:
            return False

    def read_text(self, encoding: str = "utf-8") -> str:
        return self._exec(f'cat "{self._path}"', encoding=encoding)

    def write_text(self, content: str, encoding: str = "utf-8") -> None:
        encoded = base64.b64encode(content.encode(encoding)).decode("ascii")
        # 分块写入，避免命令行过长
        chunk_size = 4000
        if len(encoded) <= chunk_size:
            self._exec(f'echo "{encoded}" | base64 -d > "{self._path}"')
        else:
            # 先清空，再追加
            first = True
            for i in range(0, len(encoded), chunk_size):
                chunk = encoded[i:i + chunk_size]
                if first:
                    self._exec(f'echo -n "{chunk}" | base64 -d > "{self._path}"')
                    first = False
                else:
                    # 追加模式需要用 printf 和 >>
                    self._exec(f'echo -n "{chunk}" | base64 -d >> "{self._path}"')

    # ── 远程目录操作 ──

    def remote_copytree(self, dest: "RemotePath") -> None:
        """远程复制目录。"""
        self._exec(f'cp -r "{self._path}" "{dest._path}"')

    def remote_rmtree(self) -> None:
        """远程删除目录。"""
        self._exec(f'rm -rf "{self._path}"')
