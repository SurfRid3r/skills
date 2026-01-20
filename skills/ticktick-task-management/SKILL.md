---
name: ticktick-task-management
description: TickTick/滴答清单统一管理 CLI,支持任务、项目、标签、评论和习惯管理。当用户需要以下操作时使用: (1) 创建/更新/删除/完成任务, (2) 管理项目, (3) 整理标签, (4) 添加任务评论, (5) 追踪习惯。所有操作需配置 `.env` 文件中的 DIDA_USERNAME 和 DIDA_PASSWORD。
---

# TickTick 任务管理

TickTick/滴答清单统一 CLI 接口,所有命令通过 `python scripts/ticktick.py` 执行。

## 快速参考

| 分类 | 命令 |
|------|------|
| **项目管理** | `list`, `get <id>`, `create --name <name>`, `update <id>`, `delete <id>` |
| **任务管理** | `list [--project-id]`, `create --title <title> --project-id <id>`, `update <id> <projectId>`, `complete <id> <projectId>`, `delete <id> <projectId>`, `search <keyword>`, `move <id> <projectId> --to-project-id <id>`, `find <id> [--project-id]`, `completed [--from-date] [--to-date] [--limit]`, `batch-update/delete/move` |
| **标签管理** | `list`, `create --name <name>`, `update <old> <new>`, `delete <name>`, `merge <src> <dst>` |
| **评论管理** | `get <taskId> <projectId>`, `add <taskId> <projectId> --content <text>`, `update <commentId> <taskId> <projectId>`, `delete <commentId> <taskId> <projectId>` |
| **习惯管理** | `list`, `create --name <name>`, `update <id>`, `delete <id>`, `sections`, `checkins --habit-ids <ids>`, `records --habit-ids <ids>` |

## 初始设置

```bash
pip install -r requirements.txt
cp .env.template .env
# 编辑 .env: 设置 DIDA_USERNAME 和 DIDA_PASSWORD
```

## 常用命令

### 创建任务
```bash
# 首先获取项目 ID
python scripts/ticktick.py projects list

# 使用项目 ID 创建任务
python scripts/ticktick.py tasks create --title "任务标题" --project-id "63946e00f7244412354e4c9c" --priority high --due-date "2026-01-20T17:00:00+08:00" --tags "重要,紧急" --content "任务描述"
```

### 按项目列出任务
```bash
python scripts/ticktick.py tasks list --project-id "63946e00f7244412354e4c9c"
```

### 搜索并完成任务
```bash
python scripts/ticktick.py tasks search "关键词"
python scripts/ticktick.py tasks complete <任务ID> <项目ID>
```

### 跨项目移动任务
```bash
python scripts/ticktick.py tasks move <任务ID> <源项目ID> --to-project-id "目标项目ID"
```

## 关键参数

| 参数 | 值/格式 |
|------|---------|
| `--priority` | `high`(5), `medium`(3), `low`(1), `none`(0) |
| `--due-date` | ISO 8601: `2026-01-20T17:00:00+08:00` |
| `--color` | 十六进制: `#FF6B6B`, `#4ECDC4` |
| `--repeat-rule` | iCalendar: `FREQ=DAILY;INTERVAL=1`, `FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,WE,FR` |
| `--tags` | 逗号分隔: `"标签1,标签2"` |

## 批量操作

```bash
# 批量更新
python scripts/ticktick.py tasks batch-update --tasks '[{"id":"id1","title":"新标题"},{"id":"id2","priority":5}]'

# 批量删除
python scripts/ticktick.py tasks batch-delete --tasks '[{"taskId":"id1","projectId":"pid1"}]'

# 批量移动
python scripts/ticktick.py tasks batch-move --tasks '[{"taskId":"id1","projectId":"srcPid"}]' --to-project-id "目标项目ID"
```

## 显示符号

- `✓` / `○` - 已完成 / 未完成
- `🔴` / `🟡` / `🔵` - 高 / 中 / 低优先级
- `📅` - 截止日期
- `🏷️` - 标签

## 错误处理

| 错误 | 解决方案 |
|------|----------|
| 认证失败 | 检查 `.env` 中的用户名密码 |
| 任务未找到 | 使用 `search` 或 `completed` - 任务可能已完成 |
| 无效的项目 ID | 使用 `projects list` 获取正确 ID |
| SOCKS 代理错误 | 运行 `pip install httpx[socks]` |

## 高级工作流

完整工作流示例(周计划、任务整理、团队协作、习惯追踪)见 [references/examples.md](references/examples.md)。
