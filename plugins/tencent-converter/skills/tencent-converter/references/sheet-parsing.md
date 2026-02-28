# 腾讯表格解析逻辑

## 概述

本文档记录腾讯文档表格（Sheet）API 响应的解析逻辑，特别是富文本定位的关键发现。

## 数据流

```
API 响应 → related_sheet (Base64) → zlib 解压 → Protobuf 解析 → 单元格数据
```

## Protobuf 字段结构

### F19.6 位置映射

位置映射字段 `F19.6` 是解析单元格数据的核心，每个重复字段代表一个单元格的位置和内容索引。

```
F19.6[i]
├── F19.6.1 → row (0-based 行号)
├── F19.6.2 → col (0-based 列号)
└── F19.6.3 → 单元格数据定位
    ├── F19.6.3.1 → cell_type (单元格类型)
    ├── F19.6.3.2 → 索引容器
    │   └── F19.6.3.2.1 → 根据类型有不同含义
    └── F19.6.3.4 → 富文本索引容器
        └── F19.6.3.4.1 → rich_text_idx
```

### F19.6.3.1 单元格类型

| 值 | 含义 | 说明 |
|----|------|------|
| 4 | 普通单元格 | 纯文本内容 |
| 6 | 富文本单元格 | 包含超链接等格式化内容 |

### F19.6.3.2.1 的双重含义

**关键发现**：`F19.6.3.2.1` 的含义取决于 `cell_type`：

| cell_type | F19.6.3.2.1 含义 | 指向 |
|-----------|-----------------|------|
| 4 (普通) | text_idx | F19.5.1 纯文本列表 |
| 6 (富文本) | direct_f2_index | F19.5.2 富文本列表（0-based 直接索引） |

### F19.6.3.4.1 rich_text_idx

- 指向 F19.4 引用表的索引（1-based）
- 通过引用表映射到 F2 索引：`F19.4.F1[rich_text_idx].F9.F1 - 1`
- 仅在 `cell_type=6` 且无 `direct_f2_index` 时作为备选

## 富文本定位优先级

当 `cell_type=6`（富文本单元格）时，按以下优先级定位内容：

1. **direct_f2_index** (`F19.6.3.2.1`)
   - 直接索引，F19.5.2 的 0-based 索引
   - **优先使用**

2. **rich_text_idx** (`F19.6.3.4.1`)
   - 通过 F19.4 引用表映射
   - 备选方案

## 实际案例分析

| 单元格 | cell_type | direct_f2_index | rich_text_idx | 实际 F2 索引 |
|--------|-----------|-----------------|---------------|-------------|
| D13 | 6 | 无 | 9 | F2[0] (通过引用表) |
| D16 | 6 | 1 | 10 | F2[1] (直接索引) |
| A23 | 6 | 2 | 17 | F2[2] (直接索引) |

### D16 单元格详情

- **问题**：之前显示纯文本 "接口人"，应显示 "GPT研判链路研判细节" 链接
- **原因**：`direct_f2_index=1` 被错误当作纯文本索引
- **修复**：当 `cell_type=6` 时，`F19.6.3.2.1` 是 F2 的直接索引

### A23 单元格详情

- **问题**：之前显示纯文本 "职责范围描述"，应显示 "通用POC旅程（供参考）" 链接
- **原因**：`direct_f2_index=2` 被错误当作纯文本索引
- **修复**：同上

## 增量编码规则

位置映射使用增量编码来减少数据量：

1. **隐式第一单元格**：`text_idx=0` 始终位于 `(0, 0)`，不出现在位置映射中
2. **行切换**：当 `row` 有值时，`current_col` 重置为 -1
3. **列递增**：当 `col` 无值时，`current_col += 1`

## 代码实现

```python
# 解析 F3 字段
if nf.field_number == 3 and nf.nested_fields:
    # F3.1 → cell_type
    f1_type = nf.get_nested_field(1)
    if f1_type and f1_type.wire_type == 0:
        cell_type = f1_type.value

    # F3.2 → 索引容器
    f2 = nf.get_nested_field(2)
    if f2 and f2.nested_fields:
        f1_inner = f2.get_nested_field(1)
        if f1_inner and f1_inner.wire_type == 0:
            if cell_type == 6:
                # 富文本：直接 F2 索引
                direct_f2_index = f1_inner.value
            else:
                # 普通文本：纯文本索引
                text_idx = f1_inner.value

# 构建单元格值
if cell_type == 6:
    # 富文本单元格
    if direct_f2_index is not None and 0 <= direct_f2_index < len(f2_items):
        paragraphs = f2_items[direct_f2_index]
    elif rich_text_idx is not None:
        f2_index = rich_text_to_f2.get(rich_text_idx, 0)
        paragraphs = f2_items[f2_index]
```

## 相关文件

- `scripts/sheet_api_parser.py` - API 响应解析器
- `scripts/sheet_parser.py` - 浏览器数据解析器
- `scripts/sheet_enums.py` - 数据模型和枚举定义
- `scripts/sheet_converter.py` - Markdown 转换器

## 更新记录

| 日期 | 更新内容 |
|------|----------|
| 2026-02-27 | 初始版本，记录富文本定位逻辑 |
