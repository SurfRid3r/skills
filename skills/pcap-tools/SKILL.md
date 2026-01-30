---
name: pcap-tools
description: PCAP 文件处理工具。当用户需要: (1) 修改 PCAP 中的 IP 地址（支持同时修改源IP和目的IP、保持双向流完整性）、(2) 列出 PCAP 中的 IP 流、(3) 提取数据包 payload、(4) 按端口/IP 过滤流量时使用。关键词：修改IP、替换地址、IP到IP、源IP、目的IP、X到Y
---

# PCAP 工具集

PCAP 网络包文件分析处理工具集，包含 IP 提取和 IP 修改两大核心功能。

## 快速参考

### 通用工具

```bash
python scripts/pcap_tools.py <command> [options]
```

| 命令 | 说明 |
|------|------|
| `list <pcap> [--top N]` | 列出所有 IP 流及统计信息（默认显示前 20 个） |
| `filter <pcap> --port <n>` | 按端口/IP 过滤流 |
| `extract <pcap> <src> <dst> [--dst-port N] [--max N] [--hex] [--full]` | 提取流的 payload（按 TCP 五元组聚合，支持双向流） |
| `modify <pcap> <out> <old:new>` | 修改流中的 IP 地址 |

## 安装依赖

```bash
pip install scapy
```

---

## IP 提取分析工作流

从 PCAP 文件中提取**攻击场景的关键流 IP**，需要综合分析判断。

### 核心分析流程

```
┌─────────────────┐
│  PCAP 文件名    │
└────────┬────────┘
         ↓
┌─────────────────┐
│ 推断攻击类型    │ ← 根据文件名关键词
└────────┬────────┘
         ↓
┌─────────────────┐
│ 列出候选 IP 流  │ ← list 命令
└────────┬────────┘
         ↓
┌─────────────────┐
│ 分析流量特征    │ ← 协议、端口、字节数、方向
└────────┬────────┘
         ↓
┌─────────────────┐
│ 提取 Payload    │ ← extract 命令
└────────┬────────┘
         ↓
┌─────────────────┐
│ 验证场景匹配    │ ← 确认核心攻击流量
└────────┬────────┘
         ↓
    输出: 源IP,目的IP
```

### 攻击场景推断

根据 PCAP 文件名关键词推断攻击类型：

| 文件名特征 | 攻击类型 | 预期流量方向 | 典型协议 |
|-----------|---------|-------------|---------|
| `*shell*`, `*ms17-010*` | 反向 Shell | victim → attacker | TCP/自定义端口 |
| `*certutil*`, `*wget*`, `*curl*` | 文件下载 | client → server | HTTP |
| `*smb*`, `*psexec*`, `*wmi*` | 横向移动 | source → target | SMB/DCE-RPC |
| `*ssh*`, `*rdp*` | 远程访问 | client → server | SSH/RDP |
| `*c2*`, `*cobalt*`, `*beacon*` | C2 通信 | victim → C2 | TCP/自定义 |
| `*cve-*`, `*exploit*` | 漏洞利用 | 依漏洞类型 | 依漏洞 |

详见 [references/extractor/scenarios.md](references/extractor/scenarios.md)

### 流量分析要点

**1. 识别主流量**：
- 字节数最多的流通常是核心流量
- 通过端口信息判断协议类型（由 Agent 分析）
- 提取 payload 查看攻击特征

**2. 排除背景流量**：
- 广播: `255.255.255.255`
- 多播: `224.x.x.x` - `239.x.x.x`
- mDNS: `224.0.0.251:5353`
- NetBIOS: 端口 137-139

**3. 验证攻击特征**：
- 提取 payload 查看攻击命令
- 确认流量方向与攻击场景匹配
- 检查是否有异常行为（如非常规端口）

### 输出格式控制

extract 命令支持输出格式控制：

