# IP 修改器 - 详细说明

## 用户意图理解指南

### 常见用户表达模式

#### 表达 1: "文件：X，到Y"
**示例**: "webshell.pcap：11.22.33.44，到22.33.44.55"

**理解**:
- X (11.22.33.44) 是修改后的源IP
- Y (22.33.44.55) 是修改后的目的IP
- 需要同时修改原始流的源IP和目的IP

**工作流程**:
1. 使用 `list` 命令找到原始IP
2. 生成两个 IP 映射
3. 执行 `modify` 命令，输出文件名自动添加后缀

### 命令映射速查表

| 用户说 | Claude 应执行 |
|-------|-------------|
| "11.22.33.44，到22.33.44.55" | 1. list 查原始IP<br>2. modify 同时改源和目的 |
| "只修改源IP" | 只提供一个映射 |
| "只修改目的IP" | 只提供一个映射 |
| "源和目的都改" | 提供两个映射 |

---

## 功能概述

修改 PCAP 文件中用户指定的流的 IP 地址，保持双向流完整性，自动同步 HTTP Host 头。

## 使用方式

```bash
python scripts/pcap_tools.py modify <input> <output> <mapping> [...]
```

## 参数说明

- `input`: 输入 PCAP 文件路径
- `output`: 输出 PCAP 文件路径
- `mapping`: IP 映射，格式为 `old_ip:new_ip`，可以指定多个映射

## 工作原理

### 1. IP 层修改

扫描所有数据包，匹配源 IP 或目的 IP：

```
if pkt.src == old_ip:
    pkt.src = new_ip
if pkt.dst == old_ip:
    pkt.dst = new_ip
```

**双向流同步**：无论是源 IP 还是目的 IP，只要匹配就会替换，确保双向通信完整性。

### 2. HTTP Host 同步

扫描 TCP payload 中的 HTTP 请求头：

```
Host: old_ip  →  Host: new_ip
```

### 3. 校验和重算

删除以下字段，Scapy 写入时自动重新计算：

- IP 层: `len`, `chksum`
- TCP 层: `chksum`

## 使用示例

### 场景 1: 单流修改

```bash
# 先列出流，找到要修改的 IP
python scripts/pcap_tools.py list input.pcap
# 输出:
# 192.168.1.10 -> 192.168.1.20

# 执行修改
python scripts/pcap_tools.py modify input.pcap output.pcap 192.168.1.10:10.0.0.5

# 验证结果
python scripts/pcap_tools.py list output.pcap
# 输出:
# 10.0.0.5 -> 192.168.1.20
```

### 场景 2: 双向流修改

```bash
# 将双向流的 IP 都替换
python scripts/pcap_tools.py modify input.pcap output.pcap \
    192.168.1.10:10.0.0.5 \
    192.168.1.20:10.0.0.6
```

### 场景 3: 重放流量到测试环境

```bash
# 生产环境 IP: 192.168.1.x
# 测试环境 IP: 10.0.0.x

python scripts/pcap_tools.py modify prod.pcap test.pcap \
    192.168.1.10:10.0.0.5 \
    192.168.1.20:10.0.0.6
```

## 处理细节

### 双向流完整性

假设原始流量：
```
192.168.1.10 -> 192.168.1.20 : SYN
192.168.1.20 -> 192.168.1.10 : SYN-ACK
192.168.1.10 -> 192.168.1.20 : ACK
```

执行 `192.168.1.10:10.0.0.5` 后：
```
10.0.0.5 -> 192.168.1.20 : SYN
192.168.1.20 -> 10.0.0.5 : SYN-ACK
10.0.0.5 -> 192.168.1.20 : ACK
```

### HTTP Host 同步

原始 HTTP 请求：
```
GET /download/file.exe HTTP/1.1
Host: 192.168.1.20
```

执行 `192.168.1.20:10.0.0.6` 后：
```
GET /download/file.exe HTTP/1.1
Host: 10.0.0.6
```

### 加密流量处理

对于 HTTPS/SSH 等加密流量：
- ✅ IP 地址正常替换
- ✅ 校验和正常重算
- ❌ 无法修改加密内容中的 IP（因为加密）

**注意**：加密流量修改 IP 后，证书验证会失败，需要在目标环境中忽略证书验证。

## 限制

| 限制项 | 说明 |
|-------|------|
| IPv6 | 仅支持 IPv4 |
| 加密内容 | 无法修改 HTTPS/SSH 加密 payload 中的 IP |
| TCP 序列号 | 不修改序列号，可能影响 TCP 状态机 |
| 应用层协议 | 仅同步 HTTP Host 头，其他协议需手动处理 |

## 输出示例

```
# 修改完成

- **修改数据包数**: `245`
- **HTTP Host 头同步**: `3`
- **输出文件**: `output.pcap`
```

## 常见用途

1. **流量重放**：将生产环境流量重放到测试环境
2. **隐私保护**：脱敏真实 IP 地址
3. **目标迁移**：将流量指向新的目标服务器
4. **渗透测试**：修改攻击流量的目标 IP
