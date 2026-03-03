#!/usr/bin/env python3
"""modify 命令实现 - 修改 PCAP 文件中的 IP 地址和端口

支持:
- IP 地址修改（双向流同步）
- 端口修改（双向流同步）
- HTTP Host 头同步修改（IP/域名/端口）
- HTTP Header 替换
- HTTP Body 字符串替换
- 原始 payload 字节替换
- TCP 序列号偏移跟踪
"""

import logging
import re
from scapy.all import rdpcap, wrpcap, IP, TCP, UDP, Raw

# 配置日志
logger = logging.getLogger(__name__)

# 连接四元组 -> 磯积序列号偏移量
_conn_deltas = {}


def cmd_modify(
    pcap_file: str,
    output_file: str,
    ip_mappings: dict,
    port_mappings: dict,
    host_mappings: dict,
    header_mappings: list = None,
    body_mappings: list = None,
    raw_mappings: list = None,
    quiet: bool = False,
) -> None:
    """修改 PCAP 文件中的 IP 地址和端口

    Args:
        pcap_file: 输入 PCAP 文件路径
        output_file: 输出 PCAP 文件路径
        ip_mappings: IP 映射字典 {old_ip: new_ip}
        port_mappings: 端口映射字典 {old_port: new_port}
        host_mappings: HTTP Host 映射字典 {old_host: new_host}
        header_mappings: HTTP Header 替换列表 [(name, old, new), ...]
        body_mappings: HTTP Body 替换列表 [(old, new), ...]
        raw_mappings: 原始字节替换列表 [(old_bytes, new_bytes), ...]
        quiet: 静默模式，减少输出
    """
    global _conn_deltas
    _conn_deltas = {}  # 重置偏移量

    # 确保参数不为 None
    header_mappings = header_mappings or []
    body_mappings = body_mappings or []
    raw_mappings = raw_mappings or []

    packets = rdpcap(pcap_file)
    modified_count = 0
    ip_modified_count = 0
    port_modified_count = 0
    http_host_count = 0
    http_header_count = 0
    http_body_count = 0
    raw_count = 0
    seq_adjusted_count = 0

    for pkt in packets:
        result = _modify_packet(pkt, ip_mappings, port_mappings, host_mappings,
                                 header_mappings, body_mappings, raw_mappings)
        if result["modified"]:
            modified_count += 1
            if result["ip_modified"]:
                ip_modified_count += 1
            if result["port_modified"]:
                port_modified_count += 1
            http_host_count += result["http_host_modified"]
            http_header_count += result["http_header_modified"]
            http_body_count += result["http_body_modified"]
            raw_count += result["raw_modified"]
            if result["seq_adjusted"]:
                seq_adjusted_count += 1
            _recalculate_checksums(pkt)

    wrpcap(output_file, packets)
    if not quiet:
        _print_summary(
            modified_count,
            ip_modified_count,
            port_modified_count,
            http_host_count,
            http_header_count,
            http_body_count,
            raw_count,
            seq_adjusted_count,
            output_file,
        )
    else:
        print(output_file)


def _get_conn_id(pkt) -> tuple:
    """获取 TCP 连接四元组"""
    if pkt.haslayer(IP) and pkt.haslayer(TCP):
        return (pkt[IP].src, pkt[TCP].sport, pkt[IP].dst, pkt[TCP].dport)
    return None


def _get_reverse_conn_id(conn_id: tuple) -> tuple:
    """获取反向流的连接 ID"""
    if conn_id:
        return (conn_id[2], conn_id[3], conn_id[0], conn_id[1])
    return None


def _apply_seq_offset(pkt) -> bool:
    """对 TCP 包应用已累积的序列号偏移

    Returns:
        是否应用了偏移
    """
    if not pkt.haslayer(TCP):
        return False

    conn_id = _get_conn_id(pkt)
    if not conn_id:
        return False

    adjusted = False

    # 正向流 SEQ 偏移
    forward_delta = _conn_deltas.get(conn_id, 0)
    if forward_delta != 0:
        pkt[TCP].seq += forward_delta
        adjusted = True

    # 反向流 ACK 偏移
    reverse_id = _get_reverse_conn_id(conn_id)
    reverse_delta = _conn_deltas.get(reverse_id, 0)
    if reverse_delta != 0:
        pkt[TCP].ack += reverse_delta
        adjusted = True

    return adjusted


