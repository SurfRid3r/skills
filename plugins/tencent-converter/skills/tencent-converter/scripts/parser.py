#!/usr/bin/env python3
"""
腾讯文档 ultrabuf Protobuf 解析器

基于 JS 源码深度分析实现的解析器，完整复用腾讯文档的 ultrabuf 解析逻辑。

核心原理:
1. initialAttributedText.text[0] 是 Base64 编码的 ultrabuf Protobuf 消息
2. ultrabuf 使用 UltrabufEntries.Command schema
3. Mutation 结构包含 ty, mt, mm, bi, ei, s, pr 字段
"""

import base64
import json
import re
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# 预编译的正则表达式
AUTHOR_USER_ID_PATTERN = re.compile(r'p\.(\d{17,})')
AUTHOR_TIMESTAMP_PATTERN = re.compile(r'(\d{13})')
AUTHOR_STYLE_ID_PATTERN = re.compile(r'\u0006([a-zA-Z0-9]{6})')

# 导入枚举值定义
try:
    from .enums import (
        MUTATION_TYPE_MAP, RANGE_TYPE_MAP, ControlChars,
        MODIFY_TYPE_MAP, MODIFY_STYLE_TYPE_MAP,
        PARAGRAPH_ALIGNMENT_MAP, FontVariant,
        MutationTarget
    )
except ImportError:
    from enums import (
        MUTATION_TYPE_MAP, RANGE_TYPE_MAP, ControlChars,
        MODIFY_TYPE_MAP, MODIFY_STYLE_TYPE_MAP,
        PARAGRAPH_ALIGNMENT_MAP, FontVariant,
        MutationTarget
    )


# =============================================================================
# Protobuf 解析核心
# =============================================================================

def decode_varint(data: bytes, offset: int) -> tuple[int, int]:
    """解码 varint，返回 (值, 新偏移量)"""
    result = 0
    shift = 0

    while offset < len(data):
        byte = data[offset]
        offset += 1
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            break
        shift += 7

    return result, offset


@dataclass
class PbField:
    """Protobuf 字段"""
    field_number: int
    wire_type: int
    offset: int
    value: Any = None
    raw_bytes: bytes = b''
    nested_fields: list['PbField'] = field(default_factory=list)

    def get_nested_field(self, field_number: int) -> Optional['PbField']:
        """获取指定编号的嵌套字段"""
        return next((nf for nf in self.nested_fields if nf.field_number == field_number), None)

    def get_all_nested_fields(self, field_number: int) -> list['PbField']:
        """获取所有指定编号的嵌套字段"""
        return [nf for nf in self.nested_fields if nf.field_number == field_number]


def parse_protobuf_message(data: bytes, max_depth: int = 20, _current_depth: int = 0) -> list[PbField]:
    """递归解析 Protobuf 消息"""
    if _current_depth >= max_depth or not data:
        return []

    fields = []
    offset = 0

    while offset < len(data):
        try:
            tag, offset = decode_varint(data, offset)
        except Exception:
            break

        if offset > len(data):
            break

        field_number = tag >> 3
        wire_type = tag & 0x07
        pb_field = PbField(field_number=field_number, wire_type=wire_type, offset=offset)

        if wire_type == 0:  # varint
            try:
                pb_field.value, offset = decode_varint(data, offset)
            except Exception:
                break

        elif wire_type == 1:  # 64-bit fixed
            if offset + 8 <= len(data):
                pb_field.raw_bytes = data[offset:offset + 8]
                pb_field.value = struct.unpack('<Q', pb_field.raw_bytes)[0]
                offset += 8
            else:
                break

        elif wire_type == 2:  # length-delimited
            try:
                length, offset = decode_varint(data, offset)
            except Exception:
                break

            if offset + length > len(data):
                break

            pb_field.raw_bytes = data[offset:offset + length]
            offset += length

            if length > 0:
                try:
                    nested = parse_protobuf_message(pb_field.raw_bytes, max_depth, _current_depth + 1)
                    if nested:
                        pb_field.nested_fields = nested
                except Exception:
                    pass

        elif wire_type == 5:  # 32-bit fixed
            if offset + 4 <= len(data):
                pb_field.raw_bytes = data[offset:offset + 4]
                pb_field.value = struct.unpack('<I', pb_field.raw_bytes)[0]
                offset += 4
            else:
                break

        elif wire_type in (3, 4):  # deprecated group types
            break
        else:
            break

        fields.append(pb_field)

    return fields


def unescape(s: str) -> str:
    """实现 JavaScript 的 unescape 函数"""
    # 处理 %uXXXX 和 %XX 格式
    def replace_unicode(m):
        return chr(int(m.group(1), 16))

    def replace_ascii(m):
        return chr(int(m.group(1), 16))

    result = re.sub(r'%u([0-9a-fA-F]{4})', replace_unicode, s)
    return re.sub(r'%([0-9a-fA-F]{2})', replace_ascii, result)


