# IP 修改指南

## 用户意图理解

### 常见用户表达模式

| 用户说 | Claude 应执行 |
|-------|-------------|
| "11.22.33.44，到22.33.44.55" | 1. list 查原始IP<br>2. modify 同时改源和目的 |
| "只修改源IP" | 只提供一个映射 |
| "只修改目的IP" | 只提供一个映射 |
| "源和目的都改" | 提供两个映射 |
| "把端口8080改成80" | `--port 8080:80` |
| "同时修改IP和端口" | `old:new --port old_port:new_port` |

### 输出文件命名规范

**AI应自动添加后缀**： `<基础名>_源IP_目的IP_时间.pcap`

**示例**：
```bash
# 原始文件： webshell.pcap
# 修改为：源IP 11.22.33.44，目的IP 22.33.44.55
# 输出文件: webshell_11.22.33.44_22.33.44.55_20250829.pcap
```

## 命令示例

### 场景 1: 单流修改

```bash
# 先列出流，找到要修改的 IP
python scripts/pcap_tools.py list input.pcap

# 执行修改
python scripts/pcap_tools.py modify input.pcap output.pcap 192.168.1.10:10.0.0.5
```

### 场景 2: 双向流修改

```bash
python scripts/pcap_tools.py modify input.pcap output.pcap \
    192.168.1.10:10.0.0.5 \
    192.168.1.20:10.0.0.6
```

### 场景 3: 纯端口修改

```bash
python scripts/pcap_tools.py modify input.pcap output.pcap --port 8080:80
```

### 场景 4: HTTP 内容修改

```bash
# 修改域名 Host
python scripts/pcap_tools.py modify input.pcap output.pcap \
    --host old.api.com:new.api.com

# HTTP Header 替换
python scripts/pcap_tools.py modify input.pcap output.pcap \
    --header "User-Agent:Mozilla/5.0:CustomAgent/1.0"

# HTTP Body 替换
python scripts/pcap_tools.py modify input.pcap output.pcap \
    --body '"status":"error"':'"status":"success"'

# 组合使用
python scripts/pcap_tools.py modify input.pcap output.pcap \
    192.168.1.10:10.0.0.5 \
    --port 8080:80 \
    --header "User-Agent:Mozilla/5.0:CustomAgent/1.0"
```

## 内容替换限制

| 限制 | 说明 |
|------|------|
| Content-Length | 不会自动更新，需确保 Body 长度不变 |
| 压缩内容 | gzip/deflate 压缩的 Body 无法直接替换 |
| HTTPS/TLS | 加密内容无法替换（仅支持明文) |
