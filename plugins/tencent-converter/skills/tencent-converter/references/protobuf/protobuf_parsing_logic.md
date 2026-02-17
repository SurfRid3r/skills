# 腾讯文档 ultrabuf Protobuf 解析逻辑分析

## 概述

本报告分析了腾讯文档 ultrabuf Protobuf 消息的解析逻辑，基于 JS 源码深度分析实现。

**数据来源**: `https://doc.weixin.qq.com/dop-api/opendoc` API
**数据格式**: Base64 编码的 ultrabuf Protobuf 消息
**分析时间**: 2026-02-04

---

## 1. 数据流程

### 1.1 数据路径

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

### 1.2 unescape 函数

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

## 2. ultrabuf Protobuf 消息结构

### 2.1 外层结构

```
Field 1 (length-delimited)
  └── 嵌套消息
      ├── Field 1 (varint): 版本号 = 1
      └── Field 2 (repeated): Mutation 列表
```

### 2.2 Mutation 结构

每个 Mutation 包含：

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

### 2.3 Wire Type 定义

| Wire Type | 类型 | 说明 |
|-----------|------|------|
| 0 | varint | 变长整数 |
| 1 | 64-bit | 固定 64 位 |
| 2 | length-delimited | 长度限定的字符串/字节/嵌套消息 |
| 5 | 32-bit | 固定 32 位 |

---

## 3. Varint 编码规则

### 3.1 编码原理

- 每个字节的最高位是 continuation bit
- 低 7 位是有效数据
- 小端序存储

### 3.2 解码算法

```python
def decode_varint(data: bytes, offset: int) -> Tuple[int, int]:
    """
    解码 varint，返回 (值, 新偏移量)
    """
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

## 4. Mutation 解析

### 4.1 MutationType 枚举

| Code | 名称 | 说明 |
|------|------|------|
| 1 | INSERT_STRING | 插入字符串 ("is") |
| 2 | DELETE_STRING | 删除字符串 ("ds") |
| 3 | MODIFY_PROPERTY | 修改属性 ("mp") |
| 4 | MODIFY_STYLE | 修改样式 ("ms") |

**重要**: `ty_code=5` 不是 MutationType，而是 `rangeType: 5` (RevisionRange - 修订范围)

### 4.2 ModifyType 枚举 (status_code)

| Code | 名称 | 说明 |
|------|------|------|
| 101 | RUN_PROPERTY | Run 属性（文本运行） |
| 102 | PARAGRAPH_PROPERTY | 段落属性 |
| 103 | SECTION_PROPERTY | 节属性 |
| 104 | HEADER_STORY_PROPERTY | 页眉故事属性 |
| 105 | FOOTER_STORY_PROPERTY | 页脚故事属性 |
| 106 | FOOTNOTE_STORY_PROPERTY | 脚注故事属性 |
| 107 | ENDNOTE_STORY_PROPERTY | 尾注故事属性 |
| 108 | COMMENT_STORY_PROPERTY | 评注故事属性 |
| 109 | TEXTBOX_STORY_PROPERTY | 文本框故事属性 |
| 110 | SETTINGS_PROPERTY | 设置属性 |
| 111 | STYLES_PROPERTY | 样式属性 |
| 112 | CODE_BLOCK_PROPERTY | 代码块属性 |
| 113 | NUMBERING_PROPERTY | 编号属性 |
| 114 | PICTURE_PROPERTY | 图片属性 |
| 115 | TABLE_PROPERTY | 表格属性 |
| 116 | TABLE_CELL_PROPERTY | 表格单元格属性 |
| 117 | TABLE_ROW_PROPERTY | 表格行属性 |
| 118 | TABLE_AUTO_PROPERTY | 表格自动属性 |

### 4.3 Mutation 数据类

```python
@dataclass
class Mutation:
    """Mutation 操作"""
    ty: int = 0                           # 类型: 1=is, 2=ds, 3=mp, 4=ms
    mt: Optional[str] = None              # 目标: run, paragraph, section, etc.
    mm: Optional[str] = None              # 模式: insert, merge, etc.
    bi: Optional[int] = None              # Begin Index
    ei: Optional[int] = None              # End Index
    s: Optional[str] = None               # String content (仅 ty=1 时)
    pr: Optional[Dict] = None             # Property object
    author: Optional[str] = None          # 作者/用户ID
    status_code: Optional[int] = None     # 状态码
    marker: Optional[str] = None          # 标记
    image_info: Optional[ImageInfo] = None  # 图片信息
    range_type: Optional[int] = None      # Range Type (1=Normal, 5=RevisionRange)
    hyperlink: Optional[Dict] = None      # HYPERLINK 信息
    list_marker: Optional[Dict] = None    # List Marker 信息
