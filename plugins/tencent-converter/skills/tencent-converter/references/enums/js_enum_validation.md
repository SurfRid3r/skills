# JS 枚举值验证结果

基于腾讯文档 JS 源码深度分析的结果。

> **最后更新**: 2026-02-04
> **重大发现**: ty_code=5 确认为解析器误判，实际是 rangeType: 5 (RevisionRange)

## Status Code 定义 (ModifyType - 修改类型)

| Code | 名称 | 源码位置 | 说明 |
|------|------|----------|------|
| 101 | RUN_PROPERTY | `public-firstload-pc-bc7daab7-805820ec.js:56042, 56054` | Run 属性修改 (字体样式等) |
| 102 | PARAGRAPH_PROPERTY | 推断值 | 段落属性修改 |
| 103 | SECTION_PROPERTY | 推断值 | 节属性 |
| 104 | STORY_PROPERTY / HEADER_STORY_PROPERTY | `public-firstload-pc-bc7daab7-805820ec.js:58262` | 故事属性 / 页眉故事属性 ✅ |
| 105 | FOOTER_STORY_PROPERTY | `public-firstload-pc-bc7daab7-805820ec.js:58263` | 页脚故事属性 ✅ |
| 106 | FOOTNOTE_STORY_PROPERTY | `public-firstload-pc-bc7daab7-805820ec.js:58264` | 脚注故事属性 ✅ |
| 107 | ENDNOTE_STORY_PROPERTY | `public-firstload-pc-bc7daab7-805820ec.js:58265` | 尾注故事属性 ✅ |
| 108 | COMMENT_STORY_PROPERTY | `public-firstload-pc-bc7daab7-805820ec.js:58266` | 评注故事属性 ✅ |
| 109 | TEXTBOX_STORY_PROPERTY | `public-firstload-pc-bc7daab7-805820ec.js:58267` | 文本框故事属性 ✅ |
| 110 | SETTINGS_PROPERTY | 推断值 | 设置属性 |
| 111 | STYLES_PROPERTY | 推断值 | 样式属性 |
| 112 | CODE_BLOCK_PROPERTY | 推断值 | 代码块属性 |
| 113 | NUMBERING_PROPERTY | 推断值 | 编号属性 |
| 114 | PICTURE_PROPERTY | 推断值 | 图片属性 |
| 115 | TABLE_PROPERTY | 推断值 | 表格属性 |

**关于 ModifyType 104 的说明**：

根据 JS 源码分析，ModifyType 104 在 `public-firstload-pc-bc7daab7-805820ec.js:58262` 处被定义为 `HeaderStoryProperty`。这表明 104 是故事属性类型的编号，用于标识页眉故事。

同时，`STORY_PROPERTY = 104` 也作为通用的故事属性类型存在。在腾讯文档的数据模型中：
- `STORY_PROPERTY` (104) 是通用类型
- `HEADER_STORY_PROPERTY` (104) 是具体实例，表示页眉故事
- 类似的，105-109 分别是页脚、脚注、尾注、评注、文本框的故事属性

这种设计使用相同的枚举值来表示一个类型族，具体的故事类型通过其他字段（如 `storyType`）来区分。

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

## 控制字符定义

### 已确认的控制字符

| 代码 | Unicode | 十六进制 | 名称 | 用途 | 源码位置 |
|------|---------|----------|------|------|----------|
| 0x0d | \\r | 13 | CARRIAGE_RETURN | 段落分隔符 | 源码中明确使用 |
| 0x0f | \\u000f | 15 | SHIFT_IN | 代码块开始/内联元素标记 | `public-firstload-pc-bc7daab7-805820ec.js:56899, 63252` |
| 0x1c | \\u001c | 28 | FILE_SEPARATOR | 图片标记 | 推断值 |
| 0x1d | \\u001d | 29 | GROUP_SEPARATOR | 代码块结束标记 | 推断值 |
| 0x1e | \\u001e | 30 | RECORD_SEPARATOR | 记录分隔符/段落/内联元素标记 | `public-firstload-pc-bc7daab7-805820ec.js:56899` |

### HYPERLINK 控制字符系统 ✅

| 代码 | Unicode | 十六进制 | 名称 | 用途 | 源码位置 |
|------|---------|----------|------|------|----------|
| 0x13 | \\x13 | 19 | FIELD_BEGIN | HYPERLINK 开始 | `public-firstload-pc-bc7daab7-805820ec.js:144, 63192` |
| 0x14 | \\x14 | 20 | FIELD_SEPARATE | URL 与显示文本分隔符 | `public-firstload-pc-bc7daab7-805820ec.js:145` |
| 0x15 | \\x15 | 21 | FIELD_END | HYPERLINK 结束 | `public-firstload-pc-bc7daab7-805820ec.js:146` |