# =============================================================================
# Mutation 数据结构
# =============================================================================

@dataclass
class ImageInfo:
    """图片信息"""
    url: str
    width: Optional[int] = None
    height: Optional[int] = None
    mime_type: Optional[str] = None


@dataclass
class AuthorInfo:
    """
    结构化的作者信息

    Author 字段格式:
        [type]\u001a\u0002\b\u0002\u0005\u0015\n\x13p.[user_id]\u0005[flags]\u0006[timestamp]

    注意: 0x0c 后的字节已被证明不是"作者类型前缀"，而是与修改属性操作相关的数据编码。
    """
    user_id: Optional[str] = None
    timestamp: Optional[int] = None
    raw: str = ""
    fonts: list[dict] = field(default_factory=list)
    style_id: Optional[str] = None
    colors: list[str] = field(default_factory=list)
    font_sizes: list[float] = field(default_factory=list)

    @classmethod
    def _parse_fonts(cls, raw_text: str) -> list[dict]:
        """解析字体信息（基于控制字符分割）"""
        fonts = []
        STYLE_VARIANT_MARKER = '\x0e'
        FONT_NAME_MARKER = '\x0c'
        VARIANT_MAPPING = {'*': 'primary', ':': 'alternative', 'J': 'special'}

        for part in raw_text.split(STYLE_VARIANT_MARKER):
            if FONT_NAME_MARKER not in part:
                continue

            font_part = part.split(FONT_NAME_MARKER)[-1]
            if not font_part:
                continue

            variant_marker = None
            font_name = font_part

            if font_part and font_part[-1] in '*:J':
                variant_marker = font_part[-1]
                font_name = font_part[:-1]

            # 使用 FontVariant 枚举或本地映射
            variant = None
            try:
                variant_enum = FontVariant.from_marker(variant_marker)
                if variant_enum:
                    variant = variant_enum.value
            except (NameError, AttributeError):
                variant = VARIANT_MAPPING.get(variant_marker)

            # 清理字体名称：在遇到控制字符时停止
            cleaned_name = []
            for char in font_name:
                if ord(char) < 0x20 and char not in ' \t\n\r':
                    break
                cleaned_name.append(char)
            font_name = ''.join(cleaned_name).strip()

            # 过滤无效的字体条目
            if not font_name or (len(font_name) == 1 and font_name in '.1-9ng'):
                continue

            # 检查是否包含有效的字体名称字符
            has_valid_char = any(
                '\u4e00' <= char <= '\u9fff' or char.isalpha()
                for char in font_name
            )
            if has_valid_char:
                fonts.append({'name': font_name, 'variant': variant})

        return fonts

    @classmethod
    def _parse_colors(cls, raw_text: str) -> list[str]:
        """解析颜色值（RGB 十六进制）"""
        colors = []
        pattern = re.compile(r'([0-9A-Fa-f]{6})')

        for match in pattern.finditer(raw_text):
            start, end = match.start(), match.end()
            prefix = raw_text[max(0, start - 3):start]
            suffix = raw_text[end:min(len(raw_text), end + 3)]

            # 排除用户ID和时间戳中的数字
            if prefix.isdigit() or suffix.isdigit():
                continue
            if 'p.' in raw_text[max(0, start - 3):start + 1]:
                continue

            colors.append(match.group(1))

        return colors

    @classmethod
    def _parse_style_id(cls, raw_text: str) -> Optional[str]:
        """解析样式ID（6字符字母数字）"""
        match = re.search(r'\n\n\n\x08\n\x06([a-zA-Z0-9]{6})', raw_text)
        return match.group(1) if match else None

    @classmethod
    def _parse_font_sizes(cls, raw_bytes: bytes) -> list[float]:
        """解析字号值（二进制浮点数）"""
        font_sizes = []
        fields = parse_protobuf_message(raw_bytes, max_depth=5)

        def try_parse_size(wire_type: int, data: bytes) -> Optional[float]:
            try:
                if wire_type == 1 and len(data) >= 8:  # 64-bit double
                    value = struct.unpack('<d', data[:8])[0]
                elif wire_type == 5 and len(data) >= 4:  # 32-bit float
                    value = struct.unpack('<f', data[:4])[0]
                else:
                    return None

                if 6.0 <= value <= 144.0:
                    return round(value, 1)
            except (struct.error, ValueError):
                pass
            return None

        for field in fields:
            size = try_parse_size(field.wire_type, field.raw_bytes)
            if size:
                font_sizes.append(size)

            for nested in field.nested_fields:
                size = try_parse_size(nested.wire_type, nested.raw_bytes)
                if size:
                    font_sizes.append(size)

        # 去重保持顺序
        seen = set()
        return [s for s in font_sizes if not (s in seen or seen.add(s))]

    @classmethod
    def parse(cls, raw_bytes: bytes) -> Optional['AuthorInfo']:
        """从原始字节解析作者信息"""
        if not raw_bytes:
            return None

        try:
            raw_text = raw_bytes.decode('utf-8', errors='ignore')
        except Exception:
            return None

        # 提取用户ID
        match = AUTHOR_USER_ID_PATTERN.search(raw_text)
        user_id = f"p.{match.group(1)}" if match else None

        # 提取时间戳
        timestamp = None
        ts_match = re.search(r'\x06\x0f\n\r(\d{13})', raw_text)
        if ts_match:
            try:
                ts = int(ts_match.group(1))
                if 1577836800000 <= ts <= 2000000000000:  # 2020-2033年
                    timestamp = ts
            except ValueError:
                pass

        if not timestamp:
            for ts_str in AUTHOR_TIMESTAMP_PATTERN.findall(raw_text):
                try:
                    ts = int(ts_str)
                    if 1577836800000 <= ts <= 2000000000000:
                        ts_index = raw_text.find(ts_str)
                        if ts_index > 0:
                            prefix = raw_text[max(0, ts_index - 5):ts_index]
                            if '\x06' in prefix or '\r' in prefix:
                                timestamp = ts
                                break
                except ValueError:
                    pass

        return cls(
            user_id=user_id,
            timestamp=timestamp,
            raw=raw_text,
            fonts=cls._parse_fonts(raw_text),
            style_id=cls._parse_style_id(raw_text),
            colors=cls._parse_colors(raw_text),
            font_sizes=cls._parse_font_sizes(raw_bytes)
        )


