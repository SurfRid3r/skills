# PCAP 工具使用指南

## 统一命令行接口

```bash
python scripts/pcap_tools.py <command> [options]
```

## 命令详解

### list - 列出所有 IP 流

列出 PCAP 文件中的所有 IP 流及统计信息，按字节数排序。

```bash
python scripts/pcap_tools.py list <pcap_file> [--top N]
```

**示例**：
```bash
# 列出前 20 个流
python scripts/pcap_tools.py list input.pcap

# 列出前 10 个流
python scripts/pcap_tools.py list input.pcap --top 10
```

**输出**：
```
# IP 流列表 (Top 20)

| 源 IP | 目的 IP | 字节数 | 数据包 | 端口 |
|-------|---------|--------|--------|------|
| 192.168.1.10 | 192.168.1.20 | 12345 | 500 | 49152->80 |
| 10.0.0.5 | 172.16.0.100 | 9876 | 300 | 54321->22 |
```

**用途**：
- 快速了解 PCAP 文件中的流量概况
- 识别字节数最多的流（通常是核心流量）
- 查看每个流的协议类型

### filter - 按条件过滤流

按端口、IP 地址过滤 IP 流。

```bash
python scripts/pcap_tools.py filter <pcap> [--port N] [--src IP] [--dst IP]
```

**示例**：
```bash
# 查找 HTTP 流量 (端口 80)
python scripts/pcap_tools.py filter input.pcap --port 80

# 查找特定 IP 的流量
python scripts/pcap_tools.py filter input.pcap --src 192.168.1.10

# 查找特定流
python scripts/pcap_tools.py filter input.pcap --src 192.168.1.10 --dst 192.168.1.20
```

**用途**：
- 定位特定协议的流量
- 检查某个 IP 参与的所有连接
- 缩小分析范围

### extract - 提取 payload 内容

提取指定 IP 流的数据包 payload 内容。

```bash
python scripts/pcap_tools.py extract <pcap> <src_ip> <dst_ip> [--dst-port <n>] [--max <n>]
```

**示例**：
```bash
# 提取流的 payload（默认 50 个包）
python scripts/pcap_tools.py extract input.pcap 192.168.1.10 192.168.1.20

# 提取特定端口
python scripts/pcap_tools.py extract input.pcap 192.168.1.10 192.168.1.20 --dst-port 80

# 提取更多包
python scripts/pcap_tools.py extract input.pcap 192.168.1.10 192.168.1.20 --max 100
```

**输出**：
```
# 找到 2 个 TCP 流

## 流 1: `192.168.1.10:49152` → `192.168.1.20:80`

### 数据包 1

- **SEQ**: `1000`
- **ACK**: `2000`

**Payload**:

```
GET /download/payload.exe HTTP/1.1
Host: 192.168.1.20
```

### 数据包 2

- **SEQ**: `2000`
- **ACK**: `1200`

**Payload**:

```
HTTP/1.1 200 OK
Content-Type: application/octet-stream
```
```

**用途**：
- 查看攻击命令
- 确认流量内容与攻击场景匹配
- 识别下载的文件名、URL 等

### modify - 修改 IP 地址

修改 PCAP 文件中的 IP 地址，保持双向流完整性。

```bash
python scripts/pcap_tools.py modify <input> <output> <mapping> [...]
```

**示例**：
```bash
# 单流映射
python scripts/pcap_tools.py modify input.pcap output.pcap 192.168.1.10:10.0.0.5

# 多流映射
python scripts/pcap_tools.py modify input.pcap output.pcap \
    192.168.1.10:10.0.0.5 \
    192.168.1.20:10.0.0.6
```

**输出**：
```
# 修改完成

- **修改数据包数**: `245`
- **HTTP Host 头同步**: `3`
- **输出文件**: `output.pcap`
```

**用途**：
- 重放流量到不同目标
- 测试环境流量迁移
- 隐私保护（IP 地址脱敏）

## 典型分析流程

### 场景 1: 文件名有明确攻击描述

**PCAP 文件**: `certutil-download.pcap`

1. **推断攻击类型**: 文件名包含 "certutil"，判断为文件下载攻击
2. **列出所有流**:
   ```bash
   python scripts/pcap_tools.py list certutil-download.pcap
   ```
3. **查找 HTTP 流量**:
   ```bash
   python scripts/pcap_tools.py filter certutil-download.pcap --port 80
   ```
4. **提取 payload 验证**:
   ```bash
   python scripts/pcap_tools.py extract certutil-download.pcap <src> <dst>
   ```
5. **确认**: 看到 `GET /malware.exe` 请求，确认这是核心流量

### 场景 2: 文件名无明确描述

**PCAP 文件**: `traffic.pcap`

1. **列出所有流**:
   ```bash
   python scripts/pcap_tools.py list traffic.pcap
   ```
2. **分析流量特征**:
   - 字节数最多的流是核心流量
   - 有应用层协议（HTTP/SMB）的流优先
3. **提取 payload 判断**:
   ```bash
   python scripts/pcap_tools.py extract traffic.pcap <src> <dst>
   ```
4. **确认**: 看到 PowerShell 命令、恶意 URL 等攻击特征

### 场景 3: IP 修改工作流

1. **列出所有流，找到要修改的 IP**:
   ```bash
   python scripts/pcap_tools.py list input.pcap
   ```
2. **执行 IP 修改**:
   ```bash
   python scripts/pcap_tools.py modify input.pcap output.pcap 192.168.1.10:10.0.0.5
   ```
3. **验证修改结果**:
   ```bash
   python scripts/pcap_tools.py list output.pcap
   ```

## 协议识别

Agent 根据端口和 payload 判断协议类型，工具只提供端口信息和原始数据。

### 常见端口对照

| 协议 | 端口 | 识别方式 |
|------|------|---------|
| HTTP | 80, 8080 | 端口 + Payload 中 `GET`, `POST`, `HTTP/1.` |
| HTTPS | 443 | 端口（加密，无法分析 payload） |
| SSH | 22 | 端口（加密，无法分析 payload） |
| RDP | 3389 | 端口（加密，无法分析 payload） |
| SMB | 445 | 端口 + Payload 中 `SMB` 标识 |
| DNS | 53 | 端口 |
| MySQL | 3306 | 端口 + 协议握手包 |
| Redis | 6379 | 端口 + 命令（`PING`, `GET`） |
| PostgreSQL | 5432 | 端口 |

### 协议判断流程

```
1. 查看端口 → 推测协议类型
2. 提取 payload → 查看协议特征
3. 综合判断 → 确认协议和流量方向
```

### 加密流量分析

对于 HTTPS/SSH 等加密流量：
- 通过端口号识别协议类型
- 通过字节数判断主流量
- 通过流量方向判断角色（client → server）
