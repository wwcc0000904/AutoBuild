from __future__ import annotations

import re
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    passed: bool
    warnings: list[str] = field(default_factory=list)


def validate_user_app(project_root: Path) -> ValidationResult:
    """校验 userApp.xml 文件完整性。

    检查项:
    1. 文件是否存在
    2. com.disney.disneyplus 节点是否存在
    """
    result = ValidationResult(passed=True)
    xml_path = project_root / "configs" / "userApp.xml"

    if not xml_path.exists():
        result.passed = False
        result.warnings.append("userApp.xml 文件不存在")
        return result

    content = xml_path.read_text(encoding="utf-8")

    if '<package>com.disney.disneyplus</package>' not in content:
        result.passed = False
        result.warnings.append("userApp.xml 缺少 Disney+ 配置节点 (<package>com.disney.disneyplus</package>)")

    if '<density>240</density>' not in content:
        result.passed = False
        result.warnings.append("Disney+ 节点缺少 density 配置 (<density>240</density>)")

    return result


def validate_product_model(project_root: Path) -> ValidationResult:
    """校验并修正 ctvbuild.prop 中 ro.product.model 为 SMART_TV。

    如果不是 SMART_TV，自动修改并记录警告。
    如果已经是 SMART_TV，不做处理。
    """
    result = ValidationResult(passed=True)
    prop_path = project_root / "ctvbuild.prop"

    if not prop_path.exists():
        result.passed = False
        result.warnings.append("ctvbuild.prop 文件不存在，无法校验 product model")
        return result

    content = prop_path.read_text(encoding="utf-8")

    match = re.search(r'(ro\.product\.model\s*=\s*)(.+)', content)
    if not match:
        result.passed = False
        result.warnings.append("ctvbuild.prop 中未找到 ro.product.model 配置项")
        return result

    model_value = match.group(2).strip()
    if model_value.upper() == "SMART_TV":
        return result

    # 不是 SMART_TV，自动修正
    new_content = content[:match.start(2)] + "SMART_TV" + content[match.end(2):]
    prop_path.write_text(new_content, encoding="utf-8")
    result.warnings.append(
        f"ro.product.model 已从 \"{model_value}\" 修改为 \"SMART_TV\""
    )

    return result