def _modify_packet(
    pkt, ip_mappings: dict, port_mappings: dict, host_mappings: dict,
    header_mappings: list, body_mappings: list, raw_mappings: list
) -> dict:
    """修改单个数据包

    Returns:
        包含修改状态的字典
    """
    result = {
        "modified": False,
        "ip_modified": False,
        "port_modified": False,
        "http_host_modified": 0,
        "http_header_modified": 0,
        "http_body_modified": 0,
        "raw_modified": 0,
        "seq_adjusted": False,
    }

    # 1. 先应用已有序列号偏移（必须在内容修改之前）
    result["seq_adjusted"] = _apply_seq_offset(pkt)

    # 2. IP 修改
    if pkt.haslayer(IP):
        if pkt[IP].src in ip_mappings:
            pkt[IP].src = ip_mappings[pkt[IP].src]
            result["modified"] = True
            result["ip_modified"] = True
        if pkt[IP].dst in ip_mappings:
            pkt[IP].dst = ip_mappings[pkt[IP].dst]
            result["modified"] = True
            result["ip_modified"] = True

    # 3. 端口修改（TCP）
    if pkt.haslayer(TCP) and port_mappings:
        if pkt[TCP].sport in port_mappings:
            pkt[TCP].sport = port_mappings[pkt[TCP].sport]
            result["modified"] = True
            result["port_modified"] = True
        if pkt[TCP].dport in port_mappings:
            pkt[TCP].dport = port_mappings[pkt[TCP].dport]
            result["modified"] = True
            result["port_modified"] = True

    # 4. 端口修改（UDP）
    if pkt.haslayer(UDP) and port_mappings:
        if pkt[UDP].sport in port_mappings:
            pkt[UDP].sport = port_mappings[pkt[UDP].sport]
            result["modified"] = True
            result["port_modified"] = True
        if pkt[UDP].dport in port_mappings:
            pkt[UDP].dport = port_mappings[pkt[UDP].dport]
            result["modified"] = True
            result["port_modified"] = True

    # 累积 payload 长度变化
    total_payload_delta = 0

    # 5. HTTP Host 头同步修改
    if pkt.haslayer(TCP) and pkt.haslayer(Raw):
        host_modified_count, payload_delta = _sync_http_host(
            pkt, ip_mappings, port_mappings, host_mappings
        )
        if host_modified_count > 0:
            result["http_host_modified"] = host_modified_count
            result["modified"] = True
            total_payload_delta += payload_delta

    # 6. HTTP Header 替换
    if pkt.haslayer(TCP) and pkt.haslayer(Raw) and header_mappings:
        header_modified_count, payload_delta = _replace_http_headers(pkt, header_mappings)
        if header_modified_count > 0:
            result["http_header_modified"] = header_modified_count
            result["modified"] = True
            total_payload_delta += payload_delta

    # 7. HTTP Body 替换
    if pkt.haslayer(TCP) and pkt.haslayer(Raw) and body_mappings:
        body_modified_count, payload_delta = _replace_http_body(pkt, body_mappings)
        if body_modified_count > 0:
            result["http_body_modified"] = body_modified_count
            result["modified"] = True
            total_payload_delta += payload_delta

    # 8. 原始 Payload 替换（支持 TCP 和 UDP）
    if raw_mappings:
        if pkt.haslayer(TCP) and pkt.haslayer(Raw):
            raw_modified_count, payload_delta = _replace_raw_payload(pkt, raw_mappings)
            if raw_modified_count > 0:
                result["raw_modified"] = raw_modified_count
                result["modified"] = True
                total_payload_delta += payload_delta
        elif pkt.haslayer(UDP) and pkt.haslayer(Raw):
            raw_modified_count, payload_delta = _replace_raw_payload(pkt, raw_mappings)
            if raw_modified_count > 0:
                result["raw_modified"] = raw_modified_count
                result["modified"] = True
                # UDP 不需要序列号调整

    # 更新该连接的序列号偏移量
    if total_payload_delta != 0:
        conn_id = _get_conn_id(pkt)
        if conn_id:
            _conn_deltas[conn_id] = _conn_deltas.get(conn_id, 0) + total_payload_delta

    return result


