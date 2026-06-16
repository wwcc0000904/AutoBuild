from __future__ import annotations

from .analysis import AnalysisResult
from .base import RequirementAnalyzer
from .dummy import DummyAnalyzer

# ---------------------------------------------------------------
# 当前选中的分析器
# 后续可通过配置 / 环境变量 / 运行时切换来替换真实实现
# ---------------------------------------------------------------
_analyzer: RequirementAnalyzer = DummyAnalyzer()


def set_analyzer(a: RequirementAnalyzer) -> None:
    """运行时切换 AI 分析器。

    后续从 UI 或 MCP 调用此函数，可换成:
    - OpenAIAnalyzer(skill_path="ai/skills/requirement_analysis.md")
    - CodexAnalyzer(...)
    - McpAgentAnalyzer(...)
    """
    global _analyzer
    _analyzer = a


def get_analyzer() -> RequirementAnalyzer:
    return _analyzer


def analyze(requirement_text: str, **context) -> AnalysisResult:
    """统一的入口，下游只调这个函数，不关心底层是谁。"""
    return _analyzer.analyze(requirement_text, **context)
