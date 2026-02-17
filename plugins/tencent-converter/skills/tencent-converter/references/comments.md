# 腾讯文档评论数据处理

## 概述

腾讯文档的评论数据有**双重来源**：

1. **独立 HTTP API**: `/comment/list` API 返回完整的评论数据
2. **Protobuf 数据**: opendoc API 的 protobuf 响应中包含部分评论信息

这两种来源各有用途，互相补充。

---

## 来源 1: 独立 API (/comment/list)

### API 端点

```
POST https://doc.weixin.qq.com/comment/list
```

### 请求参数

```
Content-Type: application/x-www-form-urlencoded

docid=w3_ARwAaAYhAAkCNcIEThq6OSN6Em0ag&type=0&func=2
```

| 参数 | 说明 |
|------|------|
| docid | 文档 ID |
| type | 评论类型 (0=文档评论) |
| func | 功能代码 (2=获取列表) |

### 响应结构

```json
{
  "head": {
    "ret": 0,
    "cgi": "xmcommentlogicsvr/list",
    "time": 1769945819,
    "msg": ""
  },
  "param": {
    "protocol": "http",
    "hostname": "doc.weixin.qq.com",
    "sid": "1gpyaoxHVGIus3h2AChLZAAA"
  },
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

### 数据结构详解

#### CommentGroup (评论组)

同一位置的多个评论被组织成一个组。

| 字段 | 类型 | 说明 |
|------|------|------|
| group_id | string | 组 ID |
| item | array | 评论列表 |
| status | int | 状态 (1=正常) |
| ooxml_anchor_id | string | OOXML 锚点 ID，关联文档位置 |

#### CommentItem (单条评论)

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
| read_time | int64 | 阅读时间 |
| sheet_id | string | 工作表 ID (表格文档) |
| position | string | 位置信息 (JSON 字符串) |
| is_global | bool | 是否全局评论 |
| submitter_id | string | 提交者 ID |
| ooxml_comment_id | string | OOXML 评论 ID |

#### UserInfo (用户信息)

| 字段 | 类型 | 说明 |
|------|------|------|
| vid | string | 企业微信用户 ID |
| name | string | 用户名 |
| image | string | 头像 URL |
| corpname | string | 企业名称 |
| corpid | int64 | 企业 ID |

---

## 来源 2: Protobuf 数据 (opendoc API)

### 数据位置

评论数据存在于 opendoc API 的 protobuf 响应的特定部分中（通过 ModifyType 108 的 mutation）。

### ModifyType 枚举

| Code | 名称 | 说明 | 状态 |
|------|------|------|------|
| 108 | COMMENT_STORY_PROPERTY | 评注故事属性 | 已确认 |

源码位置: `public-firstload-pc-bc7daab7-805820ec.js:58266`

### 数据结构

评论通过 ModifyType 108 的 mutation 存储在 Protobuf 中。当解析 mutations 时，可以通过 `status_code == 108` 来识别评论相关的 mutations。

---

## 与独立 API 的对比

| 特性 | Protobuf 中 | /comment/list API |
|------|-------------|-------------------|
| ooxml_comment_id | ✓ | ✓ |
| ooxml_anchor_id | ✓ | ✓ |
| 评论内容 | ✓ | ✓ |
| 用户信息 | ✓ | ✓ |
| 时间戳 | ✓ | ✓ |
| 返回方式 | 主动推送 | 按需获取 |
| 数据完整性 | 部分 | 完整 |

---

## 使用建议

### 优先使用 Protobuf 数据

如果已经获取了 opendoc 响应，评论数据已包含在内，无需额外请求。

### 独立 API 作为补充

当需要获取完整的评论线程、回复等信息时，使用 `/comment/list` API。

### 锚点关联

通过 `ooxml_anchor_id` 关联评论与文档位置。

---

## 解析方法

### 方法 1: 使用解析器处理 Protobuf 数据

```python
from scripts.parse_ultrabuf.parser import TencentDocParser
from scripts.parse_ultrabuf.enums import ModifyType

# 解析文档
parser = TencentDocParser(text_data)
result = parser.parse()

# 查找评论相关的 mutations
comment_mutations = [
    m for m in result['mutations']
    if m.get('status_code') == ModifyType.COMMENT_STORY_PROPERTY
]

for mut in comment_mutations:
    print(f"评论 ID: {mut.get('comment_id')}")
    print(f"内容: {mut.get('s')}")
    print(f"作者: {mut.get('author')}")
```

### 方法 2: 使用独立 API 获取完整评论

```bash
# 使用 chrome-devtools MCP 工具
# 1. 打开文档页面
# 2. 查找 /comment/list 请求
# 3. 获取响应数据
```

```python
import requests

# 请求评论列表
url = "https://doc.weixin.qq.com/comment/list"
data = {
    "docid": "w3_ARwAaAYhAAkCNcIEThq6OSN6Em0ag",
    "type": "0",
    "func": "2"
}
response = requests.post(url, data=data)
comments = response.json()
```

---

## 与文档内容的关联

评论与文档内容的关联通过以下机制实现：

1. **ooxml_anchor_id**: 锚点 ID，指向文档中的特定位置
2. **position**: 位置信息（可能是 JSON 格式的详细位置）
3. **ooxml_comment_id**: OOXML 标准的评论 ID

这些 ID 可能与文档编辑器内部的元素 ID 相对应。

---

## 示例数据

```json
{
  "docid": "w3_ARwAaAYhAAkCNcIEThq6OSN6Em0ag",
  "group_id": 4,
  "comment_id": 5,
  "father_id": 0,
  "content": "测试",
  "ctime": 1769945787,
  "utime": 1769945787,
  "create_user": {
    "vid": "1688854308415516",
    "name": "韩航波(19336)",
    "image": "https://wework.qpic.cn/wwpic3az/281966_5iM7ULsbQvee1NX_1757553767/0",
    "corpname": "深信服科技股份有限公司",
    "corpid": 1970325129095822
  },
  "read_time": 0,
  "sheet_id": "",
  "position": "",
  "is_global": false,
  "submitter_id": "0",
  "ooxml_comment_id": "c_mm18mh"
}
```

---

## 关键发现

1. **双重来源**: 评论同时存在于独立 API 和 Protobuf 数据中
2. **ModifyType 108**: 评论通过 COMMENT_STORY_PROPERTY mutation 存储
3. **锚点关联**: 评论通过 `ooxml_anchor_id` 与文档位置关联
4. **层级结构**: 支持评论回复 (`father_id` 字段)
5. **分组管理**: 同一位置的评论被组织成一个组 (`group_id`)

---

## 评论内容过滤

`format_parser.py` 在解析时会自动过滤评论内容，避免审阅意见、用户提及等内容出现在正文 Markdown 中。

**实现原理**:
1. 收集所有 `status_code=108` (COMMENT_STORY_PROPERTY) 的 mutations
2. 计算 bi 最小值 → 向前查找 `\x0f` 作为评论区域开始
3. 计算 ei 最大值 → 作为评论区域结束
4. 在 `_parse_sections()` 中遇到 CODE_BLOCK_START 时检查是否在评论区域，如果是则跳过

---

**更新日期**: 2026-02-16
**状态**: 已确认双重来源
