# IP 提取分析指南

## 命令详解

### list - 列出所有 IP 流

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
# TCP/UDP 流列表 (Top 20)

| 类型 | 流 | IP 地址 | 字节数 | 端口 |
|------|----|---------|--------|------|
| TCP | 1 | 192.168.1.10 -> 192.168.1.20 | 783->1023 | 37374 |
```

### filter - 按条件过滤流

```bash
python scripts/pcap_tools.py filter <pcap> [--port N] [--src IP] [--dst IP]
```

**示例**：
```bash
# 查找 HTTP 流量 (端口 80)
python scripts/pcap_tools.py filter input.pcap --port 80

# 查找特定 IP 的流量
python scripts/pcap_tools.py filter input.pcap --src 192.168.1.10
```

### extract - 提取 payload 内容

```bash
python scripts/pcap_tools.py extract <pcap> <src_ip> <dst_ip> [--dst-port N] [--max N] [--hex] [--full]
```

| 参数 | 说明 |
|------|------|
| `--dst-port N` | 目的端口过滤 |
| `--max N` | 最大显示数据包数（默认 50） |
| `--hex` | 十六进制输出 |
| `--full` | 显示完整内容 |

**示例**：
```bash
# 默认文本输出
python scripts/pcap_tools.py extract file.pcap 192.168.1.111 192.168.1.21

# 十六进制输出（二进制数据）
python scripts/pcap_tools.py extract file.pcap 192.168.1.111 192.168.1.21 --hex

# 完整输出（不截断）
python scripts/pcap_tools.py extract file.pcap 192.168.1.111 192.168.1.21 --full
```

***

## 排除背景流量

- 广播: `255.255.255.255`
- 多播: `224.x.x.x` - `239.x.x.x`
- mDNS: `224.0.0.251:5353`
- NetBIOS: 端口 137-139

详见 [攻击场景知识库](scenarios.md)
