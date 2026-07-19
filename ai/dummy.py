from __future__ import annotations

import json
import re
from pathlib import Path

from .analysis import AnalysisResult
from .base import RequirementAnalyzer
from config.logging_setup import get_logger


_COUNTRY_MAP: dict[str, str] | None = None
_LANGUAGE_MAP: dict[str, dict] | None = None


def _load_country_map() -> dict[str, str]:
    global _COUNTRY_MAP
    if _COUNTRY_MAP is None:
        path = Path("config/country_map.json")
        if path.exists():
            with open(path, encoding="utf-8") as f:
                _COUNTRY_MAP = json.load(f)
        else:
            _COUNTRY_MAP = {}
    return _COUNTRY_MAP


def _load_language_map() -> dict[str, dict]:
    global _LANGUAGE_MAP
    if _LANGUAGE_MAP is None:
        path = Path("config/language_map.json")
        if path.exists():
            with open(path, encoding="utf-8") as f:
                _LANGUAGE_MAP = json.load(f)
        else:
            _LANGUAGE_MAP = {}
    return _LANGUAGE_MAP


def _check_country_in_list(country_code: str, project_root: Path | None = None) -> bool:
    if project_root is None:
        return False
    xml_path = project_root / "overlay/cultraview/common/apps/CtvMiddleware/CultraviewTvService/res/raw/ctv_data.xml"
    if not xml_path.exists():
        return False
    content = xml_path.read_text(encoding="utf-8")
    m = re.search(r'name="CountryList"\s+item="([^"]+)"', content)
    if not m:
        return False
    items = [i.strip() for i in m.group(1).split(",")]
    return country_code.upper() in [i.upper() for i in items]


WHITELIST_PACKAGES = {
    "谷歌商城": "com.android.vending",
    "谷歌商店": "com.android.vending",
    "chrome": "com.android.chrome",
    "谷歌邮箱": "com.google.android.gm",
    "miracast": "com.hisilicon.miracast",
}


# 已知会被匹配的行模式（用于过滤已匹配的行）
_MATCHED_PATTERNS = [
    r"默认语言", r"默认国家", r"出口", r"打开", r"开启", r"关闭", r"隐藏", r"显示",
    r"电流", r"客户",
    r"上电模式", r"开机模式", r"开机桌面", r"菜单显示时间", r"语言显示",
    r"W/B", r"白平衡", r"R\s+Gain", r"G\s+Gain", r"B\s+Gain",
    r"Curve", r"曲线", r"OSD", r"Brightness", r"Contrast", r"Saturation",
    r"Sharpness", r"Hue", r"Backlight",
    r"Color\s*Space", r"SatGain", r"HueGain", r"BriGain",
    r"直接修改",
    r"谷歌商城", r"谷歌商店", r"chrome", r"谷歌邮箱", r"miracast",
    r"杜比", r"HBG", r"TVcasting", r"ESHARE", r"蓝屏",
    r"FakeInfoEnable",
    # 值行（纯数字、逗号、空格）
    r"^[\s\d,.\-/]+$",
]

# 不需要警告的噪声行模式
_NOISE_PATTERNS = [
    r"^\s*$",                           # 空行
    r"^\s*\d+[\s,./]+$",               # 纯数字行
    r"^\s*[-=]+\s*$",                   # 分隔线
    r"^\s*原始需求摘要",                 # 标题
    # r"Android\s*\d+",                 # 不过滤，让它作为未识别需求报出来
    r"^\s*\d+[,，]\s*$",               # 序号
    r"PQ\s*需求",                       # PQ 需求标题
    r"^\s*Red\s+Green\s+Blue",          # 表头
    r"^\s*Flesh\s*$",                   # 表头
    r"^\s*Cyan\s+Magenta",             # 表头
]


def _find_language(target: str) -> bool:
    """检查 language_map.json 中是否有指定语言（按代码或中文名匹配）。"""
    lang_map = _load_language_map()
    # 标准化：将"文"后缀转为"语"后缀
    normalized = target
    if normalized.endswith("文"):
        normalized = normalized[:-1] + "语"
    for code, info in lang_map.items():
        name = info.get("name", "")
        if target.upper() == code.upper() or target == name or normalized == name:
            return True
    return False