@dataclass
class Mutation:
    """Mutation 操作"""
    ty: int = 0
    mt: Optional[str] = None
    mm: Optional[str] = None
    bi: Optional[int] = None
    ei: Optional[int] = None
    s: Optional[str] = None
    pr: Optional[dict] = None
    author: Optional[str] = None
    author_info: Optional[AuthorInfo] = None
    status_code: Optional[int] = None
    marker: Optional[str] = None
    image_info: Optional[ImageInfo] = None
    range_type: Optional[int] = None
    hyperlink: Optional[dict] = None
    list_marker: Optional[dict] = None
    style_id: Optional[str] = None
    alignment: Optional[str] = None

    @property
    def type_name(self) -> str:
        """获取类型名称"""
        type_names = {1: "is", 2: "ds", 3: "mp", 4: "ms", 5: "cr"}
        return type_names.get(self.ty, f"unknown({self.ty})")

    @staticmethod
    def _extract_style_id(author: str) -> Optional[str]:
        """从 author 字段中提取样式ID"""
        match = AUTHOR_STYLE_ID_PATTERN.search(author)
        return match.group(1) if match else None

    @staticmethod
    def _extract_alignment(pr: Optional[dict]) -> Optional[str]:
        """从 pr 字段中提取段落对齐方式"""
        if not pr or not isinstance(pr, dict):
            return None

        paragraph = pr.get('paragraph', {})
        if not isinstance(paragraph, dict):
            return None

        jc_info = paragraph.get('jc')
        if jc_info is None:
            return None

        # jc 可能是直接的数值或 {'val': 数值} 格式
        if isinstance(jc_info, (int, float)):
            jc_value = int(jc_info)
        elif isinstance(jc_info, dict):
            jc_value = jc_info.get('val')
            if jc_value is None:
                return None
            jc_value = int(jc_value)
        else:
            return None

        return PARAGRAPH_ALIGNMENT_MAP.get(jc_value, 'LEFT')

    def _get_heading_level(self, style_id: str) -> Optional[int]:
        """获取标题级别（已废弃，返回 None）"""
        return None

    def _add_style_info(self, result: dict, style_id: str):
        """添加样式信息到结果"""
        result["style_id"] = style_id
        level = self._get_heading_level(style_id)
        if level:
            result["heading_level"] = level

    def to_dict(self) -> dict:
        """转换为字典"""
        result = {
            "ty": self.type_name,
            "ty_code": self.ty,
        }

        # 基础字段
        for field_name in ["mt", "mm", "bi", "ei", "s", "pr", "author", "marker",
                           "range_type", "hyperlink", "list_marker", "style_id"]:
            value = getattr(self, field_name)
            if value is not None:
                result[field_name] = value

        # 作者信息
        if self.author_info is not None:
            author_dict = {}
            if self.author_info.user_id:
                author_dict["user_id"] = self.author_info.user_id
            if self.author_info.timestamp:
                author_dict["timestamp"] = self.author_info.timestamp
            if self.author_info.fonts:
                author_dict["fonts"] = self.author_info.fonts
            if self.author_info.style_id:
                author_dict["style_id"] = self.author_info.style_id
            if self.author_info.colors:
                author_dict["colors"] = self.author_info.colors
            if self.author_info.font_sizes:
                author_dict["font_sizes"] = self.author_info.font_sizes

            result["author_info"] = author_dict

            # 提取样式ID
            style_id = self._extract_style_id(self.author_info.raw)
            if style_id and style_id != self.author_info.style_id:
                self._add_style_info(result, style_id)
            elif self.author_info.style_id:
                self._add_style_info(result, self.author_info.style_id)
        elif self.author is not None:
            style_id = self._extract_style_id(self.author)
            if style_id:
                self._add_style_info(result, style_id)

        # status_code
        if self.status_code is not None:
            result["status_code"] = self.status_code
            status_name = None
            if self.ty == 3:  # MODIFY_PROPERTY
                status_name = MODIFY_TYPE_MAP.get(self.status_code)
            elif self.ty == 4:  # MODIFY_STYLE
                status_name = MODIFY_STYLE_TYPE_MAP.get(self.status_code)
            if status_name:
                result["status_code_name"] = status_name

        # 图片信息
        if self.image_info is not None:
            result["image_info"] = {"url": self.image_info.url}
            for field_name in ["width", "height", "mime_type"]:
                value = getattr(self.image_info, field_name)
                if value is not None:
                    result["image_info"][field_name] = value

        # 段落对齐方式
        alignment = self._extract_alignment(self.pr)
        if alignment:
            result["alignment"] = alignment

        return result


