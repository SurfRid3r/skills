# 参考文档索引

本目录包含腾讯文档转换器的技术参考文档。

## 文档列表

| 文档 | 内容 | 适用场景 |
|------|------|----------|
| [data-format.md](data-format.md) | 数据格式和 Protobuf 解析逻辑 | 理解 ultrabuf 结构、Mutation 字段 |
| [enums-reference.md](enums-reference.md) | 枚举值完整参考 | 查找 MutationType、ModifyType、控制字符定义 |
| [format-parsing.md](format-parsing.md) | 控制字符处理逻辑 | 理解代码块、超链接、列表的解析方式 |
| [sheet-parsing.md](sheet-parsing.md) | 表格解析逻辑 | 处理腾讯表格的富文本定位 |
| [advanced-topics.md](advanced-topics.md) | 高级主题 | 评论处理、JS 文件获取 |

## 快速查找

### 我想了解...

- **数据是如何编码的？** → [data-format.md](data-format.md)
- **ty=3 是什么意思？** → [enums-reference.md](enums-reference.md) 的 MutationType 表
- **如何处理超链接？** → [format-parsing.md](format-parsing.md) 的 HYPERLINK 格式
- **表格的富文本为什么显示错误？** → [sheet-parsing.md](sheet-parsing.md) 的富文本定位优先级
- **如何获取评论数据？** → [advanced-topics.md](advanced-topics.md) 的评论数据处理

## 相关脚本

| 脚本 | 说明 |
|------|------|
| `scripts/parser.py` | ultrabuf 解析器 |
| `scripts/format_parser.py` | 格式解析器 |
| `scripts/enums.py` | 枚举值定义 |
| `scripts/sheet_api_parser.py` | 表格 API 解析器 |
| `scripts/convert.py` | 统一转换入口 |

## 更新记录

| 日期 | 更新内容 |
|------|----------|
| 2026-02-28 | 初始版本，整合原有参考文档 |