def _extract_unrecognized_lines(requirement_text: str) -> list[str]:
    """提取未被任何规则匹配的有意义行。"""
    lines = requirement_text.splitlines()
    unrecognized: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # 检查是否是噪声
        is_noise = False
        for pattern in _NOISE_PATTERNS:
            if re.search(pattern, stripped, re.IGNORECASE):
                is_noise = True
                break
        if is_noise:
            continue

        # 检查是否匹配了已知规则模式
        is_matched = False
        for pattern in _MATCHED_PATTERNS:
            if re.search(pattern, stripped, re.IGNORECASE):
                is_matched = True
                break
        # 检查是否匹配了自定义规则关键词
        if not is_matched:
            from rules.custom_rule_manager import load_rules
            for cr in load_rules():
                keywords = [k.strip() for k in cr.get("keywords", "").split(",") if k.strip()]
                if any(kw in stripped for kw in keywords):
                    is_matched = True
                    break
        if is_matched:
            continue

        # 剩下的就是未识别的行
        unrecognized.append(stripped)

    return unrecognized


def _extract_custom_value(text: str, keyword: str, params: dict) -> None:
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
    m = re.match(r"[=\s：:]+\s*(.+)", first_line)
    extracted = m.group(1).strip() if m else (first_line.split()[0] if first_line.split() else "")
    if not extracted:
        return
    for field in ["value", "country_code", "target", "package", "app"]:
        if field in params and not params[field]:
            params[field] = extracted
            return
    params["value"] = extracted