def _sync_http_host(
    pkt, ip_mappings: dict, port_mappings: dict, host_mappings: dict
) -> tuple:
    """同步修改 HTTP Host 头

    优先级：
    1. IP 映射 → 自动同步 Host 中的 IP[:port]
    2. 端口映射 → 自动同步 Host 中的 :port
    3. --host 参数 → 修改域名 Host

    Returns:
        (修改数量, payload 长度变化量)
    """
    count = 0
    total_delta = 0

    try:
        payload = pkt[Raw].load
        original_len = len(payload)

        # 1. IP[:port] 格式同步（自动）
        for old_ip, new_ip in ip_mappings.items():
            # 匹配 "Host: 192.168.1.1" 或 "Host: 192.168.1.1:8080"
            pattern = rf"(?i)(^Host:\s*){re.escape(old_ip)}(?::(\d+))?(\r\n)".encode()

            def replace_ip_host(m, new_ip=new_ip):
                prefix = m.group(1)
                port = m.group(2)
                suffix = m.group(3)
                if port and int(port) in port_mappings:
                    # IP 和端口都需要修改
                    new_port = port_mappings[int(port)]
                    return f"{prefix.decode()}:{new_ip}:{new_port}{suffix.decode()}".encode()
                elif port:
                    # 只修改 IP
                    return f"{prefix.decode()}{new_ip}:{port.decode()}{suffix.decode()}".encode()
                else:
                    # 只有 IP，无端口
                    return f"{prefix.decode()}{new_ip}{suffix.decode()}".encode()

            new_payload, n = re.subn(pattern, replace_ip_host, payload, flags=re.MULTILINE)
            if n > 0:
                count += n
                payload = new_payload

        # 2. 域名:port 格式 - 端口同步（自动）
        if port_mappings:
            for old_port, new_port in port_mappings.items():
                # 匹配 "Host: api.example.com:8080"（域名不含已处理的 IP）
                pattern = rf"(?i)(^Host:\s*[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9]):{old_port}(\r\n)".encode()
                replacement = f"\\g<1>:{new_port}\\g<2>".encode()
                new_payload, n = re.subn(pattern, replacement, payload, flags=re.MULTILINE)
                if n > 0:
                    count += n
                    payload = new_payload

        # 3. 域名格式 - 仅用户指定时修改
        if host_mappings:
            for old_host, new_host in host_mappings.items():
                # 匹配 "Host: api.example.com" 或 "Host: api.example.com:8080"
                pattern = rf"(?i)(^Host:\s*){re.escape(old_host)}(?::(\d+))?(\r\n)".encode()

                def replace_domain_host(m, new_host=new_host):
                    prefix = m.group(1)
                    port = m.group(2)
                    suffix = m.group(3)
                    if port and int(port) in port_mappings:
                        # 域名和端口都需要修改
                        new_port = port_mappings[int(port)]
                        return f"{prefix.decode()}{new_host}:{new_port}{suffix.decode()}".encode()
                    elif port:
                        # 只修改域名，保留端口
                        return f"{prefix.decode()}{new_host}:{port.decode()}{suffix.decode()}".encode()
                    else:
                        # 只有域名
                        return f"{prefix.decode()}{new_host}{suffix.decode()}".encode()

                new_payload, n = re.subn(pattern, replace_domain_host, payload, flags=re.MULTILINE)
                if n > 0:
                    count += n
                    payload = new_payload

        if count > 0:
            pkt[Raw].load = payload
            total_delta = len(payload) - original_len

    except Exception:
        pass

    return count, total_delta


def _is_http_payload(payload: bytes) -> bool:
    """检查 payload 是否为 HTTP 数据"""
    # 检查常见的 HTTP 方法或响应
    http_prefixes = (b"GET ", b"POST ", b"PUT ", b"DELETE ", b"HEAD ", b"OPTIONS ",
                     b"PATCH ", b"HTTP/1.", b"HTTP/2")
    return payload.startswith(http_prefixes)


