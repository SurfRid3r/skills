# 腾讯文档枚举值完整参考

本文档汇总腾讯文档解析器中所有枚举值的定义和用法。

> **最后更新**: 2026-02-28

---

## MutationType (变更类型)

| Code | 字符串标识 | 含义 | 源码位置 |
|------|-----------|------|----------|
| 1 | "is" | INSERT_STRING - 插入字符串 | `public-firstload-pc-*.js:4520, 4859, 4905` |
| 2 | "ds" | DELETE_STRING - 删除字符串 | `public-firstload-pc-*.js:4863, 4906` |
| 3 | "mp" | MODIFY_PROPERTY - 修改属性 | `public-firstload-pc-*.js:4900` |
| 4 | "ms" | MODIFY_STYLE - 修改样式 | 推断值 |
| 5 | "cr" | COMMENT_REFERENCE - 评论引用 | ✅ 已确认 |

**重要**: `ty_code=5` 确认为 MutationType 5 (COMMENT_REFERENCE)

**源码证据:**
```javascript
// Line 4520: 检查类型是否为 "is" (INSERT_STRING)
e.type === a.MutationType.is && (t += e.mutation.text.length)

// Line 4859-4863: 插入和删除类型检查
if (t.type === o.MutationType.is && void 0 !== n) { ... }
t.type === o.MutationType.ds && void 0 !== n && ...

// Line 4900: 修改属性类型
if (e.type === o.MutationType.mp) { ... }
```

---

## ModifyType (修改类型 - status_code)

| Code | 名称 | 说明 | 源码位置 |
|------|------|------|----------|
| 101 | RUN_PROPERTY | Run 属性（文本运行） | `public-firstload-pc-*.js:56042, 56054` |
| 102 | PARAGRAPH_PROPERTY | 段落属性 | 推断值 |
| 103 | SECTION_PROPERTY | 节属性 | 推断值 |
| 104 | HEADER_STORY_PROPERTY | 页眉故事属性 | `public-firstload-pc-*.js:58262` |
| 105 | FOOTER_STORY_PROPERTY | 页脚故事属性 | `public-firstload-pc-*.js:58263` |
| 106 | FOOTNOTE_STORY_PROPERTY | 脚注故事属性 | `public-firstload-pc-*.js:58264` |
| 107 | ENDNOTE_STORY_PROPERTY | 尾注故事属性 | `public-firstload-pc-*.js:58265` |
| 108 | COMMENT_STORY_PROPERTY | 评注故事属性 | `public-firstload-pc-*.js:58266` |
| 109 | TEXTBOX_STORY_PROPERTY | 文本框故事属性 | `public-firstload-pc-*.js:58267` |
| 110 | SETTINGS_PROPERTY | 设置属性 | 推断值 |
| 111 | STYLES_PROPERTY | 样式属性 | 推断值 |
| 112 | CODE_BLOCK_PROPERTY | 代码块属性 | 推断值 |
| 113 | NUMBERING_PROPERTY | 编号属性 | 推断值 |
| 114 | PICTURE_PROPERTY | 图片属性 | 推断值 |
| 115 | TABLE_PROPERTY | 表格属性 | `feature-pc-bundle_word-helper-*.js:477` |
| 116 | TABLE_CELL_PROPERTY | 表格单元格属性 | 推断值 |
| 117 | TABLE_ROW_PROPERTY | 表格行属性 | 推断值 |
| 118 | TABLE_AUTO_PROPERTY | 表格自动属性 | 推断值 |

**关于 ModifyType 104 的说明**：

根据 JS 源码分析，ModifyType 104 被定义为 `HeaderStoryProperty`。这表明 104 是故事属性类型的编号，用于标识页眉故事。在腾讯文档的数据模型中：
- `STORY_PROPERTY` (104) 是通用类型
- `HEADER_STORY_PROPERTY` (104) 是具体实例，表示页眉故事
- 类似的，105-109 分别是页脚、脚注、尾注、评注、文本框的故事属性

**源码证据:**
```javascript
// Line 56042: 验证类型检查
verifyType(e) {
  return !!super.verifyType(e) && 101 === e.mutation.modifyType;
}

// Line 58262-58267: 故事属性映射
const t = new Map([
  ["HeaderStoryProperty", 104],
  ["FooterStoryProperty", 105],
  ["FootnoteStoryProperty", 106],
  ["EndnoteStoryProperty", 107],
  ["CommentStoryProperty", 108],
  ["TextboxStoryProperty", 109],
]);
```

---

## ModifyStyleType (样式修改类型)

| Code | 名称 | 说明 |
|------|------|------|
| 1 | FONT_STYLE | 字体样式 |
| 2 | PARAGRAPH_STYLE | 段落样式 |
| 3 | CHARACTER_STYLE | 字符样式 |
| 4 | TABLE_STYLE | 表格样式 |
| 5 | LIST_STYLE | 列表样式 |
| 6 | SECTION_STYLE | 节样式 |
| 7 | DOCUMENT_STYLE | 文档样式 |

