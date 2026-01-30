#!/usr/bin/env python3
import argparse
import sys
from collections import defaultdict
from scapy.all import rdpcap, IP, TCP, UDP, Raw, wrpcap


def cmd_list(pcap_file, top_n=20):
    """列出所有 TCP/UDP 流

    TCP: 双向聚合（一行一流），通过 SYN 包识别连接发起方
    UDP: 单向显示
    """
    packets = rdpcap(pcap_file)

    # TCP 流聚合（双向）和 UDP 流（单向）
    tcp_flows = {}
    udp_flows = defaultdict(lambda: {'bytes': 0, 'packets': 0})

    for pkt in packets:
        if not pkt.haslayer(IP):
            continue

        src, dst = pkt[IP].src, pkt[IP].dst

        if pkt.haslayer(TCP):
            # TCP 流：双向聚合
            sport, dport = pkt[TCP].sport, pkt[TCP].dport
            endpoint1 = (src, sport)
            endpoint2 = (dst, dport)
            flow_key = tuple(sorted([endpoint1, endpoint2]))

            if flow_key not in tcp_flows:
                tcp_flows[flow_key] = {
                    'bytes_1to2': 0, 'packets_1to2': 0,
                    'bytes_2to1': 0, 'packets_2to1': 0,
                    'initiator': None,  # 连接发起方的 endpoint
                }

            # 通过 SYN 包识别连接发起方（只记录第一个 SYN）
            if tcp_flows[flow_key]['initiator'] is None and pkt[TCP].flags.S:
                tcp_flows[flow_key]['initiator'] = endpoint1

            # 统计双向字节数
            if endpoint1 == flow_key[0]:
                tcp_flows[flow_key]['bytes_1to2'] += len(pkt)
                tcp_flows[flow_key]['packets_1to2'] += 1
            else:
                tcp_flows[flow_key]['bytes_2to1'] += len(pkt)
                tcp_flows[flow_key]['packets_2to1'] += 1

        elif pkt.haslayer(UDP):
            # UDP 流：单向
            key = (src, dst, pkt[UDP].sport, pkt[UDP].dport)
            udp_flows[key]['bytes'] += len(pkt)
            udp_flows[key]['packets'] += 1

    # 合并并排序：TCP 按请求方向字节数，UDP 按字节数
    all_flows = []

    for flow_key, stats in tcp_flows.items():
        total_bytes = stats['bytes_1to2'] + stats['bytes_2to1']
        all_flows.append(('tcp', flow_key, stats, total_bytes))

    for key, stats in udp_flows.items():
        all_flows.append(('udp', key, stats, stats['bytes']))

    all_flows.sort(key=lambda x: x[3], reverse=True)

    # 输出
    print(f"\n# TCP/UDP 流列表 (Top {top_n})\n")
    print("| 类型 | 流 | IP 地址 | 字节数 | 端口 |")
    print("|------|----|---------|--------|------|")

    for idx, (proto, flow_key, stats, _) in enumerate(all_flows[:top_n], 1):
        if proto == 'tcp':
            # TCP: 通过 SYN 发起方确定请求→响应方向
            initiator = stats['initiator'] or flow_key[0]  # 无 SYN 时默认用 flow_key[0]
            is_initiator_first = initiator == flow_key[0]

            if is_initiator_first:
                req_ip, req_port = flow_key[0]
                resp_ip = flow_key[1][0]
                req_bytes = stats['bytes_1to2']
                resp_bytes = stats['bytes_2to1']
            else:
                req_ip, req_port = flow_key[1]
                resp_ip = flow_key[0][0]
                req_bytes = stats['bytes_2to1']
                resp_bytes = stats['bytes_1to2']

            ip_str = f"{req_ip} → {resp_ip}"
            bytes_str = f"{req_bytes}→{resp_bytes}"
        else:
            # UDP: 单向
            src, dst, sport, _ = flow_key
            ip_str = f"{src} → {dst}"
            bytes_str = str(stats['bytes'])

        print(f"| {proto.upper()} | {idx} | {ip_str} | {bytes_str} | {req_port if proto == 'tcp' else sport} |")


def cmd_filter(pcap_file, port=None, src_ip=None, dst_ip=None):
    """按条件过滤流"""
    packets = rdpcap(pcap_file)
    flows = set()

    if port:
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

    else:
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


def format_payload(payload, use_hex=False):
    """格式化 payload 为十六进制或 UTF-8 文本"""
    return payload.hex() if use_hex else payload.decode('utf-8', errors='replace')


def print_payload_packet(pkt, use_hex, full_output):
    """打印单个数据包的 payload"""
    print("**Payload**:")
    print("```")
    formatted = format_payload(pkt[Raw].load, use_hex)
    if not full_output and len(formatted) > 500:
        formatted = formatted[:500] + "...(截断)"
    print(formatted)
    print("```\n")


