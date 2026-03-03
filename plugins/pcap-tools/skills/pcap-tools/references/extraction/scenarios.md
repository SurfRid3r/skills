# PCAP IP 提取 - 场景验证指南

## 目录

- [攻击场景分类](#攻击场景分类)
- [各攻击类型详解](#各攻击类型详解)

---

## 攻击场景分类

根据 PCAP 文件名或上下文，可以推断出以下攻击类型：

| 攻击类型 | 流量方向 | 典型文件名特征 |
|---------|---------|---------------|
| 反向 Shell | victim → attacker | `*shell*`, `*reverse*` |
| 正向 Shell | attacker → victim | `*bind*shell*` |
| 文件下载 | client → server | `*certutil*`, `*wget*`, `*curl*`, `*download*` |
| 文件上传 | client → server | `*upload*`, `*put*`, `*post*` |
| C2 通信 | victim → C2 server | `*c2*`, `*cobalt*`, `*beacon*`, `*payload*` |
| 横向移动 | source → target | `*psexec*`, `*wmi*`, `*smb*`, `*winrm*` |
| 漏洞利用 | attacker → victim | `*cve-*`, `*ms17-010*`, `*eternalblue*`, `*weblogic*`, `*struts2*` |
| 凭据窃取 | victim → attacker | `*mimikatz*`, `*credential*`, `*hash*` |

---

## 各攻击类型详解

### 1. 反向 Shell (Reverse Shell)

**特征**: 受害者主动连接攻击者

**流量方向**: victim → attacker

**文件名特征**:

- `*shell*.pcap`
- `*reverse*.pcap`

**验证要点**:

- TCP 连接由受害者发起
- 攻击者端口通常是高位端口 (4444, 8888 等)
- 后续命令执行流量方向: attacker → victim

---

### 2. 文件下载 (File Download)

**特征**: 客户端从服务器下载文件

**流量方向**: client → server (请求)

**文件名特征**:

- `*certutil*.pcap`
- `*wget*.pcap`
- `*curl*.pcap`
- `*download*.pcap`

**验证要点**:

- HTTP GET 请求: client → server
- HTTP 响应: server → client
- 下载文件通常是恶意负载

---

### 3. C2 通信 (Command & Control)

**特征**: 受害者与 C2 服务器保持持续通信

**流量方向**: victim → C2 server (心跳/ Beacon)

**文件名特征**:

- `*c2*.pcap`
- `*cobalt*.pcap`
- `*beacon*.pcap`
- `*payload*.pcap`

**验证要点**:

- 周期性心跳流量
- 受害者主动发起连接
- 可能使用加密通道
- Heartbeat 间隔通常固定 (如 60s)

---

### 4. 横向移动 (Lateral Movement)

**特征**: 攻击者从已攻陷主机移动到内网其他主机

**流量方向**: source → target

**文件名特征**:

- `*psexec*.pcap`
- `*wmi*.pcap`
- `*smb*.pcap`
- `*winrm*.pcap`
- `*lateral*.pcap`

**验证要点**:

- SMB/DCE-RPC 流量
- 源 IP 是已攻陷主机
- 目的 IP 是内网其他主机
- 通常包含服务创建/命令执行

---

### 5. 漏洞利用 (Exploitation)

**特征**: 利用特定漏洞执行代码

**流量方向**: attacker → victim

**文件名特征**:

- `*cve-*.pcap`
- `*ms17-010*.pcap`
- `*eternalblue*.pcap`
- `*weblogic*.pcap`
- `*struts2*.pcap`
- `*exploit*.pcap`

**验证要点**:

- SMB RCE (MS17-010/EternalBlue): attacker → victim (SMB 端口 445)
- Web 漏洞: attacker → web server
- 可能包含特定 exploit payload

---

## 快速匹配表

| 文件名关键词 | 攻击类型 | 源IP | 目的IP |
|-------------|---------|------|--------|
| shell, reverse | 反向 Shell | 受害者 | 攻击者 |
| certutil, wget, curl | 文件下载 | 客户端 | 服务器 |
| c2, cobalt, beacon | C2 通信 | 受害者 | C2 服务器 |
| psexec, wmi, smb | 横向移动 | 源主机 | 目标主机 |
| ms17-010, eternalblue, cve | 漏洞利用 | 攻击者 | 受害者 |