---

## ParagraphAlignment (段落对齐)

| Code | 名称 | 说明 |
|------|------|------|
| 1 | LEFT | 左对齐 |
| 2 | CENTER | 居中 |
| 3 | RIGHT | 右对齐 |
| 4 | JUSTIFY | 两端对齐 |
| 5 | DISTRIBUTED | 分散对齐 |

---

## RangeType 定义

| Code | 名称 | 说明 | 源码位置 |
|------|------|------|----------|
| 1 | NormalRange | 普通范围 | 推断值 |
| 5 | RevisionRange | 修订范围 | `public-firstload-pc-*.js:55751-55755, 56131-56137` |

**关键区别**:
- `ty` (MutationType): 1-5，定义 mutation 的操作类型
- `rangeType`: 1, 5，定义范围类型，仅用于 InsertRangeMutation

**源码证据:**
```javascript
// Line 55751-55755: InsertRangeMutation 验证
static validateInsertRangeMutation(e, t) {
    return 5 === t.rangeType
      ? !!O.validateRange(e, t.beginIndex, t.endIndex) &&
          x.validateInsertRevisionRangeMutation(e, t)
      : O.validateRange(e, t.beginIndex, t.endIndex);
}

// Line 56131-56137: InsertRangeMutation 创建
new c.InsertRangeMutation({
  id: e.id,
  beginIndex: e.beginIndex,
  endIndex: e.endIndex,
  property: { [c.MutationPropType.revisionRange]: a },
  rangeType: 5,  // ← 这是 rangeType，不是 ty!
})
```

---

## MutationTarget (变更目标)

| 字符串值 | 含义 | 源码位置 |
|----------|------|----------|
| "run" | 文本运行 | `public-firstload-pc-*.js:56899` |
| "paragraph" | 段落 | `public-firstload-pc-*.js:56899` |
| "section" | 节 | `public-firstload-pc-*.js:56899` |
| "story" | 故事 | `public-firstload-pc-*.js:56899, 58252-58253` |
| "settings" | 设置 | `public-firstload-pc-*.js:56899` |
| "webSettings" | Web 设置 | `public-firstload-pc-*.js:56899` |
| "background" | 背景 | `public-firstload-pc-*.js:56899` |
| "styles" | 样式 | `public-firstload-pc-*.js:56899` |
| "numbering" | 编号 | `public-firstload-pc-*.js:56899` |
| "fonts" | 字体 | `public-firstload-pc-*.js:56899` |
| "themes" | 主题 | `public-firstload-pc-*.js:56899` |
| "table" | 表格 | `feature-pc-bundle_word-helper-*.js:477` |

**源码证据 (Line 56899 - 空文档初始化):**
```javascript
'{"bi":0,"ei":1,"ty":"mp","mm":"insert","mt":"run","pr":{"run":{"isPlaceholder":true}}}'
'{"bi":0,"ei":1,"ty":"mp","mm":"merge","mt":"paragraph","pr":{"paragraph":{...}}}'
'{"bi":2,"ei":3,"ty":"mp","mm":"merge","mt":"section","pr":{"section":{...}}}'
'{"bi":3,"ei":4,"ty":"mp","mm":"merge","mt":"story","pr":{"story":{"storyType":"STStoryType_mainDocument"}}}'
'{"ty":"ms","mt":"settings","pr":{"settings":{...}}}'
```

---

## 控制字符定义

### 基础控制字符

| 代码 | Unicode | 十六进制 | 名称 | 用途 | 源码位置 |
|------|---------|----------|------|------|----------|
| 0x0d | \\r | 13 | CARRIAGE_RETURN | 段落分隔符 | 源码中明确使用 |
| 0x0f | \\u000f | 15 | SHIFT_IN | 代码块开始/内联元素标记 | `public-firstload-pc-*.js:56899, 63252` |
| 0x1c | \\u001c | 28 | FILE_SEPARATOR | 图片标记 | 推断值 |
| 0x1d | \\u001d | 29 | GROUP_SEPARATOR | 代码块结束标记 | 推断值 |
| 0x1e | \\u001e | 30 | RECORD_SEPARATOR | 记录分隔符/段落/内联元素标记 | `public-firstload-pc-*.js:56899` |

### HYPERLINK 控制字符系统

| 代码 | Unicode | 十六进制 | 名称 | 用途 | 源码位置 |
|------|---------|----------|------|------|----------|
| 0x13 | \\x13 | 19 | FIELD_BEGIN | HYPERLINK 开始 | `public-firstload-pc-*.js:144, 63192` |
| 0x14 | \\x14 | 20 | FIELD_SEPARATE | URL 与显示文本分隔符 | `public-firstload-pc-*.js:145` |
| 0x15 | \\x15 | 21 | FIELD_END | HYPERLINK 结束 | `public-firstload-pc-*.js:146` |

