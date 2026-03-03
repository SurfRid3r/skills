---
name: tencent-converter
description: "将腾讯文档和腾讯表格转换为 Markdown 格式。当用户提供 doc.weixin.qq.com 或 sheet.weixin.qq.com 链接，或提到「腾讯文档」「腾讯表格」「导出」「下载」「转换」腾讯在线文档时，必须使用此 skill。支持标题、段落、列表、代码块、图片、表格、超链接。自动处理 cookies 认证，支持增量更新。"
---

# Tencent Converter

将腾讯文档/表格转换为 Markdown。

## 核心原则

**为什么优先使用 Cookies？**
- 脚本直接调用 API，速度快且可靠
- 无需启动浏览器，资源占用少
- 支持批量获取多个工作表

**为什么需要 MCP 降级？**
- Cookies 可能过期或不存在
- MCP 可以自动获取新 Cookies 并保存复用

| 场景 | 方案 |
|------|------|
| 有 cookies.txt | 直接调用脚本获取 API 数据 |
| 无 cookies | 浏览器MCP 打开页面 → 提取 cookies → 调用脚本 |

## 工作流程

### Step 1: 检查 Cookies

```
优先级：用户指定路径 > cookies.txt > 浏览器 MCP
```

### Step 2: 获取数据并转换

根据 URL 类型选择处理方式：

**文档 (doc.weixin.qq.com)**
```bash
# 有 cookies - 指定输出目录（推荐）
python3 scripts/convert.py --url "<文档URL>" --cookie cookies.txt --output-dir output/ --cleanup-source

# 有 cookies - 指定文档名称
python3 scripts/convert.py --url "<文档URL>" --cookie cookies.txt --output-dir output/ --doc-name "我的文档"

# 有 cookies - 使用完整路径（向后兼容）
python3 scripts/convert.py --url "<文档URL>" --cookie cookies.txt -o output/doc.md --cleanup-source

# 无 cookies（使用 MCP 捕获 opendoc API 响应）
1. new_page(url="<文档URL>")
2. navigate_page(type="reload")
3. list_network_requests(resourceTypes=["xhr", "fetch"])
4. get_network_request(reqid=N, responseFilePath="output/opendoc.json")
5. evaluate_script: document.cookie → 保存到 cookies.txt
6. python3 scripts/convert.py output/opendoc.json --output-dir output/ --cleanup-source
7. close_page(pageId=N)
```

**表格 (sheet.weixin.qq.com)**
```bash
# 有 cookies - 获取所有工作表（默认）
python3 scripts/convert.py --url "<表格URL?scode=xxx>" --cookie cookies.txt --output-dir output/

# 有 cookies - 指定单个工作表
python3 scripts/convert.py --url "<表格URL?scode=xxx>" --cookie cookies.txt --sheet-name "工作表名" -o output/sheet.md

# 无 cookies（使用 MCP 获取 cookies）
1. new_page(url="<表格URL?scode=xxx>")  # scode 参数必需
2. 等待页面加载完成
3. evaluate_script: document.cookie → 保存到 cookies.txt
4. python3 scripts/convert.py --url "<表格URL?scode=xxx>" --cookie cookies.txt --output-dir output/
5. close_page(pageId=N)
```

### Step 3: 输出结果

| 类型 | 输出 |
|------|------|
| 文档 | 单个 `.md` 文件，自动使用文档标题命名 |
| 表格 | `<表格名称>/<工作表>.md`，每个工作表一个文件 |

## 常用参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--url` | 文档/表格 URL | `--url "https://doc.weixin.qq.com/..."` |
| `--cookie` | Cookie 文件路径 | `--cookie cookies.txt` |
| `-o` | 输出文件路径（向后兼容） | `-o output/doc.md` |
| `--output-dir` | 输出目录 | `--output-dir ./exports/` |
| `--doc-name` | 指定文档名称（仅文档） | `--doc-name "我的文档"` |
| `--sheet-name` | 指定工作表（仅表格） | `--sheet-name "Sheet1"` |
| `--cleanup-source` | 转换后删除源 JSON | `--cleanup-source` |

## Cookies 管理

**格式**：纯文本，格式为 `session_id=xxx; user_token=yyy; ...`

**过期处理**：删除 `cookies.txt` → 使用 MCP 重新访问 → 自动保存新 cookies

**获取方式**：浏览器 DevTools → Application → Cookies → 复制所有 cookie 键值对

## 常见问题

**Q: 提示 "cookies 无效或过期"**
- 删除 `cookies.txt`
- 使用 MCP 方式重新获取

**Q: 表格只获取了第一个工作表**
- 不指定 `--sheet-name` 时默认获取所有可见工作表
- 检查 scode 参数是否正确

## 增量更新

已转换的 Markdown 文件 front matter 包含 `revision` 字段，可用于检测更新：

```bash
# 获取当前版本号
revision=$(grep "^revision:" output/doc.md | cut -d' ' -f2)

# 检查是否有更新（无变化则跳过）
python3 scripts/convert.py --url "<URL>" --cookie cookies.txt --output-dir output/ --revision $revision
```

## References

技术细节和高级用法请参考 references 目录：

- [data-format.md](references/data-format.md) - 数据格式和 Protobuf 解析
- [enums-reference.md](references/enums-reference.md) - 枚举值完整参考
- [format-parsing.md](references/format-parsing.md) - 控制字符处理
- [sheet-parsing.md](references/sheet-parsing.md) - 表格解析逻辑
- [advanced-topics.md](references/advanced-topics.md) - 评论处理、增量更新
