# 腾讯文档数据格式分析总结

## 概述

本文档总结了腾讯文档 `initialAttributedText.text[0]` 数据格式的完整分析结果。

**核心结论**：`initialAttributedText.text[0]` 是 **Base64 编码的 ultrabuf Protobuf 消息**。

## 数据格式详解

### 1. 数据流程

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

### 2. ultrabuf Mutation 结构

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
| `status_code` | int | ModifyType (修改类型): 101-115 | 101 |
| `marker` | string | 标记 | - |
| `flags` | int | 标志位 | - |
| `range_type` | int | RangeType: 1=Normal, 5=RevisionRange | 1 |
| `image_info` | ImageInfo | 图片信息（当 mutation 包含图片时） | ImageInfo(url=...) |
| `hyperlink` | dict | HYPERLINK 信息 (从文本中解析) | {"url": "...", "display_text": "..."} |
| `list_marker` | dict | List Marker 信息 (从文本中解析) | {"type": "bullet", "marker": "\\b-"} |

### 3. Protobuf 字段映射

ultrabuf 使用以下 Protobuf 字段编号：

| 字段编号 | Wire Type | 内容 |
|----------|-----------|------|
| 1 | varint | ty (MutationType) |
| 2 | nested | bi (beginIndex) |
| 3 | nested | ei (endIndex) |
| 4 | string/varint | mt (mutation target) |
| 5 | string/varint | mm (mutation mode) |
| 6 | nested | s (string content) 或 pr (property) |
| 7 | bytes | author/userId 或图片信息 |
| 8 | varint | status_code (ModifyType) |
| 9 | bytes | marker |
| 10 | varint | flags |

### 4. 控制字符系统

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

## 使用解析器

项目提供了完整的 ultrabuf 解析器实现：

### 命令行使用

```bash
# 解析文档并生成 JSON 和 Markdown
python3 scripts/parse_ultrabuf/01_parser.py data/opendoc_response.json -o output/case1/result

# 显示详细信息和所有 mutations
python3 scripts/parse_ultrabuf/01_parser.py data/opendoc_response.json -o output/case1/result -v --mutations
```

### Python 代码使用

```python
from scripts.parse_ultrabuf.parser import TencentDocParser
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
```

## 枚举值定义

所有枚举值定义在 `scripts/parse_ultrabuf/enums.py` 中：

```python
from scripts.parse_ultrabuf.enums import (
    MutationType,      # 1-4: is/ds/mp/ms
    ModifyType,        # 101-115: 属性类型
    ControlChars,      # 控制字符
    MutationTarget,    # 目标类型常量
    MutationMode,      # 模式常量
    MUTATION_TYPE_MAP,
    MODIFY_TYPE_MAP,
    CONTROL_CHAR_MAP,
)
```

## 相关文档

- `js_enum_validation.md` - JS 枚举值验证结果
- `protobuf_analysis.md` - Protobuf 数据格式详细分析
- `../../CLAUDE.md` - 项目开发指南

---

**更新日期**: 2026-02-04
**状态**: ✅ 分析完成，解析器已实现