def _replace_http_headers(pkt, header_mappings: list) -> tuple:
    """替换 HTTP Header

    Args:
        header_mappings: [(header_name, old_value, new_value), ...]

    Returns:
        (修改次数, payload 长度变化量)
    """
    count = 0
    total_delta = 0

    try:
        payload = pkt[Raw].load
        original_len = len(payload)

        # 仅处理 HTTP 流量
        if not _is_http_payload(payload):
            return 0, 0

        for header_name, old_value, new_value in header_mappings:
            # 正则模式：匹配 Header 行（Header: value\r\n）
            # 使用 re.escape 处理特殊字符
            pattern = rf"(?i)(^{re.escape(header_name)}:\s*){re.escape(old_value)}(\r\n)".encode()
            replacement = f"\\g<1>{new_value}\\g<2>".encode()
            new_payload, n = re.subn(pattern, replacement, payload, flags=re.MULTILINE)
            if n > 0:
                count += n
                payload = new_payload

        if count > 0:
            pkt[Raw].load = payload
            total_delta = len(payload) - original_len

    except Exception:
        pass

    return count, total_delta


def _replace_http_body(pkt, body_mappings: list) -> tuple:
    """替换 HTTP Body 中的字符串

    Args:
        body_mappings: [(old_str, new_str), ...]

    Returns:
        (修改次数, payload 长度变化量)
    """
    count = 0
    total_delta = 0

    try:
        payload = pkt[Raw].load
        original_len = len(payload)

        # 仅处理 HTTP 流量
        if not _is_http_payload(payload):
            return 0, 0

        # 分离 Header 和 Body（以 \r\n\r\n 为界）
        header_end = payload.find(b"\r\n\r\n")
        if header_end == -1:
            return 0, 0  # 没有 Body 分隔符

        headers = payload[:header_end + 4]
        body = payload[header_end + 4:]

        # 检查是否为压缩内容（不处理压缩内容）
        if re.search(rb"Content-Encoding:\s*(gzip|deflate|br)", headers, re.IGNORECASE):
            return 0, 0

        # 使用 str.replace 而非正则，避免特殊字符问题
        for old_str, new_str in body_mappings:
            old_bytes = old_str.encode("utf-8")
            new_bytes = new_str.encode("utf-8")
            if old_bytes in body:
                n = body.count(old_bytes)
                body = body.replace(old_bytes, new_bytes)
                count += n

        if count > 0:
            pkt[Raw].load = headers + body
            total_delta = len(pkt[Raw].load) - original_len

    except Exception:
        pass

    return count, total_delta


def _replace_raw_payload(pkt, raw_mappings: list) -> tuple:
    """替换原始 TCP/UDP payload 中的字节

    Args:
        raw_mappings: [(old_bytes, new_bytes), ...]

    Returns:
        (修改次数, payload 长度变化量)
    """
    count = 0
    total_delta = 0

    try:
        if not pkt.haslayer(Raw):
            return 0, 0

        payload = pkt[Raw].load
        original_len = len(payload)

        for old_bytes, new_bytes in raw_mappings:
            if old_bytes in payload:
                n = payload.count(old_bytes)
                payload = payload.replace(old_bytes, new_bytes)
                count += n

        if count > 0:
            pkt[Raw].load = payload
            total_delta = len(payload) - original_len

    except Exception:
        pass

    return count, total_delta


def _recalculate_checksums(pkt) -> None:
    """重新计算校验和"""
    if pkt.haslayer(IP):
        del pkt[IP].len, pkt[IP].chksum
    if pkt.haslayer(TCP):
        del pkt[TCP].chksum
    if pkt.haslayer(UDP):
        del pkt[UDP].chksum


def _print_summary(
    modified_count: int,
    ip_modified_count: int,
    port_modified_count: int,
    http_host_count: int,
    http_header_count: int,
    http_body_count: int,
    raw_count: int,
    seq_adjusted_count: int,
    output_file: str,
) -> None:
    """打印修改摘要"""
    print("\n# 修改完成\n")
    print(f"- **修改数据包数**: `{modified_count}`")
    if ip_modified_count > 0:
        print(f"- **IP 修改**: `{ip_modified_count}` 包")
    if port_modified_count > 0:
        print(f"- **端口修改**: `{port_modified_count}` 包")
    if http_host_count > 0:
        print(f"- **HTTP Host 头同步**: `{http_host_count}`")
    if http_header_count > 0:
        print(f"- **HTTP Header 替换**: `{http_header_count}`")
    if http_body_count > 0:
        print(f"- **HTTP Body 替换**: `{http_body_count}`")
    if raw_count > 0:
        print(f"- **原始 Payload 替换**: `{raw_count}`")
    if seq_adjusted_count > 0:
        print(f"- **TCP 序列号调整**: `{seq_adjusted_count}` 包")
    print(f"- **输出文件**: `{output_file}`\n")