# =============================================================================
# ultrabuf 解析器
# =============================================================================

class UltrabufParser:
    """ultrabuf Protobuf 解析器"""

    # 目标类型映射
    TARGET_MAP = {
        1: "run", 2: "paragraph", 3: "section", 4: "story",
        5: "settings", 6: "styles", 7: "fonts", 8: "themes",
        9: "background", 10: "numbering", 11: "webSettings",
    }

    # 模式类型映射
    MODE_MAP = {1: "insert", 2: "delete", 3: "merge", 4: "split"}

    def __init__(self, protobuf_data: bytes):
        self.data = protobuf_data
        self.fields = parse_protobuf_message(protobuf_data)
        self._style_definitions = None

    def get_version(self) -> int:
        """获取文档版本"""
        for f in self.fields:
            if f.field_number == 1 and f.nested_fields:
                for nf in f.nested_fields:
                    if nf.field_number == 1 and nf.wire_type == 0:
                        return nf.value
        return 0

    def parse_mutation_field(self, field: PbField) -> Optional[Mutation]:
        """解析单个 Mutation 字段"""
        if not field.nested_fields:
            return None

        mutation = Mutation()

        for nf in field.nested_fields:
            self._parse_mutation_field_content(nf, mutation)

        # 解析文本内容中的特殊控制字符
        if mutation.s:
            mutation.hyperlink = ControlChars.parse_hyperlink(mutation.s)
            mutation.list_marker = ControlChars.parse_list_marker(mutation.s)

        mutation.alignment = Mutation._extract_alignment(mutation.pr)
        return mutation

    def _parse_mutation_field_content(self, nf: PbField, mutation: Mutation):
        """解析单个字段内容"""
        if nf.field_number == 1 and nf.wire_type == 0:
            mutation.ty = nf.value

        elif nf.field_number == 2 and nf.nested_fields:
            inner = nf.get_nested_field(1)
            if inner and inner.wire_type == 0:
                mutation.bi = inner.value

        elif nf.field_number == 3 and nf.nested_fields:
            inner = nf.get_nested_field(1)
            if inner and inner.wire_type == 0:
                mutation.ei = inner.value

        elif nf.field_number == 4:
            if nf.wire_type == 0:
                mutation.mt = self.TARGET_MAP.get(nf.value, f"unknown({nf.value})")
            elif nf.raw_bytes:
                mutation.mt = nf.raw_bytes.decode('utf-8', errors='ignore')

        elif nf.field_number == 5:
            if nf.wire_type == 0:
                mutation.mm = self.MODE_MAP.get(nf.value, f"unknown({nf.value})")
            elif nf.raw_bytes:
                mutation.mm = nf.raw_bytes.decode('utf-8', errors='ignore')

        elif nf.field_number == 6:
            self._parse_field_6(nf, mutation)

        elif nf.field_number == 7 and nf.raw_bytes:
            author_info = AuthorInfo.parse(nf.raw_bytes)
            if author_info:
                mutation.author_info = author_info
                mutation.author = author_info.raw

            raw_text = nf.raw_bytes.decode('utf-8', errors='ignore')
            if 'wdcdn' in raw_text or 'qpic' in raw_text:
                mutation.image_info = self._extract_image_from_bytes(nf.raw_bytes)

        elif nf.field_number == 8 and nf.wire_type == 0:
            mutation.status_code = nf.value

        elif nf.field_number == 9 and nf.raw_bytes:
            mutation.marker = nf.raw_bytes.decode('utf-8', errors='ignore')

    def _parse_field_6(self, nf: PbField, mutation: Mutation):
        """解析 Field 6 (string content 或 property)"""
        if not nf.raw_bytes:
            return

        if nf.nested_fields:
            # 查找嵌套的 Field 1 (text content)
            for sub in nf.nested_fields:
                if sub.field_number == 1 and sub.raw_bytes:
                    mutation.s = sub.raw_bytes.decode('utf-8', errors='ignore')
                    return

            # 如果没有文本内容，解析为属性结构
            mutation.pr = self._parse_property(nf.nested_fields)
        else:
            mutation.s = nf.raw_bytes.decode('utf-8', errors='ignore')

    def _parse_property(self, nested_fields: list[PbField]) -> Optional[dict]:
        """解析属性结构"""
        pr = {}
        for sub in nested_fields:
            if sub.field_number != 1 or not sub.raw_bytes:
                continue

            try:
                key = sub.raw_bytes.decode('utf-8', errors='ignore')
            except Exception:
                continue

            if sub.nested_fields:
                pr[key] = self._parse_property_value(sub.nested_fields)

        return pr if pr else None

    def _parse_property_value(self, nested_fields: list[PbField]) -> dict:
        """解析属性值"""
        result = {}
        for sub2 in nested_fields:
            if sub2.field_number != 1 or not sub2.raw_bytes:
                continue

            try:
                sub_key = sub2.raw_bytes.decode('utf-8', errors='ignore')
            except Exception:
                continue

            # 查找 Field 2 (value)
            for sub3 in nested_fields:
                if sub3.field_number == 2:
                    if sub3.wire_type == 0:
                        result[sub_key] = sub3.value
                    elif sub3.nested_fields:
                        nested_value = {}
                        for n in sub3.nested_fields:
                            if n.field_number in (1, 2) and n.wire_type == 0:
                                nested_value['val'] = n.value
                        if nested_value:
                            result[sub_key] = nested_value
                    elif sub3.raw_bytes:
                        result[sub_key] = sub3.raw_bytes.decode('utf-8', errors='ignore')
                    break

        return result

    def _extract_image_from_bytes(self, data: bytes) -> Optional[ImageInfo]:
        """从字节中提取图片信息"""
        try:
            text = data.decode('utf-8', errors='ignore')
            for url in re.findall(r'https?://[^\s<>"\x00-\x1f]+', text):
                # 清理 URL
                url = url.rstrip('*\x00-\x1f')
                while url and not (url[-1].isalnum() or url[-1] in '/_-=&?'):
                    url = url[:-1]

                if any(kw in url for kw in ['wdcdn', 'qpic', 'image', 'img']) and len(url) > 10:
                    img_info = ImageInfo(url=url)

                    w_match = re.search(r'w=(\d+)', url)
                    h_match = re.search(r'h=(\d+)', url)
                    if w_match:
                        img_info.width = int(w_match.group(1))
                    if h_match:
                        img_info.height = int(h_match.group(1))

                    type_match = re.search(r'type=([^&]+)', url)
                    if type_match:
                        img_info.mime_type = type_match.group(1)

                    return img_info
        except Exception:
            pass
        return None

    def get_mutations(self) -> list[Mutation]:
        """获取所有 Mutation"""
        mutations = []
        for f in self.fields:
            if f.field_number == 1 and f.nested_fields:
                for nf in f.nested_fields:
                    if nf.field_number == 2 and nf.nested_fields:
                        mutation = self.parse_mutation_field(nf)
                        if mutation:
                            mutations.append(mutation)
        return mutations

    def extract_text_content(self) -> str:
        """提取所有文本内容"""
        text_parts = []
        for mut in self.get_mutations():
            if mut.ty == 1 and mut.s:
                # 过滤控制字符，保留可打印字符、中文、\r、\n
                text = ''.join(
                    c for c in mut.s
                    if ord(c) >= 32 or ord(c) in (0x09, 0x0a, 0x0d) or ord(c) > 127
                )
                for para in text.split('\r'):
                    para = para.strip()
                    if para:
                        text_parts.append(para)
        return '\n\n'.join(text_parts)

    def extract_style_definitions(self) -> dict[str, dict]:
        """提取样式定义信息"""
        if self._style_definitions is not None:
            return self._style_definitions

        style_definitions = {}

        # 第一步：从 TABLE_STYLE (ty=4, status_code=4) mutations 中解析样式定义
        for mut in self.get_mutations():
            if mut.ty == 4 and mut.status_code == 4 and mut.author:
                # TABLE_STYLE mutation 包含样式定义
                parsed = self._parse_style_definitions_from_author(mut.author)
                style_definitions.update(parsed)

        # 第二步：从 PARAGRAPH_PROPERTY mutations 中补充（如果有 pr 字段）
        for mut in self.get_mutations():
            if mut.ty != 3 or mut.status_code != 102:
                continue

            style_id = mut.style_id or (mut.author_info.style_id if mut.author_info else None)
            if not style_id or style_id in style_definitions:
                continue

            outline_lvl = None
            style_name = None

            if mut.pr and isinstance(mut.pr, dict):
                paragraph = mut.pr.get("paragraph", {})

                # 提取 outlineLvl
                outline_lvl_info = paragraph.get("outlineLvl", {})
                if isinstance(outline_lvl_info, dict):
                    val = outline_lvl_info.get("val")
                    if val is not None and isinstance(val, (int, float)):
                        try:
                            lvl = int(val)
                            if 0 <= lvl <= 8:
                                outline_lvl = lvl
                        except (ValueError, TypeError):
                            pass

                # 提取样式名称
                p_style = paragraph.get("pStyle", {})
                if isinstance(p_style, dict):
                    val = p_style.get("val")
                    if val and isinstance(val, str):
                        style_name = val

            style_definitions[style_id] = {
                "name": style_name,
                "outline_lvl": outline_lvl
            }

        self._style_definitions = style_definitions
        return style_definitions

    def _parse_style_definitions_from_author(self, author: str) -> dict[str, dict]:
        """从 author 字段解析样式定义

        TABLE_STYLE mutations 的 author 字段包含样式定义：
        - style_id:name (如 "sy0ypo" 包含 "heading 4")
        - 模式1：*\x01\n\x06<style_id>\x12\x01\n\r\n\x0b\n\t<样式名称>*
        - 模式2：\x06<style_id>\x12\x01\n\t\n\x07\n\x05<样式名称>*
        - 模式3：\x06<style_id>\x12+\n\n\n\x08\n\x06<样式名称>*
        """
        style_definitions = {}
        import re

        # 模式1：完整的标题样式定义
        # \x06<style_id>\x12\x01\n\r\n\x0b\n\t<样式名称>*
        pattern1 = re.compile(r'\x06([a-zA-Z0-9]{6})\x12\x01\n\r\n\x0b\n\t([^\x00-\x1f*]+)')

        # 模式2：Title 样式定义
        # \x06<style_id>\x12\x01\n\t\n\x07\n\x05<样式名称>*
        pattern2 = re.compile(r'\x06([a-zA-Z0-9]{6})\x12\x01\n\t\n\x07\n\x05([^\x00-\x1f*]+)')

        # 模式3：Normal 样式定义
        # \x06<style_id>\x12+\n\n\n\x08\n\x06<样式名称>*
        pattern3 = re.compile(r'\x06([a-zA-Z0-9]{6})\x12\+\n\n\n\x08\n\x06([^\x00-\x1f*]+)')

        # 查找所有样式定义位置
        for match in pattern1.finditer(author):
            style_id = match.group(1)
            style_name = match.group(2).strip()
            if style_name and style_id not in style_definitions:
                outline_lvl = self._get_outline_lvl_from_name(style_name)
                style_definitions[style_id] = {
                    "name": style_name,
                    "outline_lvl": outline_lvl
                }

        for match in pattern2.finditer(author):
            style_id = match.group(1)
            style_name = match.group(2).strip()
            if style_name and style_id not in style_definitions:
                outline_lvl = self._get_outline_lvl_from_name(style_name)
                style_definitions[style_id] = {
                    "name": style_name,
                    "outline_lvl": outline_lvl
                }

        for match in pattern3.finditer(author):
            style_id = match.group(1)
            style_name = match.group(2).strip()
            if style_name and style_id not in style_definitions:
                outline_lvl = self._get_outline_lvl_from_name(style_name)
                style_definitions[style_id] = {
                    "name": style_name,
                    "outline_lvl": outline_lvl
                }

        return style_definitions

    def _get_outline_lvl_from_name(self, style_name: str) -> Optional[int]:
        """从样式名称获取大纲级别"""
        if not style_name:
            return None

        style_name_lower = style_name.lower()

        # 标题样式
        heading_match = re.match(r'heading\s*(\d+)', style_name_lower)
        if heading_match:
            level = int(heading_match.group(1))
            if 1 <= level <= 9:
                return level - 1  # outline_lvl 从 0 开始

        # Title 样式
        if 'title' in style_name_lower and 'subtitle' not in style_name_lower:
            return 0

        # Subtitle 样式
        if 'subtitle' in style_name_lower:
            return 1

        # 代码块样式不是标题
        if 'codeblock' in style_name_lower or 'code-block' in style_name_lower:
            return None

        return None


