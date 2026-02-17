# 腾讯文档 JavaScript 源码分析总结

## 执行摘要

本报告详细分析了腾讯文档处理 `initialAttributedText.text[0]` 数据的 JavaScript 源码逻辑。

## 任务完成情况

### 1. 已下载的 JS 文件

| 文件 | 大小 | 来源 |
|------|------|------|
| `public-common-d2f2905e.js` | 463KB | https://res.wx.qq.com/d/doc/js/public-common-d2f2905e.js |
| `feature-pc-bundle_word-helper-10be9b90.js` | 18KB | https://res.wx.qq.com/d/doc/js/feature-pc-bundle_word-helper-10be9b90.js |

**位置**: `/Users/surfrid3r/Desktop/Temp/SangforXDR/tencent_js/`

### 2. 关键代码片段

#### 2.1 initialAttributedText 赋值逻辑

**文件**: `feature-pc-bundle_word-helper-10be9b90.js`
**位置**: 字节偏移 ~20437

```javascript
(a.clientVars.collab_client_vars.initialAttributedText.text = r),
(a.clientVars.collab_client_vars.initialAttributedText.attribs = t.attribs.value);
```

#### 2.2 数据使用模式

```javascript
// 使用 unescape 处理文本数据
data: unescape(t.initialAttributedText.text || "")

// 版本信息
version: t.rev,
dver: t.collab_client_vars.dver
```

#### 2.3 初始数据结构

```javascript
initialAttributedText: {
  text: "%0A%0A%0F%03%02%0A%03%0A",
  attribs: "*0*1*2+1+2*3+1*4*5+1+1*4*5+1+1"
}
```

### 3. 数据结构

```
Base64 编码的字符串
  └── Base64 解码
      └── Protobuf 二进制消息 (ultrabuf 格式)
          └── Field 1 (length-delimited)
              ├── Field 1 (varint): 版本号 = 1
              └── Field 2 (repeated): 操作记录数组 (Mutations)
                  ├── Field 1: ty (MutationType)
                  ├── Field 2: bi (beginIndex)
                  ├── Field 3: ei (endIndex)
                  ├── Field 4: mt (mutation target)
                  ├── Field 5: mm (mutation mode)
                  ├── Field 6: s (string content) 或 pr (property)
                  ├── Field 7: author/userId
                  ├── Field 8: status_code (ModifyType)
                  └── ...
```

### 4. 控制字符定义

| 分隔符 | 代码 | 十六进制 | 名称 | 用途 |
|--------|------|----------|------|------|
| \\r | 13 | 0x0d | CARRIAGE_RETURN | 段落分隔符 |
| \\f | 12 | 0x0c | FORM_FEED | 分页符 |
| \\x1e | 30 | 0x1e | RECORD_SEPARATOR | 记录分隔符 |
| \\x1c | 28 | 0x1c | FILE_SEPARATOR | 图片标记 |
| \\x1d | 29 | 0x1d | GROUP_SEPARATOR | 代码块结束标记 |
| \\b | 8 | 0x08 | BACKSPACE | List Marker 前缀 |
| \\x13 | 19 | 0x13 | FIELD_BEGIN | HYPERLINK 开始 |
| \\x14 | 20 | 0x14 | FIELD_SEPARATE | URL 与显示文本分隔符 |
| \\x15 | 21 | 0x15 | FIELD_END | HYPERLINK 结束 |
| \\x05 | 5 | 0x05 | ENQ | 作者字段分隔符 |

### 5. 已实现的功能

| 功能 | 文件 | 状态 |
|------|------|------|
| 数据获取 | `scripts/01_fetch_data.py` | ✅ |
| JS 文件下载 | `scripts/02_download_js.py` | ✅ |
| ultrabuf 解析器 | `scripts/parse_ultrabuf/parser.py` | ✅ |
| 枚举值分析 | `scripts/parse_ultrabuf/enums.py` | ✅ |
| HYPERLINK 解析 | `scripts/parse_ultrabuf/enums.py` | ✅ |
| List Marker 解析 | `scripts/parse_ultrabuf/enums.py` | ✅ |
| DocumentBuilder | `scripts/parse_ultrabuf/parser.py` | ✅ |
| 分析文档 | `docs/02_protobuf/`, `docs/03_enums/` | ✅ |

### 6. 源码统计

在 `public-common-d2f2905e.js` (463KB) 中：
- `Uint8Array`: 39 处使用
- `charCodeAt`: 29 处使用
- `fromCharCode`: 8 处使用
- `btoa`: 1 处使用
- `unescape`: 1 处使用

在 `feature-pc-bundle_word-helper-10be9b90.js` (18KB) 中：
- `attribs` 访问: 2 处
- `collab_client_vars` 访问: 26 处
- `version/rev` 访问: 8 处

### 7. 解析结果

从示例数据 (`opendoc_response.json`) 中提取：
- **Base64 数据长度**: 6664 字符
- **解码后长度**: 4998 字节
- **版本号**: 1
- **操作记录数**: 76
- **文本段落数**: 4
- **图片数量**: 1

