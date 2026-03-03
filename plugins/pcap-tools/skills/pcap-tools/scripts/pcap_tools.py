#!/usr/bin/env python3
"""PCAP 工具集 - 统一命令行接口

提供以下子命令:
- list: 列出所有 TCP/UDP 流（TCP 双向聚合）
- filter: 按条件过滤流
- extract: 提取 TCP/UDP 流的 payload
- modify: 修改 IP 地址和端口
- build: 将 JSON 数据转换为 PCAP 文件
"""

import argparse
import sys

from commands import cmd_list, cmd_filter, cmd_extract, cmd_modify, cmd_build


def main() -> None:
    """主入口函数"""
    parser = argparse.ArgumentParser(description="PCAP 工具集 - 统一命令行接口")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="静默模式，减少输出信息")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    _setup_list_parser(subparsers)
    _setup_filter_parser(subparsers)
    _setup_extract_parser(subparsers)
    _setup_modify_parser(subparsers)
    _setup_build_parser(subparsers)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        _dispatch_command(args)
    except FileNotFoundError:
        print(f"错误: 文件不存在 - {args.pcap}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


def _setup_list_parser(subparsers) -> None:
    """配置 list 命令解析器"""
    p = subparsers.add_parser("list", help="列出所有 TCP/UDP 流（TCP 双向聚合）")
    p.add_argument("pcap", help="PCAP 文件")
    p.add_argument("--top", type=int, default=20, help="显示前 N 个流")


def _setup_filter_parser(subparsers) -> None:
    """配置 filter 命令解析器"""
    p = subparsers.add_parser("filter", help="按条件过滤流")
    p.add_argument("pcap", help="PCAP 文件")
    p.add_argument("--port", type=int, help="按端口过滤")
    p.add_argument("--src", help="按源 IP 过滤")
    p.add_argument("--dst", help="按目的 IP 过滤")


def _setup_extract_parser(subparsers) -> None:
    """配置 extract 命令解析器"""
    p = subparsers.add_parser("extract", help="提取 TCP/UDP 流的 payload")
    p.add_argument("pcap", help="PCAP 文件")
    p.add_argument("src", help="源 IP 地址")
    p.add_argument("dst", help="目的 IP 地址")
    p.add_argument("--dst-port", type=int, help="目的端口（可选，用于精确定位流）")
    p.add_argument("--max", type=int, default=50, help="最大显示数据包数")
    p.add_argument("--hex", action="store_true", help="使用十六进制输出（默认为 UTF-8 文本）")
    p.add_argument("--full", action="store_true", help="显示完整内容（默认截断为 500 字节）")


def _setup_modify_parser(subparsers) -> None:
    """配置 modify 命令解析器"""
    p = subparsers.add_parser("modify", help="修改 IP 地址和端口")
    p.add_argument("pcap", help="输入 PCAP 文件")
    p.add_argument("output", help="输出 PCAP 文件")
    p.add_argument(
        "mapping", nargs="*", help="IP 映射，格式: old_ip:new_ip"
    )
    p.add_argument(
        "--port",
        action="append",
        metavar="OLD:NEW",
        help="端口映射，格式: old_port:new_port（可多次使用）",
    )
    p.add_argument(
        "--host",
        action="append",
        metavar="OLD:NEW",
        help="HTTP Host 映射，格式: old_host:new_host（可多次使用，用于域名 Host 修改）",
    )
    p.add_argument(
        "--header",
        action="append",
        metavar="NAME:OLD:NEW",
        help="HTTP Header 替换，格式: HeaderName:old_value:new_value（可多次使用）",
    )
    p.add_argument(
        "--body",
        action="append",
        metavar="OLD:NEW",
        help="HTTP Body 字符串替换（可多次使用）",
    )
    p.add_argument(
        "--raw",
        action="append",
        metavar="HEX_OLD:HEX_NEW",
        help="原始 payload 字节替换，十六进制格式（可多次使用）",
    )


def _setup_build_parser(subparsers) -> None:
    """配置 build 命令解析器"""
    p = subparsers.add_parser("build", help="将 JSON 数据转换为 PCAP 文件")
    p.add_argument("input_path", help="输入 JSON 文件或目录路径")
    p.add_argument("-o", "--output", default=None,
                   help="输出路径（默认: {input}_{timestamp}）")
    p.add_argument("--req-key", default="request_data_base64",
                   help="JSON 请求字段键（默认: request_data_base64）")
    p.add_argument("--res-key", default="response_data_base64",
                   help="JSON 响应字段键（默认: response_data_base64）")
    p.add_argument("--net-type", default="wan-lan",
                   choices=['wan-lan', 'lan-wan', 'wan-wan', 'lan-lan'],
                   help="网络类型预设（默认: wan-lan）")
    p.add_argument("--src-ip", default=None,
                   help="源 IP（IP 地址或 WAN/LAN）")
    p.add_argument("--dst-ip", default=None,
                   help="目的 IP（IP 地址或 WAN/LAN）")
    p.add_argument("--src-port", type=int, default=None,
                   help="源端口（默认: 随机）")
    p.add_argument("--dst-port", type=int, default=None,
                   help="目的端口（默认: 80）")
    p.add_argument("--src-mac", default=None,
                   help="源 MAC（默认: 随机）")
    p.add_argument("--dst-mac", default=None,
                   help="目的 MAC（默认: 随机）")
    p.add_argument("-i", "--interval", type=float, default=0.01,
                   help="包时间间隔/秒（默认: 0.01）")
    p.add_argument("--interval-rand", type=float, default=0.5,
                   help="间隔随机度 0-1（默认: 0.5）")
    p.add_argument("-k", "--keep-alive", action="store_true",
                   help="长连接模式")
    p.add_argument("--mtu", type=int, default=1500,
                   help="MTU 大小（默认: 1500）")


def _dispatch_command(args) -> None:
    """分发命令到对应的处理函数"""
    quiet = getattr(args, "quiet", False)

    if args.command == "list":
        cmd_list(args.pcap, args.top, quiet)

    elif args.command == "filter":
        cmd_filter(args.pcap, args.port, args.src, args.dst)

    elif args.command == "extract":
        cmd_extract(
            args.pcap,
            args.src,
            args.dst,
            args.dst_port,
            args.max,
            args.hex,
            args.full,
            quiet,
        )

    elif args.command == "modify":
        ip_mappings, port_mappings, host_mappings, header_mappings, body_mappings, raw_mappings = _parse_modify_args(args)
        if not quiet:
            if ip_mappings:
                print(f"IP 映射: {ip_mappings}")
            if port_mappings:
                print(f"端口映射: {port_mappings}")
            if host_mappings:
                print(f"Host 映射: {host_mappings}")
            if header_mappings:
                print(f"Header 映射: {header_mappings}")
            if body_mappings:
                print(f"Body 映射: {body_mappings}")
            if raw_mappings:
                print(f"Raw 映射: {[(o.hex(), n.hex()) for o, n in raw_mappings]}")
        cmd_modify(args.pcap, args.output, ip_mappings, port_mappings, host_mappings,
                   header_mappings, body_mappings, raw_mappings, quiet)

    elif args.command == "build":
        cmd_build(
            args.input_path,
            args.output,
            args.req_key,
            args.res_key,
            args.net_type,
            args.src_ip,
            args.dst_ip,
            args.src_port,
            args.dst_port,
            args.src_mac,
            args.dst_mac,
            args.interval,
            args.interval_rand,
            args.keep_alive,
            args.mtu
        )


def _parse_modify_args(args) -> tuple:
    """解析 modify 命令的参数

    Returns:
        (ip_mappings, port_mappings, host_mappings, header_mappings, body_mappings, raw_mappings) 元组
    """
    # 解析 IP 映射
    ip_mappings = dict(m.split(":", 1) for m in args.mapping if ":" in m)

    # 解析端口映射
    port_mappings = {}
    if args.port:
        for p in args.port:
            if ":" in p:
                old_port, new_port = p.split(":", 1)
                try:
                    port_mappings[int(old_port)] = int(new_port)
                except ValueError:
                    print(f"错误: 无效的端口格式 - {p}", file=sys.stderr)
                    sys.exit(1)

    # 解析 Host 映射
    host_mappings = {}
    if args.host:
        for h in args.host:
            if ":" in h:
                old_host, new_host = h.split(":", 1)
                host_mappings[old_host] = new_host

    # 解析 Header 映射 (Name:Old:New)
    header_mappings = []
    if args.header:
        for h in args.header:
            parts = h.split(":", 2)
            if len(parts) == 3:
                header_mappings.append((parts[0], parts[1], parts[2]))
            else:
                print(f"错误: 无效的 Header 格式 - {h}，应为 Name:Old:New", file=sys.stderr)
                sys.exit(1)

    # 解析 Body 映射 (Old:New)
    body_mappings = []
    if args.body:
        for b in args.body:
            if ":" in b:
                old, new = b.split(":", 1)
                body_mappings.append((old, new))
            else:
                print(f"错误: 无效的 Body 格式 - {b}，应为 Old:New", file=sys.stderr)
                sys.exit(1)

    # 解析 Raw 映射 (HexOld:HexNew)
    raw_mappings = []
    if args.raw:
        for r in args.raw:
            if ":" in r:
                old_hex, new_hex = r.split(":", 1)
                try:
                    raw_mappings.append((bytes.fromhex(old_hex), bytes.fromhex(new_hex)))
                except ValueError as e:
                    print(f"错误: 无效的十六进制格式 - {r}: {e}", file=sys.stderr)
                    sys.exit(1)
            else:
                print(f"错误: 无效的 Raw 格式 - {r}，应为 HexOld:HexNew", file=sys.stderr)
                sys.exit(1)

    # 至少需要一个映射
    if not ip_mappings and not port_mappings and not host_mappings and not header_mappings and not body_mappings and not raw_mappings:
        print("错误: 请提供至少一个映射", file=sys.stderr)
        print("  IP 映射格式: old_ip:new_ip", file=sys.stderr)
        print("  端口映射格式: --port old_port:new_port", file=sys.stderr)
        print("  Host 映射格式: --host old_host:new_host", file=sys.stderr)
        print("  Header 映射格式: --header Name:old:new", file=sys.stderr)
        print("  Body 映射格式: --body old:new", file=sys.stderr)
        print("  Raw 映射格式: --raw hex_old:hex_new", file=sys.stderr)
        sys.exit(1)

    return ip_mappings, port_mappings, host_mappings, header_mappings, body_mappings, raw_mappings


if __name__ == "__main__":
    main()
