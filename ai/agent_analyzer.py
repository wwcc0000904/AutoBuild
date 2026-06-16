from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional

from .analysis import AnalysisResult
from .base import RequirementAnalyzer
from config.logging_setup import get_logger


class AgentAnalyzer(RequirementAnalyzer):
    """通过外部 Agent 分析客户需求。

    支持两种调用方式：
    1. subprocess: 调用外部可执行文件，通过 stdin/stdout 通信
    2. http: 调用 HTTP 接口（预留）

    Agent 收到的输入：
    - skill 文件路径
    - 需求文本
    - feature_mapping.json 路径（供 Agent 参考已有的功能映射）

    Agent 需要返回标准 JSON 格式，与 AnalysisResult 结构一致。
    """

    def __init__(
        self,
        skill_path: Path | None = None,
        agent_command: Optional[list[str]] = None,
        agent_url: Optional[str] = None,
        mapping_path: Optional[Path] = None,
    ) -> None:
        """
        Args:
            skill_path: Skill 文件路径，指导 Agent 如何分析
            agent_command: subprocess 模式，如 ["python3", "agent.py"]
            agent_url: HTTP 模式，如 "http://localhost:8080/analyze"
            mapping_path: feature_mapping.json 路径
        """
        super().__init__(skill_path)
        self._agent_command = agent_command
        self._agent_url = agent_url
        self._mapping_path = mapping_path or Path("config/feature_mapping.json")
        self._logger = get_logger()

    def analyze(self, requirement_text: str) -> AnalysisResult:
        if self._agent_command:
            return self._analyze_via_subprocess(requirement_text)
        elif self._agent_url:
            return self._analyze_via_http(requirement_text)
        else:
            raise RuntimeError(
                "AgentAnalyzer 未配置调用方式。请设置 agent_command 或 agent_url。"
            )

    def _build_prompt(self, requirement_text: str) -> dict:
        """构造发给 Agent 的输入结构。"""
        skill_content = ""
        if self.skill_path and self.skill_path.exists():
            skill_content = self.skill_path.read_text(encoding="utf-8")

        mapping_content = ""
        if self._mapping_path and self._mapping_path.exists():
            mapping_content = self._mapping_path.read_text(encoding="utf-8")

        return {
            "skill": skill_content,
            "requirement": requirement_text,
            "feature_mapping": mapping_content,
        }

    def _parse_response(self, response_text: str) -> AnalysisResult:
        """解析 Agent 返回的 JSON 为标准 AnalysisResult。"""
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Agent 返回了无效的 JSON: {e}\n{response_text[:200]}")

        required = ["customer", "platform", "project", "operation", "target_customer_dir"]
        for key in required:
            if key not in data:
                raise RuntimeError(f"Agent 返回缺少必填字段: {key}")

        # 验证 modifications 格式
        for mod in data.get("modifications", []):
            if "type" not in mod:
                raise RuntimeError(f"修改项缺少 type 字段: {mod}")

        return AnalysisResult(
            customer=data["customer"],
            platform=data["platform"],
            project=data["project"],
            operation=data.get("operation", "copy_and_modify"),
            target_customer_dir=data["target_customer_dir"],
            modifications=data.get("modifications", []),
            notes=data.get("notes", ""),
        )

    def _analyze_via_subprocess(self, requirement_text: str) -> AnalysisResult:
        """通过 subprocess 调用外部 Agent。"""
        if not self._agent_command:
            raise RuntimeError("subprocess 模式需要设置 agent_command")

        prompt = self._build_prompt(requirement_text)
        input_json = json.dumps(prompt, ensure_ascii=False)

        self._logger.info(
            "调用外部 Agent: %s", " ".join(self._agent_command)
        )

        try:
            result = subprocess.run(
                self._agent_command,
                input=input_json,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("外部 Agent 调用超时（60秒）")
        except FileNotFoundError as e:
            raise RuntimeError(f"找不到 Agent 可执行文件: {e}")

        if result.returncode != 0:
            self._logger.error("Agent stderr: %s", result.stderr[:500])
            raise RuntimeError(
                f"外部 Agent 返回错误码 {result.returncode}: {result.stderr[:200]}"
            )

        return self._parse_response(result.stdout)

    def _analyze_via_http(self, requirement_text: str) -> AnalysisResult:
        """通过 HTTP 调用外部 Agent（预留）。"""
        raise NotImplementedError("HTTP 模式暂未实现，请先使用 subprocess 模式")
