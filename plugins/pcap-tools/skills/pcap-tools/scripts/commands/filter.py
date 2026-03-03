#!/usr/bin/env python3
"""filter 命令实现 - 按条件过滤流"""

from scapy.all import rdpcap, IP, TCP, UDP


def cmd_filter(
    pcap_file: str, port: int = None, src_ip: str = None, dst_ip: str = None
) -> None:
    """按条件过滤流

    Args:
        pcap_file: PCAP 文件路径
        port: 按端口过滤
        src_ip: 按源 IP 过滤
        dst_ip: 按目的 IP 过滤
    """
    packets = rdpcap(pcap_file)
    flows = set()

    if port:
        _filter_by_port(packets, port, flows)
    else:
        _filter_by_ip(packets, src_ip, dst_ip, flows)


def _filter_by_port(packets, port: int, flows: set) -> None:
    """按端口过滤"""
    for pkt in packets:
        if not pkt.haslayer(IP):
            continue

        if pkt.haslayer(TCP) and (pkt[TCP].sport == port or pkt[TCP].dport == port):
            flows.add((pkt[IP].src, pkt[IP].dst, pkt[TCP].sport, pkt[TCP].dport))
        elif pkt.haslayer(UDP) and (pkt[UDP].sport == port or pkt[UDP].dport == port):
            flows.add((pkt[IP].src, pkt[IP].dst, pkt[UDP].sport, pkt[UDP].dport))

    print(f"\n# 端口 {port} 的流\n")
    print("| 源地址 | 目的地址 |")
    print("|--------|----------|")
    for src, dst, sport, dport in flows:
        print(f"| {src}:{sport} | {dst}:{dport} |")


def _filter_by_ip(packets, src_ip: str, dst_ip: str, flows: set) -> None:
    """按 IP 过滤"""
    for pkt in packets:
        if not pkt.haslayer(IP):
            continue

        src, dst = pkt[IP].src, pkt[IP].dst

        if (not src_ip or src == src_ip) and (not dst_ip or dst == dst_ip):
            flows.add((src, dst))

    print("\n# IP 流\n")
    print("| 源 IP | 目的 IP |")
    print("|-------|---------|")
    for src, dst in flows:
        print(f"| {src} | {dst} |")
