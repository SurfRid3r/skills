#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
样式定义 - 基于 commands.json 分析

腾讯文档的样式定义存储在 STYLES_PROPERTY 中，包含：
- styleId: 6 位十六进制 ID（如 "000002", "000013"）
- name: 样式名称（如 "heading 1", "Title"）
- outlineLvl: 大纲级别（0-8，对应 heading 1-9）
"""

# 基于 commands.json 提取的样式定义
STYLE_DEFINITIONS = {
    # 内置标题样式
    "000002": {"name": "heading 1", "outline_lvl": 0},
    "000003": {"name": "heading 2", "outline_lvl": 1},
    "000004": {"name": "heading 3", "outline_lvl": 2},
    "000005": {"name": "heading 4", "outline_lvl": 3},
    "000006": {"name": "heading 5", "outline_lvl": 4},
    "000007": {"name": "heading 6", "outline_lvl": 5},
    "000008": {"name": "heading 7", "outline_lvl": 6},
    "000009": {"name": "heading 8", "outline_lvl": 7},
    "00000a": {"name": "heading 9", "outline_lvl": 8},
    # 特殊标题样式
    "000011": {"name": "Subtitle", "outline_lvl": 1},
    "000013": {"name": "Title", "outline_lvl": 0},
    # Normal 样式
    "000001": {"name": "Normal", "outline_lvl": None},
}


def get_heading_level(style_id: str) -> int | None:
    """根据样式 ID 获取标题级别 (1-9) 或 None"""
    style_def = STYLE_DEFINITIONS.get(style_id)
    if style_def and style_def["outline_lvl"] is not None:
        return style_def["outline_lvl"] + 1
    return None


def is_heading_style(style_id: str) -> bool:
    """判断是否是标题样式"""
    return get_heading_level(style_id) is not None


def get_style_name(style_id: str) -> str | None:
    """获取样式名称"""
    style_def = STYLE_DEFINITIONS.get(style_id)
    return style_def["name"] if style_def else None


# 已废弃：空映射，禁止使用启发式标题识别
LEGACY_STYLE_ID_MAP: dict[str, int] = {}


if __name__ == "__main__":
    print("样式定义测试:")
    print("-" * 60)

    for style_id in ["000002", "000003", "000013", "000001", "999999"]:
        level = get_heading_level(style_id)
        name = get_style_name(style_id)
        is_heading = is_heading_style(style_id)
        print(f"{style_id}: {name or 'Unknown':15} | Level: {level or 'N/A':2} | Heading: {is_heading}")

    print("\n" + "=" * 60)
    print("注意：LEGACY_STYLE_ID_MAP 仅供向后兼容，不应在新代码中使用")
