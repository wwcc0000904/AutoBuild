from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from .analysis import AnalysisResult
from .base import RequirementAnalyzer
from config.logging_setup import get_logger


class OpenAIAnalyzer(RequirementAnalyzer):
    """通过 OpenAI 兼容接口分析客户需求。

    支持 OpenAI 官方 API，也支持任何兼容 Chat Completions 格式的服务
    （DeepSeek、通义千问、智谱等），只需改 base_url 和模型名。
    """

    def __init__(
        self,
        skill_path: Path | None = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "gpt-4o",
        mapping_path: Optional[Path] = None,
        timeout: int = 60,
    ) -> None:
        super().__init__(skill_path)
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._base_url = base_url or os.environ.get("OPENAI_BASE_URL")
        self._model = model
        self._mapping_path = mapping_path or Path("config/feature_mapping.json")
        self._timeout = timeout
        self._logger = get_logger()

    def analyze(self, requirement_text: str, **context) -> AnalysisResult:
        if not self._api_key:
            raise RuntimeError(
                "未配置 API Key。请在设置中填入，或设置环境变量 OPENAI_API_KEY。"
            )

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(requirement_text)

        try:
            raw = self._call_api(system_prompt, user_prompt)
        except Exception as e:
            self._logger.error("AI 分析调用失败: %s", e, exc_info=True)
            raise RuntimeError(f"AI 分析调用失败: {e}") from e

        return self._parse_response(raw, requirement_text)

    # ── prompt 构造 ──

    def _build_system_prompt(self) -> str:
        parts: list[str] = []

        skill_content = ""
        if self.skill_path and self.skill_path.exists():
            skill_content = self.skill_path.read_text(encoding="utf-8")
        if skill_content:
            parts.append(skill_content)

        mapping_content = ""
        if self._mapping_path and self._mapping_path.exists():
            mapping_content = self._mapping_path.read_text(encoding="utf-8")
        if mapping_content:
            parts.append(
                "\n\n## 功能映射参考表\n"
                "以下是已知的中文需求到配置项的映射，供你参考。\n"
                "如果需求无法精确匹配下表，请根据语义推断最接近的配置项。\n"
                f"{mapping_content}"
            )

        parts.append(
            "\n\n## 重要要求\n"
            "1. 只输出一个 JSON 对象，不要输出任何解释文字、markdown 代码块标记。\n"
            "2. JSON 必须可被 json.loads 直接解析。\n"
            "3. modifications 中每项必须有 type 字段。\n"
            "4. 如果某个需求你无法确定对应的配置项，跳过它并在 notes 中说明。\n"
            "5. notes 里用一句话回述你对需求的理解，方便人工审核确认。"
        )
        return "\n".join(parts)

    def _build_user_prompt(self, requirement_text: str) -> str:
        return f"请分析以下客户需求，输出结构化 JSON：\n\n{requirement_text}"

    # ── API 调用 ──

    def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        from openai import OpenAI

        client = OpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=self._timeout,
        )
        resp = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content or ""

    # ── 响应解析 ──

    def _parse_response(self, response_text: str, requirement_text: str) -> AnalysisResult:
        text = response_text.strip()
        # 兼容模型偶尔带 markdown 代码块
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
            text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            self._logger.error("AI 返回非法 JSON: %s\n原始: %s", e, response_text[:300])
            raise RuntimeError(f"AI 返回了无效的 JSON: {e}") from e

        required = ["customer", "platform", "project", "operation", "target_customer_dir"]
        missing = [k for k in required if k not in data]
        if missing:
            raise RuntimeError(f"AI 返回缺少必填字段: {missing}")

        modifications = data.get("modifications", [])
        for mod in modifications:
            if "type" not in mod:
                raise RuntimeError(f"修改项缺少 type 字段: {mod}")

        return AnalysisResult(
            customer=str(data["customer"]),
            platform=str(data["platform"]),
            project=str(data["project"]),
            operation=str(data.get("operation", "copy_and_modify")),
            target_customer_dir=str(data["target_customer_dir"]),
            modifications=modifications,
            notes=str(data.get("notes", "")),
        )
