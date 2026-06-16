from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from rules.base_rule import BaseRule


CTV_DATA_RELATIVE = "overlay/cultraview/common/apps/CtvMiddleware/CultraviewTvService/res/raw/ctv_data.xml"


class CtvDataRule(BaseRule):
    """修改 ctv_data.xml 中的 data 节点值。

    逻辑：
    1. 节点存在且值相同 → 不处理
    2. 节点存在但值不同 → 替换
    3. 节点不存在 → 追加到 after_name 节点后面
    """

    def __init__(
        self,
        name: str,
        value: str,
        default_value: str | None = None,
        after_name: str | None = None,
    ) -> None:
        self.name = name
        self.value = value
        self.default_value = default_value or value
        self.after_name = after_name or name
        self.last_action = ""  # "added" | "replaced" | "skipped_exists" | "skipped_file_missing"

    def apply(self, project_root: Path) -> List[Path]:
        changed: List[Path] = []
        target = project_root / CTV_DATA_RELATIVE

        if not target.exists():
            self.last_action = "skipped_file_missing"
            return changed

        content = target.read_text(encoding="utf-8")

        # 检查节点是否已存在
        pattern = re.escape(self.name)
        node_match = re.search(
            rf'<data\s+name="{pattern}"\s+value="([^"]*)"',
            content,
        )

        if node_match:
            current_value = node_match.group(1)
            if current_value == self.value:
                self.last_action = "skipped_exists"
                return changed
            # 值不同，替换
            modified = self._replace_value(content)
            if modified != content:
                target.write_text(modified, encoding="utf-8")
                changed.append(target)
                self.last_action = "replaced"
            return changed

        # 节点不存在，追加到 customized 区域
        appended = self._append_node(content)
        if appended != content:
            target.write_text(appended, encoding="utf-8")
            changed.append(target)
            self.last_action = "added"
        else:
            self.last_action = "skipped_insert_failed"

        return changed

    def _replace_value(self, content: str) -> str:
        pattern = re.escape(self.name)
        return re.sub(
            rf'(<data\s+name="{pattern}"\s+value=")([^"]*)(")',
            rf'\g<1>{self.value}\g<3>',
            content,
        )

    def _append_node(self, content: str) -> str:
        """追加新节点，优先插入 <customized> 区域内。"""
        indent = "        "
        new_node = f'{indent}<data name="{self.name}" value="{self.default_value}"/>'

        # 1. 先尝试在 after_name 节点后插入
        pattern = re.escape(self.after_name)
        match = re.search(
            rf'(<data\s+name="{pattern}"\s+value="[^"]*"\s*/>)',
            content,
        )
        if match:
            insert_pos = match.end()
            return content[:insert_pos] + "\n" + new_node + content[insert_pos:]

        # 2. 插入到 <customized> 下一行（customized 区域第一行）
        customized_open = content.find("<customized>")
        if customized_open >= 0:
            line_end = content.find("\n", customized_open)
            if line_end >= 0:
                insert_pos = line_end + 1
                comment = f'{indent}<!-- 自定义信息{self.name} -->'
                return content[:insert_pos] + comment + "\n" + new_node + "\n" + content[insert_pos:]

        # 3. 兜底：找最后一个 <data ... /> 节点后追加
        last_data = list(re.finditer(r'<data\s+[^/]*/>\s*', content))
        if last_data:
            insert_pos = last_data[-1].end()
            return content[:insert_pos] + new_node + "\n" + content[insert_pos:]

        # 4. 在 </resources> 或 </ctvdata> 前插入
        for tag in ("</resources>", "</ctvdata>"):
            closing = content.rfind(tag)
            if closing >= 0:
                return content[:closing] + new_node + "\n" + content[closing:]

        return content + "\n" + new_node + "\n"
