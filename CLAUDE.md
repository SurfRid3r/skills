# Claude Skills 创建指南

本指南基于 [Anthropic Agent Skills 开放标准](https://agentskills.io/specification)，帮助您创建符合规范的 Skills。

## 参考资料

- **[Agent Skills 规范](https://agentskills.io/specification)** - 官方规范文档
- **[Anthropic Skills 仓库](https://github.com/anthropics/skills)** - 官方示例集合
- **[技能创建器](https://github.com/anthropics/skills/tree/main/skills/skill-creator)** - 交互式技能创建指南

---

## 目录结构

一个技能目录至少包含 `SKILL.md` 文件：

```
skill-name/
├── SKILL.md          # 必需：技能定义文件
├── scripts/          # 可选：可执行代码
├── references/       # 可选：参考文档
├── assets/           # 可选：静态资源
└── LICENSE.txt       # 可选：许可证文件
```

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

## 新增 Skill 工作流程

### 1. 创建 Skill

按照官方规范创建技能目录和内容。

### 2. 同步更新配置文件

每次新增 skill 后，需要同步更新以下文件：

#### README.md
在 Skills 表格中添加新技能条目：

```markdown
| Skill | Description |
|-------|-------------|
| [your-skill](skills/your-skill/) | 技能描述 |
```

#### .claude-plugin/marketplace.json
在 plugins 数组中添加新技能配置：

```json
{
  "name": "your-skill-name",
  "description": "技能描述",
  "source": "./",
  "strict": false,
  "skills": ["./skills/your-skill-name/"]
}
```

### 3. Git 提交流程

```bash
# 创建新分支（分支名与技能名保持一致）
git checkout -b your-skill-name

# 添加变更
git add skills/your-skill-name/
git add README.md
git add .claude-plugin/marketplace.json

# 提交
git commit -m "feat(your-skill): add new skill"

# 推送并创建 PR
git push origin your-skill-name
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
- 示例：数据库 schema、API 文档、公司政策
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
bigquery-skill/
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
skills-ref validate ./my-skill
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
- [技能创建器](https://github.com/anthropics/skills/tree/main/skills/skill-creator)