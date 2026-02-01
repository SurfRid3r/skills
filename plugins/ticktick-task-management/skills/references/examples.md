# TickTick CLI - 详细示例与工作流

本文档包含 TickTick/滴答清单常见场景的完整工作流示例。

---

## 工作流 0: 任务创建标准流程

当用户需要创建任务时，遵循以下标准流程：

### 步骤 1: 获取项目 ID

**所有任务创建都需要先获取项目 ID**：
```bash
# 列出所有项目
python scripts/ticktick.py projects list

# 输出示例:
# 📁 📥 收集箱 (0 任务) [ID: inbox1022290574]
# 📁 💼工作任务 (15 任务) [ID: 63946e00f7244412354e4c9c]
# 📁 🚤定时任务 (5 任务) [ID: 671dbf3cd3c7bc0000000161]
# 📁 📚 个人学习 (8 任务) [ID: 696cc835e4b0e5948ab76023]
```

### 步骤 2: 使用项目 ID 创建任务

```bash
# 基本任务创建
python scripts/ticktick.py tasks create --title "任务标题" --project-id "63946e00f7244412354e4c9c"

# 带优先级和截止日期
python scripts/ticktick.py tasks create \
  --title "线上参与湘雅医院的汇报并更新进展" \
  --project-id "63946e00f7244412354e4c9c" \
  --priority high \
  --due-date "2026-01-22T17:00:00+08:00"

# 带标签
python scripts/ticktick.py tasks create \
  --title "季度总结" \
  --project-id "63946e00f7244412354e4c9c" \
  --tags "重要,紧急" \
  --content "详细描述..."
```

### 错误处理

**如果出现认证错误**:
```bash
# 首次使用需要配置 ~/.ticktick/.env
# macOS/Linux:
mkdir -p ~/.ticktick
cp .env.template ~/.ticktick/.env
nano ~/.ticktick/.env  # 编辑设置 DIDA_USERNAME 和 DIDA_PASSWORD

# Windows:
mkdir %USERPROFILE%\.ticktick
copy .env.template %USERPROFILE%\.ticktick\.env
notepad %USERPROFILE%\.ticktick\.env
```

### 完整示例对话

```
用户: 这周四注意添加一个工作任务，线上参与湘雅医院的汇报

Claude 执行流程:
1. 先列出项目获取 ID
2. 找到"工作任务"项目 ID: 63946e00f7244412354e4c9c
3. 计算日期：这周四 = 2026-01-22
4. 执行命令:
   python scripts/ticktick.py tasks create \
     --title "线上参与湘雅医院的汇报并更新进展" \
     --project-id "63946e00f7244412354e4c9c" \
     --due-date "2026-01-22T17:00:00+08:00"
5. 返回任务 ID
```

---

## 工作流 1: 每周计划

```bash
# 1. 查看所有项目
python scripts/ticktick.py projects list

# 2. 创建本周任务 (使用项目 ID)
python scripts/ticktick.py tasks create --title "周一会议准备" --project-id "63946e00f7244412354e4c9c" --priority high --due-date "2026-01-20T09:00:00+08:00"
python scripts/ticktick.py tasks create --title "周三报告" --project-id "63946e00f7244412354e4c9c" --priority medium --due-date "2026-01-22T17:00:00+08:00"
python scripts/ticktick.py tasks create --title "周五复盘" --project-id "63946e00f7244412354e4c9c" --priority low --due-date "2026-01-24T17:00:00+08:00"

# 3. 查看项目中的任务
python scripts/ticktick.py tasks list --project-id "63946e00f7244412354e4c9c"
```

## 工作流 2: 标签整理任务

```bash
# 1. 搜索待整理任务
python scripts/ticktick.py tasks search "待定"

# 2. 创建组织标签
python scripts/ticktick.py tags create --name "重要" --color "#FF6B6B"
python scripts/ticktick.py tags create --name "紧急" --color "#F38181"

# 3. 创建带标签的任务 (使用项目 ID)
python scripts/ticktick.py tasks create --title "季度总结" --project-id "63946e00f7244412354e4c9c" --tags "重要,紧急" --priority high

# 4. 查看所有标签
python scripts/ticktick.py tags list

# 5. 如需合并相似标签
python scripts/ticktick.py tags merge "旧标签" "新标签"
```

