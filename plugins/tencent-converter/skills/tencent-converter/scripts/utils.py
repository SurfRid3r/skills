#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
共享工具函数和常量

包含:
- 常量定义 (时间戳范围、默认文件名)
- escape_cell: 转义 Markdown 表格单元格
- generate_front_matter: 统一的 YAML Front Matter 生成器
"""

from datetime import datetime
from typing import Callable


# ============================================================================
# 常量定义
# ============================================================================

# 时间戳验证范围 (毫秒)
TIMESTAMP_MIN = 1577836800000  # 2020-01-01 00:00:00 UTC
TIMESTAMP_MAX = 2000000000000  # 2033-05-18 03:33:20 UTC

# 默认文件名
DEFAULT_DOC_NAME = "未命名文档.md"
DEFAULT_SHEET_OUTPUT_NAME = "未命名表格.md"
FALLBACK_SHEET_TITLE = "未命名表格"


# ============================================================================
# 单元格转义
# ============================================================================

def escape_cell(text: str, strip_control_chars: bool = True) -> str:
    """转义 Markdown 表格单元格

    Args:
        text: 原始文本
        strip_control_chars: 是否移除控制字符 (默认 True)

    Returns:
        转义后的文本
    """
    if not text:
        return ""

    text = text.replace("\n", "<br>").replace("|", "\\|")

    if strip_control_chars:
        # 移除控制字符 (ASCII < 32 且非扩展 ASCII)
        text = "".join(c if ord(c) >= 32 or ord(c) > 127 else " " for c in text)

    return text


# ============================================================================
# Front Matter 生成
# ============================================================================

def generate_front_matter(
    title: str | None = None,
    source: str | None = None,
    doc_type: str = "doc",
    created: str | None = None,
    modified: str | None = None,
    revision: int | None = None,
    fetched_date: str | None = None,
    trailing_newlines: int = 2,
) -> str:
    """生成 YAML Front Matter

    Args:
        title: 文档标题
        source: 文档在线链接
        doc_type: 文档类型 ("doc" 或 "sheet")
        created: 创建时间 (YYYY-MM-DD)
        modified: 修改时间 (YYYY-MM-DD)
        revision: 版本号
        fetched_date: 获取日期，默认为当前日期
        trailing_newlines: 结尾换行数 (默认 2)

    Returns:
        YAML Front Matter 字符串
    """
    lines = ["---"]

    if title:
        lines.append(f"title: {title}")
    if source:
        lines.append(f"source: {source}")
    lines.append(f"type: {doc_type}")

    if created:
        lines.append(f"created: {created}")
    if modified:
        lines.append(f"modified: {modified}")

    fetched = fetched_date or datetime.now().strftime('%Y-%m-%d')
    lines.append(f"fetched: {fetched}")

    if revision is not None:
        lines.append(f"revision: {revision}")

    lines.append("---")

    return "\n".join(lines) + "\n" * trailing_newlines


def generate_sheet_front_matter(
    metadata: dict | None = None,
    page_url: str | None = None,
    title_getter: Callable[[], str | None] | None = None,
) -> str:
    """生成表格文档的 Front Matter (便捷函数)

    Args:
        metadata: 元数据字典，可包含 title, created, modified, revision, source
        page_url: 文档在线链接
        title_getter: 可选的标题获取函数，用于回退
    """
    metadata = metadata or {}

    # 获取标题，支持回退
    title = metadata.get("title")
    if not title and title_getter:
        title = title_getter()

    # source 优先使用 metadata 中的 source， 否则使用 page_url
    source = metadata.get("source") or page_url

    return generate_front_matter(
        title=title,
        source=source,
        doc_type="sheet",
        created=metadata.get("created"),
        modified=metadata.get("modified"),
        revision=metadata.get("revision"),
    )
