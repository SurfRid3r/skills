#!/usr/bin/env python3
"""extract 命令实现 - 提取 TCP/UDP 流的 payload"""

from collections import defaultdict

from scapy.all import rdpcap, IP, TCP, UDP, Raw

from utils import print_payload_packet


def cmd_extract(
    pcap_file: str,
    src_ip: str,
    dst_ip: str,
    dport: int = None,
    max_lines: int = 50,
    use_hex: bool = False,
    full_output: bool = False,
    quiet: bool = False,
) -> None:
    """提取 TCP/UDP 流的 payload

    Args:
        pcap_file: PCAP 文件路径
        src_ip: 源 IP 地址
        dst_ip: 目的 IP 地址
        dport: 目的端口（可选，用于精确定位流）
        max_lines: 最大显示数据包数
        use_hex: 使用十六进制输出
        full_output: 显示完整内容
        quiet: 静默模式，减少输出
    """
    packets = rdpcap(pcap_file)
    tcp_streams = defaultdict(list)
    udp_packets = []

    for pkt in packets:
        if not pkt.haslayer(IP):
            continue

        # 检查 IP 方向（双向）
        src, dst = pkt[IP].src, pkt[IP].dst
        if not ((src == src_ip and dst == dst_ip) or (src == dst_ip and dst == src_ip)):
            continue

        # 处理 TCP 数据包
        if pkt.haslayer(TCP):
            if _tcp_port_matches(pkt, dport) and pkt.haslayer(Raw):
                stream_key = (src, pkt[TCP].sport, dst, pkt[TCP].dport)
                tcp_streams[stream_key].append(pkt)

        # 处理 UDP 数据包
        elif pkt.haslayer(UDP):
            if _udp_port_matches(pkt, dport) and pkt.haslayer(Raw):
                udp_packets.append(pkt)

    # 输出结果
    _print_results(
        tcp_streams, udp_packets, src_ip, dst_ip, dport, max_lines, use_hex, full_output, quiet
    )


def _tcp_port_matches(pkt, dport: int) -> bool:
    """检查 TCP 端口是否匹配"""
    if dport is None:
        return True
    return pkt[TCP].sport == dport or pkt[TCP].dport == dport


def _udp_port_matches(pkt, dport: int) -> bool:
    """检查 UDP 端口是否匹配"""
    if dport is None:
        return True
    return pkt[UDP].sport == dport or pkt[UDP].dport == dport


def _port_matches(pkt, layer, dport: int) -> bool:
    """通用端口匹配检查

    Args:
        pkt: 数据包
        layer: 协议层 (TCP 或 UDP)
        dport: 要匹配的端口号

    Returns:
        是否匹配
    """
    if dport is None:
        return True
    return layer.sport == dport or layer.dport == dport


def _print_results(
    tcp_streams: dict,
    udp_packets: list,
    src_ip: str,
    dst_ip: str,
    dport: int,
    max_lines: int,
    use_hex: bool,
    full_output: bool,
    quiet: bool = False,
) -> None:
    """打印提取结果"""
    # 输出 TCP 流
    if tcp_streams:
        if not quiet:
            print(f"\n# TCP 流 ({len(tcp_streams)} 个)\n")
        for idx, (stream_key, pkts) in enumerate(sorted(tcp_streams.items()), 1):
            _print_tcp_stream(idx, stream_key, pkts, max_lines, use_hex, full_output, quiet)

    # 输出 UDP 数据包
    if udp_packets:
        if not quiet:
            print(f"\n# UDP 数据包 ({len(udp_packets)} 个)\n")
        for pkt_idx, pkt in enumerate(udp_packets[:max_lines], 1):
            _print_udp_packet(pkt_idx, pkt, use_hex, full_output, quiet)

        if len(udp_packets) > max_lines and not quiet:
            print(f"\n> ... 还有 {len(udp_packets) - max_lines} 个数据包未显示\n")

    # 都没有找到
    if not tcp_streams and not udp_packets:
        _print_not_found(src_ip, dst_ip, dport, quiet)


def _print_tcp_stream(
    idx: int, stream_key: tuple, pkts: list, max_lines: int, use_hex: bool, full_output: bool, quiet: bool = False
) -> None:
    """打印单个 TCP 流"""
    src_ip_str, src_port, dst_ip_str, dst_port = stream_key
    if not quiet:
        print(f"## 流 {idx}: `{src_ip_str}:{src_port}` -> `{dst_ip_str}:{dst_port}`\n")

    for pkt_idx, pkt in enumerate(pkts[:max_lines], 1):
        if not quiet:
            print(f"### 数据包 {pkt_idx}\n")
        print_payload_packet(pkt, use_hex, full_output)

    if len(pkts) > max_lines and not quiet:
        print(f"\n> ... 还有 {len(pkts) - max_lines} 个数据包未显示\n")


def _print_udp_packet(pkt_idx: int, pkt, use_hex: bool, full_output: bool, quiet: bool = False) -> None:
    """打印单个 UDP 数据包"""
    src_ip_str, dst_ip_str = pkt[IP].src, pkt[IP].dst
    src_port, dst_port = pkt[UDP].sport, pkt[UDP].dport
    if not quiet:
        print(f"## 数据包 {pkt_idx}: `{src_ip_str}:{src_port}` -> `{dst_ip_str}:{dst_port}`\n")
    print_payload_packet(pkt, use_hex, full_output)


def _print_not_found(src_ip: str, dst_ip: str, dport: int, quiet: bool = False) -> None:
    """打印未找到结果"""
    if not quiet:
        print("## 未找到 payload\n")
        port_str = f" (端口 {dport})" if dport else ""
        print(f"**流**: {src_ip} <-> {dst_ip}{port_str}")
        print("\n> 提示: 使用 `filter` 命令查看实际端口")