## 工作流 3: 任务协作与评论

```bash
# 1. 创建协作任务 (使用项目 ID)
python scripts/ticktick.py tasks create --title "团队项目" --project-id "63946e00f7244412354e4c9c" --content "需要与设计团队协调"

# 2. 查找任务获取 ID
python scripts/ticktick.py tasks search "团队项目"

# 3. 添加评论
python scripts/ticktick.py comments add <任务ID> <项目ID> --content "需要安排与利益相关者的会议"

# 4. 查看所有评论
python scripts/ticktick.py comments get <任务ID> <项目ID>

# 5. 如需更新评论
python scripts/ticktick.py comments update <评论ID> <任务ID> <项目ID> --content "会议已安排下周二"
```

## 工作流 4: 习惯追踪设置

```bash
# 1. 创建每日习惯
python scripts/ticktick.py habits create --name "晨间阅读" --goal 1.0 --unit "小时" --color "#4ECDC4"

# 2. 创建每周健身习惯
python scripts/ticktick.py habits create --name "健身" --repeat-rule "FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,WE,FR" --goal 3 --unit "次"

# 3. 查看所有习惯
python scripts/ticktick.py habits list

# 4. 查看习惯分组
python scripts/ticktick.py habits sections

# 5. 查询打卡记录
python scripts/ticktick.py habits checkins --habit-ids "<习惯ID1>,<习惯ID2>" --after-stamp 20260101
```

## 工作流 5: 跨项目移动任务

```bash
# 1. 列出项目找到源和目标
python scripts/ticktick.py projects list

# 2. 查找要移动的任务
python scripts/ticktick.py tasks search "要移动的任务"

# 3. 使用项目 ID 移动
python scripts/ticktick.py tasks move <任务ID> <源项目ID> --to-project-id "目标项目ID"
```

## 工作流 6: 批量任务操作

```bash
# 批量更新多个任务
python scripts/ticktick.py tasks batch-update --tasks '[
  {"id":"task1","priority":5},
  {"id":"task2","title":"更新后的标题"},
  {"id":"task3","content":"新描述"}
]'

# 批量删除任务
python scripts/ticktick.py tasks batch-delete --tasks '[
  {"taskId":"task1","projectId":"proj1"},
  {"taskId":"task2","projectId":"proj1"}
]'

# 批量移动到新项目 (使用项目 ID)
python scripts/ticktick.py tasks batch-move --tasks '[
  {"taskId":"task1","projectId":"proj1"},
  {"taskId":"task2","projectId":"proj1"}
]' --to-project-id "目标项目ID"
```

## 工作流 7: 项目管理

```bash
# 1. 创建带自定义颜色的新项目
python scripts/ticktick.py projects create --name "Q1 计划" --color "#95E1D3" --sort-order 1

# 2. 获取项目详情(包含任务)
python scripts/ticktick.py projects get <项目ID> --include-tasks

# 3. 更新项目属性
python scripts/ticktick.py projects update <项目ID> --name "Q1 计划(修订)" --color "#FF6B6B"

# 4. 删除空项目(谨慎操作!)
python scripts/ticktick.py projects delete <项目ID>
```

## 工作流 8: 查找并完成任务

```bash
# 1. 搜索任务
python scripts/ticktick.py tasks search "报告"

# 2. 按 ID 查找特定任务(知道项目时更快)
python scripts/ticktick.py tasks find <任务ID> --project-id <项目ID>

# 3. 标记任务完成
python scripts/ticktick.py tasks complete <任务ID> <项目ID>

# 4. 查看日期范围内的已完成任务
python scripts/ticktick.py tasks completed --from-date "2026-01-01" --to-date "2026-01-31" --limit 100
```

## 工作流 9: 标签清理

```bash
# 1. 列出所有标签
python scripts/ticktick.py tags list

# 2. 重命名标签(更新所有使用该标签的任务)
python scripts/ticktick.py tags update "旧名称" "新名称"

# 3. 合并重复标签
python scripts/ticktick.py tags merge "待办" "to-do"

# 4. 删除未使用的标签
python scripts/ticktick.py tags delete "过时标签"
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
