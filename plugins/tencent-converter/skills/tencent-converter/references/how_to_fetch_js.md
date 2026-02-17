# 腾讯文档 JS 文件获取指南

本文档说明如何通过浏览器 MCP 工具获取腾讯文档的 JavaScript 文件。

## 获取步骤

### 1. 打开腾讯文档

使用 MCP 工具打开目标腾讯文档：

```
mcp__chrome-devtools__new_page - 打开文档 URL
```

### 2. 查找 JS 文件请求

等待页面加载完成后，列出所有网络请求：

```
mcp__chrome-devtools__list_network_requests - 查找 JS 文件
```

筛选 resourceTypes: ["script"]

### 3. 识别关键 JS 文件

腾讯文档的关键 JS 文件：

| 文件名模式 | 用途 |
|-----------|------|
| `public-firstload-pc-*.js` | 核心解析逻辑，包含 ultrabuf 解析 |
| `feature-pc-bundle_word-helper-*.js` | 表格功能 |

### 4. 保存 JS 文件

使用 get_network_request 获取 JS 内容并保存：

```
mcp__chrome-devtools__get_network_request - 保存到 tencent_js/ 目录
```

### 5. 格式化 JS 文件

使用脚本格式化 JS 文件以便分析：

```bash
python3 scripts/02_download_js.py --format-only
```

该命令会格式化 `tencent_js/` 目录中的所有 JS 文件。

## 前置依赖

格式化功能需要 prettier：

```bash
npm install -g prettier
```

## 注意事项

- JS 文件较大（1-2MB），格式化需要一些时间
- 格式化后的文件扩展名为 `.formatted.js`
- 建议只保留正在分析的文件，其他可删除以节省空间
- `tencent_js/` 目录已添加到 `.gitignore`，不会提交到版本控制