# =============================================================================
# 腾讯文档解析器
# =============================================================================

class TencentDocParser:
    """腾讯文档解析器"""

    def __init__(self, initial_text: str):
        self.raw_text = initial_text
        self.unescaped_text = unescape(initial_text)
        self.protobuf_data = base64.b64decode(self.unescaped_text)
        self.ultrabuf = UltrabufParser(self.protobuf_data)

    def parse(self) -> dict[str, Any]:
        """解析文档"""
        mutations = self.ultrabuf.get_mutations()
        doc_builder = DocumentBuilder(mutations)
        images = [m.to_dict()["image_info"] for m in mutations if m.image_info]
        textbox_mappings = self._extract_textbox_mappings(mutations)

        return {
            "version": self.ultrabuf.get_version(),
            "mutations_count": len(mutations),
            "mutations": [m.to_dict() for m in mutations],
            "images": images,
            "image_count": len(images),
            "style_definitions": self.ultrabuf.extract_style_definitions(),
            "textbox_mappings": textbox_mappings,
            "document_builder": doc_builder,
        }

    def _extract_textbox_mappings(self, mutations: list[Mutation]) -> list[dict]:
        """从 TABLE_PROPERTY mutations 中提取文本框视觉位置映射

        映射结构：
        - visual_bi: 视觉位置（文本流中占位符的位置）
        - textbox_style_id: 外层文本框样式ID
        - content_style_id: 内层内容样式ID（用于关联 TEXTBOX_STORY_PROPERTY）
        - is_code_block: 是否是代码块（通过 TEXTBOX_STORY_PROPERTY 的 author 字段判断）

        TEXTBOX_STORY_PROPERTY author 字段中：
        - 有 "plain text" 标记 (J 字段) = 代码块
        - 无此标记 = 普通文本框
        """
        TABLE_PROPERTY = 115
        TEXTBOX_STORY_PROPERTY = 109

        # style_id 提取模式：\x0a\x08\x0a\x06<style_id>
        style_id_in_textbox = re.compile(r'\x0a\x08\x0a\x06([a-zA-Z0-9]{6})')

        # 先收集 TEXTBOX_STORY_PROPERTY 中每个 style_id 的类型信息
        content_style_types: dict[str, bool] = {}  # style_id -> is_code_block
        for mut in mutations:
            if mut.ty != 3 or mut.status_code != TEXTBOX_STORY_PROPERTY:
                continue
            if not mut.author:
                continue

            # 从 author 中提取 style_id
            style_id_match = style_id_in_textbox.search(mut.author)
            if not style_id_match:
                continue
            style_id = style_id_match.group(1)

            # 检查 author 中是否有 J 字段 (0x4a) 表示 "plain text"
            # 代码块的特征是有 "plain text" 标记
            has_plain_text_marker = '\x4a' in mut.author

            # 如果已经有记录，保持一致性
            if style_id in content_style_types:
                # 如果任何一个 mutation 有 plain text 标记，则认为是代码块
                if has_plain_text_marker:
                    content_style_types[style_id] = True
            else:
                content_style_types[style_id] = has_plain_text_marker

        # 然后从 TABLE_PROPERTY 提取映射
        mappings = []
        style_id_pattern = re.compile(r':\x08\x0a\x06([a-zA-Z0-9]{6})')

        for mut in mutations:
            if mut.ty != 3 or mut.status_code != TABLE_PROPERTY:
                continue

            if mut.bi is None or not mut.author:
                continue

            style_ids = style_id_pattern.findall(mut.author)

            # 区分图片和文本框：图片的 author 包含 wdcdn/qpic URL
            if 'wdcdn' in mut.author or 'qpic' in mut.author:
                continue

            if len(style_ids) >= 2:
                content_style_id = style_ids[1]
                is_code_block = content_style_types.get(content_style_id, False)

                mappings.append({
                    "visual_bi": mut.bi,
                    "textbox_style_id": style_ids[0],
                    "content_style_id": content_style_id,
                    "is_code_block": is_code_block
                })

        return mappings


