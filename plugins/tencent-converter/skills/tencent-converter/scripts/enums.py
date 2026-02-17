#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
腾讯文档 ultrabuf 解析 - 枚举值定义集中管理

基于腾讯文档 JS 源码分析，定义所有相关的枚举值和控制字符。
"""

from enum import IntEnum, Enum
from typing import Optional


class MutationType(IntEnum):
    """Mutation 类型 (ty 字段)"""
    INSERT_STRING = 1      # "is"
    DELETE_STRING = 2      # "ds"
    MODIFY_PROPERTY = 3    # "mp"
    MODIFY_STYLE = 4       # "ms"
    COMMENT_REFERENCE = 5  # 评论引用


class ModifyType(IntEnum):
    """Modify 类型 (status_code/pr 字段)"""
    RUN_PROPERTY = 101
    PARAGRAPH_PROPERTY = 102
    SECTION_PROPERTY = 103
    HEADER_STORY_PROPERTY = 104  # 也作为通用 STORY_PROPERTY
    FOOTER_STORY_PROPERTY = 105
    FOOTNOTE_STORY_PROPERTY = 106
    ENDNOTE_STORY_PROPERTY = 107
    COMMENT_STORY_PROPERTY = 108
    TEXTBOX_STORY_PROPERTY = 109
    SETTINGS_PROPERTY = 110
    STYLES_PROPERTY = 111
    CODE_BLOCK_PROPERTY = 112
    NUMBERING_PROPERTY = 113
    PICTURE_PROPERTY = 114
    TABLE_PROPERTY = 115
    TABLE_CELL_PROPERTY = 116
    TABLE_ROW_PROPERTY = 117
    TABLE_AUTO_PROPERTY = 118

    @classmethod
    def get_name(cls, code: int) -> str:
        """获取枚举值的名称"""
        return next((m.name for m in cls if m.value == code), f"UNKNOWN_{code}")


class ModifyStyleType(IntEnum):
    """样式修改类型 - 用于 'ms' 类型的 status_code"""
    FONT_STYLE = 1
    PARAGRAPH_STYLE = 2
    CHARACTER_STYLE = 3
    TABLE_STYLE = 4
    LIST_STYLE = 5
    SECTION_STYLE = 6
    DOCUMENT_STYLE = 7


# AuthorType 枚举已废弃
# 此枚举已被证明不准确，0x0c 后的字节不是"作者类型前缀"。
# 相关实现已移除，不再使用。


class FontVariant(str, Enum):
    """字体变体标记"""
    PRIMARY = "primary"
    ALTERNATIVE = "alternative"
    SPECIAL = "special"

    _MARKER_MAP = {'*': PRIMARY, ':': ALTERNATIVE, 'J': SPECIAL}
    _VARIANT_MAP = {PRIMARY: '*', ALTERNATIVE: ':', SPECIAL: 'J'}

    @classmethod
    def from_marker(cls, marker: str) -> Optional['FontVariant']:
        return cls._MARKER_MAP.get(marker)

    @classmethod
    def to_marker(cls, variant: Optional['FontVariant']) -> Optional[str]:
        return cls._VARIANT_MAP.get(variant) if variant else None


class ParagraphAlignment(IntEnum):
    """段落对齐方式 (jc 字段)"""
    LEFT = 1
    CENTER = 2
    RIGHT = 3
    JUSTIFY = 4
    DISTRIBUTED = 5

    @classmethod
    def get_name(cls, code: int) -> str:
        return next((m.name for m in cls if m.value == code), "LEFT")


class PlaceholderCharCode(IntEnum):
    """Placeholder 字段控制字符"""
    FIELD_BEGIN = 0x13
    FIELD_SEPARATE = 0x14
    FIELD_END = 0x15


class ControlChars:
    """控制字符定义"""

    # 基础控制字符
    PARAGRAPH_SEP = 0x0d
    CODE_BLOCK_START = 0x0f
    CODE_BLOCK_END = 0x1d
    PICTURE_MARKER = 0x1c
    RECORD_SEP = 0x1e
    GROUP_SEP = 0x1d

    # List Marker
    LIST_MARKER = 0x08

    # HYPERLINK
    HYPERLINK_START = PlaceholderCharCode.FIELD_BEGIN
    HYPERLINK_URL_SEP = PlaceholderCharCode.FIELD_SEPARATE
    HYPERLINK_END = PlaceholderCharCode.FIELD_END

    # 作者字段
    AUTHOR_FIELD_SEP = 0x05
    AUTHOR_FIELD_PREFIX = 0x1a
    AUTHOR_FLAG_SEP = 0x01
    AUTHOR_FIELD_VALUE = 0x06
    AUTHOR_NEWLINE = 0x0a

    # Protobuf Encoding
    PROTOBUF_NULL = 0x00
    PROTOBUF_FIELD_START = 0x02
    PROTOBUF_SUBFIELD = 0x03
    PROTOBUF_LENGTH = 0x04
    PROTOBUF_ALIGN = 0x09
    PROTOBUF_FIELD_SEP = 0x0b

    # Font & Style Markers
    FONT_NAME_MARKER = 0x0c
    STYLE_VARIANT_MARKER = 0x0e
    LABEL_MARKER = 0x12

    # Font Variant Markers
    FONT_VARIANT_PRIMARY = 0x2a
    FONT_VARIANT_ALTERNATIVE = 0x3a
    FONT_VARIANT_SPECIAL = 0x4a

    # Text Content Markers
    TABLE_MARKER = 0x07
    COMPARISON_MARKER = 0x1b

    # Special Element Markers
    TEXTBOX_MARKER = 0x10
    NUMERIC_VALUE_MARKER = 0x11
    BINARY_DATA_MARKER = 0x16
    SECTION_END_MARKER = 0x17
    GROUP_MARKER = 0x18
    DELETE_OP_MARKER = 0x1f

    # 控制字符表示映射
    _REPR_MAP = {
        0x00: "\\u0000 (PROTOBUF_NULL)",
        0x01: "\\u0001 (AUTHOR_FLAG_SEP)",
        0x02: "\\u0002 (PROTOBUF_FIELD_START)",
        0x03: "\\u0003 (PROTOBUF_SUBFIELD)",
        0x04: "\\u0004 (PROTOBUF_LENGTH)",
        0x05: "\\x05 (AUTHOR_FIELD_SEP)",
        0x06: "\\u0006 (AUTHOR_FIELD_VALUE)",
        0x07: "\\u0007 (TABLE_MARKER)",
        0x08: "\\b (LIST_MARKER)",
        0x09: "\\u0009 (PROTOBUF_ALIGN)",
        0x0a: "\\n (AUTHOR_NEWLINE)",
        0x0b: "\\u000b (PROTOBUF_FIELD_SEP)",
        0x0c: "\\u000c (FONT_NAME_MARKER)",
        0x0d: "\\r (PARAGRAPH_SEP)",
        0x0e: "\\u000e (STYLE_VARIANT_MARKER)",
        0x0f: "\\u000f (CODE_BLOCK_START)",
        0x10: "\\u0010 (TEXTBOX_MARKER)",
        0x11: "\\u0011 (NUMERIC_VALUE_MARKER)",
        0x12: "\\u0012 (LABEL_MARKER)",
        0x13: "\\x13 (HYPERLINK_START)",
        0x14: "\\x14 (HYPERLINK_URL_SEP)",
        0x15: "\\x15 (HYPERLINK_END)",
        0x16: "\\u0016 (BINARY_DATA_MARKER)",
        0x17: "\\u0017 (SECTION_END_MARKER)",
        0x18: "\\u0018 (GROUP_MARKER)",
        0x1a: "\\u001a (AUTHOR_FIELD_PREFIX)",
        0x1b: "\\u001b (COMPARISON_MARKER)",
        0x1c: "\\u001c (PICTURE_MARKER)",
        0x1d: "\\u001d (CODE_BLOCK_END/GROUP_SEP)",
        0x1e: "\\u001e (RECORD_SEP)",
        0x1f: "\\u001f (DELETE_OP_MARKER)",
    }

    @classmethod
    def to_char(cls, code: int) -> str:
        return chr(code) if 0 <= code <= 0x1f else f"\\x{code:02x}"

    @classmethod
    def to_repr(cls, code: int) -> str:
        return cls._REPR_MAP.get(code, f"\\x{code:02x} (UNKNOWN)")

    @classmethod
    def parse_hyperlink(cls, text: str) -> Optional[dict]:
        """解析 HYPERLINK 控制字符序列"""
        import re
        match = re.search(r'\x13HYPERLINK\s+([^\x14]+)\x14([^\x15]+)\x15', text)
        if match:
            return {'url': match.group(1).strip(), 'display_text': match.group(2).strip()}
        return None

    @classmethod
    def parse_list_marker(cls, text: str) -> Optional[dict]:
        """解析 List Marker 控制字符"""
        import re
        match = re.search(r'\x08([-\w])', text)
        if match:
            marker_char = match.group(1)
            return {
                'type': {'-': 'bullet', '8': 'numbering'}.get(marker_char, 'unknown'),
                'marker': f'\\x08{marker_char}',
                'marker_char': marker_char
            }
        return None

    @classmethod
    def parse_author_field(cls, text: str) -> Optional[dict]:
        """解析作者字段"""
        import re
        match = re.search(r'p\.(\d+)\x05([^\x06]+)\x06', text)
        if match:
            return {'user_id': match.group(1), 'flags': match.group(2).strip()}
        return None


class MutationTarget:
    """Mutation 目标类型 (mt 字段)"""
    RUN = "run"
    PARAGRAPH = "paragraph"
    SECTION = "section"
    STORY = "story"
    SETTINGS = "settings"
    STYLES = "styles"
    FONTS = "fonts"
    THEMES = "themes"
    BACKGROUND = "background"
    NUMBERING = "numbering"
    WEB_SETTINGS = "webSettings"
    COMMENT = "comment"


class MutationMode:
    """Mutation 模式 (mm 字段)"""
    INSERT = "insert"
    DELETE = "delete"
    MERGE = "merge"
    SPLIT = "split"
    REPLACE = "replace"


# 便捷映射字典
MUTATION_TYPE_MAP = {
    1: "INSERT_STRING (is)",
    2: "DELETE_STRING (ds)",
    3: "MODIFY_PROPERTY (mp)",
    4: "MODIFY_STYLE (ms)",
    5: "COMMENT_REFERENCE (cr)",
}

RANGE_TYPE_MAP = {
    1: "NormalRange",
    5: "RevisionRange",
}

HYPERLINK_FIELD_NAME = "HYPERLINK"

MODIFY_TYPE_MAP = {
    101: "RUN_PROPERTY",
    102: "PARAGRAPH_PROPERTY",
    103: "SECTION_PROPERTY",
    104: "HEADER_STORY_PROPERTY",
    105: "FOOTER_STORY_PROPERTY",
    106: "FOOTNOTE_STORY_PROPERTY",
    107: "ENDNOTE_STORY_PROPERTY",
    108: "COMMENT_STORY_PROPERTY",
    109: "TEXTBOX_STORY_PROPERTY",
    110: "SETTINGS_PROPERTY",
    111: "STYLES_PROPERTY",
    112: "CODE_BLOCK_PROPERTY",
    113: "NUMBERING_PROPERTY",
    114: "PICTURE_PROPERTY",
    115: "TABLE_PROPERTY",
    116: "TABLE_CELL_PROPERTY",
    117: "TABLE_ROW_PROPERTY",
    118: "TABLE_AUTO_PROPERTY",
}

MODIFY_STYLE_TYPE_MAP = {
    1: "FONT_STYLE",
    2: "PARAGRAPH_STYLE",
    3: "CHARACTER_STYLE",
    4: "TABLE_STYLE",
    5: "LIST_STYLE",
    6: "SECTION_STYLE",
    7: "DOCUMENT_STYLE",
}

PARAGRAPH_ALIGNMENT_MAP = {
    1: "LEFT",
    2: "CENTER",
    3: "RIGHT",
    4: "JUSTIFY",
    5: "DISTRIBUTED",
}

CONTROL_CHAR_MAP = ControlChars._REPR_MAP


if __name__ == "__main__":
    print("=== MutationType ===")
    for mt in MutationType:
        print(f"  {mt.name} = {mt.value}")

    print("\n=== ModifyType ===")
    for mt in ModifyType:
        print(f"  {mt.name} = {mt.value}")

    print("\n=== ControlChars ===")
    for attr in dir(ControlChars):
        if not attr.startswith('_'):
            code = getattr(ControlChars, attr)
            if isinstance(code, int):
                print(f"  {attr} = 0x{code:02x} ({ControlChars.to_repr(code)})")
