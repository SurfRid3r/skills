#!/usr/bin/env python3
"""list 命令实现 - 列出所有 TCP/UDP 流

TCP: 双向聚合（一行一流），通过 SYN 包识别连接发起方
UDP: 单向显示
"""

from collections import defaultdict

from scapy.all import rdpcap, IP, TCP, UDP


def cmd_list(pcap_file: str, top_n: int = 20, quiet: bool = False) -> None:
    """列出所有 TCP/UDP 流

    Args:
        pcap_file: PCAP 文件路径
        top_n: 显示前 N 个流（默认 20）
        quiet: 静默模式，减少输出
    """
    packets = rdpcap(pcap_file)

    # TCP 流聚合（双向）和 UDP 流（单向）
    tcp_flows = {}
    udp_flows = defaultdict(lambda: {"bytes": 0, "packets": 0})

    for pkt in packets:
        if not pkt.haslayer(IP):
            continue

        src, dst = pkt[IP].src, pkt[IP].dst

        if pkt.haslayer(TCP):
            _process_tcp_packet(pkt, src, dst, tcp_flows)
        elif pkt.haslayer(UDP):
            _process_udp_packet(pkt, src, dst, udp_flows)

    # 合并并排序
    all_flows = _merge_and_sort_flows(tcp_flows, udp_flows)

    # 输出
    _print_flows(all_flows, top_n, quiet)


def _process_tcp_packet(pkt, src: str, dst: str, tcp_flows: dict) -> None:
    """处理 TCP 数据包"""
    sport, dport = pkt[TCP].sport, pkt[TCP].dport
    endpoint1 = (src, sport)
    endpoint2 = (dst, dport)
    flow_key = tuple(sorted([endpoint1, endpoint2]))

    if flow_key not in tcp_flows:
        tcp_flows[flow_key] = {
            "bytes_1to2": 0,
            "packets_1to2": 0,
            "bytes_2to1": 0,
            "packets_2to1": 0,
            "initiator": None,
        }

    # 通过 SYN 包识别连接发起方（只记录第一个 SYN）
    if tcp_flows[flow_key]["initiator"] is None and pkt[TCP].flags.S:
        tcp_flows[flow_key]["initiator"] = endpoint1

    # 统计双向字节数
    if endpoint1 == flow_key[0]:
        tcp_flows[flow_key]["bytes_1to2"] += len(pkt)
        tcp_flows[flow_key]["packets_1to2"] += 1
    else:
        tcp_flows[flow_key]["bytes_2to1"] += len(pkt)
        tcp_flows[flow_key]["packets_2to1"] += 1


def _process_udp_packet(pkt, src: str, dst: str, udp_flows: dict) -> None:
    """处理 UDP 数据包"""
    key = (src, dst, pkt[UDP].sport, pkt[UDP].dport)
    udp_flows[key]["bytes"] += len(pkt)
    udp_flows[key]["packets"] += 1


def _merge_and_sort_flows(tcp_flows: dict, udp_flows: dict) -> list:
    """合并并排序流"""
    all_flows = []

    for flow_key, stats in tcp_flows.items():
        total_bytes = stats["bytes_1to2"] + stats["bytes_2to1"]
        all_flows.append(("tcp", flow_key, stats, total_bytes))

    for key, stats in udp_flows.items():
        all_flows.append(("udp", key, stats, stats["bytes"]))

    all_flows.sort(key=lambda x: x[3], reverse=True)
    return all_flows


def _print_flows(all_flows: list, top_n: int, quiet: bool = False) -> None:
    """打印流列表"""
    if not quiet:
        print(f"\n# TCP/UDP 流列表 (Top {top_n})\n")
    print("| 类型 | 流 | IP 地址 | 字节数 | 端口 |")
    print("|------|----|---------|--------|------|")

    for idx, (proto, flow_key, stats, _) in enumerate(all_flows[:top_n], 1):
        if proto == "tcp":
            ip_str, bytes_str, port = _format_tcp_flow(flow_key, stats)
        else:
            ip_str, bytes_str, port = _format_udp_flow(flow_key, stats)

        print(f"| {proto.upper()} | {idx} | {ip_str} | {bytes_str} | {port} |")


def _format_tcp_flow(flow_key: tuple, stats: dict) -> tuple:
    """格式化 TCP 流输出"""
    initiator = stats["initiator"] or flow_key[0]
    is_initiator_first = initiator == flow_key[0]

    if is_initiator_first:
        req_ip, req_port = flow_key[0]
        resp_ip = flow_key[1][0]
        req_bytes = stats["bytes_1to2"]
        resp_bytes = stats["bytes_2to1"]
    else:
        req_ip, req_port = flow_key[1]
        resp_ip = flow_key[0][0]
        req_bytes = stats["bytes_2to1"]
        resp_bytes = stats["bytes_1to2"]

    ip_str = f"{req_ip} -> {resp_ip}"
    bytes_str = f"{req_bytes}->{resp_bytes}"
    return ip_str, bytes_str, req_port


def _format_udp_flow(flow_key: tuple, stats: dict) -> tuple:
    """格式化 UDP 流输出"""
    src, dst, sport, _ = flow_key
    ip_str = f"{src} -> {dst}"
    bytes_str = str(stats["bytes"])
    return ip_str, bytes_str, sport