# =============================================================================
# DocumentBuilder - 基于 mutations 构建文档结构
# =============================================================================

@dataclass
class TextPosition:
    """文档位置元素"""
    index: int
    type: str
    content: Any
    mutations: list[int]


class DocumentBuilder:
    """基于 mutations 构建文档结构"""

    def __init__(self, mutations: list[Mutation]):
        self.mutations = mutations
        self.positions: list[TextPosition] = []
        self._build_document()

    def _build_document(self):
        """构建文档结构"""
        positioned_mutations = []
        initial_mutations = []

        for idx, mut in enumerate(self.mutations):
            if mut.ty == 1 and mut.s:  # INSERT_STRING
                target = positioned_mutations if mut.bi is not None else initial_mutations
                target.append((mut.bi or 0, idx, mut, "text", mut.s))
            elif mut.image_info:
                target = positioned_mutations if mut.bi is not None else initial_mutations
                target.append((mut.bi or 0, idx, mut, "image", mut.image_info))
            elif mut.ty == 2 and mut.bi is not None and mut.ei and mut.ei > mut.bi:
                positioned_mutations.append((mut.bi, idx, mut, "paragraph_break", None))

        positioned_mutations.sort(key=lambda x: x[0])

        # 添加初始 mutations
        for _, mut_idx, mut, pos_type, content in initial_mutations:
            self.positions.append(TextPosition(index=0, type=pos_type, content=content, mutations=[mut_idx]))

        # 添加有位置信息的 mutations
        for bi, mut_idx, _, pos_type, content in positioned_mutations:
            self.positions.append(TextPosition(index=bi, type=pos_type, content=content, mutations=[mut_idx]))

    def get_document_structure(self) -> list[TextPosition]:
        """获取完整文档结构"""
        return self.positions


