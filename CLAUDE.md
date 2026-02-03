# Claude Skills & Plugins 创建指南

本指南基于 [Anthropic Agent Skills 开放标准](https://agentskills.io/specification)，帮助您创建符合规范的 Skills 和 Plugins。

## 参考资料

- **[Agent Skills 规范](https://agentskills.io/specification)** - 官方规范文档
- **[Anthropic Skills 仓库](https://github.com/anthropics/skills)** - 官方示例集合
- **[Claude Plugins Official](https://github.com/anthropics/claude-plugins-official)** - 官方插件仓库

---

## 市场仓库结构

本项目采用市场仓库结构，可包含多个独立插件：

```
SurfRid3rSkills/
├── .claude-plugin/
│   └── marketplace.json              # 市场目录配置
├── plugins/
│   └── {plugin-name}/                # 单个插件目录
│       ├── .claude-plugin/
│       │   └── plugin.json           # 插件元数据
│       ├── skills/                   # 技能目录（可选）
│       │   └── {skill-name}/
│       │       ├── SKILL.md          # 技能定义
│       │       ├── scripts/          # 可执行代码（可选）
│       │       └── references/       # 参考文档（可选）
│       ├── commands/                 # 命令目录（可选）
│       ├── agents/                   # 代理目录（可选）
│       └── README.md                 # 插件说明（可选）
```

### 组件说明

| 目录 | 说明 | 自动发现 |
|------|------|----------|
| `skills/` | 技能目录，每个技能是子目录 | ✅ 自动扫描 SKILL.md |
| `commands/` | 命令目录，放 .md 命令文件 | ✅ 自动扫描 |
| `agents/` | 代理目录，放 .md 代理文件 | ✅ 自动扫描 |

---

## SKILL.md 格式规范

### Frontmatter（必需）

`SKILL.md` 必须以 YAML frontmatter 开头：

```yaml
---
name: skill-name
description: 技能描述和使用场景
---
```

### 字段约束

| 字段 | 必需 | 约束 |
|------|------|------|
| `name` | 是 | 最多 64 字符。仅限小写字母、数字和连字符。不能以连字符开头或结尾。必须与目录名匹配。 |
| `description` | 是 | 最多 1024 字符。描述技能功能、使用场景和触发条件。 |
| `license` | 否 | 许可证名称或对捆绑许可证文件的引用。 |
| `metadata` | 否 | 任意键值映射，用于附加元数据。 |

#### description 写作要点

**好的示例**：
```yaml
description: 从 PDF 文件中提取文本和表格，填写 PDF 表单，合并多个 PDF。当处理 PDF 文档或用户提到 PDF、表单或文档提取时使用。
```

**不好的示例**：
```yaml
description: 帮助处理 PDF。
```

---

## 版本管理

**每次更新插件内容时，必须增加 `plugin.json` 中的 `version` 字段**，否则更新不会生效。

| 变更类型 | 版本升级 |
|----------|----------|
| Bug 修复 | `1.0.0` → `1.0.1` |
| 新增功能 | `1.0.0` → `1.1.0` |
| 破坏性变更 | `1.0.0` → `2.0.0` |

---

## 新增插件/技能工作流程

### 方式一：新增独立插件

适用于功能相对独立的工具，创建新的插件目录：

```bash
# 1. 创建插件目录
mkdir -p plugins/your-plugin/.claude-plugin
mkdir -p plugins/your-plugin/skills/your-skill

# 2. 创建 plugin.json
cat > plugins/your-plugin/.claude-plugin/plugin.json << 'EOF'
{
  "name": "your-plugin",
  "version": "1.0.0",
  "description": "插件描述",
  "author": {
    "name": "SurfRid3r"
  }
}
EOF

# 3. 创建技能文件 SKILL.md
# 编辑 plugins/your-plugin/skills/your-skill/SKILL.md
```

#### 同步更新配置文件

**README.md** - 在插件列表中添加：

```markdown
| [your-plugin](plugins/your-plugin/) | 分类 | 插件描述 |
```

**.claude-plugin/marketplace.json** - 在 plugins 数组中添加：

```json
{
  "name": "your-plugin",
  "description": "插件描述",
  "version": "1.0.0",
  "author": { "name": "SurfRid3r" },
  "source": "./plugins/your-plugin",
  "category": "分类",
  "strict": false
}
```

### 方式二：在现有插件中新增技能

适用于相关功能，在现有插件下添加新技能：

```bash
# 在现有插件目录下创建新技能
mkdir -p plugins/existing-plugin/skills/new-skill

# 创建 SKILL.md
# 编辑 plugins/existing-plugin/skills/new-skill/SKILL.md
```

### Git 提交流程

```bash
# 创建新分支
git checkout -b feat/your-plugin-or-skill

# 添加变更
git add plugins/your-plugin/
git add README.md
git add .claude-plugin/marketplace.json

# 提交
git commit -m "feat: add your-plugin/skill"

# 推送并创建 PR
git push origin feat/your-plugin-or-skill
```

---

## 创建 Skills 的最佳实践

### 1. 简洁优先（Concise is Key）

上下文窗口是公共资源。Skills 与系统提示、对话历史、其他技能共享上下文。

**核心原则**：默认假设 Claude 已经很智能，只添加 Claude 不具备的信息。

- **避免冗余**：不要重复解释通用编程概念
- **优先示例**：用具体示例代替长篇解释
- **挑战每一段**："这个信息真的必要吗？"

### 2. 渐进式披露（Progressive Disclosure）

技能应构建为高效使用上下文：

| 层级 | 内容 | 时机 |
|------|------|------|
| **元数据** | name + description (~100 tokens) | 启动时加载 |
| **指令** | SKILL.md 正文 (< 5000 tokens) | 技能激活时加载 |
| **资源** | scripts/、references/、assets/ | 按需加载 |

**组织建议**：
- 保持主 `SKILL.md` 在 500 行以下
- 详细内容移至 `references/` 目录
- 复杂代码逻辑移至 `scripts/` 目录

### 3. 选择合适的自由度

根据任务性质选择指令的具体程度：

| 自由度 | 适用场景 | 实现方式 |
|------|----------|----------|
| **高** | 多种方法都有效、依赖上下文判断 | 文本指导 + 启发式规则 |
| **中** | 有推荐模式、允许变化 | 伪代码或带参数的脚本 |
| **低** | 操作脆弱、一致性关键 | 特定脚本、少量参数 |

### 4. 引用资源指南

**scripts/** - 可执行代码
- 何时使用：代码被重复编写或需要确定性可靠性
- 优势：节省 token、可执行、无需加载到上下文

**references/** - 参考文档
- 何时使用：需要 Claude 在工作过程中参考的文档
- 示例：数据库 schema、API 文档、使用说明
- 最佳实践：文件 > 10k 行时，在 SKILL.md 中包含 grep 搜索模式

**assets/** - 输出资源
- 何时使用：将用于 Claude 输出中的文件
- 示例：模板、图片、图标、样例代码
- 注意：这些文件不会被加载到上下文

### 5. description 写作原则

- **说明功能和使用场景**：让 Claude 知道何时激活此技能
- **包含关键词**：使用用户可能说的词汇
- **具体而非抽象**：避免模糊的描述
- **明确触发条件**：说明"何时使用此技能"

### 6. 内容组织模式

**模式 1: 高层指南 + 引用**
```markdown
# PDF 处理

## 快速开始
使用 pdfplumber 提取文本...

## 高级功能
- 表单填写: 见 [FORMS.md](references/FORMS.md)
- API 参考: 见 [REFERENCE.md](references/REFERENCE.md)
```

**模式 2: 领域特定组织**
```
bigquery-plugin/
└── skills/
    └── bigquery/
        ├── SKILL.md (概览和导航)
        └── references/
            ├── finance.md
            ├── sales.md
            └── product.md
```

### 7. 文件引用规范

- 使用从技能根目录开始的相对路径
- 保持引用距离 `SKILL.md` 只有一层
- 避免深层嵌套的引用链

---

## 验证

使用 skills-ref 参考库验证技能：

```bash
skills-ref validate ./plugins/your-plugin/skills/your-skill
```

检查项目：
- YAML frontmatter 格式
- 技能命名约定
- 目录结构
- 描述完整性

---

## 相关资源

- [Agent Skills 规范](https://agentskills.io/specification)
- [Anthropic Skills 仓库](https://github.com/anthropics/skills)
- [Claude Plugins Official](https://github.com/anthropics/claude-plugins-official)
