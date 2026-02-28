# 腾讯文档数据格式分析

## 概述

本文档总结了腾讯文档 `initialAttributedText.text[0]` 数据格式的完整分析结果。

**核心结论**：`initialAttributedText.text[0]` 是 **Base64 编码的 ultrabuf Protobuf 消息**。

**数据来源**: `https://doc.weixin.qq.com/dop-api/opendoc` API

## 数据流程

```
API Response (opendoc)
    ↓
initialAttributedText.text[0] (Base64 + URL 编码)
    ↓
unescape() (JavaScript 函数，处理 URL 编码)
    ↓
Base64 解码
    ↓
ultrabuf.decode() (Protobuf 解析)
    ↓
Command (Mutations 列表)
```

### 数据路径

```
opendoc API 响应
  └── clientVars
      └── collab_client_vars
          └── initialAttributedText
              └── text[0] (Base64 字符串)
                  └── unescape()
                      └── Base64 解码
                          └── ultrabuf.decode() → Command
```

### unescape 函数

实现 JavaScript 的 unescape 函数，处理 URL 编码：

```python
def unescape(s: str) -> str:
    """
    实现 JavaScript 的 unescape 函数
    在 JS 中，unescape 用于处理 URL 编码的字符串
    %xx 形式的编码会被解码为对应的字符
    """
    # 处理 %uXXXX 格式 (Unicode)
    def replace_unicode(match):
        try:
            code = int(match.group(1), 16)
            return chr(code)
        except:
            return match.group(0)

    # 处理 %XX 格式 (ASCII)
    def replace_ascii(match):
        try:
            code = int(match.group(1), 16)
            return chr(code)
        except:
            return match.group(0)

    # 先处理 %uXXXX，再处理 %XX
    result = re.sub(r'%u([0-9a-fA-F]{4})', replace_unicode, s)
    result = re.sub(r'%([0-9a-fA-F]{2})', replace_ascii, result)

    return result
```

---

## ultrabuf Mutation 结构

### 外层结构

```
Field 1 (length-delimited)
  └── 嵌套消息
      ├── Field 1 (varint): 版本号 = 1
      └── Field 2 (repeated): Mutation 列表
```

### Mutation 字段

腾讯文档使用 ultrabuf 格式存储文档变更，每个 Mutation 包含以下字段：

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `ty` | int | MutationType: 1=is(插入), 2=ds(删除), 3=mp(修改属性), 4=ms(修改样式) | 1 |
| `mt` | string | MutationTarget: run, paragraph, section, story, settings 等 | "run" |
| `mm` | string | MutationMode: insert, delete, merge, split, replace | "insert" |
| `bi` | int | Begin Index (起始位置) | 0 |
| `ei` | int | End Index (结束位置) | 10 |
| `s` | string | String content (文本内容，仅 ty=1 时有效) | "这是文本" |
| `pr` | dict | Property (属性对象) | {"run": {...}} |
| `author` | string | 作者/用户ID | "13102700362417930" |
| `status_code` | int | ModifyType (修改类型): 101-118 | 101 |
| `marker` | string | 标记 | - |
| `flags` | int | 标志位 | - |
| `range_type` | int | RangeType: 1=Normal, 5=RevisionRange | 1 |
| `image_info` | ImageInfo | 图片信息（当 mutation 包含图片时） | ImageInfo(url=...) |
| `hyperlink` | dict | HYPERLINK 信息 (从文本中解析) | {"url": "...", "display_text": "..."} |
| `list_marker` | dict | List Marker 信息 (从文本中解析) | {"type": "bullet", "marker": "\\b-"} |

### Protobuf 字段映射

| 字段编号 | Wire Type | 字段名 | 说明 |
|----------|-----------|--------|------|
| 1 | 0 (varint) | ty | MutationType (1-4) |
| 2 | 2 (length-delimited) | bi | Begin Index (嵌套在 Field 1 中) |
| 3 | 2 (length-delimited) | ei | End Index (嵌套在 Field 1 中) |
| 4 | 0/2 | mt | Mutation Target |
| 5 | 0/2 | mm | Mutation Mode |
| 6 | 2 (length-delimited) | s/pr | String content 或 Property |
| 7 | 2 (length-delimited) | author | 作者/用户ID 或图片信息 |
| 8 | 0 (varint) | status_code | ModifyType |
| 9 | 2 (length-delimited) | marker | 标记 |
| 10 | 0/2 | flags | 标志 |

