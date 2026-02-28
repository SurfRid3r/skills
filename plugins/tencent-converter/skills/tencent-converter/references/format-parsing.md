# 格式解析逻辑

## 概述

本文档记录腾讯文档格式解析的控制字符处理逻辑，用于将 mutations 转换为语义化的文档结构。

## 控制字符定义

| 代码 | 十六进制 | 名称 | 用途 |
|------|----------|------|------|
| 13 | 0x0d | PARAGRAPH_SEP | 段落分隔符 (\r) |
| 15 | 0x0f | CODE_BLOCK_START | 代码块开始 |
| 28 | 0x1c | PICTURE_MARKER | 图片标记 |
| 29 | 0x1d | CODE_BLOCK_END | 代码块结束/组分隔符 |
| 30 | 0x1e | RECORD_SEP | 记录分隔符 |
| 19 | 0x13 | HYPERLINK_START | HYPERLINK 开始 |
| 20 | 0x14 | HYPERLINK_URL_SEP | URL 与显示文本分隔符 |
| 21 | 0x15 | HYPERLINK_END | HYPERLINK 结束 |
| 8 | 0x08 | LIST_MARKER | List Marker 前缀 |
| 5 | 0x05 | AUTHOR_FIELD_SEP | 作者字段分隔符 |
| 26 | 0x1a | AUTHOR_FIELD_PREFIX | 表格开始 |
| 6 | 0x06 | AUTHOR_FIELD_VALUE | 行开始标记 |
| 7 | 0x07 | TABLE_MARKER | 列分隔符 |
| 27 | 0x1b | COMPARISON_MARKER | 表格结束 |

## 代码块格式

### 标准代码块

```
0x0f (CODE_BLOCK_START)
0x1e×N (RECORD_SEP 填充, 5-6个)
[行1] 0x1c + 内容 + 0x0d + 0x1d
[行2] 0x1c + 内容 + 0x0d + 0x1d
...
0x1e×N (可选的末尾填充)
```

### 文本框格式

文本框是特殊的代码块，格式与标准代码块类似：

```
开始标记: \x1d\x1e\x1c
行格式: \x1d\x1c + 内容 + \r
结束: 直到下一个非文本框控制字符
```

**子块分隔符**: `\x1d\x1c` (独立块分隔符)

## HYPERLINK 格式

### 基本格式

```
\x13HYPERLINK <URL> <params>\x14<显示文本>\x15
```

### 带引号格式

```
\x13HYPERLINK "URL" \t "target"\x14<显示文本>\x15
```

### 解析逻辑

1. 跳过 HYPERLINK_START (0x13)
2. 跳过 "HYPERLINK" 字符串
3. 提取 URL（处理带引号和不带引号的情况）
4. 跳过 HYPERLINK_URL_SEP (0x14)
5. 提取显示文本直到 HYPERLINK_END (0x15)

## 列表格式

### 语法

```
\b[x] 其中 x 是 list marker 字符
```

### Marker 类型

| Marker | 列表类型 | 渲染字体 |
|--------|----------|----------|
| \b- | 无序列表 (bullet) | Wingdings |
| \b8 | 有序列表 (numbering) | Wingdings |

## 表格格式

### 实际格式

```
\x1a <cell1> \r \x07 <cell2> \r \x07 <cell3> \r
\x07 \x06 <cell1> \r \x07 <cell2> \r ... \x1b
```

### 控制字符

- 0x1a (AUTHOR_FIELD_PREFIX): 表格开始
- 0x07 (TABLE_MARKER): 列分隔符
- 0x06 (AUTHOR_FIELD_VALUE): 行开始标记
- 0x0d (PARAGRAPH_SEP): 单元格内容结束
- 0x1b (COMPARISON_MARKER): 表格结束

## 评论区域处理

评论内容通过 COMMENT_STORY_PROPERTY (108) mutation 的位置范围识别：

1. 收集所有 status_code=108 的 mutations
2. 计算评论区域：`min(bi)` 到 `max(ei)`
3. 向前查找 `\x0f` 开始标记
4. 在解析时跳过评论区域

## 文本框视觉位置映射

从 TABLE_PROPERTY mutations 中提取文本框视觉位置：

- visual_bi: 视觉位置（文本流中占位符的位置）
- textbox_style_id: 外层文本框样式ID
- content_style_id: 内层内容样式ID
- is_code_block: 是否是代码块（通过 TEXTBOX_STORY_PROPERTY 的 author 字段判断）

**代码块识别**: TEXTBOX_STORY_PROPERTY author 字段中有 "plain text" 标记 (J 字段) = 代码块

## 相关文件

- `scripts/format_parser.py` - 格式解析器实现
- `scripts/enums.py` - 控制字符定义 (ControlChars 类)
- `references/enums-reference.md` - 枚举值完整参考

## 更新记录

| 日期 | 更新内容 |
|------|----------|
| 2026-02-28 | 从 format_parser.py 提取控制字符处理逻辑 |
