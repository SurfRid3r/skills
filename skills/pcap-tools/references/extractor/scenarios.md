# PCAP IP 提取 - 场景验证指南

## 目录

- [攻击场景分类](#攻击场景分类)
- [场景验证流程](#场景验证流程)
- [各攻击类型详解](#各攻击类型详解)

---

## 攻击场景分类

根据 PCAP 文件名或上下文，可以推断出以下攻击类型：

| 攻击类型 | 流量方向 | 典型文件名特征 |
|---------|---------|---------------|
| 反向 Shell | victim → attacker | `*shell*`, `*ms17-010*`, `*eternalblue*` |
| 正向 Shell | attacker → victim | `*bind*shell*`, `*reverse*` |
| 文件下载 | client → server | `*certutil*`, `*wget*`, `*curl*`, `*download*` |
| 文件上传 | client → server | `*upload*`, `*put*`, `*post*` |
| C2 通信 | victim → C2 server | `*c2*`, `*cobalt*`, `*beacon*`, `*payload*` |
| 横向移动 | source → target | `*psexec*`, `*wmi*`, `*smb*`, `*winrm*` |
| 漏洞利用 | 依漏洞类型 | `*cve-*`, `*weblogic*`, `*struts2*` |
| 凭据窃取 | victim → attacker | `*mimikatz*`, `*credential*`, `*hash*` |

---

## 场景验证流程

```
┌─────────────────┐
│  PCAP 文件名    │
└────────┬────────┘
         ↓
┌─────────────────┐
│ 推断攻击类型    │
└────────┬────────┘
         ↓
┌─────────────────┐
│ 提取候选 IP 流  │
└────────┬────────┘
         ↓
┌─────────────────┐
│ 验证流量方向    │
│ 与场景是否匹配  │
└────────┬────────┘
         ↓
    匹配? ──Yes→ 输出结果
         │
         No
         ↓
┌─────────────────┐
│ 深度包检测      │
│ 分析内容确认    │
└─────────────────┘
```

---

## 各攻击类型详解

### 1. 反向 Shell (Reverse Shell)

**特征**: 受害者主动连接攻击者

**流量方向**: victim → attacker

**文件名特征**:

- `*shell*.pcap`
- `*ms17-010*.pcap`
- `*eternalblue*.pcap`
- `*reverse*.pcap`

**验证要点**:

- TCP 连接由受害者发起
- 攻击者端口通常是高位端口 (4444, 8888 等)
- 后续命令执行流量方向: attacker → victim

**tshark 验证命令**:

```bash
# 查看 TCP 三次握手方向
tshark -r <pcap> -Y "tcp.flags.syn==1 and tcp.flags.ack==0" \
  -T fields -e ip.src -e ip.dst

# 查看后续命令流量
tshark -r <pcap> -Y "tcp.payload" -V | grep -A5 "data"
```

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

**tshark 验证命令**:

```bash
# 查看 HTTP 请求
tshark -r <pcap> -Y "http.request" -T fields \
  -e ip.src -e ip.dst -e http.request.uri

# 查看下载的文件名
tshark -r <pcap> -Y "http.file_data" -V
```

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

**tshark 验证命令**:

```bash
# 查看周期性连接
tshark -r <pcap> -Y "tcp.flags.syn==1" -T fields \
  -e frame.time_epoch -e ip.src -e ip.dst

# 计算心跳间隔
tshark -r <pcap> -Y "tcp.flags.syn==1" -T fields \
  -e frame.time | awk '{print $2}' | uniq -c
```

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

**tshark 验证命令**:

```bash
# 查看 SMB 命令
tshark -r <pcap> -Y "smb.cmd" -T fields \
  -e ip.src -e ip.dst -e smb.cmd

# 查看 DCE-RPC 操作
tshark -r <pcap> -Y "dcerpc" -T fields \
  -e ip.src -e ip.dst -e dcerpc.opnum
```

---

### 5. 漏洞利用 (Exploitation)

**特征**: 利用特定漏洞执行代码

**流量方向**: 依漏洞类型而定

**文件名特征**:

- `*cve-*.pcap`
- `*weblogic*.pcap`
- `*struts2*.pcap`
- `*exploit*.pcap`

**验证要点**:

- Web 漏洞: attacker → web server
- RCE 漏洞: attacker → victim
- 可能包含特定 payload

**常见 CVE 流量方向**:

| CVE | 类型 | 方向 |
|-----|------|------|
| CVE-2017-0144 (MS17-010) | SMB RCE | attacker → victim |
| CVE-2019-0708 | RDP RCE | attacker → victim |
| CVE-2017-5638 | Struts2 RCE | attacker → web server |
| CVE-2017-10271 | WebLogic RCE | attacker → web server |

---

## 场景匹配决策树

```
提取到候选 IP 流
       ↓
   文件名有关键词?
       ↓
    Yes │ No
       ↓         ↓
  根据关键词    分析流量内容
  推断场景      推断场景
       ↓         ↓
       └─────┬───┘
             ↓
    流量方向与场景匹配?
             ↓
        Yes │ No
           ↓    ↓
       输出结果  深度分析
```

---

## 快速匹配表

| 文件名关键词 | 攻击类型 | 源IP | 目的IP |
|-------------|---------|------|--------|
| shell, ms17, eternalblue | 反向 Shell | 受害者 | 攻击者 |
| certutil, wget, curl | 文件下载 | 客户端 | 服务器 |
| c2, cobalt, beacon | C2 通信 | 受害者 | C2 服务器 |
| psexec, wmi, smb | 横向移动 | 源主机 | 目标主机 |
| cve, weblogic, struts | 漏洞利用 | 攻击者 | 受害者 |

---

## 验证检查清单

完成 IP 提取后，进行以下验证：

- [ ] 流量方向与攻击场景匹配
- [ ] 端口号符合协议特征
- [ ] 数据包内容支持推断
- [ ] 排除了背景流量 (广播/多播)
- [ ] 流大小符合主流量特征
- [ ] 文件名关键词与场景一致
