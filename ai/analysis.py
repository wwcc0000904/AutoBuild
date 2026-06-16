from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AnalysisResult:
    """AI 分析结果的标准化输出。

    下游（规则匹配、人工审核、执行器）只依赖这个结构，
    不关心具体是谁做的分析。
    """
    customer: str                  # 客户标识，如 "SXWDD"
    platform: str                  # 平台/型号，如 "CV352-B55-20"
    project: str                   # 项目变体，如 "EsharePlus"
    operation: str                 # 操作模式: "modify" | "copy_and_modify"
    target_customer_dir: str       # 目标客户目录名
    modifications: list[dict]      # 要做的修改项列表，供规则匹配用
    notes: str                     # 备注或原始需求摘要
    region: str = ""               # 区域
    target_dir: str = ""           # 目标目录
