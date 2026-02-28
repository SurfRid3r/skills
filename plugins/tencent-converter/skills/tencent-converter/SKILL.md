---
name: tencent-converter
description: "将腾讯文档/表格转换为Markdown格式。支持标题、段落、列表、代码块、图片、表格和超链接。使用场景：用户提供doc.weixin.qq.com或sheet.weixin.qq.com的网址请求将腾讯文档/表格转换为Markdown。当用户提供腾讯文档/表格链接时，优先使用此skill。"
---

# Tencent Converter

将腾讯文档/表格转换为 Markdown。

## 依赖安装

```bash
pip install -r scripts/requirements.txt
```

## 核心原则

1. **Cookies 优先**：如果用户提供 cookies 或存在 `cookies.txt`，优先使用 cookies 获取（更快、更可靠）
2. **自动降级**：cookies 不存在或过期时，使用浏览器 MCP 获取
3. **自动保存**：使用 MCP 时自动保存 cookies 到 `cookies.txt`，供后续复用

## 工作流程

### Step 1: 检查 Cookies

```
检查顺序：
1. 用户提供的 cookies 文件路径
2. 项目根目录的 cookies.txt
3. 都没有 → 使用浏览器 MCP
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

***

## 文档转换

### 方式 A: 使用 Cookies（推荐）

用户提供了 cookies 或存在 `cookies.txt`：

```bash
python3 scripts/convert.py --url "<文档URL>" --cookie cookies.txt -o output/doc.md --cleanup-source
```

### 方式 B: 使用浏览器 MCP

没有 cookies 时：

```
1. new_page(url="<文档URL>")
2. navigate_page(type="reload")
3. list_network_requests(resourceTypes=["xhr", "fetch"])
4. get_network_request(reqid=N, responseFilePath="output/opendoc.json")
5. # 保存 cookies 供后续使用
   evaluate_script: document.cookie → 保存到 cookies.txt
6. python3 scripts/convert.py output/opendoc.json -o output/doc.md --cleanup-source
7. close_page(pageId=N)
```

***

## 表格转换

### 方式 A: 使用 Cookies（推荐）

用户提供了 cookies 或存在 `cookies.txt`：

```bash
# 获取所有工作表
python3 scripts/convert.py --url "<表格URL?scode=xxx>" --cookie cookies.txt --output-dir output/ --all-tabs

# 获取单个工作表
python3 scripts/convert.py --url "<表格URL?scode=xxx>" --cookie cookies.txt -o output/sheet.md
```

### 方式 B: 使用浏览器 MCP

没有 cookies 或 cookies 过期时：

```
1. new_page(url="<表格URL?scode=xxx>")  # 必须带 scode 参数
2. 等待页面加载完成
3. # 导出并保存 cookies
   evaluate_script: document.cookie → 保存到 cookies.txt
4. python3 scripts/convert.py --url "<表格URL?scode=xxx>" --cookie cookies.txt --output-dir output/ --all-tabs
5. close_page(pageId=N)
```

**参数选项**:
- `--all-tabs`: 获取所有工作表（推荐）
- 不带参数: 只获取 URL 中指定的单个工作表
- `--sheet-name "名称"`: 只获取指定名称的工作表

**输出结构**:
```
output/
└── <表格名称>/
    ├── 工作表1.md
    ├── 工作表2.md
    └── ...
```

***

## Cookies 管理

### 保存 Cookies

使用浏览器 MCP 时，**必须**保存 cookies 供后续复用：

```javascript
// 在 evaluate_script 中执行
document.cookie

// 保存到项目根目录的 cookies.txt
```

### Cookies 文件格式

纯文本格式，直接从浏览器 `document.cookie` 复制：

```
session_id=xxx; user_token=yyy; ...
```

### Cookies 过期处理

错误: `文档内容为空，可能需要重新登录获取新 Cookie`

处理流程：
1. 删除过期的 `cookies.txt`
2. 使用浏览器 MCP 重新访问文档
3. 保存新的 cookies
4. 重试转换

***

## 参数参考

### convert.py

| 参数 | 说明 |
|------|------|
| `input` | JSON 文件路径（MCP 方式获取） |
| `-o, --output` | 输出单个 .md 文件路径 |
| `--output-dir` | 输出目录，表格会保存到 `<目录>/<表格名称>/` 下 |
| `--url` | 腾讯文档/表格 URL（Cookie 方式） |
| `--cookie` | Cookie 文件路径 |
| `--all-tabs` | 获取所有可见工作表 |
| `--sheet-name` | 指定单个工作表名称 |
| `--cleanup-source` | 转换完成后删除输入 JSON |

### fetch_sheet.py

| 参数 | 说明 |
|------|------|
| `-u, --url` | 腾讯表格 URL |
| `-c, --cookie` | Cookie 文件路径 |
| `-o, --output` | 输出 JSON 路径 |
| `--all-tabs` | 获取所有可见工作表 |

***

## 输出格式

### 文档

```markdown
# 文档标题

正文内容...
```

### 表格

```markdown
## 工作计划

| 任务 | 负责人 | 状态 |
| --- | --- | --- |
| 需求分析 | 张三 | 完成 |
```

***

## References

- [data-format.md](references/data-format.md) - 数据格式和 Protobuf 解析
- [enums-reference.md](references/enums-reference.md) - 枚举值完整参考
- [format-parsing.md](references/format-parsing.md) - 控制字符处理
- [sheet-parsing.md](references/sheet-parsing.md) - 表格解析逻辑
- [advanced-topics.md](references/advanced-topics.md) - 评论处理、JS 获取
