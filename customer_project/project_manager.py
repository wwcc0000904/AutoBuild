from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CustomerProject:
    source_dir: Path
    target_dir: Path


class CustomerProjectManager:
    def __init__(self, root: Path) -> None:
        self.root = root

    def list_customer_dirs(self) -> list[Path]:
        if not self.root.exists():
            return []
        return sorted(p for p in self.root.iterdir() if p.is_dir())

    def resolve_target(self, customer_dir_name: str, operation: str) -> CustomerProject:
        source = self.root / customer_dir_name
        if operation == "modify":
            target = source
        else:
            target = self.root / f"{customer_dir_name}_AUTO"
        return CustomerProject(source_dir=source, target_dir=target)

    def prepare_target(self, project: CustomerProject) -> Path:
        if not project.source_dir.exists():
            raise FileNotFoundError(
                f"源目录不存在: {project.source_dir}\n"
                f"请确认客户工程根目录设置正确，且目标客户目录 '{project.source_dir.name}' 存在于该目录中。"
            )
        if project.source_dir == project.target_dir:
            return project.target_dir
        if project.target_dir.exists():
            shutil.rmtree(project.target_dir)
        shutil.copytree(project.source_dir, project.target_dir)
        return project.target_dir