```

---

## 5. 控制字符处理

### 5.1 控制字符定义

| 代码 | 字符 | 用途 |
|------|------|------|
| 0x0d | \\r | 段落分隔符 |
| 0x0f | \\u000f | 代码块开始 |
| 0x1c | \\u001c | 图片标记 |
| 0x1d | \\u001d | 代码块结束 |
| 0x1e | \\u001e | 记录分隔符 |
| 0x08 | \\b | List Marker 前缀 |
| 0x13 | \\x13 | HYPERLINK 开始 |
| 0x14 | \\x14 | HYPERLINK URL分隔符 |
| 0x15 | \\x15 | HYPERLINK 结束 |

### 5.2 List Marker 系统

语法: `\b[x]` 其中 x 是 list marker 字符

- `\b-` = 无序列表 (bullet list)
- `\b8` = 有序列表 (numbering list)

渲染字体: Wingdings

### 5.3 HYPERLINK 系统

完整语法: `\x13HYPERLINK <URL>\x14<显示文本>\x15`

```python
def parse_hyperlink(cls, text: str) -> dict:
    """
    解析 HYPERLINK 控制字符序列

    语法: \x13HYPERLINK <URL>\x14<显示文本>\x15
    """
    import re
    pattern = r'\x13HYPERLINK\s+([^\x14]+)\x14([^\x15]+)\x15'
    match = re.search(pattern, text)
    if match:
        return {
            'url': match.group(1).strip(),
            'display_text': match.group(2).strip()
        }
    return None
```

---

## 6. 图片信息提取

### 6.1 ImageInfo 数据类

```python
@dataclass
class ImageInfo:
    """图片信息"""
    url: str
    width: Optional[int] = None
    height: Optional[int] = None
    mime_type: Optional[str] = None
```

### 6.2 识别标记

图片信息嵌在 mutation 的 Field 7 (author) 中，识别标记：

- Field 7 的 raw_bytes 中包含 `wdcdn` 或 `qpic` 关键字
- 从 URL 参数中提取尺寸和类型：
  - `w=` 宽度
  - `h=` 高度
  - `type=` MIME 类型

```python
def _extract_image_from_bytes(self, data: bytes) -> Optional[ImageInfo]:
    """从字节中提取图片信息"""
    try:
        text = data.decode('utf-8', errors='ignore')
        url_pattern = r'https?://[^\s<>"\x00-\x1f]+'
        for url in re.findall(url_pattern, text):
            if any(kw in url for kw in ['wdcdn', 'qpic', 'image', 'img']):
                img_info = ImageInfo(url=url)
                # 提取尺寸
                w_match = re.search(r'w=(\d+)', url)
                h_match = re.search(r'h=(\d+)', url)
                if w_match:
                    img_info.width = int(w_match.group(1))
                if h_match:
                    img_info.height = int(h_match.group(1))
                # 提取 mime 类型
                type_match = re.search(r'type=([^&]+)', url)
                if type_match:
                    img_info.mime_type = type_match.group(1)
                return img_info
    except:
        pass
    return None
```

### 6.3 图片 URL 格式

```
https://wdcdn.qpic.cn/MTY4ODg1NDMwODQxNTUxNg_333054_o3leuNdJBXuCHvUZ_1769945968?w=1126&h=264&type=image/png*
```

---

## 6.5. 中文文本编码对照表

| 文本 | UTF-8 编码 | 十六进制 |
|------|------------|----------|
| 标题 | U+6807 U+9898 | `e6a087 e9a298` |
| 正文 | U+6B63 U+6587 | `e6ada3 e69687` |
| 图片 | U+56FE U+7247 | `e59bbe e78987` |
| 测试 | U+6D4B U+8BD5 | `e6b58b e8af95` |

---

## 7. 文档结构构建

### 7.1 DocumentBuilder

基于 mutations 构建文档结构，按照 bi/ei 索引顺序重建文档：

```python
class DocumentBuilder:
    """
    基于 mutations 构建文档结构

    按照生物/ei 索引顺序重建文档，正确关联文本和图片位置
    """

    def __init__(self, mutations: List[Mutation]):
        self.mutations = mutations
        self.positions: List[TextPosition] = []
        self._build_document()
```

### 7.2 TextPosition

文档位置元素：

```python
@dataclass
class TextPosition:
    """文档位置元素"""
    index: int              # 位置索引
    type: str               # 类型: text, image, paragraph_break
    content: Any            # 内容: 文本字符串或 ImageInfo
    mutations: List[int]    # 影响此位置的 mutation 索引列表
```

---

## 8. 使用方法

### 8.1 Python 解析

```python
from scripts.parse_ultrabuf.parser import TencentDocParser

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

### 8.2 命令行使用

```bash
# Step 1: 解析 ultrabuf → intermediate.json
python3 scripts/parse_ultrabuf/parser.py opendoc_response.json -o output/case1/case1

# Step 2: 解析格式 → result.json
python3 scripts/parse_ultrabuf/format_parser.py output/case1/case1_intermediate.json -o output/case1/result.json

# 显示详细信息
python3 scripts/parse_ultrabuf/parser.py opendoc_response.json -o output/case1/case1 -v
```

---

## 9. 相关文件

| 文件 | 说明 |
|------|------|
| `scripts/parse_ultrabuf/parser.py` | Step 1: ultrabuf 解析器 (opendoc → intermediate.json) |
| `scripts/parse_ultrabuf/format_parser.py` | Step 2: 格式解析器 (intermediate.json → result.json) |
| `scripts/parse_ultrabuf/enums.py` | 枚举值定义集中管理 |
| `scripts/parse_ultrabuf/02_analyze_enums.py` | 枚举值统计分析 |
| `scripts/to_markdown/main.py` | Markdown 转换 (result.json → doc.md) |

---

**文档版本**: 2.1
**最后更新**: 2026-02-14
**基于**: scripts/parse_ultrabuf/parser.py
