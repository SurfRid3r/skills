---
name: pcap-tools
description: "PCAP 网络数据包分析与修改工具。用于：(1) 分析攻击流量、提取关键 IP 流；(2) 修改 IP 地址、端口、HTTP Host/Header/Body；(3) 合并多个 PCAP 文件；(4) 从 JSON 重建 PCAP 流量。当用户处理 .pcap 文件、分析网络攻击流量、修改流量包内容。"
---

# PCAP 工具集

PCAP 网络包文件分析处理工具集，包含 IP 提取、IP 修改、PCAP 合并等核心功能。

## 快速参考

### 通用工具

```bash
python scripts/pcap_tools.py [-q] <command> [options]
```

| 命令 | 说明 |
|------|------|
| `list <pcap> [--top N]` | 列出所有 IP 流及统计信息 |
| `filter <pcap> --port <n>` | 按端口/IP 过滤流 |
| `extract <pcap> <src> <dst> [options]` | 提取流的 payload |
| `modify <pcap> <out> [mappings...]` | 修改 IP、端口、HTTP 内容 |
| `build <input> [options]` | 将 JSON 数据转换为 PCAP |

**全局参数**: `-q, --quiet` 静默模式，减少输出

### PCAP 合并

```bash
python scripts/pcap_merge.py <pcap1> <pcap2> [pcap3...] [-o output.pcap]
```

## 安装依赖

```bash
pip install scapy
```

***

## 工具选择建议：tshark vs 本工具

**如果用户已安装 tshark（Wireshark 命令行工具），以下场景建议优先使用 tshark：**

| 场景 | 推荐工具 |
|------|----------|
| 协议解析（HTTP/DNS/TLS/SMB 等） | **tshark** - 协议解码更准确完整 |
| 流量统计汇总（协议分布、会话统计） | **tshark** - 内置强大的统计功能 |
| 复杂过滤表达式 | **tshark** - BPF/display filter 更灵活 |
| 快速查看数据包详情 | **tshark** - 输出格式丰富（JSON/文本/PSML） |

**本工具更适合的场景：**

| 场景 | 原因 |
|------|------|
| 修改 PCAP 内容（IP/端口/HTTP Body） | tshark 不支持内容修改 |
| 从 JSON 重建 PCAP | 本工具特有功能 |
| 合并多个 PCAP 文件 | tshark 无此功能 |
| 提取特定流的 payload | 本工具输出更直观 |
| 无 tshark 环境 | 本工具仅需 Python + scapy |

**优先级策略**：分析类任务优先尝试 tshark，修改/构建类任务使用本工具。

***

## IP 提取分析工作流

从 PCAP 文件中提取**攻击场景的关键流 IP**。

### 分析流程

1. **推断攻击类型** - 根据文件名关键词（如 `*shell*`、`*smb*`、`*c2*`），**仅作为参考**
2. **列出候选流** - `list` 命令查看流量概况
3. **分析流量特征** - 端口、字节数、协议
4. **提取 Payload** - `extract` 命令验证攻击特征

### 攻击场景推断

> **注意**：下面仅仅是极少数攻击场景的示例，实际情况可能更复杂，需要结合流量特征综合分析。

| 文件名特征 | 攻击类型 | 典型协议 |
|-----------|---------|---------|
| `*shell*` | 反向 Shell | TCP/自定义端口 |
| `*ms17-010*`, `*eternalblue*` | 漏洞利用 | SMB |
| `*certutil*`, `*wget*` | 文件下载 | HTTP |
| `*smb*`, `*psexec*` | 横向移动 | SMB/DCE-RPC |
| `*c2*`, `*beacon*` | C2 通信 | TCP/自定义 |

详见 [攻击场景知识库](references/extraction/scenarios.md)

### extract 命令

```bash
# 基本用法
python scripts/pcap_tools.py extract file.pcap 192.168.1.10 192.168.1.20

# 指定端口
python scripts/pcap_tools.py extract file.pcap 192.168.1.10 192.168.1.20 --dst-port 80

# 十六进制输出（二进制数据）
python scripts/pcap_tools.py extract file.pcap 192.168.1.10 192.168.1.20 --hex

# 完整输出（不截断）
python scripts/pcap_tools.py extract file.pcap 192.168.1.10 192.168.1.20 --full
```

| 参数 | 说明 |
|------|------|
| `--dst-port N` | 目的端口过滤 |
| `--max N` | 最大显示数据包数（默认 50） |
| `--hex` | 十六进制输出 |
| `--full` | 显示完整内容 |

### 排除背景流量

- 广播: `255.255.255.255`
- 多播: `224.x.x.x` - `239.x.x.x`
- mDNS: `224.0.0.251:5353`
- NetBIOS: 端口 137-139

详见 [攻击场景知识库](references/extraction/scenarios.md) | [提取分析指南](references/extraction/guide.md)

***

## IP 和端口修改工作流

修改 PCAP 文件中的 IP 地址和端口，保持双向流完整性。

### 用户表达识别

| 用户表达 | 命令示例 |
|---------|----------|
| "文件：X，到Y" | `modify input output old_src:X old_dst:Y` |
| "把端口8080改成80" | `modify input output --port 8080:80` |
| "同时修改IP和端口" | `modify input output old:new --port old_port:new_port` |

### modify 命令

