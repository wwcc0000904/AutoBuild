"""远程文件系统抽象：通过 SSH 模拟 pathlib.Path 接口。

所有文件操作（exists, read_text, write_text）都通过 SSH 执行，
使得规则引擎可以直接操作远程服务器上的文件。
"""
from __future__ import annotations

import base64
import shlex
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

    def _q(self) -> str:
        """返回路径的安全 shell 引用形式。"""
        return shlex.quote(self._path)

    def exists(self) -> bool:
        try:
            out = self._exec(
                f'test -e {self._q()} && echo YES || echo NO'
            )
            return out.strip() == "YES"
        except RemoteCommandError:
            return False

    def is_dir(self) -> bool:
        try:
            out = self._exec(
                f'test -d {self._q()} && echo YES || echo NO'
            )
            return out.strip() == "YES"
        except RemoteCommandError:
            return False

    def read_text(self, encoding: str = "utf-8") -> str:
        return self._exec(f'cat {self._q()}', encoding=encoding)

    def write_text(self, content: str, encoding: str = "utf-8") -> None:
        encoded = base64.b64encode(content.encode(encoding)).decode("ascii")
        # chunk_size 必须是 4 的倍数：base64 每 4 个字符解码为 3 字节，
        # 分块时如果不对齐会导致解码错误。
        chunk_size = 4000
        if len(encoded) <= chunk_size:
            self._exec(f'echo {shlex.quote(encoded)} | base64 -d > {self._q()}')
        else:
            # 按 chunk_size 分块，如果最后一块不是 4 的倍数则合并到前一块
            chunks = [encoded[i:i + chunk_size] for i in range(0, len(encoded), chunk_size)]
            if len(chunks) > 1 and len(chunks[-1]) % 4 != 0:
                chunks[-2] += chunks.pop()
            first = True
            for chunk in chunks:
                if first:
                    self._exec(f'echo -n {shlex.quote(chunk)} | base64 -d > {self._q()}')
                    first = False
                else:
                    self._exec(f'echo -n {shlex.quote(chunk)} | base64 -d >> {self._q()}')

    # ── 远程目录操作 ──

    def remote_copytree(self, dest: "RemotePath") -> None:
        """远程复制目录。"""
        self._exec(f'cp -r {self._q()} {dest._q()}')

    def remote_rmtree(self) -> None:
        """远程删除目录。"""
        self._exec(f'rm -rf {self._q()}')