class DummyAnalyzer(RequirementAnalyzer):
    def __init__(
        self,
        skill_path: Path | None = None,
        mapping_path: Path | None = None,
    ) -> None:
        super().__init__(skill_path)
        self.mapping_path = mapping_path or Path("config/feature_mapping.json")
        self._mapping: dict | None = None
        self._logger = get_logger()

    @property
    def mapping(self) -> dict:
        if self._mapping is None:
            with open(self.mapping_path, encoding="utf-8") as f:
                self._mapping = json.load(f)
        return self._mapping

    def _match_value_map(self, text: str, keyword: str, value_map: dict) -> str | None:
        variants = [keyword]
        for i in range(len(keyword) - 1, 1, -1):
            variants.append(keyword[:i])
        for match_text, mapped_value in value_map.items():
            for kw in variants:
                if f"{kw}{match_text}" in text or f"{kw} {match_text}" in text or f"{kw}为{match_text}" in text:
                    return mapped_value
        return None

    def _match_whitelist(self, text: str) -> list[dict]:
        results: list[dict] = []
        for keyword, package in WHITELIST_PACKAGES.items():
            for prefix in ["打开", "开启"]:
                if f"{prefix}{keyword}" in text:
                    results.append({"type": "whitelist", "package": package, "action": "add"})
            for prefix in ["关闭", "隐藏"]:
                if f"{prefix}{keyword}" in text:
                    results.append({"type": "whitelist", "package": package, "action": "remove"})
        return results

    def analyze(self, requirement_text: str, **context) -> AnalysisResult:
        operation = "copy_and_modify"
        if "直接修改" in requirement_text:
            operation = "modify"

        modifications: list[dict] = []
        warnings: list[str] = []
        mapping = self.mapping

        # ---- 默认语言（支持"默认语言：默认英语。其他：意大利语，德文，..."格式）----
        lang_match = re.search(r"默认语言[：:]*\s*(?:默认)?\s*([\u4e00-\u9fa5A-Za-z]+)", requirement_text)
        if lang_match:
            lang_target = lang_match.group(1).strip()
            if _find_language(lang_target):
                modifications.append({"type": "language_first", "target": lang_target})
            else:
                warnings.append(f"语言 \"{lang_target}\" 不在系统支持的语言列表中，已跳过")

        # ---- 添加语言（识别"其他：意大利语，德文，..."格式）----
        other_lang_match = re.search(r"其他[：:]*\s*([^\n]+)", requirement_text)
        if other_lang_match:
            other_langs_text = other_lang_match.group(1)
            # 按逗号分割
            for lang_item in re.split(r"[，,、]+", other_langs_text):
                lang_item = lang_item.strip()
                if not lang_item:
                    continue
                # 保留完整语言名（如"意大利语"、"德文"）
                lang_name = lang_item.strip()
                if not lang_name:
                    continue
                if _find_language(lang_name):
                    modifications.append({"type": "language_add", "target": lang_name})
                else:
                    warnings.append(f"语言 \"{lang_name}\" 不在系统支持的语言列表中，已跳过")
        
        # ---- 兼容旧格式：添加语言 ----
        add_lang_match = re.search(r"添加\s*([\u4e00-\u9fa5A-Za-z-]+)\s*语?", requirement_text)
        if add_lang_match:
            lang_target = add_lang_match.group(1).strip()
            # 检查是否已经在"其他"中处理过
            already_added = any(
                mod.get("type") == "language_add" and mod.get("target") == lang_target
                for mod in modifications
            )
            if not already_added:
                if _find_language(lang_target):
                    modifications.append({"type": "language_add", "target": lang_target})
                else:
                    warnings.append(f"语言 \"{lang_target}\" 不在系统支持的语言列表中，已跳过")

        # ---- 白名单 ----
        modifications.extend(self._match_whitelist(requirement_text))

        # ---- 默认国家（也识别"出口"）----
        country_match = re.search(r"(?:默认国家|出口)[：:]*\s*([^\s，,]+)", requirement_text)
        if country_match:
            raw_country = country_match.group(1)
            mapping_country = _load_country_map()
            reverse_map = {v: k for k, v in mapping_country.items()}
            country_code_from_cn = reverse_map.get(raw_country)
            if country_code_from_cn:
                if _check_country_in_list(country_code_from_cn):
                    modifications.append({"type": "country_list_first", "country_code": country_code_from_cn})
                else:
                    warnings.append(f"国家 \"{raw_country}\" ({country_code_from_cn}) 不在当前 CountryList 中，已跳过")
            else:
                if _check_country_in_list(raw_country.upper()):
                    modifications.append({"type": "country_list_first", "country_code": raw_country.upper()})
                else:
                    warnings.append(f"国家 \"{raw_country}\" 未在映射表或 CountryList 中找到，已跳过")

        # ---- 参数类 ----
        for keyword, mod in mapping.get("param", {}).items():
            pattern = mod.get("pattern", "")
            if not pattern:
                continue
            pm = re.search(pattern, requirement_text)
            if pm:
                raw_val = pm.group(1)
                if not raw_val.isdigit():
                    msg = f"参数 \"{keyword}\" 的值 \"{raw_val}\" 不是纯数字，已忽略"
                    warnings.append(msg)
                    self._logger.warning(msg)
                    continue
                mod_type = "db_ini" if mod["file"].startswith("configs/") else "build_config"
                entry = {
                    "type": mod_type, "file": mod["file"],
                    "key": mod["key"], "value": raw_val,
                    "mode": mod.get("mode", "value"),
                }
                modifications.append(entry)

        # ---- prop 类 ----
        for keyword, mod in mapping.get("prop", {}).items():
            value_map = mod.get("value_map", {})
            matched_val = self._match_value_map(requirement_text, keyword, value_map)
            if matched_val:
                modifications.append({
                    "type": "prop", "file": mod["file"],
                    "key": mod["key"], "value": matched_val,
                })

        # ---- ctv_data 类 ----
        for keyword, mod in mapping.get("ctv_data", {}).items():
            value_map = mod.get("value_map", {})
            matched_val = self._match_value_map(requirement_text, keyword, value_map)
            if matched_val:
                modifications.append({
                    "type": "ctv_data", "name": mod["name"],
                    "value": matched_val,
                })

        # ---- ctv_data_ensure（节点不存在时才添加到 customized 区域）----
        for item in mapping.get("ctv_data_ensure", []):
            modifications.append({
                "type": "ctv_data",
                "name": item["name"],
                "value": item["default_value"],
                "default_value": item["default_value"],
                "after_name": item["after_name"],
            })

        # ---- ctv_setting 菜单开关 ----
        menu_map = mapping.get("ctv_setting_menu", {})
        for cn_name, en_name in menu_map.items():
            matched = False
            enable_val = None
            if f"隐藏{cn_name}" in requirement_text or f"隐藏{cn_name}信息" in requirement_text:
                enable_val = "hide"
                matched = True
            elif f"显示{cn_name}" in requirement_text or f"显示{cn_name}信息" in requirement_text:
                enable_val = "support"
                matched = True
            if matched:
                use_prefix = cn_name in ("蓝牙",)
                modifications.append({
                    "type": "ctv_setting", "name": en_name,
                    "enable": enable_val, "prefix": use_prefix,
                })

        # ---- 基本开关 ----
        for keyword, mod in mapping.get("open", {}).items():
            if keyword.lower() == "eshare": continue
            if f"打开{keyword}" in requirement_text or f"开启{keyword}" in requirement_text:
                mod_type = "db_ini" if mod["file"].startswith("configs/") else "build_config"
                entry = {"type": mod_type, "file": mod["file"], "key": mod["key"], "value": mod["value"]}
                if mod_type == "build_config":
                    entry["mode"] = "value"
                modifications.append(entry)
        for keyword, mod in mapping.get("close", {}).items():
            if keyword.lower() == "eshare": continue
            if f"关闭{keyword}" in requirement_text:
                mod_type = "db_ini" if mod["file"].startswith("configs/") else "build_config"
                entry = {"type": mod_type, "file": mod["file"], "key": mod["key"], "value": mod["value"]}
                if mod_type == "build_config":
                    entry["mode"] = "value"
                modifications.append(entry)

        # ---- 白平衡 Normal（6值模式）----
        wb_match = re.search(
            r'(?:W/B|白平衡).*?'
            r'R\s+Gain\s+(\d+).*?G\s+Gain\s+(\d+).*?B\s+Gain\s+(\d+).*?'
            r'R\s+Gain\s+Offset\s+(\d+).*?G\s+Gain\s+Offset\s+(\d+).*?B\s+Gain\s+Offset\s+(\d+)',
            requirement_text, re.DOTALL
        )
        if wb_match:
            modifications.append({
                "type": "color_temp",
                "values": [wb_match.group(i) for i in range(1, 7)],
            })

        # ---- OSD_50 图像曲线（全值替换）----
        osd_curve_match = re.search(r'Curve|曲线|OSD|OSD_50', requirement_text, re.IGNORECASE)
        if osd_curve_match:
            curve_idx = osd_curve_match.start()
            curve_text = requirement_text[curve_idx:]
            osd_params = {
                "Brightness": "brightness",
                "Contrast": "contrast",
                "Saturation": "saturation",
                "Sharpness": "sharpness",
                "Hue": "hue",
                "Backlight": "backlight",
            }
            for eng_name, param_name in osd_params.items():
                m = re.search(
                    rf'{eng_name}\s+(\d+)',
                    curve_text, re.IGNORECASE
                )
                if m:
                    modifications.append({
                        "type": "nla", "param": param_name, "value": m.group(1),
                    })

        # ---- Color Space PQ（SatGain/HueGain/BriGain 7组值）----
        cs_idx = requirement_text.lower().find("color space")
        if cs_idx >= 0:
            cs_text = requirement_text[cs_idx:]
            cs_names = {"Saturation": "SatGain", "Hue": "HueGain", "Brightness": "BriGain"}
            for keyword, gain_name in cs_names.items():
                m = re.search(
                    rf'{keyword}\s+([\d\s-]+)',
                    cs_text, re.IGNORECASE
                )
                if m:
                    values = [v.strip() for v in m.group(1).split() if v.strip()]
                    if len(values) >= 7:
                        modifications.append({
                            "type": "gain",
                            "name": gain_name,
                            "values": values[:7],
                        })

        # ---- 自定义规则匹配 ----
        from rules.custom_rule_manager import load_rules
        for cr in load_rules():
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
            _extract_custom_value(requirement_text, matched_kw, params)
            mod = {"type": rtype}
            mod.update(params)
            modifications.append(mod)

        # ---- 未识别需求检测 ----
        unrecognized = _extract_unrecognized_lines(requirement_text)
        if unrecognized:
            warnings.append(f"以下内容未被识别为已知规则: {'; '.join(unrecognized)}")

        notes = f"原始需求摘要: {requirement_text.strip()[:2000]}"
        if warnings:
            notes += " | 警告: " + "; ".join(warnings)

        result = AnalysisResult(
            customer=context.get("customer", ""),
            platform=context.get("platform", ""),
            project=context.get("project", ""),
            operation=operation,
            target_customer_dir=context.get("customer_dir", ""),
            modifications=modifications, notes=notes,
            region=context.get("region", ""),
            target_dir=context.get("target_dir", ""),
        )
        self._logger.info("AI 分析完成: %d 条修改, %d 条警告", len(modifications), len(warnings))
        if warnings:
            self._logger.warning("分析警告: %s", "; ".join(warnings))
        return result
