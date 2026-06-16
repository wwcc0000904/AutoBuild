from __future__ import annotations

from typing import List

from rules.base_rule import BaseRule


class RuleRegistry:
    def __init__(self, rules: List[BaseRule] | None = None) -> None:
        self.rules: List[BaseRule] = rules or []

    def add(self, rule: BaseRule) -> None:
        self.rules.append(rule)
