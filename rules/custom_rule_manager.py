"""自定义规则管理：从 config/custom_rules.json 加载/保存用户自定义规则。"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "custom_rules.json"

# 支持的规则类型及其参数
RULE_TYPES = {
    "db_ini": {"label": "DB INI 修改", "params": ["file", "key", "value"], "required": ["key"]},
    "prop": {"label": "属性修改", "params": ["file", "key", "value"], "required": ["key"]},
    "ctv_data": {"label": "CTV Data 修改", "params": ["name", "value"], "required": ["name"]},
    "build_config": {"label": "Build Config 修改", "params": ["file", "key", "value"], "required": ["key"]},
    "whitelist": {"label": "白名单修改", "params": ["package", "action"], "required": ["package"]},
    "preinstall": {"label": "预装应用", "params": ["app", "enabled"], "required": ["app"]},
    "country_list_first": {"label": "国家列表置顶", "params": ["country_code"], "required": ["country_code"]},
    "language_first": {"label": "语言置顶", "params": ["target"], "required": ["target"]},
    "color_temp": {"label": "色温调整", "params": ["values"], "required": ["values"]},
    "gain": {"label": "增益调整", "params": ["name", "values"], "required": ["name", "values"]},
    "nla": {"label": "NLA 参数", "params": ["param", "value"], "required": ["param"]},
    "ctv_setting": {"label": "CTV Setting", "params": ["name", "enable"], "required": ["name"]},
}


def _load_raw() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {"rules": []}


def _save_raw(data: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_keywords(kw) -> list[str]:
    """关键词统一成数组，兼容旧的逗号分隔字符串。"""
    if isinstance(kw, list):
        return [k.strip() for k in kw if k and k.strip()]
    if isinstance(kw, str):
        return [k.strip() for k in kw.split(",") if k.strip()]
    return []


def load_rules() -> list[dict]:
    rules = _load_raw().get("rules", [])
    for r in rules:
        r["keywords"] = _normalize_keywords(r.get("keywords"))
    return rules


def save_rule(rule: dict) -> dict:
    """添加或更新一条规则，返回完整的 rule dict（含 id）。"""
    data = _load_raw()
    rules = data.get("rules", [])
    if rule.get("id"):
        # 更新
        for i, r in enumerate(rules):
            if r["id"] == rule["id"]:
                rules[i] = rule
                break
    else:
        # 新增
        rule["id"] = uuid.uuid4().hex[:12]
        rules.append(rule)
    # keywords 规范化为数组存储
    if "keywords" in rule:
        rule["keywords"] = _normalize_keywords(rule["keywords"])
    data["rules"] = rules
    _save_raw(data)
    return rule


def delete_rule(rule_id: str) -> None:
    data = _load_raw()
    data["rules"] = [r for r in data.get("rules", []) if r.get("id") != rule_id]
    _save_raw(data)
