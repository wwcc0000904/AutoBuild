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
        user_prompt = self._build_user_prompt(requirement_text, context)

        try:
            raw = self._call_api(system_prompt, user_prompt)
        except Exception as e:
            self._logger.error("AI 分析调用失败: %s", e, exc_info=True)
            raise RuntimeError(f"AI 分析调用失败: {e}") from e

        return self._parse_response(raw, requirement_text, context)

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

    def _build_user_prompt(self, requirement_text: str, context: dict) -> str:
        ctx_lines = []
        for k in ("project", "platform", "region", "customer", "customer_dir", "target_dir"):
            v = context.get(k, "")
            if v:
                ctx_lines.append(f"- {k}: {v}")
        ctx_block = "\n".join(ctx_lines) if ctx_lines else "（无）"
        return (
            f"## 当前上下文（用户在 UI 上选定的项目信息，请用于填充 customer/platform 等字段）\n"
            f"{ctx_block}\n\n"
            f"## 客户需求\n{requirement_text}\n\n"
            f"请输出结构化 JSON。"
        )

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

    def _parse_response(self, response_text: str, requirement_text: str, context: dict | None = None) -> AnalysisResult:
        context = context or {}
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

        # UI 上下文优先，模型返回值作为补充
        def _pick(ctx_key: str, data_key: str, default: str = "") -> str:
            v = str(context.get(ctx_key, "") or "").strip()
            if not v:
                v = str(data.get(data_key, "") or "").strip()
            return v or default

        modifications = data.get("modifications", [])
        for mod in modifications:
            if "type" not in mod:
                raise RuntimeError(f"修改项缺少 type 字段: {mod}")

        # 注入固定规则：ctv_data_ensure（如 FakeInfoEnable），与 DummyAnalyzer 一致
        modifications = self._inject_fixed_rules(modifications)

        return AnalysisResult(
            customer=_pick("customer", "customer"),
            platform=_pick("platform", "platform"),
            project=_pick("project", "project"),
            operation=str(data.get("operation", "copy_and_modify")),
            target_customer_dir=_pick("customer_dir", "target_customer_dir"),
            modifications=modifications,
            notes=str(data.get("notes", "")),
            region=_pick("region", "region"),
            target_dir=_pick("target_dir", "target_dir"),
            analyzer=f"AI({self._model})",
        )

    def _inject_fixed_rules(self, modifications: list[dict]) -> list[dict]:
        """注入固定规则（与 DummyAnalyzer 行为一致）。

        读取 feature_mapping.json 中的 ctv_data_ensure 列表，
        如 FakeInfoEnable（不存在时添加到 customized 区域，默认值 true）。
        这些规则不依赖需求文本，每次分析都应包含。
        """
        import json
        try:
            if not self._mapping_path or not self._mapping_path.exists():
                return modifications
            mapping = json.loads(self._mapping_path.read_text(encoding="utf-8"))
        except Exception:
            return modifications

        # 已有的 ctv_data 节点名，避免重复
        existing_names = {
            m.get("name") for m in modifications if m.get("type") == "ctv_data"
        }

        for item in mapping.get("ctv_data_ensure", []):
            name = item.get("name")
            if not name or name in existing_names:
                continue
            modifications.append({
                "type": "ctv_data",
                "name": name,
                "value": item.get("default_value", "true"),
                "default_value": item.get("default_value", "true"),
                "after_name": item.get("after_name"),
            })
            existing_names.add(name)

        return modifications
