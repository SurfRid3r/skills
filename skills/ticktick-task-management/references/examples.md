# TickTick CLI - 详细示例与工作流

本文档包含 TickTick/滴答清单常见场景的完整工作流示例。

## 工作流 1: 每周计划

```bash
# 1. 查看所有项目
python ticktick.py projects list

# 2. 创建本周任务
python ticktick.py tasks create --title "周一会议准备" --project-name "工作" --priority high --due-date "2026-01-20T09:00:00+08:00"
python ticktick.py tasks create --title "周三报告" --project-name "工作" --priority medium --due-date "2026-01-22T17:00:00+08:00"
python ticktick.py tasks create --title "周五复盘" --project-name "工作" --priority low --due-date "2026-01-24T17:00:00+08:00"

# 3. 查看项目中的任务
python ticktick.py tasks list --project-name "工作"
```

## 工作流 2: 标签整理任务

```bash
# 1. 搜索待整理任务
python ticktick.py tasks search "待定"

# 2. 创建组织标签
python ticktick.py tags create --name "重要" --color "#FF6B6B"
python ticktick.py tags create --name "紧急" --color "#F38181"

# 3. 创建带标签的任务
python ticktick.py tasks create --title "季度总结" --project-name "工作" --tags "重要,紧急" --priority high

# 4. 查看所有标签
python ticktick.py tags list

# 5. 如需合并相似标签
python ticktick.py tags merge "旧标签" "新标签"
```

## 工作流 3: 任务协作与评论

```bash
# 1. 创建协作任务
python ticktick.py tasks create --title "团队项目" --project-name "工作" --content "需要与设计团队协调"

# 2. 查找任务获取 ID
python ticktick.py tasks search "团队项目"

# 3. 添加评论
python ticktick.py comments add <任务ID> <项目ID> --content "需要安排与利益相关者的会议"

# 4. 查看所有评论
python ticktick.py comments get <任务ID> <项目ID>

# 5. 如需更新评论
python ticktick.py comments update <评论ID> <任务ID> <项目ID> --content "会议已安排下周二"
```

## 工作流 4: 习惯追踪设置

```bash
# 1. 创建每日习惯
python ticktick.py habits create --name "晨间阅读" --goal 1.0 --unit "小时" --color "#4ECDC4"

# 2. 创建每周健身习惯
python ticktick.py habits create --name "健身" --repeat-rule "FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,WE,FR" --goal 3 --unit "次"

# 3. 查看所有习惯
python ticktick.py habits list

# 4. 查看习惯分组
python ticktick.py habits sections

# 5. 查询打卡记录
python ticktick.py habits checkins --habit-ids "<习惯ID1>,<习惯ID2>" --after-stamp 20260101
```

## 工作流 5: 跨项目移动任务

```bash
# 1. 列出项目找到源和目标
python ticktick.py projects list

# 2. 查找要移动的任务
python ticktick.py tasks search "要移动的任务"

# 3. 使用项目名移动(更简单)
python ticktick.py tasks move <任务ID> <源项目ID> --to-project-name "目标项目"

# 或使用项目 ID 移动(已知时更快)
python ticktick.py tasks move <任务ID> <源项目ID> --to-project-id <目标项目ID>
```

## 工作流 6: 批量任务操作

```bash
# 批量更新多个任务
python ticktick.py tasks batch-update --tasks '[
  {"id":"task1","priority":5},
  {"id":"task2","title":"更新后的标题"},
  {"id":"task3","content":"新描述"}
]'

# 批量删除任务
python ticktick.py tasks batch-delete --tasks '[
  {"taskId":"task1","projectId":"proj1"},
  {"taskId":"task2","projectId":"proj1"}
]'

# 批量移动到新项目
python ticktick.py tasks batch-move --tasks '[
  {"taskId":"task1","projectId":"proj1"},
  {"taskId":"task2","projectId":"proj1"}
]' --to-project-name "归档"
```

## 工作流 7: 项目管理

```bash
# 1. 创建带自定义颜色的新项目
python ticktick.py projects create --name "Q1 计划" --color "#95E1D3" --sort-order 1

# 2. 获取项目详情(包含任务)
python ticktick.py projects get <项目ID> --include-tasks

# 3. 更新项目属性
python ticktick.py projects update <项目ID> --name "Q1 计划(修订)" --color "#FF6B6B"

# 4. 删除空项目(谨慎操作!)
python ticktick.py projects delete <项目ID>
```

## 工作流 8: 查找并完成任务

```bash
# 1. 搜索任务
python ticktick.py tasks search "报告"

# 2. 按 ID 查找特定任务(知道项目时更快)
python ticktick.py tasks find <任务ID> --project-id <项目ID>

# 3. 标记任务完成
python ticktick.py tasks complete <任务ID> <项目ID>

# 4. 查看日期范围内的已完成任务
python ticktick.py tasks completed --from-date "2026-01-01" --to-date "2026-01-31" --limit 100
```

## 工作流 9: 标签清理

```bash
# 1. 列出所有标签
python ticktick.py tags list

# 2. 重命名标签(更新所有使用该标签的任务)
python ticktick.py tags update "旧名称" "新名称"

# 3. 合并重复标签
python ticktick.py tags merge "待办" "to-do"

# 4. 删除未使用的标签
python ticktick.py tags delete "过时标签"
```

## 常用颜色代码

| 颜色 | 十六进制 |
|------|----------|
| 红色 | `#FF6B6B` |
| 珊瑚色 | `#F38181` |
| 青色 | `#4ECDC4` |
| 薄荷绿 | `#95E1D3` |
| 蓝色 | `#6C5CE7` |
| 黄色 | `#FFEAA7` |
| 绿色 | `#55EFC4` |

## 重复规则参考

| 模式 | RRULE |
|------|-------|
| 每天 | `FREQ=DAILY;INTERVAL=1` |
| 每周(周一/三/五) | `FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,WE,FR` |
| 每周(周二/四) | `FREQ=WEEKLY;INTERVAL=1;BYDAY=TU,TH` |
| 每月 | `FREQ=MONTHLY;INTERVAL=1` |
| 工作日 | `FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,TU,WE,TH,FR` |
| 周末 | `FREQ=WEEKLY;INTERVAL=1;BYDAY=SA,SU` |
