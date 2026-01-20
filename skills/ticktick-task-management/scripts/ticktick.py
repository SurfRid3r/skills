#!/usr/bin/env python3
"""
TickTick Skill CLI - 统一命令行接口

使用方法：
    uv run ticktick.py <category> <action> [options]

示例：
    uv run ticktick.py tasks list --project-name "工作"
    uv run ticktick.py tasks create --title "完成报告" --project-name "工作" --priority high
    uv run ticktick.py projects list
    uv run ticktick.py tags list
"""

import asyncio
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from auth.web_auth import WebAuth
from api.services.tasks import TaskService
from api.services.projects import ProjectService
from api.services.tags import TagService
from api.services.comments import CommentService
from api.services.habits import HabitService


class TickTickCLI:
    """TickTick CLI 主类"""

    PRIORITY_MAP = {'none': 0, 'low': 1, 'medium': 3, 'high': 5}

    def __init__(self):
        self.auth = None

    async def ensure_auth(self):
        """确保认证"""
        if not self.auth:
            self.auth = WebAuth()
            await self.auth.ensure_authenticated()

    async def _resolve_project_id(self, project_service, project_id=None, project_name=None):
        """Resolve project ID from either ID or name.

        Returns None if neither is provided or if project is not found.
        """
        if project_id:
            return project_id

        if not project_name:
            return None

        projects = await project_service.get_all()
        for project in projects:
            if project.get('name') == project_name:
                return project['id']

        return None

    @staticmethod
    def _parse_priority(priority_str):
        """Convert priority string to numeric value."""
        return TickTickCLI.PRIORITY_MAP.get(priority_str, 0) if priority_str else None
    
    # ========== 项目管理 ==========
    
    async def projects_list(self, args):
        """列出所有项目"""
        await self.ensure_auth()
        service = ProjectService(self.auth)
        try:
            projects = await service.get_all()
            self._print_projects(projects)
        finally:
            await service.close()
    
    async def projects_get(self, args):
        """获取项目详情"""
        await self.ensure_auth()
        service = ProjectService(self.auth)
        try:
            project = await service.get_by_id(
                args.project_id,
                include_tasks=args.include_tasks
            )
            print(json.dumps(project, indent=2, ensure_ascii=False))
        finally:
            await service.close()
    
    async def projects_create(self, args):
        """创建项目"""
        await self.ensure_auth()
        service = ProjectService(self.auth)
        try:
            project = await service.create(
                name=args.name,
                color=args.color,
                sort_order=args.sort_order
            )
            print(f"✓ 创建项目成功: {project['name']} (ID: {project['id']})")
        finally:
            await service.close()
    
    async def projects_update(self, args):
        """更新项目"""
        await self.ensure_auth()
        service = ProjectService(self.auth)
        try:
            await service.update(
                project_id=args.project_id,
                name=args.name,
                color=args.color
            )
            print(f"✓ 更新项目成功")
        finally:
            await service.close()
    
    async def projects_delete(self, args):
        """删除项目"""
        await self.ensure_auth()
        service = ProjectService(self.auth)
        try:
            await service.delete(project_id=args.project_id)
            print(f"✓ 删除项目成功")
        finally:
            await service.close()
    
    # ========== 任务管理 ==========
    
    async def tasks_list(self, args):
        """列出任务"""
        await self.ensure_auth()
        task_service = TaskService(self.auth)
        project_service = ProjectService(self.auth)

        try:
            project_id = await self._resolve_project_id(project_service, args.project_id, args.project_name)

            if project_id:
                tasks = await task_service.list_in_project(project_id)
            else:
                tasks = await task_service.get_all()

            self._print_tasks(tasks)
        finally:
            await task_service.close()
            await project_service.close()
    
    async def tasks_create(self, args):
        """创建任务"""
        await self.ensure_auth()
        task_service = TaskService(self.auth)
        project_service = ProjectService(self.auth)

        try:
            project_id = await self._resolve_project_id(project_service, args.project_id, args.project_name)

            if not project_id:
                print("❌ 错误: 必须指定项目ID或项目名称")
                return

            priority = self._parse_priority(args.priority)

            task = await task_service.create(
                project_id=project_id,
                title=args.title,
                content=args.content,
                priority=priority,
                due_date=args.due_date,
                tags=args.tags.split(',') if args.tags else None
            )
            print(f"✓ 创建任务成功: {task['title']} (ID: {task['id']})")
        finally:
            await task_service.close()
            await project_service.close()
    
    async def tasks_update(self, args):
        """更新任务"""
        await self.ensure_auth()
        service = TaskService(self.auth)

        try:
            priority = self._parse_priority(args.priority)

            await service.update(
                task_id=args.task_id,
                project_id=args.project_id,
                title=args.title,
                content=args.content,
                priority=priority
            )
            print(f"✓ 更新任务成功")
        finally:
            await service.close()
    
    async def tasks_complete(self, args):
        """完成任务"""
        await self.ensure_auth()
        service = TaskService(self.auth)
        try:
            await service.complete(
                project_id=args.project_id,
                task_id=args.task_id
            )
            print(f"✓ 任务已完成")
        finally:
            await service.close()
    
    async def tasks_delete(self, args):
        """删除任务"""
        await self.ensure_auth()
        service = TaskService(self.auth)
        try:
            await service.delete(
                project_id=args.project_id,
                task_id=args.task_id
            )
            print(f"✓ 删除任务成功")
        finally:
            await service.close()
    
    async def tasks_search(self, args):
        """搜索任务"""
        await self.ensure_auth()
        service = TaskService(self.auth)
        try:
            tasks = await service.search(keywords=args.keywords)
            self._print_tasks(tasks)
        finally:
            await service.close()
    
    async def tasks_move(self, args):
        """移动任务到其他项目"""
        await self.ensure_auth()
        task_service = TaskService(self.auth)
        project_service = ProjectService(self.auth)

        try:
            to_project_id = await self._resolve_project_id(project_service, args.to_project_id, args.to_project_name)

            if not to_project_id:
                print("❌ 错误: 必须指定目标项目ID或项目名称")
                return

            await task_service.move(
                task_id=args.task_id,
                from_project_id=args.from_project_id,
                to_project_id=to_project_id
            )
            print(f"✓ 任务移动成功")
        finally:
            await task_service.close()
            await project_service.close()
    
    async def tasks_find(self, args):
        """查找任务"""
        await self.ensure_auth()
        service = TaskService(self.auth)
        try:
            task = await service.find(
                task_id=args.task_id,
                project_id=args.project_id
            )
            if task:
                print(json.dumps(task, indent=2, ensure_ascii=False))
            else:
                print("❌ 未找到任务")
        finally:
            await service.close()
    
    async def tasks_completed(self, args):
        """获取已完成任务"""
        await self.ensure_auth()
        service = TaskService(self.auth)
        try:
            tasks = await service.get_completed_in_all(
                from_date=args.from_date,
                to_date=args.to_date,
                limit=args.limit
            )
            
            if isinstance(tasks, dict):
                # 提取任务列表
                task_list = tasks.get('tasks', [])
                print(f"\n找到 {len(task_list)} 个已完成任务:\n")
                for task in task_list:
                    title = task.get('title', 'Unknown')
                    completed_time = task.get('completedTime', '')
                    print(f"  ✓ {title}")
                    print(f"      ID: {task['id']}")
                    print(f"      完成时间: {completed_time}")
                    print()
            else:
                self._print_tasks(tasks if isinstance(tasks, list) else [])
        finally:
            await service.close()
    
    async def tasks_batch_update(self, args):
        """批量更新任务"""
        await self.ensure_auth()
        service = TaskService(self.auth)
        try:
            updates = json.loads(args.tasks)
            await service.batch_update_tasks(updates=updates)
            print(f"✓ 批量更新成功: {len(updates)} 个任务")
        finally:
            await service.close()
    
    async def tasks_batch_delete(self, args):
        """批量删除任务"""
        await self.ensure_auth()
        service = TaskService(self.auth)
        try:
            deletes = json.loads(args.tasks)
            await service.batch_delete_tasks(deletes=deletes)
            print(f"✓ 批量删除成功: {len(deletes)} 个任务")
        finally:
            await service.close()
    
    async def tasks_batch_move(self, args):
        """批量移动任务"""
        await self.ensure_auth()
        task_service = TaskService(self.auth)
        project_service = ProjectService(self.auth)

        try:
            to_project_id = await self._resolve_project_id(project_service, args.to_project_id, args.to_project_name)

            if not to_project_id:
                print("❌ 错误: 必须指定目标项目ID或项目名称")
                return

            task_moves = json.loads(args.tasks)
            await task_service.batch_move(
                task_moves=task_moves,
                to_project_id=to_project_id
            )
            print(f"✓ 批量移动成功: {len(task_moves)} 个任务")
        finally:
            await task_service.close()
            await project_service.close()
    
    # ========== 标签管理 ==========
    
    async def tags_list(self, args):
        """列出所有标签"""
        await self.ensure_auth()
        service = TagService(self.auth)
        try:
            tags = await service.list_all()
            for tag in tags:
                color = tag.get('color', '')
                print(f"  [{color}] {tag.get('name')} (ID: {tag['id']})")
        finally:
            await service.close()
    
    async def tags_create(self, args):
        """创建标签"""
        await self.ensure_auth()
        service = TagService(self.auth)
        try:
            tag = await service.create(
                name=args.name,
                color=args.color
            )
            print(f"✓ 创建标签成功: {tag['name']}")
        finally:
            await service.close()
    
    async def tags_delete(self, args):
        """删除标签"""
        await self.ensure_auth()
        service = TagService(self.auth)
        try:
            await service.delete(tag_name=args.tag_name)
            print(f"✓ 删除标签成功")
        finally:
            await service.close()
    
    async def tags_update(self, args):
        """更新/重命名标签"""
        await self.ensure_auth()
        service = TagService(self.auth)
        try:
            result = await service.update(
                old_name=args.old_name,
                new_name=args.new_name
            )
            count = result.get('updated_count', 0)
            print(f"✓ 标签更新成功: '{args.old_name}' -> '{args.new_name}' (影响 {count} 个任务)")
        finally:
            await service.close()
    
    async def tags_merge(self, args):
        """合并标签"""
        await self.ensure_auth()
        service = TagService(self.auth)
        try:
            await service.merge_tags(
                source_tag=args.source_tag,
                target_tag=args.target_tag
            )
            print(f"✓ 标签合并成功: '{args.source_tag}' -> '{args.target_tag}'")
        finally:
            await service.close()
    
    # ========== 习惯管理 ==========
    
    async def habits_list(self, args):
        """列出习惯"""
        await self.ensure_auth()
        service = HabitService(self.auth)
        try:
            habits = await service.list_all()
            for habit in habits:
                print(f"  📝 {habit.get('name')} (ID: {habit['id']})")
        finally:
            await service.close()
    
    async def habits_create(self, args):
        """创建习惯"""
        await self.ensure_auth()
        service = HabitService(self.auth)
        try:
            habit = await service.create(
                name=args.name,
                color=args.color,
                repeat_rule=args.repeat_rule,
                goal=args.goal,
                unit=args.unit
            )
            print(f"✓ 创建习惯成功: {args.name} (ID: {habit.get('id') if isinstance(habit, dict) else 'N/A'})")
        finally:
            await service.close()
    
    async def habits_update(self, args):
        """更新习惯"""
        await self.ensure_auth()
        service = HabitService(self.auth)
        try:
            await service.update(
                habit_id=args.habit_id,
                name=args.name,
                color=args.color,
                goal=args.goal,
                repeat_rule=args.repeat_rule
            )
            print(f"✓ 更新习惯成功")
        finally:
            await service.close()
    
    async def habits_delete(self, args):
        """删除习惯"""
        await self.ensure_auth()
        service = HabitService(self.auth)
        try:
            await service.delete(habit_id=args.habit_id)
            print(f"✓ 删除习惯成功")
        finally:
            await service.close()
    
    async def habits_sections(self, args):
        """获取习惯分组"""
        await self.ensure_auth()
        service = HabitService(self.auth)
        try:
            sections = await service.get_sections()
            for section in sections:
                print(f"  📂 {section.get('name', 'Unknown')} (ID: {section['id']})")
        finally:
            await service.close()
    
    async def habits_checkins(self, args):
        """查询打卡记录"""
        await self.ensure_auth()
        service = HabitService(self.auth)
        try:
            habit_ids = args.habit_ids.split(',')
            checkins = await service.query_checkins(
                habit_ids=habit_ids,
                after_stamp=args.after_stamp
            )
            print(json.dumps(checkins, indent=2, ensure_ascii=False))
        finally:
            await service.close()
    
    async def habits_records(self, args):
        """获取习惯记录"""
        await self.ensure_auth()
        service = HabitService(self.auth)
        try:
            habit_ids = args.habit_ids.split(',')
            records = await service.get_records(
                habit_ids=habit_ids,
                after_stamp=args.after_stamp
            )
            print(json.dumps(records, indent=2, ensure_ascii=False))
        finally:
            await service.close()
    
    # ========== 评论管理 ==========
    
    async def comments_get(self, args):
        """获取任务的所有评论"""
        await self.ensure_auth()
        service = CommentService(self.auth)
        try:
            comments = await service.get_by_task(
                project_id=args.project_id,
                task_id=args.task_id
            )
            if not comments:
                print("该任务暂无评论")
                return
            
            print(f"\n找到 {len(comments)} 条评论:\n")
            for comment in comments:
                creator = comment.get('userProfile', {}).get('username', 'Unknown')
                content = comment.get('title', '')
                created_time = comment.get('createdTime', '')
                print(f"  💬 {content}")
                print(f"      评论ID: {comment['id']}")
                print(f"      创建者: {creator}")
                print(f"      时间: {created_time}")
                print()
        finally:
            await service.close()
    
    async def comments_add(self, args):
        """添加评论"""
        await self.ensure_auth()
        service = CommentService(self.auth)
        try:
            comment = await service.add(
                project_id=args.project_id,
                task_id=args.task_id,
                content=args.content
            )
            print(f"✓ 添加评论成功 (ID: {comment.get('id', 'N/A')})")
        finally:
            await service.close()
    
    async def comments_update(self, args):
        """更新评论"""
        await self.ensure_auth()
        service = CommentService(self.auth)
        try:
            await service.update(
                project_id=args.project_id,
                task_id=args.task_id,
                comment_id=args.comment_id,
                content=args.content
            )
            print(f"✓ 更新评论成功")
        finally:
            await service.close()
    
    async def comments_delete(self, args):
        """删除评论"""
        await self.ensure_auth()
        service = CommentService(self.auth)
        try:
            await service.delete(
                project_id=args.project_id,
                task_id=args.task_id,
                comment_id=args.comment_id
            )
            print(f"✓ 删除评论成功")
        finally:
            await service.close()
    
    # ========== 辅助方法 ==========
    
    def _print_projects(self, projects, level=0):
        """打印项目树"""
        for project in projects:
            indent = "  " * level
            name = project.get('name', 'Unknown')
            task_count = project.get('taskCount', 0)
            print(f"{indent}📁 {name} ({task_count} 任务) [ID: {project['id']}]")
            
            children = project.get('children', [])
            if children:
                self._print_projects(children, level + 1)
    
    def _print_tasks(self, tasks):
        """打印任务列表"""
        if not tasks:
            print("没有找到任务")
            return

        print(f"\n找到 {len(tasks)} 个任务:\n")
        for task in tasks:
            status = "✓" if task.get('status') == 2 else "○"
            title = task.get('title', 'Unknown')

            priority_emoji_map = {0: "", 1: "🔵", 3: "🟡", 5: "🔴"}
            priority = priority_emoji_map.get(task.get('priority', 0), "")

            due_date = ""
            if task.get('dueDate'):
                try:
                    dt = datetime.fromisoformat(task['dueDate'].replace('Z', '+00:00'))
                    due_date = f" 📅 {dt.strftime('%m-%d %H:%M')}"
                except:
                    pass

            print(f"  {status} {priority} {title}{due_date}")
            print(f"      ID: {task['id']}")

            if task.get('tags'):
                tags = ', '.join(task['tags'])
                print(f"      🏷️  {tags}")
            print()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='TickTick CLI - 统一命令行接口',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='category', help='功能分类')
    
    # ========== 项目管理 ==========
    projects = subparsers.add_parser('projects', help='项目管理')
    projects_sub = projects.add_subparsers(dest='action', help='操作')
    
    # projects list
    projects_sub.add_parser('list', help='列出所有项目')
    
    # projects get
    projects_get = projects_sub.add_parser('get', help='获取项目详情')
    projects_get.add_argument('project_id', help='项目ID')
    projects_get.add_argument('--include-tasks', action='store_true', help='包含任务')
    
    # projects create
    projects_create = projects_sub.add_parser('create', help='创建项目')
    projects_create.add_argument('--name', required=True, help='项目名称')
    projects_create.add_argument('--color', default='#FF6B6B', help='颜色代码')
    projects_create.add_argument('--sort-order', type=int, help='排序')
    
    # projects update
    projects_update = projects_sub.add_parser('update', help='更新项目')
    projects_update.add_argument('project_id', help='项目ID')
    projects_update.add_argument('--name', help='新名称')
    projects_update.add_argument('--color', help='新颜色')
    
    # projects delete
    projects_delete = projects_sub.add_parser('delete', help='删除项目')
    projects_delete.add_argument('project_id', help='项目ID')
    
    # ========== 任务管理 ==========
    tasks = subparsers.add_parser('tasks', help='任务管理')
    tasks_sub = tasks.add_subparsers(dest='action', help='操作')
    
    # tasks list
    tasks_list = tasks_sub.add_parser('list', help='列出任务')
    tasks_list.add_argument('--project-id', help='项目ID')
    tasks_list.add_argument('--project-name', help='项目名称')
    
    # tasks create
    tasks_create = tasks_sub.add_parser('create', help='创建任务')
    tasks_create.add_argument('--title', required=True, help='任务标题')
    tasks_create.add_argument('--project-id', help='项目ID')
    tasks_create.add_argument('--project-name', help='项目名称')
    tasks_create.add_argument('--content', help='任务描述')
    tasks_create.add_argument('--priority', choices=['none', 'low', 'medium', 'high'], help='优先级')
    tasks_create.add_argument('--due-date', help='截止日期 (ISO格式)')
    tasks_create.add_argument('--tags', help='标签，逗号分隔')
    
    # tasks update
    tasks_update = tasks_sub.add_parser('update', help='更新任务')
    tasks_update.add_argument('task_id', help='任务ID')
    tasks_update.add_argument('project_id', help='项目ID')
    tasks_update.add_argument('--title', help='新标题')
    tasks_update.add_argument('--content', help='新描述')
    tasks_update.add_argument('--priority', choices=['none', 'low', 'medium', 'high'], help='优先级')
    
    # tasks complete
    tasks_complete = tasks_sub.add_parser('complete', help='完成任务')
    tasks_complete.add_argument('task_id', help='任务ID')
    tasks_complete.add_argument('project_id', help='项目ID')
    
    # tasks delete
    tasks_delete = tasks_sub.add_parser('delete', help='删除任务')
    tasks_delete.add_argument('task_id', help='任务ID')
    tasks_delete.add_argument('project_id', help='项目ID')
    
    # tasks search
    tasks_search = tasks_sub.add_parser('search', help='搜索任务')
    tasks_search.add_argument('keywords', help='搜索关键词')
    
    # tasks move
    tasks_move = tasks_sub.add_parser('move', help='移动任务到其他项目')
    tasks_move.add_argument('task_id', help='任务ID')
    tasks_move.add_argument('from_project_id', help='源项目ID')
    tasks_move.add_argument('--to-project-id', help='目标项目ID')
    tasks_move.add_argument('--to-project-name', help='目标项目名称')
    
    # tasks find
    tasks_find = tasks_sub.add_parser('find', help='查找任务')
    tasks_find.add_argument('task_id', help='任务ID')
    tasks_find.add_argument('--project-id', help='项目ID (可选)')
    
    # tasks completed
    tasks_completed = tasks_sub.add_parser('completed', help='获取已完成任务')
    tasks_completed.add_argument('--from-date', help='起始日期 (YYYY-MM-DD)')
    tasks_completed.add_argument('--to-date', help='结束日期 (YYYY-MM-DD)')
    tasks_completed.add_argument('--limit', type=int, default=50, help='限制数量')
    
    # tasks batch-update
    tasks_batch_update = tasks_sub.add_parser('batch-update', help='批量更新任务')
    tasks_batch_update.add_argument('--tasks', required=True, help='任务更新数据 (JSON 格式字符串)')
    
    # tasks batch-delete
    tasks_batch_delete = tasks_sub.add_parser('batch-delete', help='批量删除任务')
    tasks_batch_delete.add_argument('--tasks', required=True, help='任务删除数据 (JSON 格式字符串)')
    
    # tasks batch-move
    tasks_batch_move = tasks_sub.add_parser('batch-move', help='批量移动任务')
    tasks_batch_move.add_argument('--tasks', required=True, help='任务移动数据 (JSON 格式字符串)')
    tasks_batch_move.add_argument('--to-project-id', help='目标项目ID')
    tasks_batch_move.add_argument('--to-project-name', help='目标项目名称')
    
    # ========== 标签管理==========
    tags = subparsers.add_parser('tags', help='标签管理')
    tags_sub = tags.add_subparsers(dest='action', help='操作')
    
    # tags list
    tags_sub.add_parser('list', help='列出所有标签')
    
    # tags create
    tags_create = tags_sub.add_parser('create', help='创建标签')
    tags_create.add_argument('--name', required=True, help='标签名称')
    tags_create.add_argument('--color', default='#4ECDC4', help='颜色代码')
    
    # tags delete
    tags_delete = tags_sub.add_parser('delete', help='删除标签')
    tags_delete.add_argument('tag_name', help='标签名称')
    
    # tags update
    tags_update = tags_sub.add_parser('update', help='更新/重命名标签')
    tags_update.add_argument('old_name', help='旧标签名')
    tags_update.add_argument('new_name', help='新标签名')
    
    # tags merge
    tags_merge = tags_sub.add_parser('merge', help='合并标签')
    tags_merge.add_argument('source_tag', help='源标签 (将被删除)')
    tags_merge.add_argument('target_tag', help='目标标签 (保留)')
    
    # ========== 评论管理 ==========
    comments = subparsers.add_parser('comments', help='评论管理')
    comments_sub = comments.add_subparsers(dest='action', help='操作')
    
    # comments get
    comments_get = comments_sub.add_parser('get', help='获取任务评论')
    comments_get.add_argument('task_id', help='任务ID')
    comments_get.add_argument('project_id', help='项目ID')
    
    # comments add
    comments_add = comments_sub.add_parser('add', help='添加评论')
    comments_add.add_argument('task_id', help='任务ID')
    comments_add.add_argument('project_id', help='项目ID')
    comments_add.add_argument('--content', required=True, help='评论内容')
    
    # comments update
    comments_update = comments_sub.add_parser('update', help='更新评论')
    comments_update.add_argument('comment_id', help='评论ID')
    comments_update.add_argument('task_id', help='任务ID')
    comments_update.add_argument('project_id', help='项目ID')
    comments_update.add_argument('--content', required=True, help='新内容')
    
    # comments delete
    comments_delete = comments_sub.add_parser('delete', help='删除评论')
    comments_delete.add_argument('comment_id', help='评论ID')
    comments_delete.add_argument('task_id', help='任务ID')
    comments_delete.add_argument('project_id', help='项目ID')
    
    # ========== 习惯管理 ==========
    habits = subparsers.add_parser('habits', help='习惯管理')
    habits_sub = habits.add_subparsers(dest='action', help='操作')
    
    # habits list
    habits_sub.add_parser('list', help='列出习惯')
    
    # habits create
    habits_create = habits_sub.add_parser('create', help='创建习惯')
    habits_create.add_argument('--name', required=True, help='习惯名称')
    habits_create.add_argument('--color', default='#4ECDC4', help='颜色代码')
    habits_create.add_argument('--repeat-rule', default='FREQ=DAILY;INTERVAL=1', help='重复规则')
    habits_create.add_argument('--goal', type=float, default=1.0, help='目标值')
    habits_create.add_argument('--unit', default='次', help='单位')
    
    # habits update
    habits_update = habits_sub.add_parser('update', help='更新习惯')
    habits_update.add_argument('habit_id', help='习惯ID')
    habits_update.add_argument('--name', help='新名称')
    habits_update.add_argument('--color', help='新颜色')
    habits_update.add_argument('--goal', type=float, help='新目标')
    habits_update.add_argument('--repeat-rule', help='新重复规则')
    
    # habits delete
    habits_delete = habits_sub.add_parser('delete', help='删除习惯')
    habits_delete.add_argument('habit_id', help='习惯ID')
    
    # habits sections
    habits_sub.add_parser('sections', help='获取习惯分组')
    
    # habits checkins
    habits_checkins = habits_sub.add_parser('checkins', help='查询打卡记录')
    habits_checkins.add_argument('--habit-ids', required=True, help='习惯ID列表，逗号分隔')
    habits_checkins.add_argument('--after-stamp', type=int, help='起始日期戳 (YYYYMMDD)')
    
    # habits records
    habits_records = habits_sub.add_parser('records', help='获取习惯记录')
    habits_records.add_argument('--habit-ids', required=True, help='习惯ID列表，逗号分隔')
    habits_records.add_argument('--after-stamp', type=int, help='起始日期戳 (YYYYMMDD)')
    
    # 解析参数
    args = parser.parse_args()
    
    if not args.category:
        parser.print_help()
        return
    
    if not args.action:
        subparsers.choices[args.category].print_help()
        return
    
    # 执行命令
    cli = TickTickCLI()
    method_name = f"{args.category}_{args.action}"
    method = getattr(cli, method_name, None)
    
    if method:
        try:
            asyncio.run(method(args))
        except KeyboardInterrupt:
            print("\n操作已取消")
        except Exception as e:
            print(f"❌ 错误: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"❌ 未知命令: {args.category} {args.action}")


if __name__ == "__main__":
    main()