def cmd_extract(pcap_file, src_ip, dst_ip, dport=None, max_lines=50, use_hex=False, full_output=False):
    """提取 TCP/UDP 流的 payload"""
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

        # 检查端口匹配
        port_match = dport is None
        if pkt.haslayer(TCP):
            if not port_match and pkt[TCP].sport != dport and pkt[TCP].dport != dport:
                continue
            if pkt.haslayer(Raw):
                stream_key = (src, pkt[TCP].sport, dst, pkt[TCP].dport)
                tcp_streams[stream_key].append(pkt)
        elif pkt.haslayer(UDP):
            if not port_match and pkt[UDP].sport != dport and pkt[UDP].dport != dport:
                continue
            if pkt.haslayer(Raw):
                udp_packets.append(pkt)

    # 输出 TCP 流
    if tcp_streams:
        print(f"\n# TCP 流 ({len(tcp_streams)} 个)\n")
        for idx, (stream_key, pkts) in enumerate(sorted(tcp_streams.items()), 1):
            src_ip_str, src_port, dst_ip_str, dst_port = stream_key
            print(f"## 流 {idx}: `{src_ip_str}:{src_port}` → `{dst_ip_str}:{dst_port}`\n")

            for pkt_idx, pkt in enumerate(pkts[:max_lines], 1):
                print(f"### 数据包 {pkt_idx}\n")
                print_payload_packet(pkt, use_hex, full_output)

            if len(pkts) > max_lines:
                print(f"\n> ... 还有 {len(pkts) - max_lines} 个数据包未显示\n")

    # 输出 UDP 数据包
    if udp_packets:
        print(f"\n# UDP 数据包 ({len(udp_packets)} 个)\n")
        for pkt_idx, pkt in enumerate(udp_packets[:max_lines], 1):
            src_ip_str, dst_ip_str = pkt[IP].src, pkt[IP].dst
            src_port, dst_port = pkt[UDP].sport, pkt[UDP].dport
            print(f"## 数据包 {pkt_idx}: `{src_ip_str}:{src_port}` → `{dst_ip_str}:{dst_port}`\n")
            print_payload_packet(pkt, use_hex, full_output)

        if len(udp_packets) > max_lines:
            print(f"\n> ... 还有 {len(udp_packets) - max_lines} 个数据包未显示\n")

    # 都没有找到
    if not tcp_streams and not udp_packets:
        print(f"## 未找到 payload\n")
        print(f"**流**: {src_ip} <-> {dst_ip}" + (f" (端口 {dport})" if dport else ""))
        print("\n> 提示: 使用 `filter` 命令查看实际端口")


def cmd_modify(pcap_file, output_file, ip_mappings):
    """修改 PCAP 文件中的 IP 地址"""
    packets = rdpcap(pcap_file)
    modified_count = 0
    http_host_count = 0

    for pkt in packets:
        modified = False

        if pkt.haslayer(IP):
            if pkt[IP].src in ip_mappings:
                pkt[IP].src = ip_mappings[pkt[IP].src]
                modified = True
            if pkt[IP].dst in ip_mappings:
                pkt[IP].dst = ip_mappings[pkt[IP].dst]
                modified = True

        if modified and pkt.haslayer(TCP) and pkt.haslayer(Raw):
            try:
                payload = pkt[Raw].load
                payload_str = payload.decode('utf-8', errors='ignore')
                for old_ip, new_ip in ip_mappings.items():
                    old_host = f"Host: {old_ip}".encode()
                    if old_host in payload_str:
                        pkt[Raw].load = payload.replace(old_host, f"Host: {new_ip}".encode())
                        http_host_count += 1
            except Exception:
                pass

        if modified:
            modified_count += 1
            del pkt[IP].len, pkt[IP].chksum
            if pkt.haslayer(TCP):
                del pkt[TCP].chksum

    wrpcap(output_file, packets)
    print(f"\n# 修改完成\n")
    print(f"- **修改数据包数**: `{modified_count}`")
    if http_host_count > 0:
        print(f"- **HTTP Host 头同步**: `{http_host_count}`")
    print(f"- **输出文件**: `{output_file}`\n")


def main():
    parser = argparse.ArgumentParser(description="PCAP 工具集 - 统一命令行接口")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # list 命令
    p = subparsers.add_parser("list", help="列出所有 TCP/UDP 流（TCP 双向聚合）")
    p.add_argument("pcap", help="PCAP 文件")
    p.add_argument("--top", type=int, default=20, help="显示前 N 个流")

    # filter 命令
    p = subparsers.add_parser("filter", help="按条件过滤流")
    p.add_argument("pcap", help="PCAP 文件")
    p.add_argument("--port", type=int, help="按端口过滤")
    p.add_argument("--src", help="按源 IP 过滤")
    p.add_argument("--dst", help="按目的 IP 过滤")

    # extract 命令
    p = subparsers.add_parser("extract", help="提取 TCP/UDP 流的 payload")
    p.add_argument("pcap", help="PCAP 文件")
    p.add_argument("src", help="源 IP 地址")
    p.add_argument("dst", help="目的 IP 地址")
    p.add_argument("--dst-port", type=int, help="目的端口（可选，用于精确定位流）")
    p.add_argument("--max", type=int, default=50, help="最大显示数据包数")
    p.add_argument("--hex", action="store_true", help="使用十六进制输出（默认为 UTF-8 文本）")
    p.add_argument("--full", action="store_true", help="显示完整内容（默认截断为 500 字节）")

    # modify 命令
    p = subparsers.add_parser("modify", help="修改 IP 地址")
    p.add_argument("pcap", help="输入 PCAP 文件")
    p.add_argument("output", help="输出 PCAP 文件")
    p.add_argument("mapping", nargs="+", help="IP 映射，格式: old_ip:new_ip")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "list":
            cmd_list(args.pcap, args.top)
        elif args.command == "filter":
            cmd_filter(args.pcap, args.port, args.src, args.dst)
        elif args.command == "extract":
            cmd_extract(args.pcap, args.src, args.dst, args.dst_port, args.max, args.hex, args.full)
        elif args.command == "modify":
            ip_mappings = dict(m.split(":", 1) for m in args.mapping if ":" in m)
            if not ip_mappings:
                print("错误: 请提供至少一个 IP 映射，格式: old_ip:new_ip", file=sys.stderr)
                sys.exit(1)
            print(f"IP 映射: {ip_mappings}")
            cmd_modify(args.pcap, args.output, ip_mappings)
    except FileNotFoundError:
        print(f"错误: 文件不存在 - {args.pcap}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