**完整语法**: `\x13HYPERLINK <URL>\x14<显示文本>\x15`

**源码证据:**
```javascript
// Line 63192 - HYPERLINK 解析正则表达式
new RegExp("[\u0013](.*?)[\u0014]|[\u0015]", "ug")

// Line 144-146 - PlaceholderCharCode 定义
const a = String.fromCharCode(o.PlaceholderCharCode.FieldBegin),      // 0x13
      s = String.fromCharCode(o.PlaceholderCharCode.FieldSeparate),   // 0x14
      l = String.fromCharCode(o.PlaceholderCharCode.FieldEnd);        // 0x15
```

### List Marker 控制字符

| 代码 | Unicode | 十六进制 | 名称 | 用途 | 源码位置 |
|------|---------|----------|------|------|----------|
| 0x08 | \\b | 8 | BACKSPACE | List Marker 前缀 | `public-firstload-pc-*.js:34390, 35416` |

**语法**: `\b[x]` 其中 x 是 list marker 字符

| Marker | 列表类型 | 渲染字体 |
|--------|----------|----------|
| `\b-` | 无序列表 (bullet) | Wingdings |
| `\b8` | 有序列表 (numbering) | Wingdings |

**源码证据:**
```javascript
// Line 34390 - Bullet List 类型
e.BULLET_LIST = "bullet-list"

// Line 35416 - 段落 Bullet List
e.PARAGRAPH_BULLET_LIST = "paragraph-bullet-list"

// Line 28249 - Number Format
[24, "bullet"]

// Line 28303 - Bullet Symbol (■)
\u25A0
```

### 作者字段分隔符

| 代码 | Unicode | 十六进制 | 名称 | 用途 |
|------|---------|----------|------|------|
| 0x05 | \\x05 | 5 | ENQ | 作者字段分隔符 |

**格式**: `[type]\u001a\u0002\b\u0002\u0005\u0015\n\x13p.[user_id]\u0005[flags]\u0006...`

**作者类型前缀**:
- `.` - 普通作者
- `1` - 协作者
- `-` - 系统作者
- `9` - 特殊类型

### 表格控制字符

| 代码 | 十六进制 | 名称 | 用途 |
|------|----------|------|------|
| 0x1a | AUTHOR_FIELD_PREFIX | 表格开始 |
| 0x07 | TABLE_MARKER | 列分隔符 |
| 0x06 | AUTHOR_FIELD_VALUE | 行开始标记 |
| 0x1b | COMPARISON_MARKER | 表格结束 |

---

## 代码块控制字符模式

### 核心结构（固定）

| 位置 | Hex | 字符 | 含义 |
|------|-----|------|------|
| 开始 | `0x0f` | `\u000f` | CODE_BLOCK_START |
| 填充 | `0x1e × 5-6` | `\u001e` | RECORD_SEP (元数据槽位) |
| 行标记 | `0x1c` | `\u001c` | 语言标记/行分隔 |
| 行结束 | `0x0d 0x1d` | `\r\u001d` | 换行 + CODE_LINE_END |
| 结束 | `0x1e × N` | `\u001e` | 末尾填充 (可选) |

### 代码块解析流程

```
1. 定位 0x0f (CODE_BLOCK_START)
2. 跳过连续的 0x1e (RECORD_SEP 开头填充)
3. 遍历每一行:
   - 检测 0x1c (行标记) 作为行开始
   - 读取内容直到 0x1d (行结束)
   - 过滤内容中的控制字符 (保留 0x09 TAB)
4. 检测连续的 0x1e 作为代码块结束标记
5. 合并所有行内容，用换行符分隔
```

---

## 使用方法

### Python 代码使用

```python
from scripts.enums import (
    MutationType, ModifyType, ControlChars,
    MUTATION_TYPE_MAP, MODIFY_TYPE_MAP, CONTROL_CHAR_MAP,
    RANGE_TYPE_MAP, HYPERLINK_FIELD_NAME
)

# 使用解析器
from scripts.parser import TencentDocParser

parser = TencentDocParser(text_data)
result = parser.parse()

# 解析 HYPERLINK
hyperlink = ControlChars.parse_hyperlink(text)
# 返回: {'url': 'https://...', 'display_text': '...'}

# 解析 List Marker
list_marker = ControlChars.parse_list_marker(text)
# 返回: {'type': 'bullet', 'marker': '\\b-', 'marker_char': '-'}

# 解析作者字段
author = ControlChars.parse_author_field(text)
# 返回: {'user_id': '13102700362417930', 'flags': '...'}
```

---

## 相关文件

| 文件 | 说明 |
|------|------|
| `scripts/enums.py` | 枚举值定义集中管理 |
| `scripts/parser.py` | ultrabuf 解析器 |
| `scripts/format_parser.py` | 格式解析器 |
| `references/data-format.md` | 数据格式详细说明 |
| `references/format-parsing.md` | 控制字符处理逻辑 |
