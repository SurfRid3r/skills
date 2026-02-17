#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Markdown 生成器 - 从语义化文档结构生成 Markdown

简化版本，仅负责格式转换，不再处理位置重建和控制字符解析。
"""

import json
from pathlib import Path
from typing import Any


class TencentDocToMarkdown:
    """腾讯文档到 Markdown 转换器"""

    def __init__(self, result_json_path: str):
        self.result_path = Path(result_json_path)
        self.data: dict = {}

    def load(self):
        """加载数据"""
        with open(self.result_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

    def convert(self, page_url: str | None = None) -> str:
        """执行转换

        Args:
            page_url: 文档在线链接，用于生成 meta 信息
        """
        self.load()
        sections = self.data.get("document", {}).get("sections", [])
        content = self._sections_to_markdown(sections)

        if page_url:
            meta = f"---\npageUrl: {page_url}\n---\n\n"
            content = meta + content

        return content

    def _sections_to_markdown(self, sections: list[dict]) -> str:
        """将章节列表转换为 Markdown"""
        lines = []

        for section in sections:
            stype = section.get("type")

            if stype == "heading":
                level = section.get("level", 1)
                content = section.get("content", "")
                lines.append(f"{'#' * level} {content}")

            elif stype == "paragraph":
                content = self._apply_inline_formats(section)
                if content:
                    lines.append(content)

            elif stype == "list":
                list_type = section.get("list_type", "bullet")
                content = section.get("content", "")
                if content:  # 过滤空列表项
                    prefix = "- " if list_type == "bullet" else "1. "
                    lines.append(f"{prefix}{content}")

            elif stype == "code_block":
                content = section.get("content", "")
                lines.append("```")
                if content:
                    lines.append(content)
                lines.append("```")

            elif stype == "image":
                info = section.get("image_info", {})
                url = info.get("url", "")
                alt = info.get("caption", "image")
                width = info.get("width")
                height = info.get("height")
                if width and height:
                    alt += f" ({width}x{height})"
                lines.append(f"![{alt}]({url})")

            elif stype == "table":
                self._render_table(section, lines)

            lines.append("")

        # 移除末尾的空行
        while lines and not lines[-1].strip():
            lines.pop()

        return "\n".join(lines)

    def _render_table(self, section: dict, lines: list[str]):
        """渲染表格"""
        table_data = section.get("table_data", {})
        headers = table_data.get("headers", [])
        rows = table_data.get("rows", [])

        if not headers:
            return

        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

        for row in rows:
            while len(row) < len(headers):
                row.append("")
            lines.append("| " + " | ".join(row[:len(headers)]) + " |")

    def _apply_inline_formats(self, section: dict) -> str:
        """应用内联格式 (如超链接)"""
        content = section.get("content", "")
        inline_formats = section.get("inline_formats", [])

        if not inline_formats:
            return content

        # 按位置倒序排序，避免位置偏移
        sorted_formats = sorted(
            [f for f in inline_formats if f.get("type") == "hyperlink"],
            key=lambda x: x.get("start", 0),
            reverse=True
        )

        result = content
        for fmt in sorted_formats:
            start = fmt.get("start", 0)
            end = fmt.get("end", 0)
            url = fmt.get("url", "")

            if start < end and url:
                text = result[start:end]
                result = result[:start] + f"[{text}]({url})" + result[end:]

        return result

    def get_statistics(self) -> dict[str, Any]:
        """获取转换统计信息"""
        sections = self.data.get("document", {}).get("sections", [])

        return {
            "total_sections": len(sections),
            "heading_count": sum(1 for s in sections if s.get("type") == "heading"),
            "paragraph_count": sum(1 for s in sections if s.get("type") == "paragraph"),
            "list_count": sum(1 for s in sections if s.get("type") == "list"),
            "code_block_count": sum(1 for s in sections if s.get("type") == "code_block"),
            "image_count": sum(1 for s in sections if s.get("type") == "image"),
            "table_count": sum(1 for s in sections if s.get("type") == "table"),
            "hyperlink_count": sum(
                len(s.get("inline_formats", []))
                for s in sections
                if s.get("inline_formats")
            ),
            "images_list": [
                s.get("image_info", {})
                for s in sections
                if s.get("type") == "image" and s.get("image_info")
            ]
        }
