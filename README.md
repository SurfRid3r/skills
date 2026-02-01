# SurfRid3r Skills

SurfRid3r 的 Claude Skills 实用工具集合

## 快速开始

将此仓库添加为 Claude Code 的市场源：

```bash
claude marketplace add https://github.com/SurfRid3r/SurfRid3rSkills
```

然后安装单独的插件：

```bash
claude plugin install article-reviewer
claude plugin install pcap-tools
claude plugin install ticktick-task-management
```

## 插件列表

| 插件 | 分类 | 描述 |
|------|------|------|
| [article-reviewer](plugins/article-reviewer/) | 效率工具 | 文章审核与改进指导工具 - 基于写作方法论提供系统性审核 |
| [pcap-tools](plugins/pcap-tools/) | 安全工具 | PCAP 文件处理工具 - 流量分析、IP 修改、Payload 提取 |
| [ticktick-task-management](plugins/ticktick-task-management/) | 效率工具 | TickTick/滴答清单统一管理 CLI - 支持任务、项目、标签、评论和习惯管理 |

## 目录结构

```
SurfRid3rSkills/
├── .claude-plugin/
│   └── marketplace.json           # 市场目录配置
├── plugins/
│   ├── article-reviewer/
│   │   ├── .claude-plugin/plugin.json
│   │   └── skills/
│   │       ├── SKILL.md
│   │       └── references/
│   ├── pcap-tools/
│   │   ├── .claude-plugin/plugin.json
│   │   └── skills/
│   │       ├── SKILL.md
│   │       ├── scripts/
│   │       └── references/
│   └── ticktick-task-management/
│       ├── .claude-plugin/plugin.json
│       └── skills/
│           ├── SKILL.md
│           ├── scripts/
│           └── references/
```

## 贡献指南

查看 [CLAUDE.md](CLAUDE.md) 了解创建新技能的指南，遵循 [Agent Skills 规范](https://agentskills.io/specification)。