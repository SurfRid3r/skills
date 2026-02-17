---
name: tencent-converter
description: 将腾讯文档转换为 Markdown 格式。支持标题、段落、列表、代码块、图片、表格、超链接。触发条件：(1) 用户请求转换腾讯文档 (2) 用户提供 doc.weixin.qq.com URL
---

# Tencent Converter

将腾讯文档转换为 Markdown。

**优先使用浏览器 MCP 获取数据**；MCP 不可用时，使用 Cookie 文件。

## 方法一：浏览器 MCP（推荐）

使用浏览器 MCP（如 chrome-devtools、playwright 等）自动获取 opendoc 响应：

```
1. 打开文档页面: new_page(url="<腾讯文档URL>")
2. 等待加载，刷新页面以捕获请求: navigate_page(type="reload")
3. 查找网络请求: list_network_requests(resourceTypes=["xhr", "fetch"])
4. 找到 opendoc 请求（URL 包含 dop-api/opendoc）
5. 保存响应: get_network_request(reqid=N, responseFilePath="output/opendoc.json")
6. 转换: python3 scripts/convert.py output/opendoc.json -o output/doc.md --page-url "<腾讯文档URL>" --cleanup-source
7. 关闭新打开的页面: close_page(pageId=N)
```

**注意**：
- 如果是通过 `new_page()` 新打开的浏览器窗口，完成后应关闭该页面
- 如果使用用户已有的浏览器，跳过关闭步骤

**参数说明**：
- `--page-url`: 添加文档在线链接到 Markdown meta 信息
- `--cleanup-source`: 转换完成后自动删除 opendoc.json

## 方法二：Cookie 文件

当浏览器 MCP 不可用时，要求用户提供 `cookies.txt` 文件：

```bash
python3 scripts/fetch_opendoc.py \
  -u "<腾讯文档URL>" -c cookies.txt -o output/opendoc.json
python3 scripts/convert.py output/opendoc.json -o output/doc.md --page-url "<腾讯文档URL>" --cleanup-source
```

**Cookie 格式支持**:
- Netscape 格式（curl -c 输出，每行: domain\tflag\tpath\tsecure\texpiry\tname\tvalue）
- 原始格式（name=value; name2=value2）
- 每行一个 name=value

**导出方法**: 浏览器扩展（如 EditThisCookie、Cookie Editor）导出，或复制 `document.cookie` 值

## 输出示例

转换后的 Markdown 文件开头包含 meta 信息：

```markdown
---
pageUrl: https://doc.weixin.qq.com/d/xxx
---

# 文档标题

正文内容...
```

## 脚本参数

### convert.py
| 参数 | 说明 |
|------|------|
| `input` | opendoc.json 路径 |
| `-o, --output` | 输出 .md 路径 |
| `-v, --verbose` | 详细输出 |
| `--page-url URL` | 文档在线链接，用于生成 meta 信息 |
| `--cleanup-source` | 转换完成后删除输入的 opendoc.json |

### fetch_opendoc.py
| 参数 | 说明 |
|------|------|
| `-u, --url` | 腾讯文档 URL |
| `-c, --cookie` | Cookie 文件路径 |
| `-o, --output` | 输出 JSON 路径 |

## 故障排除

### Cookie 过期

当出现以下错误时，说明 Cookie 已过期：
- `文档内容为空，可能需要重新登录获取新 Cookie`
- `响应缺少用户信息，Cookie 可能已过期`

**解决方法**：
1. 在浏览器中重新登录腾讯文档
2. 使用浏览器扩展（如 EditThisCookie、Cookie Editor）导出新的 cookies.txt
3. 重新运行转换命令

### 浏览器 MCP 获取失败

如果刷新页面后仍找不到 opendoc 请求：
1. 确保文档已完全加载
2. 尝试硬刷新（Ctrl+Shift+R 或 Cmd+Shift+R）
3. 检查 Network 面板的 Preserve log 选项是否开启
