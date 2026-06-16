from __future__ import annotations

from pathlib import Path
from typing import List

from rules.base_rule import BaseRule


LANGUAGE_INI_RELATIVE = "configs/CtvLanguage.ini"


class LanguageIniRule(BaseRule):
    """操作 CtvLanguage.ini 中的语言。

    mode:
      - "first": 移到第一位（默认语言）
      - "add":   添加到列表末尾（如果不存在）
    """

    def __init__(self, target: str, mode: str = "first") -> None:
        self.target = target
        self.mode = mode

    def apply(self, project_root: Path) -> List[Path]:
        changed: List[Path] = []
        target = project_root / LANGUAGE_INI_RELATIVE
        if not target.exists():
            return changed

        content = target.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)

        # 找有效行
        valid_indices: list[int] = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            valid_indices.append(i)

        # 找匹配行
        target_idx: int | None = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split(",")
            code = parts[0].strip() if parts else ""
            name = parts[1].strip() if len(parts) >= 2 else ""
            if self.target.upper() == code.upper() or self.target == name:
                target_idx = i
                break

        if self.mode == "first":
            # 默认语言：移到第一位
            if target_idx is not None:
                first_idx = valid_indices[0]
                if target_idx == first_idx:
                    return changed
                lines[target_idx], lines[first_idx] = lines[first_idx], lines[target_idx]
            else:
                # 不存在 → 添加到首位
                from config.language_registry import find_language, format_language_line
                lang = find_language(self.target)
                if lang is None:
                    return changed
                new_line = format_language_line(*lang) + "\n"
                first_idx = valid_indices[0] if valid_indices else 0
                lines.insert(first_idx, new_line)

        elif self.mode == "add":
            # 添加语言：只添加到末尾（已存在则跳过）
            if target_idx is not None:
                return changed  # 已存在
            from config.language_registry import find_language, format_language_line
            lang = find_language(self.target)
            if lang is None:
                return changed
            new_line = format_language_line(*lang) + "\n"
            # 找最后一个非空行的位置
            last_idx = len(lines)
            for i in range(len(lines) - 1, -1, -1):
                if lines[i].strip():
                    last_idx = i + 1
                    break
            lines.insert(last_idx, new_line)

        new_content = "".join(lines)
        if new_content != content:
            target.write_text(new_content, encoding="utf-8")
            changed.append(target)

        return changed
