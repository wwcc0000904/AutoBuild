from __future__ import annotations

from rules.rule_registry import RuleRegistry


def _extract_value_from_text(text: str, keyword: str, params: dict) -> None:
    """从需求文本中提取关键词后面的值，填入 params。"""
    import re
    idx = text.find(keyword)
    if idx < 0:
        return
    after = text[idx + len(keyword):].strip()
    if not after:
        return
    first_line = after.split("\n")[0].strip()
    if not first_line:
        return
    # 提取值：去掉前导的 = ：: 等分隔符
    m = re.match(r"[=\s：:]+\s*(.+)", first_line)
    extracted = m.group(1).strip() if m else first_line.split()[0]
    if not extracted:
        return
    # 优先填 value，其次其他字段
    if "value" in params:
        if not params["value"]:
            params["value"] = extracted
    elif "country_code" in params:
        if not params["country_code"]:
            params["country_code"] = extracted
    elif "target" in params:
        if not params["target"]:
            params["target"] = extracted
    elif "package" in params:
        if not params["package"]:
            params["package"] = extracted
    elif "app" in params:
        if not params["app"]:
            params["app"] = extracted
    else:
        params["value"] = extracted


def build_rule_registry(analysis_modifications: list[dict], requirement_text: str = "") -> RuleRegistry:
    registry = RuleRegistry()

    for mod in analysis_modifications:
        t = mod["type"]

        if t == "build_config":
            from rules.build_config_rule import BuildConfigRule
            registry.add(BuildConfigRule(
                file=mod["file"], key=mod["key"],
                new_value=mod["value"], mode=mod.get("mode", "value"),
            ))
        elif t == "preinstall":
            from rules.preinstall_rule import PreinstallRule
            _enabled_raw = mod.get("enabled", False)
            _enabled = _enabled_raw if isinstance(_enabled_raw, bool) else str(_enabled_raw).lower() in ("true", "y", "1", "yes")
            registry.add(PreinstallRule(app=mod.get("app", "ESharePlus"), enabled=_enabled))
        elif t in ("whitelist", "whitelist_append"):
            from rules.whitelist_rule import WhitelistRule
            registry.add(WhitelistRule(package=mod["package"], action=mod.get("action", "add")))
        elif t == "whitelist_remove":
            from rules.whitelist_rule import WhitelistRule
            registry.add(WhitelistRule(package=mod["package"], action="remove"))
        elif t == "prop":
            from rules.prop_rule import PropRule
            registry.add(PropRule(file=mod["file"], key=mod["key"], value=mod["value"]))
        elif t == "ctv_data":
            from rules.ctv_data_rule import CtvDataRule
            registry.add(CtvDataRule(
                name=mod["name"], value=mod["value"],
                default_value=mod.get("default_value"), after_name=mod.get("after_name"),
            ))
        elif t == "country_list_first":
            from rules.country_list_rule import CountryListRule
            registry.add(CountryListRule(country_code=mod["country_code"]))
        elif t == "language_first":
            from rules.language_ini_rule import LanguageIniRule
            registry.add(LanguageIniRule(target=mod["target"], mode="first"))
        elif t == "language_add":
            from rules.language_ini_rule import LanguageIniRule
            registry.add(LanguageIniRule(target=mod["target"], mode="add"))
        elif t == "db_ini":
            from rules.db_ini_rule import DbIniRule
            registry.add(DbIniRule(file=mod["file"], key=mod["key"], value=mod["value"]))
        elif t == "color_temp":
            from rules.color_temp_rule import ColorTempRule
            registry.add(ColorTempRule(*mod["values"]))
        elif t == "nla":
            from rules.nla_rule import NlaRule
            if mod.get("mode") == "full":
                registry.add(NlaRule.full(mod["param"], mod["values"]))
            else:
                registry.add(NlaRule(param=mod["param"], value=mod["value"], position=mod.get("position", 2)))
        elif t == "nla_full":
            from rules.nla_rule import NlaRule
            registry.add(NlaRule.full(mod["param"], mod["values"]))
        elif t == "sat_gain":
            from rules.sat_gain_rule import SatGainRule
            registry.add(SatGainRule(values=mod["values"]))
        elif t == "gain":
            from rules.gain_rule import GainRule
            registry.add(GainRule(name=mod["name"], values=mod["values"]))
        elif t == "ctv_setting":
            from rules.ctv_setting_rule import CtvSettingRule
            registry.add(CtvSettingRule(name=mod["name"], enable=mod["enable"], prefix_match=mod.get("prefix", False)))

    # 加载用户自定义规则（匹配原始需求文本）
    # 先收集已有的 modifications 指纹，避免重复添加
    existing_keys = set()
    for mod in analysis_modifications:
        key = (mod.get("type"), mod.get("file", ""), mod.get("key", ""), mod.get("name", ""))
        existing_keys.add(key)

    from rules.custom_rule_manager import load_rules
    custom_rules = load_rules()
    for cr in custom_rules:
        keywords = [k.strip() for k in cr.get("keywords", "").split(",") if k.strip()]
        if not keywords:
            continue
        matched_kw = None
        for kw in keywords:
            if kw in requirement_text:
                matched_kw = kw
                break
        if matched_kw is None:
            continue
        rtype = cr.get("rule_type", "")
        params = dict(cr.get("params", {}))
        _extract_value_from_text(requirement_text, matched_kw, params)
        # 检查是否已经在 analysis_modifications 中（避免重复）
        dup_key = (rtype, params.get("file", ""), params.get("key", ""), params.get("name", ""))
        if dup_key in existing_keys:
            continue
        t = rtype
        if t == "db_ini":
            from rules.db_ini_rule import DbIniRule
            registry.add(DbIniRule(file=params.get("file", ""), key=params.get("key", ""), value=params.get("value", "")))
        elif t == "prop":
            from rules.prop_rule import PropRule
            registry.add(PropRule(file=params.get("file", ""), key=params.get("key", ""), value=params.get("value", "")))
        elif t == "ctv_data":
            from rules.ctv_data_rule import CtvDataRule
            registry.add(CtvDataRule(name=params.get("name", ""), value=params.get("value", "")))
        elif t == "build_config":
            from rules.build_config_rule import BuildConfigRule
            registry.add(BuildConfigRule(file=params.get("file", ""), key=params.get("key", ""), new_value=params.get("value", "")))
        elif t == "whitelist":
            from rules.whitelist_rule import WhitelistRule
            registry.add(WhitelistRule(package=params.get("package", ""), action=params.get("action", "add")))
        elif t == "country_list_first":
            from rules.country_list_rule import CountryListRule
            registry.add(CountryListRule(country_code=params.get("country_code", "")))
        elif t == "language_first":
            from rules.language_ini_rule import LanguageIniRule
            registry.add(LanguageIniRule(target=params.get("target", "")))

    return registry
