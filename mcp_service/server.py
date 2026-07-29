"""MCP Server — 给外部 AI Agent 提供调用接口。

启动方式:
    python3 mcp_service/server.py
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

# 把项目根目录加入 sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from mcp.server.fastmcp import FastMCP

import ai
from builder.build_service import BuildService
from config.logging_setup import get_logger
from customer_project.project_manager import CustomerProjectManager
from executor.task_executor import TaskExecutor
from review.review_service import ReviewService, ReviewDecision

# ---------- 初始化服务 ----------

logger = get_logger()

project_manager = CustomerProjectManager(root=Path.home() / "Desktop")
review_service = ReviewService()
build_service = BuildService()

mcp_server = FastMCP(
    name="软件输出自动化",
    instructions="电视软件客户定制配置自动化工具，支持需求分析、文件修改、编译触发。",
)


# ---------- Tool: 分析需求 ----------

@mcp_server.tool()
def analyze_requirement(requirement_text: str) -> str:
    """分析客户需求文本，返回结构化的修改方案（不执行修改）。

    Args:
        requirement_text: 客户需求的中文描述，例如 "打开杜比，电流改为550"

    Returns:
        JSON 格式的分析结果，包含 customer、platform、modifications 等字段。
    """
    logger.info("[MCP] analyze_requirement: %s", requirement_text[:100])
    result = ai.analyze(requirement_text)
    return json.dumps(asdict(result), ensure_ascii=False, indent=2)


# ---------- Tool: 执行任务（自动审核通过） ----------

@mcp_server.tool()
def run_task(requirement_text: str, root_dir: str = "") -> str:
    """分析客户需求并自动执行修改（MCP 模式下跳过人工审核）。

    Args:
        requirement_text: 客户需求的中文描述
        root_dir: 可选，客户工程根目录路径。为空则使用默认目录。

    Returns:
        JSON 格式的执行结果，包含修改文件列表、校验警告、编译状态。
    """
    if root_dir:
        project_manager.root = Path(root_dir)

    logger.info("[MCP] run_task: %s", requirement_text[:100])
    analysis = ai.analyze(requirement_text)

    # MCP 模式：自动通过审核
    review_service.submit_decision(ReviewDecision(approved=True, reason="MCP 自动审核"))

    executor = TaskExecutor(project_manager, review_service, build_service)
    record = executor.run(analysis)
    return json.dumps(asdict(record), ensure_ascii=False, indent=2)


# ---------- Tool: 列出客户目录 ----------

@mcp_server.tool()
def list_customer_dirs(root_dir: str = "") -> str:
    """列出客户工程根目录下的所有子目录。

    Args:
        root_dir: 可选，客户工程根目录路径。为空则使用默认目录。

    Returns:
        JSON 数组，包含目录名称列表。
    """
    if root_dir:
        project_manager.root = Path(root_dir)

    dirs = project_manager.list_customer_dirs()
    names = [d.name for d in dirs if not d.name.endswith("_AUTO")]
    return json.dumps(names, ensure_ascii=False, indent=2)


# ---------- Tool: 查看支持的修改规则 ----------

@mcp_server.tool()
def get_supported_rules() -> str:
    """查看系统支持的所有修改规则类型和用法。

    Returns:
        JSON 格式的规则说明。
    """
    rules_info = {
        "build_config": {
            "description": "修改 build_config.txt 中的开关或参数值",
            "params": {"file": "文件路径", "key": "配置键名", "value": "新值", "mode": "value|value_part"},
            "example": "打开杜比 / 电流改为550 / 客户名称改为ABC",
        },
        "preinstall": {
            "description": "控制预装应用开关",
            "params": {"app": "应用名", "enabled": "true|false"},
            "example": "预装 ESharePlus / 取消预装 ESharePlus",
        },
        "whitelist": {
            "description": "追加或删除白名单包名",
            "params": {"package": "包名", "action": "add|remove"},
            "example": "打开谷歌商城 / 关闭谷歌商城",
        },
        "prop": {
            "description": "修改 ctvbuild.prop 中的属性",
            "params": {"file": "文件路径", "key": "属性名", "value": "新值"},
            "example": "上电模式改为待机 / 开机模式改为视频",
        },
        "ctv_data": {
            "description": "修改 ctv_data.xml 中的配置项",
            "params": {"name": "节点名", "value": "新值"},
            "example": "开机桌面改为TV / 菜单显示时间改为10秒",
        },
        "country_list_first": {
            "description": "将默认国家移到 CountryList 首位",
            "params": {"country_code": "国家代码"},
            "example": "默认国家 阿联酋",
        },
        "language_first": {
            "description": "将默认语言移到 CtvLanguage.ini 首位",
            "params": {"target": "语言代码或中文名"},
            "example": "默认语言 阿拉伯语",
        },
        "db_ini": {
            "description": "修改 db.ini 中的配置项",
            "params": {"file": "文件路径", "key": "键名", "value": "新值"},
            "example": "打开蓝屏 / 关闭蓝屏",
        },
        "color_temp": {
            "description": "修改白平衡参数（所有 nature 行）",
            "params": {"values": "3个或6个数值"},
            "example": "白平衡 274 256 292 256 256 256",
        },
        "nla": {
            "description": "修改 NLA 非线性参数",
            "params": {"param": "参数名(brightness/contrast/saturation/sharpness/hue/backlight)", "value": "新中间值"},
            "example": "brightness 改成 205",
        },
        "gain": {
            "description": "修改 SatGain/HueGain/BriGain 前7个值",
            "params": {"name": "Gain名称", "values": "7个数值"},
            "example": "SatGain -5 2 10 4 -6 8 3",
        },
        "ctv_setting": {
            "description": "修改 ctvsetting.xml 菜单项显示/隐藏",
            "params": {"name": "菜单名", "enable": "support|hide"},
            "example": "隐藏内核信息 / 显示分辨率信息",
        },
    }
    return json.dumps(rules_info, ensure_ascii=False, indent=2)


# ---------- Tool: 设置客户工程根目录 ----------

@mcp_server.tool()
def set_root_dir(root_dir: str) -> str:
    """设置客户工程根目录。

    Args:
        root_dir: 根目录的绝对路径

    Returns:
        确认信息。
    """
    path = Path(root_dir)
    if not path.exists():
        return json.dumps({"error": f"目录不存在: {root_dir}"}, ensure_ascii=False)
    project_manager.root = path
    return json.dumps({"ok": True, "root": root_dir}, ensure_ascii=False)


# ---------- 启动 ----------

if __name__ == "__main__":
    mcp_server.run(transport="stdio")