# =============================================================================
# 输出生成器
# =============================================================================

def generate_json(parsed: dict[str, Any]) -> str:
    """生成 JSON 输出 (intermediate.json 格式)"""
    parsed_copy = {k: v for k, v in parsed.items() if k != "document_builder"}
    return json.dumps(parsed_copy, ensure_ascii=False, indent=2)


# =============================================================================
# API 函数 (供 convert.py 调用)
# =============================================================================

def parse_opendoc(input_file: str, output_prefix: str, verbose: bool = False) -> str:
    """
    解析 opendoc 响应文件

    Args:
        input_file: opendoc 响应 JSON 文件路径
        output_prefix: 输出文件前缀 (不含 _intermediate.json 后缀)
        verbose: 是否显示详细信息

    Returns:
        输出的 intermediate.json 文件路径
    """
    input_path = Path(input_file)

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    text_data = data['clientVars']['collab_client_vars']['initialAttributedText']['text'][0]

    if verbose:
        print(f"  原始数据长度: {len(text_data)} 字符")

    doc_parser = TencentDocParser(text_data)
    parsed = doc_parser.parse()

    if verbose:
        print(f"  Mutation 数量: {parsed['mutations_count']}")
        print(f"  图片数量: {parsed['image_count']}")

    # 保存输出
    json_output = generate_json(parsed)
    intermediate_file = Path(f"{output_prefix}_intermediate.json")
    with open(intermediate_file, 'w', encoding='utf-8') as f:
        f.write(json_output)

    return str(intermediate_file)


