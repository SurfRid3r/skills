#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
格式解析器 - 从 intermediate.json 解析为语义化文档结构

基于腾讯文档控制字符分析，将 mutations 转换为语义化的文档结构。
这是两步流水线的第二步：intermediate.json -> result.json
"""

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# 导入控制字符定义和样式定义
try:
    from .enums import ControlChars
    from .style_definitions import (
        STYLE_DEFINITIONS,
        get_heading_level,
        is_heading_style,
        get_style_name
    )
except ImportError:
    from enums import ControlChars
    from style_definitions import (
        STYLE_DEFINITIONS,
        get_heading_level,
        is_heading_style,
        get_style_name
    )


# =============================================================================
# 数据结构定义
# =============================================================================

@dataclass
class InlineFormat:
    """内联格式（如超链接）"""
    type: str
    start: int
    end: int
    url: str = ""


@dataclass
class TableData:
    """表格数据"""
    headers: list[str]
    rows: list[list[str]]


@dataclass
class Section:
    """语义化章节"""
    type: str
    content: str
    level: Optional[int] = None
    list_type: Optional[str] = None
    inline_formats: list[InlineFormat] = field(default_factory=list)
    image_info: Optional[dict[str, Any]] = None
    table_data: Optional[TableData] = None
    mutations: list[int] = field(default_factory=list)


@dataclass
class Document:
    """语义化文档"""
    sections: list[Section]

    def to_dict(self) -> dict:
        return {
            "version": 2,
            "document": {
                "sections": [self._section_to_dict(s) for s in self.sections]
            }
        }

    def _section_to_dict(self, section: Section) -> dict:
        result = {"type": section.type, "content": section.content}

        if section.level is not None:
            result["level"] = section.level
        if section.list_type is not None:
            result["list_type"] = section.list_type
        if section.inline_formats:
            result["inline_formats"] = [
                {"type": f.type, "start": f.start, "end": f.end, "url": f.url}
                for f in section.inline_formats
            ]
        if section.image_info:
            result["image_info"] = section.image_info
        if section.table_data:
            result["table_data"] = {
                "headers": section.table_data.headers,
                "rows": section.table_data.rows
            }
        if section.mutations:
            result["mutations"] = section.mutations

        return result


# =============================================================================
# 格式解析器
# =============================================================================

class FormatParser:
    """格式解析器 - 从 intermediate.json 解析出语义化的文档结构"""

    def __init__(self, intermediate_data: dict):
        self.data = intermediate_data
        self.mutations = intermediate_data.get("mutations", [])
        self.text = ""
        self.images = []
        self.position = 0
        self.style_map = {}
        self.comment_ranges = []
        self.textbox_styles: dict[int, str] = {}  # 位置 → style_id
        self._textbox_ranges: list[tuple[int, int]] = []  # 文本框区域范围
        self.style_definitions = intermediate_data.get("style_definitions", {})
        # 文本框视觉位置映射
        self.textbox_mappings: list[dict] = intermediate_data.get("textbox_mappings", [])
        # content_style_id → 内容位置范围列表
        self._textbox_content_ranges: dict[str, list[tuple[int, int]]] = {}
        self._build_style_map()

    def parse(self) -> Document:
        """解析文档"""
        self._extract_initial_text()
        self._collect_image_positions()
        self._collect_comment_ranges()
        self._collect_textbox_styles()
        self._collect_textbox_content_ranges()
        self._textbox_ranges = self._collect_textbox_ranges()
        sections = self._parse_sections()
        return Document(sections=sections)

    def _build_style_map(self):
        """构建位置到标题级别的映射"""
        # 使用已解析的样式定义
        style_definitions = self.style_definitions

        for mut in self.mutations:
            if mut.get("ty_code") == 3 and mut.get("status_code") == 102:
                # 优先使用 heading_level（如果存在）
                heading_level = mut.get("heading_level")
                if heading_level is None:
                    # 从 style_id 查找样式定义
                    style_id = mut.get("style_id")
                    if style_id:
                        style_def = style_definitions.get(style_id, {})
                        outline_lvl = style_def.get("outline_lvl")
                        if outline_lvl is not None:
                            heading_level = outline_lvl + 1  # outline_lvl 从 0 开始，heading level 从 1 开始

                if heading_level is not None:
                    # 使用 bi 作为键（段落开始位置），因为段落结束时 ei 可能指向下一个段落
                    self.style_map[mut.get("bi", 0)] = heading_level

    def _extract_initial_text(self):
        """提取初始文本"""
        for mut in self.mutations:
            if mut.get("ty_code") == 1 and mut.get("s"):
                self.text = mut["s"]
                break
        if not self.text:
            self.text = ""

    def _collect_image_positions(self):
        """收集图片位置信息，排除评论头像"""
        COMMENT_STORY_PROPERTY = 108  # ModifyType.COMMENT_STORY_PROPERTY

        self.images = [
            (mut.get("bi", 0), idx, mut["image_info"])
            for idx, mut in enumerate(self.mutations)
            if mut.get("image_info") and mut.get("status_code") != COMMENT_STORY_PROPERTY
        ]
        self.images.sort(key=lambda x: x[0])

    def _collect_comment_ranges(self):
        """收集评论区域范围，用于过滤评论内容"""
        COMMENT_STORY_PROPERTY = 108

        comment_muts = [
            m for m in self.mutations
            if m.get("status_code") == COMMENT_STORY_PROPERTY
        ]

        if not comment_muts:
            self.comment_ranges = []
            return

        # 计算评论区域
        bis = [m["bi"] for m in comment_muts if m.get("bi") is not None]
        eis = [m["ei"] for m in comment_muts if m.get("ei") is not None]

        if not bis or not eis:
            self.comment_ranges = []
            return

        # 评论区域开始 = min(bi) 之前的 \x0f 位置
        content_start = min(bis)
        comment_start = content_start
        for i in range(content_start - 1, max(0, content_start - 20), -1):
            if i < len(self.text) and ord(self.text[i]) == ControlChars.CODE_BLOCK_START:
                comment_start = i
                break

        # 评论区域结束 = max(ei)
        comment_end = max(eis)

        # 检查评论区域结束位置后面是否紧跟文本框开始标记 \x1d\x1e\x1c
        # 如果是，需要将结束位置调整到文本框开始之前
        if comment_end > 0 and comment_end - 1 < len(self.text):
            # 检查 comment_end - 1 是否是 \x1d，后面跟着 \x1e\x1c
            check_pos = comment_end - 1
            if (ord(self.text[check_pos]) == ControlChars.CODE_BLOCK_END and
                check_pos + 2 < len(self.text) and
                ord(self.text[check_pos + 1]) == ControlChars.RECORD_SEP and
                ord(self.text[check_pos + 2]) == ControlChars.PICTURE_MARKER):
                # 文本框开始，调整结束位置
                comment_end = check_pos

        self.comment_ranges = [(comment_start, comment_end)]

    def _is_in_comment_range(self, pos: int) -> bool:
        """检查位置是否在评论区域内"""
        for start, end in self.comment_ranges:
            if start <= pos < end:
                return True
        return False

    def _collect_textbox_styles(self):
        """收集 TEXTBOX_STORY_PROPERTY 的 style_id，用于识别不同元素"""
        TEXTBOX_STORY_PROPERTY = 109  # ModifyType.TEXTBOX_STORY_PROPERTY

        for m in self.mutations:
            if m.get("status_code") == TEXTBOX_STORY_PROPERTY:
                bi = m.get("bi", 0)
                style_id = m.get("style_id")
                if style_id and bi is not None:
                    self.textbox_styles[bi] = style_id

    def _collect_textbox_content_ranges(self):
        """收集每个 content_style_id 对应的内容位置范围

        从 TEXTBOX_STORY_PROPERTY (109) mutations 中收集：
        - content_style_id: 内容样式ID
        - bi, ei: 内容位置范围

        计算每个 style_id 的完整内容区域（向前查找 \x0f 开始标记）
        """
        TEXTBOX_STORY_PROPERTY = 109

        # 先收集所有单独的范围
        temp_ranges: dict[str, list[tuple[int, int]]] = {}
        for m in self.mutations:
            if m.get("status_code") != TEXTBOX_STORY_PROPERTY:
                continue

            style_id = m.get("style_id")
            bi = m.get("bi")
            ei = m.get("ei")

            if style_id and bi is not None and ei is not None:
                if style_id not in temp_ranges:
                    temp_ranges[style_id] = []
                temp_ranges[style_id].append((bi, ei))

        # 计算每个 style_id 的完整内容区域
        for style_id, ranges in temp_ranges.items():
            if ranges:
                min_bi = min(r[0] for r in ranges)
                max_ei = max(r[1] for r in ranges)

                # 向前查找 \x0f 开始标记
                start = min_bi
                while start > 0:
                    prev_code = ord(self.text[start - 1])
                    if prev_code == ControlChars.CODE_BLOCK_START:
                        start -= 1  # 包含 \x0f
                        break
                    if prev_code >= 32 and prev_code not in (0x1e, 0x1d, 0x1c, 0x0d):
                        break
                    start -= 1

                # 存储完整范围
                self._textbox_content_ranges[style_id] = [(start, max_ei)]

    def _collect_textbox_ranges(self) -> list[tuple[int, int]]:
        """收集文本框区域范围

        文本框格式：
        - 开始标记: \x1d\x1e\x1c
        - 行格式: \x1d\x1c + 内容 + \r
        - 结束: 直到下一个非文本框控制字符

        Returns:
            [(start_pos, end_pos), ...] 文本框区域列表
        """
        TEXTBOX_STORY_PROPERTY = 109

        # 收集所有 TEXTBOX_STORY_PROPERTY mutations
        textbox_muts = [
            m for m in self.mutations
            if m.get("status_code") == TEXTBOX_STORY_PROPERTY
        ]

        if not textbox_muts:
            return []

        # 找到所有 \x1d\x1e\x1c 序列（文本框开始标记）
        ranges = []
        i = 0
        while i < len(self.text) - 2:
            # 检查文本框开始标记: \x1d\x1e\x1c
            if (ord(self.text[i]) == ControlChars.CODE_BLOCK_END and
                ord(self.text[i + 1]) == ControlChars.RECORD_SEP and
                ord(self.text[i + 2]) == ControlChars.PICTURE_MARKER):

                start_pos = i
                pos = i + 3

                # 找到文本框结束位置
                while pos < len(self.text):
                    code = ord(self.text[pos])

                    # 检查是否是下一个文本框开始
                    if (code == ControlChars.CODE_BLOCK_END and
                        pos + 2 < len(self.text) and
                        ord(self.text[pos + 1]) == ControlChars.RECORD_SEP and
                        ord(self.text[pos + 2]) == ControlChars.PICTURE_MARKER):
                        # 新的文本框开始，当前文本框结束
                        break

                    # 检查是否是标准代码块开始或其他特殊标记
                    if code == ControlChars.CODE_BLOCK_START:
                        break

                    # 检查是否是段落分隔 + 新块标记（非文本框）
                    if (code == ControlChars.PARAGRAPH_SEP and
                        pos + 1 < len(self.text)):
                        next_code = ord(self.text[pos + 1])
                        # 如果下一个字符不是 \x1d\x1c，可能结束了
                        if next_code != ControlChars.CODE_BLOCK_END:
                            # 继续检查是否还有文本框内容
                            pass

                    pos += 1

                ranges.append((start_pos, pos))
                i = pos
            else:
                i += 1

        return ranges

    def _is_in_textbox_range(self, pos: int) -> bool:
        """检查位置是否在文本框区域内"""
        for start, end in self._textbox_ranges:
            if start <= pos < end:
                return True
        return False

    def _is_in_textbox_content_area(self, pos: int) -> bool:
        """检查位置是否在文本框内容区域内（用于跳过重复输出）"""
        for ranges in self._textbox_content_ranges.values():
            for start, end in ranges:
                if start <= pos < end:
                    return True
        return False

    def _extract_textbox_content(self, content_style_id: str, is_code_block: bool = True) -> Optional[Section]:
        """根据 content_style_id 提取文本框内容

        文本框内容位置通过 TEXTBOX_STORY_PROPERTY mutations 确定。
        内容格式与文本框区域相同：\x1d\x1e\x1c 或 \x0f 开头

        Args:
            content_style_id: 内容样式ID
            is_code_block: True 表示代码块，False 表示普通文本框
        """
        ranges = self._textbox_content_ranges.get(content_style_id, [])
        if not ranges:
            return None

        # 计算内容区域
        min_bi = min(r[0] for r in ranges)
        max_ei = max(r[1] for r in ranges)

        if min_bi >= len(self.text):
            return None

        # 提取该区域的内容
        content_part = self.text[min_bi:max_ei]

        # 解析文本框格式
        lines = []
        i = 0
        while i < len(content_part):
            code = ord(content_part[i]) if i < len(content_part) else 0

            # 跳过控制字符
            if code == ControlChars.CODE_BLOCK_START:  # \x0f
                i += 1
                # 跳过 RECORD_SEP 填充
                while i < len(content_part) and ord(content_part[i]) == ControlChars.RECORD_SEP:
                    i += 1
                continue

            if code == ControlChars.CODE_BLOCK_END:  # \x1d
                i += 1
                # 检查 \x1e\x1c 或 \x1c
                if i < len(content_part) and ord(content_part[i]) == ControlChars.RECORD_SEP:
                    i += 1
                if i < len(content_part) and ord(content_part[i]) == ControlChars.PICTURE_MARKER:
                    i += 1
                continue

            if code == ControlChars.PICTURE_MARKER:  # \x1c
                i += 1
                # 收集行内容直到 \r 或 \x1d
                line_chars = []
                while i < len(content_part):
                    c = content_part[i]
                    c_code = ord(c)
                    if c_code == ControlChars.PARAGRAPH_SEP:  # \r
                        i += 1
                        break
                    if c_code == ControlChars.CODE_BLOCK_END:  # \x1d
                        break
                    if c_code >= 32 or c == '\t':
                        line_chars.append(c)
                    i += 1
                if line_chars:
                    lines.append(''.join(line_chars))
                continue

            if code == ControlChars.RECORD_SEP:  # \x1e
                i += 1
                continue

            if code == ControlChars.PARAGRAPH_SEP:  # \r
                i += 1
                continue

            # 普通字符
            if code >= 32 or code == 9:  # 可打印字符或 \t
                line_chars = []
                while i < len(content_part):
                    c = content_part[i]
                    c_code = ord(c)
                    if c_code == ControlChars.PARAGRAPH_SEP:  # \r
                        i += 1
                        break
                    if c_code in (ControlChars.CODE_BLOCK_END, ControlChars.PICTURE_MARKER):
                        break
                    if c_code >= 32 or c_code == 9:
                        line_chars.append(c)
                    i += 1
                if line_chars:
                    lines.append(''.join(line_chars))
                continue

            i += 1

        if not lines:
            return None

        content = '\n'.join(lines)
        # 根据 is_code_block 返回不同类型的 Section
        section_type = "code_block" if is_code_block else "paragraph"
        return Section(type=section_type, content=content)

    def _parse_textbox_block(self, skip_header: bool = True) -> Optional[Section]:
        """解析文本框内容

        文本框格式与标准代码块类似：
        - 首块开始: \x1d\x1e\x1c
        - 子块开始: \x1d\x1c (独立块分隔符)
        - 行格式: 内容 + \r

        Args:
            skip_header: True 表示跳过 \x1d\x1e\x1c (首块)，False 表示跳过 \x1d\x1c (子块)

        Returns:
            Section(type="code_block", content=...)
        """
        if skip_header:
            self.position += 3  # 跳过 \x1d\x1e\x1c
        else:
            self.position += 2  # 跳过 \x1d\x1c

        lines = []

        while self.position < len(self.text):
            code = ord(self.text[self.position])

            # 检查是否是行开始标记 \x1d\x1c (作为子块分隔符)
            if (code == ControlChars.CODE_BLOCK_END and
                self.position + 1 < len(self.text) and
                ord(self.text[self.position + 1]) == ControlChars.PICTURE_MARKER):

                # 检查是否是新文本框开始 \x1d\x1e\x1c
                if (self.position + 2 < len(self.text) and
                    ord(self.text[self.position + 2]) == ControlChars.RECORD_SEP):
                    break  # 新文本框开始，结束当前块

                # \x1d\x1c 是子块分隔符，跳过并继续收集内容
                self.position += 2
                continue

            # 检查是否是标准行格式 \x1c + 内容
            if code == ControlChars.PICTURE_MARKER:
                self.position += 1

                # 收集行内容
                line_content = []
                while self.position < len(self.text):
                    c = self.text[self.position]
                    c_code = ord(c)

                    if c_code == ControlChars.PARAGRAPH_SEP:
                        self.position += 1
                        break

                    # 检查是否遇到 \x1d\x1c 或 \x1d\x1e\x1c
                    if (c_code == ControlChars.CODE_BLOCK_END and
                        self.position + 1 < len(self.text) and
                        ord(self.text[self.position + 1]) == ControlChars.PICTURE_MARKER):
                        break

                    line_content.append(c)
                    self.position += 1

                line_text = ''.join(c for c in line_content if ord(c) >= 32 or c == '\t')
                if line_text:
                    lines.append(line_text)
                continue

            # 检查是否到达文本框结束
            if code == ControlChars.CODE_BLOCK_START:
                break

            # 检查是否是新的文本框开始 \x1d\x1e\x1c
            if (code == ControlChars.CODE_BLOCK_END and
                self.position + 2 < len(self.text) and
                ord(self.text[self.position + 1]) == ControlChars.RECORD_SEP and
                ord(self.text[self.position + 2]) == ControlChars.PICTURE_MARKER):
                break

            # 跳过其他控制字符
            if code < 32 and code not in (9, 10):
                self.position += 1
                continue

            # 普通文本 - 收集行内容
            line_content = []
            while self.position < len(self.text):
                c = self.text[self.position]
                c_code = ord(c)

                if c_code == ControlChars.PARAGRAPH_SEP:
                    self.position += 1
                    break

                # 检查是否遇到 \x1d\x1c 或 \x1d\x1e\x1c
                if (c_code == ControlChars.CODE_BLOCK_END and
                    self.position + 1 < len(self.text) and
                    ord(self.text[self.position + 1]) == ControlChars.PICTURE_MARKER):
                    break

                line_content.append(c)
                self.position += 1

            line_text = ''.join(c for c in line_content if ord(c) >= 32 or c == '\t')
            if line_text:
                lines.append(line_text)

        if not lines:
            return None

        content = '\n'.join(lines)
        return Section(type="code_block", content=content)

    def _skip_hyperlink(self):
        """跳过 HYPERLINK 控制字符序列

        HYPERLINK 格式: \x13HYPERLINK <URL> <params>\x14<显示文本>\x15
        """
        self.position += 1  # 跳过 HYPERLINK_START (0x13)

        while self.position < len(self.text):
            code = ord(self.text[self.position])
            if code == ControlChars.HYPERLINK_END:
                self.position += 1
                return
            self.position += 1

    def _parse_hyperlink_paragraph(self) -> Optional[Section]:
        """解析独立的 HYPERLINK 段落"""
        hl_info = self._parse_hyperlink()
        if hl_info:
            display_text = hl_info["display_text"]
            url = hl_info["url"]
            if display_text and url:
                inline_format = InlineFormat(
                    type="hyperlink",
                    start=0,
                    end=len(display_text),
                    url=url
                )
                return Section(
                    type="paragraph",
                    content=display_text,
                    inline_formats=[inline_format]
                )
        return None

    def _parse_sections(self) -> list[Section]:
        """解析控制字符，构建 sections"""
        sections = []
        self.position = 0
        image_idx = 0
        max_iterations = len(self.text) * 2

        # 按视觉位置排序的文本框映射
        sorted_textbox_mappings = sorted(self.textbox_mappings, key=lambda x: x["visual_bi"])
        textbox_idx = 0

        for _ in range(max_iterations):
            if self.position >= len(self.text):
                break

            # 插入图片
            while image_idx < len(self.images) and self.images[image_idx][0] <= self.position:
                _, img_mut_idx, img_info = self.images[image_idx]
                sections.append(Section(type="image", content="", image_info=img_info, mutations=[img_mut_idx]))
                image_idx += 1

            # 在视觉位置插入文本框
            while (textbox_idx < len(sorted_textbox_mappings) and
                   sorted_textbox_mappings[textbox_idx]["visual_bi"] <= self.position):
                mapping = sorted_textbox_mappings[textbox_idx]
                content_style_id = mapping["content_style_id"]
                is_code_block = mapping.get("is_code_block", True)
                textbox_section = self._extract_textbox_content(content_style_id, is_code_block)
                if textbox_section:
                    sections.append(textbox_section)
                textbox_idx += 1

            char = self.text[self.position]
            code = ord(char)

            # 检测文本框开始: \x1d\x1e\x1c 或 \x1d\x1c
            # 如果在文本框内容区域内，跳过整个区域（已经在视觉位置插入）
            if code == ControlChars.CODE_BLOCK_END:
                # 检查是否在文本框内容区域
                if self._is_in_textbox_content_area(self.position):
                    # 跳过整个文本框内容区域
                    for ranges in self._textbox_content_ranges.values():
                        for start, end in ranges:
                            if start <= self.position < end:
                                self.position = end
                                break
                    continue

                if (self.position + 2 < len(self.text) and
                    ord(self.text[self.position + 1]) == ControlChars.RECORD_SEP and
                    ord(self.text[self.position + 2]) == ControlChars.PICTURE_MARKER):
                    # \x1d\x1e\x1c 文本框开始
                    section = self._parse_textbox_block(skip_header=True)
                    if section:
                        sections.append(section)
                    continue

                if (self.position + 1 < len(self.text) and
                    ord(self.text[self.position + 1]) == ControlChars.PICTURE_MARKER and
                    (self.position + 2 >= len(self.text) or
                     ord(self.text[self.position + 2]) != ControlChars.RECORD_SEP)):
                    # \x1d\x1c 文本框子块
                    section = self._parse_textbox_block(skip_header=False)
                    if section:
                        sections.append(section)
                    continue

                self.position += 1
                continue

            if code == ControlChars.CODE_BLOCK_START:
                # 检查是否是评论区域或文本框内容区域
                if self._is_in_comment_range(self.position):
                    # 跳过整个评论区域
                    for start, end in self.comment_ranges:
                        if start <= self.position < end:
                            self.position = end
                            break
                    continue
                if self._is_in_textbox_content_area(self.position):
                    # 跳过文本框内容区域
                    for ranges in self._textbox_content_ranges.values():
                        for start, end in ranges:
                            if start <= self.position < end:
                                self.position = end
                                break
                    continue
                section = self._parse_code_block()
                if section:
                    sections.append(section)
            elif code == ControlChars.LIST_MARKER:
                section = self._parse_list()
                if section:
                    sections.append(section)
            elif code == ControlChars.AUTHOR_FIELD_PREFIX:  # 0x1a - 表格开始
                section = self._parse_table()
                if section:
                    sections.append(section)
            elif code == ControlChars.TABLE_MARKER:
                self.position += 1
            elif code == ControlChars.HYPERLINK_START:
                # HYPERLINK 作为独立段落处理
                section = self._parse_hyperlink_paragraph()
                if section:
                    sections.append(section)
            elif code in (ControlChars.PARAGRAPH_SEP, ControlChars.RECORD_SEP, ControlChars.PICTURE_MARKER):
                self.position += 1
            elif code < 32 and code not in (9, 10):
                self.position += 1
            else:
                section = self._parse_paragraph()
                if section:
                    sections.append(section)

        # 插入剩余的图片
        while image_idx < len(self.images):
            _, img_mut_idx, img_info = self.images[image_idx]
            sections.append(Section(type="image", content="", image_info=img_info, mutations=[img_mut_idx]))
            image_idx += 1

        # 插入剩余的文本框
        while textbox_idx < len(sorted_textbox_mappings):
            mapping = sorted_textbox_mappings[textbox_idx]
            content_style_id = mapping["content_style_id"]
            is_code_block = mapping.get("is_code_block", True)
            textbox_section = self._extract_textbox_content(content_style_id, is_code_block)
            if textbox_section:
                sections.append(textbox_section)
            textbox_idx += 1

        return sections

    def _parse_code_block(self) -> Optional[Section]:
        """
        解析代码块

        格式:
        0x0f (CODE_BLOCK_START)
        0x1e×N (RECORD_SEP 填充, 5-6个)
        [行1] 0x1c + 内容 + 0x0d + 0x1d
        [行2] 0x1c + 内容 + 0x0d + 0x1d
        ...
        0x1e×N (可选的末尾填充)
        """
        start_pos = self.position
        self.position += 1  # 跳过 CODE_BLOCK_START

        # 跳过开头的 RECORD_SEP 填充
        while (self.position < len(self.text) and
               ord(self.text[self.position]) == ControlChars.RECORD_SEP):
            self.position += 1

        # 收集所有行内容
        lines = []
        current_style: Optional[str] = None  # 当前代码块的 style_id

        while self.position < len(self.text):
            code = ord(self.text[self.position])

            # 检查是否到达代码块结束 (连续的 RECORD_SEP 或其他非代码块标记)
            if code == ControlChars.RECORD_SEP:
                # 检查是否是连续的 RECORD_SEP (代码块结束标记)
                next_pos = self.position + 1
                if (next_pos < len(self.text) and
                    ord(self.text[next_pos]) == ControlChars.RECORD_SEP):
                    # 到达代码块末尾，跳过剩余的填充
                    while (self.position < len(self.text) and
                           ord(self.text[self.position]) == ControlChars.RECORD_SEP):
                        self.position += 1
                    break
                self.position += 1
                continue

            # 行标记 0x1c
            if code == ControlChars.PICTURE_MARKER:
                line_start = self.position
                self.position += 1

                # 检查 style_id 变化
                line_style = self.textbox_styles.get(line_start)
                if current_style is None:
                    current_style = line_style
                elif line_style and line_style != current_style:
                    # style_id 变化，结束当前代码块
                    self.position = line_start  # 回退，让主循环处理后续内容
                    break

                # 收集行内容直到 0x1d
                line_content = []
                while self.position < len(self.text):
                    c = self.text[self.position]
                    c_code = ord(c)
                    if c_code == ControlChars.CODE_BLOCK_END:
                        self.position += 1
                        break
                    line_content.append(c)
                    self.position += 1
                # 过滤控制字符
                line_text = ''.join(c for c in line_content if ord(c) >= 32 or c == '\t')
                if line_text:
                    lines.append(line_text)
                continue

            # 其他非代码块字符，结束解析
            if code not in (ControlChars.PARAGRAPH_SEP, ControlChars.CODE_BLOCK_END):
                break

            self.position += 1

        # 合并行内容
        content = '\n'.join(lines)
        return Section(type="code_block", content=content)

    def _parse_list(self) -> Optional[Section]:
        """解析列表"""
        self.position += 1  # 跳过 LIST_MARKER

        if self.position >= len(self.text):
            return None

        # 检查下一个字符 - 如果是控制字符，则不是有效列表
        next_code = ord(self.text[self.position])
        if next_code < 32:
            return None

        marker_char = self.text[self.position]
        self.position += 1

        list_type = "bullet" if marker_char == '-' else "numbering" if marker_char == '8' else "bullet"

        content_start = self.position
        while self.position < len(self.text) and ord(self.text[self.position]) != ControlChars.PARAGRAPH_SEP:
            self.position += 1

        content = self.text[content_start:self.position].strip()

        # 过滤控制字符（如 AUTHOR_FIELD_PREFIX）
        content = ''.join(c for c in content if ord(c) >= 32)

        if not content:
            return None

        return Section(type="list", content=content, list_type=list_type)

    def _parse_table(self) -> Optional[Section]:
        """
        解析表格

        实际格式:
        \x1a <cell1> \r \x07 <cell2> \r \x07 <cell3> \r
        \x07 \x06 <cell1> \r \x07 <cell2> \r ... \x1b

        控制字符:
        - 0x1a (AUTHOR_FIELD_PREFIX): 表格开始
        - 0x07 (TABLE_MARKER): 列分隔符
        - 0x06 (AUTHOR_FIELD_VALUE): 行开始标记
        - 0x0d (PARAGRAPH_SEP): 单元格内容结束
        - 0x1b (COMPARISON_MARKER): 表格结束
        """
        start_pos = self.position

        # 检查是否是 AUTHOR_FIELD_PREFIX (表格开始)
        if ord(self.text[self.position]) != ControlChars.AUTHOR_FIELD_PREFIX:
            return None
        self.position += 1

        # 解析表头行（没有 0x06 前缀）
        headers = self._parse_table_row()

        if not headers:
            self.position = start_pos
            return None

        # 解析数据行（每行以 0x07 0x06 开始）
        rows = []
        while self.position < len(self.text):
            code = ord(self.text[self.position])

            # 检查表格结束 (0x1b)
            if code == ControlChars.COMPARISON_MARKER:
                self.position += 1
                break

            # 检查新行开始 (0x07 0x06)
            if code == ControlChars.TABLE_MARKER:
                self.position += 1
                if (self.position < len(self.text) and
                    ord(self.text[self.position]) == ControlChars.AUTHOR_FIELD_VALUE):
                    self.position += 1
                    row = self._parse_table_row()
                    if row:
                        # 填充行以匹配列数
                        while len(row) < len(headers):
                            row.append("")
                        rows.append(row[:len(headers)])
                continue

            # 未知字符，可能是表格结束
            if code < 32 and code not in (ControlChars.TABLE_MARKER, ControlChars.PARAGRAPH_SEP):
                break

            self.position += 1

        return Section(
            type="table",
            content="",
            table_data=TableData(headers=headers, rows=rows)
        )

    def _parse_table_row(self) -> list[str]:
        """解析单个表格行，返回单元格内容列表"""
        cells = []
        current_cell = []

        while self.position < len(self.text):
            code = ord(self.text[self.position])

            if code == ControlChars.PARAGRAPH_SEP:
                # 单元格内容结束
                cells.append(''.join(current_cell).strip())
                current_cell = []
                self.position += 1
            elif code == ControlChars.TABLE_MARKER:
                # 检查是否是行标记 (0x07 0x06) - 表示当前行结束
                if (self.position + 1 < len(self.text) and
                    ord(self.text[self.position + 1]) == ControlChars.AUTHOR_FIELD_VALUE):
                    # 保存当前单元格，但不消耗 TABLE_MARKER
                    if current_cell:
                        cells.append(''.join(current_cell).strip())
                    break
                # 列分隔符 - 保存单元格并继续
                if current_cell:
                    cells.append(''.join(current_cell).strip())
                    current_cell = []
                self.position += 1
            elif code == ControlChars.COMPARISON_MARKER:
                # 表格结束
                if current_cell:
                    cells.append(''.join(current_cell).strip())
                break
            elif code == ControlChars.AUTHOR_FIELD_VALUE:
                # 没有先出现 TABLE_MARKER 的行标记 - 行结束
                break
            else:
                current_cell.append(self.text[self.position])
                self.position += 1

        if current_cell:
            cells.append(''.join(current_cell).strip())

        return cells

    def _parse_paragraph(self) -> Optional[Section]:
        """解析段落，包含 HYPERLINK 处理"""
        content_parts = []
        inline_formats = []
        current_pos = 0

        while self.position < len(self.text):
            char = self.text[self.position]
            code = ord(char)

            # 检查段落结束条件
            if code in (ControlChars.PARAGRAPH_SEP, ControlChars.CODE_BLOCK_START,
                        ControlChars.LIST_MARKER, ControlChars.TABLE_MARKER):
                break
            if code < 32 and code not in (9, 10):
                break

            # 处理 HYPERLINK
            if code == ControlChars.HYPERLINK_START:
                hl_info = self._parse_hyperlink()
                if hl_info:
                    display_text = hl_info["display_text"]
                    url = hl_info["url"]
                    if display_text:
                        # 记录 inline format
                        inline_formats.append(InlineFormat(
                            type="hyperlink",
                            start=current_pos,
                            end=current_pos + len(display_text),
                            url=url
                        ))
                        content_parts.append(display_text)
                        current_pos += len(display_text)
                continue

            # 普通字符
            content_parts.append(char)
            current_pos += 1
            self.position += 1

        content = ''.join(content_parts).strip()
        if not content:
            return None

        # 检查是否有段落级别
        level = self.style_map.get(self.position) or self.style_map.get(self.position + 1)
        if level:
            return Section(type="heading", content=content, level=level, inline_formats=inline_formats)

        return Section(type="paragraph", content=content, inline_formats=inline_formats)

    def _parse_hyperlink(self) -> Optional[dict]:
        """解析 HYPERLINK 控制字符序列

        格式: \x13HYPERLINK <URL> <params>\x14<显示文本>\x15
        带引号格式: \x13HYPERLINK "URL" \t "target"\x14<显示文本>\x15
        """
        start_pos = self.position
        self.position += 1  # 跳过 HYPERLINK_START

        if self.position + 9 > len(self.text):
            self.position = start_pos
            return None

        if not self.text[self.position:self.position + 9].startswith("HYPERLINK"):
            self.position = start_pos
            return None

        self.position += 9  # 跳过 "HYPERLINK"

        url_start = self.position
        while self.position < len(self.text):
            if ord(self.text[self.position]) == ControlChars.HYPERLINK_URL_SEP:
                url_part = self.text[url_start:self.position].strip()
                self.position += 1

                # 提取 URL：处理带引号和不带引号的情况
                if url_part.startswith('"') and '"' in url_part[1:]:
                    # 带引号的 URL
                    end_quote = url_part.index('"', 1)
                    url = url_part[1:end_quote]
                else:
                    # 不带引号的 URL，取第一部分
                    url = url_part.split(None, 1)[0] if url_part else url_part

                display_start = self.position
                while self.position < len(self.text):
                    if ord(self.text[self.position]) == ControlChars.HYPERLINK_END:
                        display_text = self.text[display_start:self.position]
                        self.position += 1
                        return {"url": url, "display_text": display_text}
                    self.position += 1
                break
            self.position += 1

        self.position = start_pos
        return None


# =============================================================================
# 主函数
# =============================================================================

# =============================================================================
# API 函数 (供 convert.py 调用)
# =============================================================================

def parse_format(input_file: str, output_file: str, verbose: bool = False) -> str:
    """
    解析 intermediate.json 文件

    Args:
        input_file: intermediate.json 文件路径
        output_file: 输出的 result.json 文件路径
        verbose: 是否显示详细信息

    Returns:
        输出的 result.json 文件路径
    """
    input_path = Path(input_file)
    output_path = Path(output_file)

    with open(input_path, 'r', encoding='utf-8') as f:
        intermediate_data = json.load(f)

    if verbose:
        print(f"  Mutation 数量: {intermediate_data.get('mutations_count', 0)}")
        print(f"  图片数量: {intermediate_data.get('image_count', 0)}")

    format_parser = FormatParser(intermediate_data)
    document = format_parser.parse()

    result = document.to_dict()
    result["source"] = f"Generated from {input_path.name}"

    if verbose:
        sections = document.sections
        print(f"  段落: {sum(1 for s in sections if s.type == 'paragraph')}")
        print(f"  列表: {sum(1 for s in sections if s.type == 'list')}")
        print(f"  代码块: {sum(1 for s in sections if s.type == 'code_block')}")
        print(f"  图片: {sum(1 for s in sections if s.type == 'image')}")

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return str(output_path)


def main():
    """主函数"""
    import argparse

    arg_parser = argparse.ArgumentParser(description='格式解析器 - 从 intermediate.json 解析为语义化文档结构')
    arg_parser.add_argument('input', help='输入文件路径 (intermediate.json)')
    arg_parser.add_argument('-o', '--output', help='输出文件路径 (result.json)')
    arg_parser.add_argument('-v', '--verbose', action='store_true', help='显示详细信息')

    args = arg_parser.parse_args()
    input_path = Path(args.input)

    print("=" * 60)
    print("格式解析器 - intermediate.json -> result.json")
    print("=" * 60)
    print(f"输入: {input_path}")

    with open(input_path, 'r', encoding='utf-8') as f:
        intermediate_data = json.load(f)

    print(f"版本: {intermediate_data.get('version', 'unknown')}")
    print(f"Mutation 数量: {intermediate_data.get('mutations_count', 0)}")
    print(f"图片数量: {intermediate_data.get('image_count', 0)}")

    format_parser = FormatParser(intermediate_data)
    document = format_parser.parse()

    result = document.to_dict()
    result["source"] = f"Generated from {input_path.name}"

    sections = document.sections
    print(f"\n解析结果:")
    print(f"  总 sections: {len(sections)}")
    print(f"  段落: {sum(1 for s in sections if s.type == 'paragraph')}")
    print(f"  列表: {sum(1 for s in sections if s.type == 'list')}")
    print(f"  代码块: {sum(1 for s in sections if s.type == 'code_block')}")
    print(f"  图片: {sum(1 for s in sections if s.type == 'image')}")
    print(f"  表格: {sum(1 for s in sections if s.type == 'table')}")

    output_path = Path(args.output) if args.output else input_path.parent / "result.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n输出已保存: {output_path}")
    print(f"下一步: python3 scripts/to_markdown/main.py {output_path} -o output.md")


if __name__ == "__main__":
    main()
