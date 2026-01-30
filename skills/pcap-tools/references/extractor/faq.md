# PCAP 工具 - 常见问题

## 目录

- [工具相关问题](#工具相关问题)
- [大文件处理](#大文件处理)
- [背景流量干扰](#背景流量干扰)
- [多个候选流难以确认](#多个候选流难以确认)
- [协议识别](#协议识别)

---

## 工具相关问题

### 问题: 找不到 scapy 模块

**症状**: `ModuleNotFoundError: No module named 'scapy'`

**解决方案**:

```bash
pip3 install scapy
```

---

## 大文件处理

### 问题: 处理大型 PCAP 文件时内存溢出

**症状**: `MemoryError` 或系统卡死

**原因**: 文件包含大量数据包，scapy 一次性加载到内存

**解决方案**:

```bash
# 使用 --top 参数限制处理的流数量
python scripts/pcap_tools.py list large.pcap --top 10

# 或者先过滤出特定流
python scripts/pcap_tools.py filter large.pcap --port 80
```

---

## 背景流量干扰

### 问题: 列出的流包含大量 mDNS/NetBIOS 流量

**症状**: 输出显示很多 224.0.0.251:5353 或 *.255:137-139 的流

**原因**: PCAP 包含局域网背景流量

**解决方案**: 使用 filter 命令过滤

```bash
# 只查看 HTTP 流量
python scripts/pcap_tools.py filter input.pcap --port 80

# 只查看特定 IP
python scripts/pcap_tools.py filter input.pcap --src 192.168.1.10
```

---

## 多个候选流难以确认

### 问题: 列出多个流，无法确定哪个是核心攻击流量

**症状**: `list` 命令输出多个字节数相近的流

**解决方案**:

```bash
# 步骤 1: 列出所有流，按字节数排序
python scripts/pcap_tools.py list input.pcap

# 步骤 2: 提取可疑流的 payload（可指定目的端口）
python scripts/pcap_tools.py extract input.pcap <src> <dst> --dst-port 80

# 步骤 3: 分析 payload 内容判断
```

**内容分析要点**:

| 流量类型 | 分析方法 | 关键特征 |
|---------|---------|---------|
| HTTP | 查看 URI、User-Agent | `/download`, `curl`, `certutil`, `wget` |
| SMB | 查看 payload 开头 | `SMB` 标识 |
| 加密流量 | 无法分析 | 通过端口和方向判断 |

---

## 协议识别

### 问题: 如何判断端口对应的协议？

**常见端口对照表**:

| 端口 | 协议 | 说明 |
|------|------|------|
| 21 | FTP | 文件传输 |
| 22 | SSH | 安全登录 |
| 23 | Telnet | 远程登录 |
| 25 | SMTP | 邮件发送 |
| 53 | DNS | 域名解析 |
| 80 | HTTP | Web |
| 110 | POP3 | 邮件接收 |
| 143 | IMAP | 邮件接收 |
| 443 | HTTPS | 加密 Web |
| 445 | SMB | 文件共享 |
| 3389 | RDP | 远程桌面 |
| 5432 | PostgreSQL | 数据库 |
| 3306 | MySQL | 数据库 |
| 6379 | Redis | 数据库 |
| 27017 | MongoDB | 数据库 |

### 问题: 端口号不是标准端口，如何判断？

**解决方案**:

1. **提取 payload 分析**:
   ```bash
   # 指定目的端口提取
   python scripts/pcap_tools.py extract input.pcap <src> <dst> --dst-port 80

   # 不指定目的端口（提取所有端口）
   python scripts/pcap_tools.py extract input.pcap <src> <dst>
   ```

2. **查看 payload 特征**:
   - HTTP: `GET`, `POST`, `HTTP/1.`
   - MySQL: 协议握手包
   - Redis: `PING`, `GET` 等命令
   - 自定义协议: 需要根据流量特征判断

### 问题: 加密流量如何分析？

**特点**:
- HTTPS (443): 加密 HTTP
- SSH (22): 加密登录
- RDP (3389): 加密远程桌面

**分析方法**:
1. 通过端口号识别协议
2. 通过流量方向判断角色（client → server）
3. 通过字节数判断主流量
4. 无法分析 payload 内容（加密）

---

## 输出格式

### 如何解读 list 命令的输出？

```
# IP 流列表 (Top 20)

| 源 IP | 目的 IP | 字节数 | 数据包 | 端口 |
|-------|---------|--------|--------|------|
| 192.168.1.10 | 192.168.1.20 | 12345 | 500 | 49152->80,8080 |
```

- **源 IP / 目的 IP**: 流的两端 IP
- **字节数**: 该流的总字节数（越大越可能是核心流量）
- **数据包**: 该流的数据包数量
- **端口**: 该流使用的端口（可能有多个）

端口格式: `源端口->目的端口`
- `49152->80`: 表示从临时端口 49152 到标准 HTTP 端口 80
- `80->49152`: 表示返回流量

### 如何确定哪个是源IP，哪个是目的IP？

根据攻击场景和流量方向：

| 场景 | 方向 | 源IP | 目的IP |
|------|------|------|--------|
| 反向 Shell | victim → attacker | 受害者 | 攻击者 |
| 文件下载 | client → server | 客户端 | 服务器 |
| C2 通信 | victim → C2 | 受害者 | C2 服务器 |
| 横向移动 | source → target | 源主机 | 目标主机 |

---