## 关键发现

### 1. 数据格式

- `initialAttributedText.text[0]` 是 **Base64 编码的 ultrabuf Protobuf 消息**
- 使用 `unescape()` 函数进行 URL 解码（非标准 Base64）
- 数据包含版本信息、Mutations 列表和文本内容

### 2. MutationType 枚举值

| Code | 字符串标识 | 含义 |
|------|-----------|------|
| 1 | "is" | INSERT_STRING - 插入字符串 |
| 2 | "ds" | DELETE_STRING - 删除字符串 |
| 3 | "mp" | MODIFY_PROPERTY - 修改属性 |
| 4 | "ms" | MODIFY_STYLE - 修改样式 |

**注意**: `ty_code=5` 不是 MutationType，而是 `rangeType: 5` (RevisionRange - 修订范围)

### 3. ModifyType 枚举值

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
| 110-115 | 其他属性 | SETTINGS, STYLES, CODE_BLOCK, NUMBERING, PICTURE, TABLE |

### 4. 解析流程

1. **Base64 解码** → 获取 Protobuf 二进制
2. **Varint 解析** → 解析字段标签和值
3. **嵌套消息解析** → 递归处理嵌套结构
4. **Mutation 提取** → 从 Protobuf 字段中提取 Mutation 列表
5. **控制字符处理** → 解析 HYPERLINK、List Marker 等特殊标记
6. **DocumentBuilder** → 基于 bi/ei 索引重建文档结构

### 5. 文本处理

- 使用 `\\r` (0x0d) 作为主要段落分隔符
- 控制字符需要根据语义处理，不应简单过滤
- 支持中文 UTF-8 编码
- HYPERLINK 语法: `\x13HYPERLINK <URL>\x14<显示文本>\x15`
- List Marker 语法: `\b[x]` (x=- 无序, x=8 有序)

## 解析器使用方法

### 命令行使用

```bash
# 基本解析
python3 scripts/parse_ultrabuf/parser.py output/case1/opendoc_response.json -o output/case1/case1

# 显示详细信息和所有 mutations
python3 scripts/parse_ultrabuf/parser.py output/case1/opendoc_response.json -o output/case1/case1 -v --mutations
```

### Python 代码使用

```python
from scripts.parse_ultrabuf.parser import TencentDocParser
from scripts.parse_ultrabuf.enums import (
    MutationType, ModifyType, ControlChars,
    MUTATION_TYPE_MAP, MODIFY_TYPE_MAP
)

# 解析文档
parser = TencentDocParser(text_data)
result = parser.parse()

# 解析 HYPERLINK
hyperlink = ControlChars.parse_hyperlink(text)
# 返回: {'url': 'https://...', 'display_text': '...'}

# 解析 List Marker
list_marker = ControlChars.parse_list_marker(text)
# 返回: {'type': 'bullet', 'marker': '\\b-', 'marker_char': '-'}
```

## 下一步建议

### 短期任务

1. **完善 ModifyType 110-115 验证**
   - 在 JS 源码中搜索对应的属性名称定义
   - 验证推断的枚举值是否正确

2. **探索 RangeType 完整定义**
   - 当前确认: 1 (NormalRange), 5 (RevisionRange)
   - 是否存在 2, 3, 4?

### 长期任务

1. **支持更多文档类型**
   - Excel
   - PPT
   - 其他腾讯文档格式

2. **导出功能增强**
   - 更完整的 Markdown 转换
   - 导出为 Word
   - 导出为 PDF

3. **性能优化**
   - 缓存解码结果
   - 增量解析支持

## 文件清单

### 源码文件
- `/Users/surfrid3r/Desktop/Temp/SangforXDR/tencent_js/public-common-d2f2905e.js`
- `/Users/surfrid3r/Desktop/Temp/SangforXDR/tencent_js/feature-pc-bundle_word-helper-10be9b90.js`

### 脚本文件
- `/Users/surfrid3r/Desktop/Temp/SangforXDR/scripts/01_fetch_data.py` - 数据获取
- `/Users/surfrid3r/Desktop/Temp/SangforXDR/scripts/02_download_js.py` - JS 下载
- `/Users/surfrid3r/Desktop/Temp/SangforXDR/scripts/parse_ultrabuf/parser.py` - ultrabuf 解析器
- `/Users/surfrid3r/Desktop/Temp/SangforXDR/scripts/parse_ultrabuf/enums.py` - 枚举值定义

### 分析文件
- `/Users/surfrid3r/Desktop/Temp/SangforXDR/docs/02_protobuf/` - Protobuf 分析文档
- `/Users/surfrid3r/Desktop/Temp/SangforXDR/docs/03_enums/` - 枚举值分析文档
- `/Users/surfrid3r/Desktop/Temp/SangforXDR/docs/01_overview/JS_ANALYSIS_SUMMARY.md` - 本总结文件

---

**报告日期**: 2026-02-04
**状态**: ✅ 分析完成，解析器已实现