### Wire Type 定义

| Wire Type | 类型 | 说明 |
|-----------|------|------|
| 0 | varint | 变长整数 |
| 1 | 64-bit | 固定 64 位 |
| 2 | length-delimited | 长度限定的字符串/字节/嵌套消息 |
| 5 | 32-bit | 固定 32 位 |

---

## Varint 编码规则

### 编码原理

- 每个字节的最高位是 continuation bit
- 低 7 位是有效数据
- 小端序存储

### 解码算法

```python
def decode_varint(data: bytes, offset: int) -> Tuple[int, int]:
    """解码 varint，返回 (值, 新偏移量)"""
    result = 0
    shift = 0

    while offset < len(data):
        byte = data[offset]
        offset += 1
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):  # continuation bit 为 0，结束
            break
        shift += 7

    return result, offset
```

---

## 枚举值定义

### MutationType (变更类型)

| Code | 字符串标识 | 含义 | 状态 |
|------|-----------|------|------|
| 1 | "is" | INSERT_STRING - 插入字符串 | ✅ 已确认 |
| 2 | "ds" | DELETE_STRING - 删除字符串 | ✅ 已确认 |
| 3 | "mp" | MODIFY_PROPERTY - 修改属性 | ✅ 已确认 |
| 4 | "ms" | MODIFY_STYLE - 修改样式 | ✅ 已确认 |
| 5 | "cr" | COMMENT_REFERENCE - 评论引用 | ✅ 已确认 |

### ModifyType (修改类型 - status_code)

| Code | 名称 | 说明 | 状态 |
|------|------|------|------|
| 101 | RUN_PROPERTY | Run 属性（文本运行） | ✅ 已确认 |
| 102 | PARAGRAPH_PROPERTY | 段落属性 | ✅ 推断值 |
| 103 | SECTION_PROPERTY | 节属性 | ✅ 推断值 |
| 104 | HEADER_STORY_PROPERTY | 页眉故事属性 | ✅ 已确认 |
| 105 | FOOTER_STORY_PROPERTY | 页脚故事属性 | ✅ 已确认 |
| 106 | FOOTNOTE_STORY_PROPERTY | 脚注故事属性 | ✅ 已确认 |
| 107 | ENDNOTE_STORY_PROPERTY | 尾注故事属性 | ✅ 已确认 |
| 108 | COMMENT_STORY_PROPERTY | 评注故事属性 | ✅ 已确认 |
| 109 | TEXTBOX_STORY_PROPERTY | 文本框故事属性 | ✅ 已确认 |
| 110 | SETTINGS_PROPERTY | 设置属性 | ✅ 已验证 |
| 111 | STYLES_PROPERTY | 样式属性 | ✅ 已验证 |
| 112 | CODE_BLOCK_PROPERTY | 代码块属性 | ✅ 已验证 |
| 113 | NUMBERING_PROPERTY | 编号属性 | ✅ 已验证 |
| 114 | PICTURE_PROPERTY | 图片属性 | ✅ 已验证 |
| 115 | TABLE_PROPERTY | 表格属性 | ✅ 已验证 |
| 116 | TABLE_CELL_PROPERTY | 表格单元格属性 | ✅ 已验证 |
| 117 | TABLE_ROW_PROPERTY | 表格行属性 | ✅ 已验证 |
| 118 | TABLE_AUTO_PROPERTY | 表格自动属性 | ✅ 已验证 |

### ModifyStyleType (样式修改类型)

| Code | 名称 | 说明 |
|------|------|------|
| 1 | FONT_STYLE | 字体样式 |
| 2 | PARAGRAPH_STYLE | 段落样式 |
| 3 | CHARACTER_STYLE | 字符样式 |
| 4 | TABLE_STYLE | 表格样式 |
| 5 | LIST_STYLE | 列表样式 |
| 6 | SECTION_STYLE | 节样式 |
| 7 | DOCUMENT_STYLE | 文档样式 |

### ParagraphAlignment (段落对齐)