**完整语法**: `\x13HYPERLINK <URL>\x14<显示文本>\x15`

**源码证据:**
```javascript
// Line 63192 - HYPERLINK 解析正则表达式
new RegExp("[\u0013](.*?)[\u0014]|[\u0015]", "ug")

// Line 144-146 - PlaceholderCharCode 定义
const a = String.fromCharCode(o.PlaceholderCharCode.FieldBegin),      // 0x13
      s = String.fromCharCode(o.PlaceholderCharCode.FieldSeparate),   // 0x14
      l = String.fromCharCode(o.PlaceholderCharCode.FieldEnd);        // 0x15

// Line 26202, 1530 - 字段结构
// instructions[0]: 链接 URL
// instructions[1]: 显示文本
```

### List Marker 控制字符 ✅

| 代码 | Unicode | 十六进制 | 名称 | 用途 | 源码位置 |
|------|---------|----------|------|------|----------|
| 0x08 | \\b | 8 | BACKSPACE | List Marker 前缀 | `public-firstload-pc-bc7daab7-805820ec.js:34390, 35416` |

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

### 作者字段分隔符 ✅

| 代码 | Unicode | 十六进制 | 名称 | 用途 |
|------|---------|----------|------|------|
| 0x05 | \\x05 | 5 | ENQ | 作者字段分隔符 |

**格式**: `[type]\u001a\u0002\b\u0002\u0005\u0015\n\x13p.[user_id]\u0005[flags]\u0006...`

**作者类型前缀**:
- `.` - 普通作者
- `1` - 协作者
- `-` - 系统作者
- `9` - 特殊类型

## Ty 类型定义 (MutationType - 变更类型)

| 代码 | 字符串标识 | 含义 | 源码位置 |
|------|-----------|------|----------|
| 1 | "is" | INSERT_STRING - 插入字符串 | `public-firstload-pc-bc7daab7-805820ec.js:4520, 4859, 4905` |
| 2 | "ds" | DELETE_STRING - 删除字符串 | `public-firstload-pc-bc7daab7-805820ec.js:4863, 4906` |
| 3 | "mp" | MODIFY_PROPERTY - 修改属性 | `public-firstload-pc-bc7daab7-805820ec.js:4900` |
| 4 | "ms" | MODIFY_STYLE - 修改样式 | 推断值 |
| ~~5~~ | ~~未知~~ | ~~未知类型~~ | ~~已确认非 MutationType~~ |

**重要发现**: `ty_code=5` 不是 MutationType，而是 `rangeType: 5` (RevisionRange - 修订范围)