# =============================================================================
# 主函数
# =============================================================================

def main():
    """主函数"""
    import argparse

    arg_parser = argparse.ArgumentParser(description='腾讯文档 ultrabuf Protobuf 解析器')
    arg_parser.add_argument('input', help='输入文件路径 (.json)')
    arg_parser.add_argument('-o', '--output', help='输出文件前缀')
    arg_parser.add_argument('-v', '--verbose', action='store_true', help='显示详细信息')
    arg_parser.add_argument('--mutations', action='store_true', help='显示所有 mutations')

    args = arg_parser.parse_args()
    input_path = Path(args.input)

    print("=" * 60)
    print("腾讯文档 ultrabuf Protobuf 解析器")
    print("=" * 60)
    print(f"输入: {input_path}")

    # 读取输入数据
    if input_path.suffix != '.json':
        print(f"错误: 不支持的文件类型 {input_path.suffix}")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    try:
        text_data = data['clientVars']['collab_client_vars']['initialAttributedText']['text'][0]
    except (KeyError, IndexError) as e:
        print(f"错误: 无法从 JSON 提取数据 - {e}")
        sys.exit(1)

    print(f"原始数据长度: {len(text_data)} 字符")

    # 解析
    doc_parser = TencentDocParser(text_data)
    parsed = doc_parser.parse()

    print(f"版本: {parsed['version']}")
    print(f"Mutation 数量: {parsed['mutations_count']}")
    print(f"图片数量: {parsed['image_count']}")

    if args.verbose:
        if parsed['images']:
            print("\n图片:")
            for i, img in enumerate(parsed['images']):
                size = f" ({img.get('width', '?')}x{img.get('height', '?')})" if 'width' in img else ""
                print(f"  [{i}] {img['url']}{size}")

        if args.mutations:
            print("\nMutations:")
            for i, mut in enumerate(parsed['mutations']):
                print(f"  [{i}] {mut}")

    # 确定输出文件前缀
    output_prefix = args.output or input_path.stem

    # 保存输出
    json_output = generate_json(parsed)
    intermediate_file = Path(f"{output_prefix}_intermediate.json")
    with open(intermediate_file, 'w', encoding='utf-8') as f:
        f.write(json_output)
    print(f"\n中间文件已保存: {intermediate_file}")
    print(f"下一步: python3 scripts/parse_ultrabuf/format_parser.py {intermediate_file} -o {Path(output_prefix).with_suffix('.json')}")


if __name__ == "__main__":
    main()