| Code | 名称 | 说明 |
|------|------|------|
| 1 | LEFT | 左对齐 |
| 2 | CENTER | 居中 |
| 3 | RIGHT | 右对齐 |
| 4 | JUSTIFY | 两端对齐 |
| 5 | DISTRIBUTED | 分散对齐 |

### MutationTarget (变更目标)

| 字符串值 | 含义 |
|----------|------|
| "run" | 文本运行 |
| "paragraph" | 段落 |
| "section" | 节 |
| "story" | 故事 |
| "settings" | 设置 |
| "webSettings" | Web 设置 |
| "background" | 背景 |
| "styles" | 样式 |
| "numbering" | 编号 |
| "fonts" | 字体 |
| "themes" | 主题 |
| "table" | 表格 |

---

## 控制字符系统

腾讯文档使用特殊控制字符标记各种文档元素：

| 代码 | 字符 | 用途 | 语法示例 |
|------|------|------|----------|
| 0x0d | \\r | 段落分隔符 | 段落1\\r段落2 |
| 0x0f | \\u000f | 代码块开始/内联元素标记 | \\u000f代码\\u001d |
| 0x1c | \\u001c | 图片标记 | \\u001c[图片信息] |
| 0x1d | \\u001d | 代码块结束/组分隔符 | 见 0x0f |
| 0x1e | \\u001e | 记录分隔符 | - |
| 0x13 | \\x13 | HYPERLINK 开始 | \\x13HYPERLINK <URL>\\x14文本\\x15 |
| 0x14 | \\x14 | URL 与显示文本分隔符 | 见 0x13 |
| 0x15 | \\x15 | HYPERLINK 结束 | 见 0x13 |
| 0x08 | \\b | List Marker 前缀 | \\b- (无序), \\b8 (有序) |
| 0x05 | \\x05 | 作者字段分隔符 | p.[user_id]\\x05[flags]\\x06 |

---

## 图片信息提取

### ImageInfo 数据类

```python
@dataclass
class ImageInfo:
    """图片信息"""
    url: str
    width: Optional[int] = None
    height: Optional[int] = None
    mime_type: Optional[str] = None
```

### 识别标记

图片信息嵌在 mutation 的 Field 7 (author) 中，识别标记：
- Field 7 的 raw_bytes 中包含 `wdcdn` 或 `qpic` 关键字
- 从 URL 参数中提取尺寸和类型：`w=` 宽度, `h=` 高度, `type=` MIME 类型

### 图片 URL 格式

```
https://wdcdn.qpic.cn/MTY4ODg1NDMwODQxNTUxNg_333054_o3leuNdJBXuCHvUZ_1769945968?w=1126&h=264&type=image/png*
```

---

## 使用解析器

### 命令行使用

```bash
# 解析文档并生成 JSON 和 Markdown
python3 scripts/convert.py opendoc_response.json -o output/result.md -v

# 分步调试
python3 scripts/parser.py opendoc_response.json -o output/case1/case1 -v
python3 scripts/format_parser.py output/case1/case1_intermediate.json -o output/case1/result.json
```

### Python 代码使用

```python
from scripts.parser import TencentDocParser
from scripts.enums import (
    MutationType, ModifyType, ControlChars,
    MUTATION_TYPE_MAP, MODIFY_TYPE_MAP, CONTROL_CHAR_MAP
)
import json

# 读取数据
with open('opendoc_response.json', 'r') as f:
    data = json.load(f)

text_data = data['clientVars']['collab_client_vars']['initialAttributedText']['text'][0]

# 解析
parser = TencentDocParser(text_data)
result = parser.parse()

print(f"版本: {result['version']}")
print(f"Mutation 数量: {result['mutations_count']}")
print(f"图片数量: {result['image_count']}")

# 解析 HYPERLINK
hyperlink = ControlChars.parse_hyperlink(text)
# 返回: {'url': 'https://...', 'display_text': '...'}

# 解析 List Marker
list_marker = ControlChars.parse_list_marker(text)
# 返回: {'type': 'bullet', 'marker': '\\b-', 'marker_char': '-'}
```

---

**更新日期**: 2026-02-28
**状态**: ✅ 分析完成，解析器已实现
