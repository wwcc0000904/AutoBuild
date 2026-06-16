from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import ai


@dataclass
class ReviewDecision:
    approved: bool
    reason: str


class ReviewService:
    """审核服务。

    支持两种模式：
    1. 程序化调用：直接 approve() / reject()
    2. 回调模式：request_review() 后通过 callback 等待结果
    """

    def __init__(self) -> None:
        self._callback: Optional[Callable[[ai.AnalysisResult], None]] = None
        self._current_analysis: Optional[ai.AnalysisResult] = None
        self._decision: Optional[ReviewDecision] = None

    def set_callback(self, callback: Callable[[ai.AnalysisResult], None]) -> None:
        """设置审核回调。每次 request_review 时会调用此回调。"""
        self._callback = callback

    def request_review(self, analysis: ai.AnalysisResult) -> None:
        """发起审核请求。"""
        self._current_analysis = analysis
        self._decision = None
        if self._callback:
            self._callback(analysis)

    def approve(self, reason: str = "人工审核通过") -> ReviewDecision:
        """程序化通过（旧接口兼容）。"""
        return ReviewDecision(approved=True, reason=reason)

    def submit_decision(self, decision: ReviewDecision) -> None:
        """外部注入审核结果（UI 回调用）。"""
        self._decision = decision

    def wait_for_decision(self) -> ReviewDecision:
        """等待审核结果（阻塞轮询）。"""
        import time
        while self._decision is None:
            time.sleep(0.05)
        return self._decision
