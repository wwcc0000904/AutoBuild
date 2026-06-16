from __future__ import annotations

from typing import Union

from rules.rule_registry import RuleRegistry
from customer_project.remote_fs import RemotePath


class RulePatcher:
    def __init__(self, registry: RuleRegistry, project_root: Union[RemotePath, "Path"]) -> None:
        self.registry = registry
        self.project_root = project_root

    def apply_all(self) -> list:
        changed: list = []
        for rule in self.registry.rules:
            changed.extend(rule.apply(self.project_root))
        return changed