```bash
# 修改 IP
python scripts/pcap_tools.py modify input.pcap output.pcap 192.168.1.10:10.0.0.1

# 修改端口
python scripts/pcap_tools.py modify input.pcap output.pcap --port 8080:80

# 同时修改 IP 和端口
python scripts/pcap_tools.py modify input.pcap output.pcap \
    192.168.1.10:10.0.0.1 \
    --port 8080:80

# 修改域名 Host
python scripts/pcap_tools.py modify input.pcap output.pcap \
    --host old.api.com:new.api.com

# HTTP Header 替换
python scripts/pcap_tools.py modify input.pcap output.pcap \
    --header "User-Agent:Mozilla/5.0:CustomAgent/1.0"

# HTTP Body 替换
python scripts/pcap_tools.py modify input.pcap output.pcap \
    --body '"status":"error"':'"status":"success"'

# 原始字节替换（十六进制）
python scripts/pcap_tools.py modify input.pcap output.pcap \
    --raw 48656c6c6f:576f726c64
```

### 参数说明

| 参数 | 格式 | 说明 |
|------|------|------|
| `ip_mapping` | `old:new` | IP 映射（可多次使用） |
| `--port` | `OLD:NEW` | 端口映射（可多次使用） |
| `--host` | `OLD:NEW` | HTTP Host 映射（域名） |
| `--header` | `Name:Old:New` | HTTP Header 替换 |
| `--body` | `Old:New` | HTTP Body 替换 |
| `--raw` | `HexOld:HexNew` | 原始字节替换 |

### 输出文件命名

格式：`<基础名>_源IP_目的IP_YYYYMMDD.pcap`

```bash
python scripts/pcap_tools.py modify webshell.pcap \
    webshell_11.22.33.44_22.33.44.55_20250829.pcap \
    192.168.1.10:11.22.33.44 \
    192.168.1.20:22.33.44.55
```

### HTTP Host 修改规则

| Host 格式 | 修改行为 |
|-----------|----------|
| `192.168.1.1` | IP 修改时自动同步 |
| `api.example.com` | 仅 `--host` 指定时修改 |

### 内容替换限制

- **Content-Length**: 不会自动更新，需确保 Body 长度不变
- **压缩内容**: gzip/deflate 无法替换
- **HTTPS/TLS**: 加密内容无法替换

详见 [修改工作流详解](references/modifier/workflows.md)

***

## PCAP 合并工作流

```bash
# 合并多个文件
python scripts/pcap_merge.py file1.pcap file2.pcap -o merged.pcap

# 禁用时间戳调整
python scripts/pcap_merge.py file1.pcap file2.pcap --no-adjust-ts
```

默认自动调整时间戳保持连续性。使用 `--no-adjust-ts` 保持原始时间戳。

***

## JSON 转 PCAP 工作流

将 JSON 格式的 HTTP 数据转换为 PCAP 文件，支持批量流量生成。

### 命令示例

```bash
# 基本转换
python scripts/pcap_build.py traffic.json

# 指定输出路径
python scripts/pcap_build.py traffic.json -o output.pcap
```

**命令行极简**：只需指定输入 JSON 和可选的输出路径，所有配置都在 JSON 中完成。

### JSON 输入格式

```json
{
  "options": {
    "keep_alive": false,
    "interval": 0.01,
    "interval_randomness": 0.5,
    "mtu": 1500,
    "flow_gap": 0.5
  },
  "traffic_flows": [
    {
      "network_params": {
        "src_ip": "10.0.0.1",
        "dst_ip": "192.168.1.100",
        "src_port": 54321,
        "dst_port": 80
      },
      "packets": [
        {
          "request_data_base64": "R0VUIC8gSFRUUC8xLjENCg==",
          "response_data_base64": "SFRUUC8xLjEgMjAwIE9LDQo="
        }
      ]
    }
  ]
}
```

### options 字段（全部可选）

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `keep_alive` | `false` | 长连接模式（true 时复用同一 TCP 连接） |
| `interval` | `0.01` | 包时间间隔（秒） |
| `interval_randomness` | `0.5` | 间隔随机度（0-1） |
| `mtu` | `1500` | MTU 大小（字节） |
| `flow_gap` | `0.5` | TCP 连接之间的时间间隔（秒） |

### network_params 字段

| 字段 | 必需 | 说明 |
|------|------|------|
| `src_ip` | 是 | 源 IP（或 `WAN`/`LAN` 随机生成） |
| `dst_ip` | 是 | 目的 IP（或 `WAN`/`LAN` 随机生成） |
| `src_port` | 否 | 源端口（默认随机，或 `CLIENT`） |
| `dst_port` | 否 | 目的端口（默认 80） |
| `src_mac` | 否 | 源 MAC（默认随机，或 `RANDOM`） |
| `dst_mac` | 否 | 目的 MAC（默认随机，或 `RANDOM`） |

### 连接模式说明

- **短连接模式**（`keep_alive: false`，默认）：每个 HTTP 请求完成后执行四次挥手，下一个请求重新建立连接
- **长连接模式**（`keep_alive: true`）：`packets` 数组中的所有 HTTP 请求/响应对复用同一个 TCP 连接

### 批量流量示例

```json
{
  "options": {
    "keep_alive": true,
    "flow_gap": 1.0
  },
  "traffic_flows": [
    {
      "network_params": {"src_ip": "10.0.0.1", "dst_ip": "192.168.1.100"},
      "packets": [
        {"request_data_base64": "...", "response_data_base64": "..."},
        {"request_data_base64": "...", "response_data_base64": "..."}
      ]
    },
    {
      "network_params": {"src_ip": "10.0.0.2", "dst_ip": "192.168.1.100"},
      "packets": [
        {"request_data_base64": "...", "response_data_base64": "..."}
      ]
    }
  ]
}
```

***

## 详细资源

### IP 提取分析
- [攻击场景知识库](references/extraction/scenarios.md)
- [提取分析指南](references/extraction/guide.md)

### IP 修改
- [修改指南](references/modification/guide.md)