| 参数 | 说明 |
|---|---|
| 无参数 | 默认 UTF-8 文本输出，截断为 500 字节 |
| `--hex` | 十六进制输出（适合二进制数据如 WebSocket 帧） |
| `--full` | 显示完整内容，不截断 |

示例：
```bash
# 默认文本输出
python scripts/pcap_tools.py extract file.pcap 192.168.1.111 192.168.1.21

# 十六进制输出
python scripts/pcap_tools.py extract file.pcap 192.168.1.111 192.168.1.21 --hex

# 完整输出
python scripts/pcap_tools.py extract file.pcap 192.168.1.111 192.168.1.21 --full

# 组合使用
python scripts/pcap_tools.py extract file.pcap 192.168.1.111 192.168.1.21 --hex --full
```

### 输出格式

```
源IP,目的IP,pcap名称
```

---

## IP 修改工作流

修改 PCAP 文件中用户指定的流的 IP 地址，保持双向流完整性。

### 用户表达识别

当用户使用以下表达方式时，应识别为需要同时修改源IP和目的IP：

| 用户表达 | 实际意图 | 命令示例 |
|---------|---------|----------|
| "文件：X，到Y" | 修改流的源IP为X，目的IP为Y | `modify input output old_src:X old_dst:Y` |
| "把源IP改成X，目的IP改成Y" | 同时修改源和目的IP | `modify input output old_src:X old_dst:Y` |
| "从11.22.33.44到22.33.44.55" | 替换流的两端IP | `modify input output old_src:11.22.33.44 old_dst:22.33.44.55` |
| "webshell流量：X到Y" | 修改webshell流的IP | `modify input output old_src:X old_dst:Y` |

**重要规则**:
- 当用户提到两个不同的IP并使用"到"、"改为"等连接词时，通常需要同时修改源IP和目的IP
- 先使用 `list` 命令查看原始IP，然后根据用户指定的目标IP生成映射

### 输出文件命名规范

**AI应自动添加后缀**：当执行 `modify` 命令时，输出文件名应添加后缀 `源IP_目的IP_时间`。

**格式**：`<基础名>_源IP_目的IP_时间.pcap`

**示例**：
```bash
# 原始文件：webshell.pcap
# 修改为：源IP 11.22.33.44，目的IP 22.33.44.55
# 输出文件应命名为：webshell_11.22.33.44_22.33.44.55_20250829.pcap

python scripts/pcap_tools.py modify webshell.pcap \
    webshell_11.22.33.44_22.33.44.55_20250829.pcap \
    192.168.1.10:11.22.33.44 \
    192.168.1.20:22.33.44.55
```

**时间格式**：使用 `YYYYMMDD` 格式（如 `20250829`）

### 工作流程

```
┌─────────────────┐
│  列出所有流     │ ← list 命令，找到要修改的 IP
└────────┬────────┘
         ↓
┌─────────────────┐
│  用户指定映射   │ ← old_ip:new_ip
└────────┬────────┘
         ↓
┌─────────────────┐
│  执行 IP 替换   │ ← modify 命令
│  - 双向流同步   │
│  - HTTP Host 同步 │
│  - 校验和重算   │
└────────┬────────┘
         ↓
    输出: 修改后的 PCAP
```

### 处理细节

- **双向流同步**: 同时修改匹配 src/dst 的数据包
- **HTTP Host 同步**: 自动替换 TCP payload 中的 `Host: old_ip` 为 `Host: new_ip`
- **校验和重算**: 自动重新计算 IP 和 TCP 校验和

---

## 详细资源

### IP 提取分析
- **攻击场景知识**: [references/extractor/scenarios.md](references/extractor/scenarios.md)
- **工具使用指南**: [references/extractor/workflows.md](references/extractor/workflows.md)
- **使用示例**: [references/extractor/examples.md](references/extractor/examples.md)
- **常见问题**: [references/extractor/faq.md](references/extractor/faq.md)

### IP 修改
- **详细说明**: [references/modifier/workflows.md](references/modifier/workflows.md)
