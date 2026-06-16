from __future__ import annotations

from pathlib import Path
from typing import List

from rules.base_rule import BaseRule


class PreinstallRule(BaseRule):
    """控制预装应用的安装状态。

    Args:
        app: 应用标识，如 "ESharePlus"
        enabled: True 表示设为预装 (Y)，False 表示取消预装 (n)
    """

    def __init__(self, app: str = "ESharePlus", enabled: bool = True) -> None:
        self.app = app
        self.enabled = enabled

    def apply(self, project_root: Path) -> List[Path]:
        changed: List[Path] = []
        target = project_root / "build_ctv_app.txt"

        if not target.exists():
            return changed

        content = target.read_text(encoding="utf-8")
        new_value = "Y" if self.enabled else "n"
        new_content = self._replace_app(content, self.app, new_value)

        if new_content != content:
            target.write_text(new_content, encoding="utf-8")
            changed.append(target)

        return changed

    @staticmethod
    def _replace_app(content: str, app: str, new_value: str) -> str:
        lines = content.splitlines(keepends=True)
        new_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            # 匹配 "ESharePlus                              = Y" 或 "= n" 格式
            if stripped.startswith(app):
                # 保留原格式，只替换 = 后面的值
                if "=" in line:
                    before, _ = line.rsplit("=", 1)
                    new_lines.append(f"{before}= {new_value}\n")
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)

        return "".join(new_lines)
