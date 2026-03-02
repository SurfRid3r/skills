---
name: tencent-converter
description: "将腾讯文档/表格转换为Markdown格式。支持标题、段落、列表、代码块、图片、表格和超链接。使用场景：用户提供doc.weixin.qq.com或sheet.weixin.qq.com的网址请求将腾讯文档/表格转换为Markdown。当用户提供腾讯文档/表格链接时，优先使用此skill。"
---

# Tencent Converter

将腾讯文档/表格转换为 Markdown。

## 快速开始

```bash
pip install -r scripts/requirements.txt
```

## 核心原则

| 原则 | 说明 |
|------|------|
| **Cookies 优先** | 有 cookies 时优先使用脚本获取（更快、更可靠） |
| **自动降级** | cookies 不存在或过期时，使用浏览器 MCP 获取 |
| **自动保存** | 使用 MCP 时自动保存 cookies 到 `cookies.txt` 供复用 |

## 工作流程

### Step 1: 检查 Cookies

```
优先级：用户指定路径 > cookies.txt > 浏览器 MCP
```

### Step 2: 根据类型选择获取方式

| 类型 | 有 Cookies | 无 Cookies |
|------|-----------|-----------|
| 文档 | 脚本获取 opendoc | MCP 捕获 opendoc API |
| 表格 | 脚本获取所有工作表 | MCP 导出 cookies → 脚本获取 |

### Step 3: 转换为 Markdown

```bash
python3 scripts/convert.py <input> -o <output>
```

## 文档转换

### 有 Cookies

```bash
python3 scripts/convert.py --url "<文档URL>" --cookie cookies.txt -o output/doc.md --cleanup-source
```

### 无 Cookies（MCP）

```
1. new_page(url="<文档URL>")
2. navigate_page(type="reload")
3. list_network_requests(resourceTypes=["xhr", "fetch"])
4. get_network_request(reqid=N, responseFilePath="output/opendoc.json")
5. evaluate_script: document.cookie → 保存到 cookies.txt
6. python3 scripts/convert.py output/opendoc.json -o output/doc.md --cleanup-source
7. close_page(pageId=N)
```

## 表格转换

### 有 Cookies

```bash
# 所有工作表
python3 scripts/convert.py --url "<表格URL?scode=xxx>" --cookie cookies.txt --output-dir output/ --all-tabs

# 单个工作表
python3 scripts/convert.py --url "<表格URL?scode=xxx>" --cookie cookies.txt -o output/sheet.md
```

### 无 Cookies（MCP）

```
1. new_page(url="<表格URL?scode=xxx>")  # 必须带 scode 参数
2. 等待页面加载
3. evaluate_script: document.cookie → 保存到 cookies.txt
4. python3 scripts/convert.py --url "<表格URL?scode=xxx>" --cookie cookies.txt --output-dir output/ --all-tabs
5. close_page(pageId=N)
```

**参数**：`--all-tabs`（所有工作表）、`--sheet-name "名称"`（指定工作表）

**输出**：`<表格名称>/<工作表>.md`

## Cookies 管理

**格式**：纯文本 `session_id=xxx; user_token=yyy; ...`

**过期处理**：删除 `cookies.txt` → MCP 重新访问 → 保存新 cookies

## 参数速查

| 参数 | 说明 |
|------|------|
| `--url` | 腾讯文档/表格 URL |
| `--cookie` | Cookie 文件路径 |
| `-o` | 输出文件路径 |
| `--output-dir` | 输出目录（表格多工作表） |
| `--all-tabs` | 获取所有可见工作表 |
| `--sheet-name` | 指定工作表名称 |
| `--cleanup-source` | 转换后删除输入 JSON |

## References

- [data-format.md](references/data-format.md) - 数据格式和 Protobuf 解析
- [enums-reference.md](references/enums-reference.md) - 枚举值完整参考
- [format-parsing.md](references/format-parsing.md) - 控制字符处理
- [sheet-parsing.md](references/sheet-parsing.md) - 表格解析逻辑
- [advanced-topics.md](references/advanced-topics.md) - 评论处理、JS 获取