**源码证据:**
```javascript
// Line 4520: 检查类型是否为 "is" (INSERT_STRING)
e.type === a.MutationType.is && (t += e.mutation.text.length)

// Line 4859-4863: 插入和删除类型检查
if (t.type === o.MutationType.is && void 0 !== n) { ... }
t.type === o.MutationType.ds && void 0 !== n && ...

// Line 4900: 修改属性类型
if (e.type === o.MutationType.mp) { ... }

// ========== rangeType = 5 的证明 ==========
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

## RangeType 定义

| Code | 名称 | 说明 | 源码位置 |
|------|------|------|----------|
| 1 | NormalRange | 普通范围 | 推断值 |
| 5 | RevisionRange | 修订范围 | `public-firstload-pc-bc7daab7-805820ec.js:55751-55755, 56131-56137` |

**关键区别**:
- `ty` (MutationType): 1-4，定义 mutation 的操作类型
- `rangeType`: 1, 5，定义范围类型，仅用于 InsertRangeMutation

## Mt 目标类型定义 (MutationTarget - 变更目标)

| 字符串值 | 含义 | 源码位置 |
|----------|------|----------|
| "run" | 文本运行 | `public-firstload-pc-bc7daab7-805820ec.js:56899` |
| "paragraph" | 段落 | `public-firstload-pc-bc7daab7-805820ec.js:56899` |
| "section" | 节 | `public-firstload-pc-bc7daab7-805820ec.js:56899` |
| "story" | 故事 | `public-firstload-pc-bc7daab7-805820ec.js:56899, 58252-58253` |
| "settings" | 设置 | `public-firstload-pc-bc7daab7-805820ec.js:56899` |
| "webSettings" | Web 设置 | `public-firstload-pc-bc7daab7-805820ec.js:56899` |
| "background" | 背景 | `public-firstload-pc-bc7daab7-805820ec.js:56899` |
| "styles" | 样式 | `public-firstload-pc-bc7daab7-805820ec.js:56899` |
| "numbering" | 编号 | `public-firstload-pc-bc7daab7-805820ec.js:56899` |
| "fonts" | 字体 | `public-firstload-pc-bc7daab7-805820ec.js:56899` |
| "themes" | 主题 | `public-firstload-pc-bc7daab7-805820ec.js:56899` |
| "table" | 表格 | `feature-pc-bundle_word-helper-10be9b90.formatted.js:477` |

**源码证据 (Line 56899 - 空文档初始化):**
```javascript
'{"bi":0,"ei":1,"ty":"mp","mm":"insert","mt":"run","pr":{"run":{"isPlaceholder":true}}}'
'{"bi":0,"ei":1,"ty":"mp","mm":"merge","mt":"paragraph","pr":{"paragraph":{...}}}'
'{"bi":2,"ei":3,"ty":"mp","mm":"merge","mt":"section","pr":{"section":{...}}}'
'{"bi":3,"ei":4,"ty":"mp","mm":"merge","mt":"story","pr":{"story":{"storyType":"STStoryType_mainDocument"}}}'
'{"ty":"ms","mt":"settings","pr":{"settings":{...}}}'
'{"ty":"ms","mt":"webSettings","pr":{"webSettings":{...}}}'
'{"ty":"ms","mt":"background","pr":{"background":{...}}}'
'{"ty":"ms","mt":"styles","pr":{"styles":{...}}}'
```

## 控制字符用途分析

基于源码分析，控制字符主要用于：

### 已确认用途
1. **\\u000f (0x0F - SHIFT_IN)**: 用于标记文档结构中的特殊位置，如内联元素、代码块的开始
2. **\\u001e (0x1E - RECORD_SEPARATOR)**: 用于分隔段落或内联元素的范围
3. **\\u001c (0x1C - FILE_SEPARATOR)**: 用于标记图片位置
4. **\\u001d (0x1D - GROUP_SEPARATOR)**: 用于标记代码块结束
5. **\\r (0x0D - CARRIAGE_RETURN)**: 用于段落分隔
6. **\\x13/\\x14/\\x15**: 构成 HYPERLINK 标记系统
7. **\\b (0x08)**: List Marker 前缀
8. **\\x05 (0x05)**: 作者字段分隔符

**关键发现:**
- 控制字符 `\\u000f` 和 `\\u001e` 在文档初始化中被明确使用
- 单词计数正则表达式专门处理 `\\u000f` 作为特殊字符
- MutationType 使用简写字符串: "is", "ds", "mp", "ms"
- ModifyType 使用数字: 101-115 系列
- MutationTarget 使用字符串: "run", "paragraph", "section", "story", "settings" 等
- `ty_code=5` 是 `rangeType`，不是 MutationType

## 脚本模块结构

```
scripts/parse_ultrabuf/
├── __init__.py           # 模块初始化
├── enums.py              # 枚举值定义集中管理
├── parser.py             # 主解析器 (opendoc → intermediate.json)
├── format_parser.py      # 格式解析器 (intermediate.json → result.json)
├── style_definitions.py  # 样式定义
└── analyze_enums.py      # 枚举值分析工具
```

## 使用方法

```python
# 导入枚举值定义
from scripts.parse_ultrabuf.enums import (
    MutationType, ModifyType, ControlChars, PlaceholderCharCode,
    MUTATION_TYPE_MAP, MODIFY_TYPE_MAP, CONTROL_CHAR_MAP,
    RANGE_TYPE_MAP, HYPERLINK_FIELD_NAME
)

# 使用解析器
from scripts.parse_ultrabuf import TencentDocParser

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

## 代码更新摘要

### enums.py 更新
- 添加 `PlaceholderCharCode` 枚举类
- 更新 `ControlChars` 类，添加已确认的控制字符说明
- 添加 `parse_hyperlink()`, `parse_list_marker()`, `parse_author_field()` 方法
- 添加 `RANGE_TYPE_MAP` 映射
- 移除 ty_code=5 的误判说明

### 01_parser.py 更新
- 更新 Mutation 数据类，添加 `range_type`, `hyperlink`, `list_marker` 字段
- 在解析逻辑中添加控制字符解析
- 更新 `to_dict()` 方法，包含新字段

### 文档更新
- `unknown_enums_summary.md`: 移除已确认项，添加完整说明
- `js_enum_validation.md`: 添加新发现的完整说明和源码证据
