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


def init_analyzer_from_config() -> None:
    """根据 config/ai_config.py 的配置初始化分析器。

    启动时调用一次：
    - enabled=False 或缺密钥 -> 用 DummyAnalyzer
    - enabled=True 且有密钥 -> 用 OpenAIAnalyzer
    """
    from config.ai_config import load_ai_config

    cfg = load_ai_config()
    if not cfg.enabled or not cfg.api_key:
        set_analyzer(DummyAnalyzer())
        return

    from pathlib import Path as _Path
    from .openai_analyzer import OpenAIAnalyzer
    set_analyzer(OpenAIAnalyzer(
        skill_path=_Path("ai/skills/requirement_analysis.md"),
        api_key=cfg.api_key,
        base_url=cfg.base_url or None,
        model=cfg.model,
        timeout=cfg.timeout,
    ))
