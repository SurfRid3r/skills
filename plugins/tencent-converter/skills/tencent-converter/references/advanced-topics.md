# 高级主题

本文档汇总腾讯文档转换的高级使用场景和技术细节。

---

## 评论数据处理

### 概述

腾讯文档的评论数据有**双重来源**：

1. **独立 HTTP API**: `/comment/list` API 返回完整的评论数据
2. **Protobuf 数据**: opendoc API 的 protobuf 响应中包含部分评论信息

这两种来源各有用途，互相补充。

### 来源 1: 独立 API (/comment/list)

#### API 端点

```
POST https://doc.weixin.qq.com/comment/list
```

#### 请求参数

```
Content-Type: application/x-www-form-urlencoded

docid=w3_ARwAaAYhAAkCNcIEThq6OSN6Em0ag&type=0&func=2
```

| 参数 | 说明 |
|------|------|
| docid | 文档 ID |
| type | 评论类型 (0=文档评论) |
| func | 功能代码 (2=获取列表) |

#### 响应结构

```json
{
  "head": { "ret": 0, "cgi": "xmcommentlogicsvr/list", ... },
  "body": {
    "comment_list": [
      {
        "group_id": "4",
        "item": [...],
        "status": 1,
        "ooxml_anchor_id": "a_2dimf2"
      }
    ]
  }
}
```

#### 数据结构详解

##### CommentGroup (评论组)

同一位置的多个评论被组织成一个组。

| 字段 | 类型 | 说明 |
|------|------|------|
| group_id | string | 组 ID |
| item | array | 评论列表 |
| status | int | 状态 (1=正常) |
| ooxml_anchor_id | string | OOXML 锚点 ID，关联文档位置 |

##### CommentItem (单条评论)

| 字段 | 类型 | 说明 |
|------|------|------|
| docid | string | 文档 ID |
| group_id | int | 组 ID |
| comment_id | int | 评论 ID |
| father_id | int | 父评论 ID (0=顶级评论) |
| content | string | 评论内容 (UTF-8) |
| ctime | int64 | 创建时间 (Unix 秒级时间戳) |
| utime | int64 | 更新时间 (Unix 秒级时间戳) |
| create_user | object | 创建用户信息 |
| ooxml_comment_id | string | OOXML 评论 ID |

##### UserInfo (用户信息)

| 字段 | 类型 | 说明 |
|------|------|------|
| vid | string | 企业微信用户 ID |
| name | string | 用户名 |
| image | string | 头像 URL |
| corpname | string | 企业名称 |
| corpid | int64 | 企业 ID |

### 来源 2: Protobuf 数据 (opendoc API)

#### 数据位置

评论数据存在于 opendoc API 的 protobuf 响应的特定部分中（通过 ModifyType 108 的 mutation）。

#### ModifyType 枚举

| Code | 名称 | 说明 | 状态 |
|------|------|------|------|
| 108 | COMMENT_STORY_PROPERTY | 评注故事属性 | 已确认 |

源码位置: `public-firstload-pc-*.js:58266`

### 与独立 API 的对比

| 特性 | Protobuf 中 | /comment/list API |
|------|-------------|-------------------|
| ooxml_comment_id | ✓ | ✓ |
| ooxml_anchor_id | ✓ | ✓ |
| 评论内容 | ✓ | ✓ |
| 用户信息 | ✓ | ✓ |
| 时间戳 | ✓ | ✓ |
| 返回方式 | 主动推送 | 按需获取 |
| 数据完整性 | 部分 | 完整 |

### 使用建议

1. **优先使用 Protobuf 数据**: 如果已经获取了 opendoc 响应，评论数据已包含在内，无需额外请求。
2. **独立 API 作为补充**: 当需要获取完整的评论线程、回复等信息时，使用 `/comment/list` API。
3. **锚点关联**: 通过 `ooxml_anchor_id` 关联评论与文档位置。

### 评论内容过滤

`format_parser.py` 在解析时会自动过滤评论内容，避免审阅意见、用户提及等内容出现在正文 Markdown 中。

**实现原理**:
1. 收集所有 `status_code=108` (COMMENT_STORY_PROPERTY) 的 mutations
2. 计算 bi 最小值 → 向前查找 `\x0f` 作为评论区域开始
3. 计算 ei 最大值 → 作为评论区域结束
4. 在 `_parse_sections()` 中遇到 CODE_BLOCK_START 时检查是否在评论区域，如果是则跳过

---

## JS 文件获取指南

### 获取步骤

#### 1. 打开腾讯文档

使用 MCP 工具打开目标腾讯文档：

```
mcp__chrome-devtools__new_page - 打开文档 URL
```

#### 2. 查找 JS 文件请求

等待页面加载完成后，列出所有网络请求：

```
mcp__chrome-devtools__list_network_requests - 查找 JS 文件
```

筛选 resourceTypes: ["script"]

#### 3. 识别关键 JS 文件

腾讯文档的关键 JS 文件：

| 文件名模式 | 用途 |
|-----------|------|
| `public-firstload-pc-*.js` | 核心解析逻辑，包含 ultrabuf 解析 |
| `feature-pc-bundle_word-helper-*.js` | 表格功能 |

#### 4. 保存 JS 文件

使用 get_network_request 获取 JS 内容并保存：

```
mcp__chrome-devtools__get_network_request - 保存到 tencent_js/ 目录
```

#### 5. 格式化 JS 文件

使用脚本格式化 JS 文件以便分析：

```bash
python3 scripts/02_download_js.py --format-only
```

### 前置依赖

格式化功能需要 prettier：

```bash
npm install -g prettier
```

### 注意事项

- JS 文件较大（1-2MB），格式化需要一些时间
- 格式化后的文件扩展名为 `.formatted.js`
- 建议只保留正在分析的文件，其他可删除以节省空间
- `tencent_js/` 目录已添加到 `.gitignore`，不会提交到版本控制

---

## 更新记录

| 日期 | 更新内容 |
|------|----------|
| 2026-02-28 | 合并 comments.md 和 how_to_fetch_js.md |
