from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from .analysis import AnalysisResult


class RequirementAnalyzer(ABC):
    """AI 分析器抽象接口。

    所有具体实现（Dummy、OpenAI、Codex、其他 Agent）
    都继承这个类，实现 analyze 方法。
    """

    def __init__(self, skill_path: Path | None = None) -> None:
        self.skill_path = skill_path

    @abstractmethod
    def analyze(self, requirement_text: str, **context) -> AnalysisResult:
        raise NotImplementedError
