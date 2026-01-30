# IP 修改 - 使用示例

## 示例 1: 用户说"11.22.33.44，到22.33.44.55"

**场景**: 用户提供了 PCAP 文件，说"webshell.pcap：11.22.33.44，到22.33.44.55"

### 步骤 1: 理解用户意图
用户想要:
- 修改源IP为 11.22.33.44
- 修改目的IP为 22.33.44.55

### 步骤 2: 列出原始流
```bash
python scripts/pcap_tools.py list webshell.pcap
```

### 步骤 3: 执行修改（包含自动命名）
```bash
python scripts/pcap_tools.py modify webshell.pcap \
    webshell_11.22.33.44_22.33.44.55_20250829.pcap \
    192.168.1.10:11.22.33.44 \
    192.168.1.20:22.33.44.55
```

### 步骤 4: 验证结果
```bash
python scripts/pcap_tools.py list webshell_11.22.33.44_22.33.44.55_20250829.pcap
```

---

## 示例 2: 只修改源IP

**场景**: "把这个文件的源IP改成10.0.0.5"

### 步骤 1: 列出原始流
```bash
python scripts/pcap_tools.py list input.pcap
# 输出: 192.168.1.10 -> 192.168.1.20
```

### 步骤 2: 执行修改
```bash
python scripts/pcap_tools.py modify input.pcap \
    input_10.0.0.5_192.168.1.20_20250829.pcap \
    192.168.1.10:10.0.0.5
```

---

## 示例 3: 双向流替换（重放到测试环境）

**场景**: 将生产流量 (192.168.1.x) 重放到测试环境 (10.0.0.x)

```bash
# 原始流
python scripts/pcap_tools.py list prod.pcap
# 输出: 192.168.1.10 -> 192.168.1.20

# 执行双向替换
python scripts/pcap_tools.py modify prod.pcap \
    prod_10.0.0.5_10.0.0.6_20250829.pcap \
    192.168.1.10:10.0.0.5 \
    192.168.1.20:10.0.0.6
```
