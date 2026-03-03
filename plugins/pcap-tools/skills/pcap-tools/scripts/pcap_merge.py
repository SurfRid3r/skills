#!/usr/bin/env python3
"""
PCAP 合并工具

将多个 PCAP 文件合并为一个，支持时间戳自动调整保持连续性。
"""
import argparse
import os
import sys
from datetime import datetime
from scapy.all import rdpcap, wrpcap


def merge_multiple_pcaps(pcap_files, output_file, adjust_timestamp=True):
    """合并多个 PCAP 文件

    按文件顺序依次合并，自动调整时间戳保持连续性。

    Args:
        pcap_files: PCAP 文件路径列表（至少 2 个）
        output_file: 输出文件路径
        adjust_timestamp: 是否自动调整时间戳
    """
    if len(pcap_files) < 2:
        print("错误: 至少需要 2 个 PCAP 文件进行合并", file=sys.stderr)
        sys.exit(1)

    # 读取所有文件
    all_packets = []
    file_stats = []

    for i, pcap_path in enumerate(pcap_files):
        try:
            packets = rdpcap(pcap_path)
        except FileNotFoundError:
            print(f"错误: 文件不存在 - {pcap_path}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"错误: 读取 PCAP 文件失败 - {pcap_path}: {e}", file=sys.stderr)
            sys.exit(1)

        file_stats.append({
            'path': pcap_path,
            'count': len(packets)
        })

        if len(packets) == 0:
            continue

        if adjust_timestamp and len(all_packets) > 0:
            # 计算偏移量：上一个包时间 + 0.1s
            last_time = all_packets[-1].time
            first_time = packets[0].time
            offset = last_time + 0.1 - first_time

            # 调整当前文件所有包的时间戳
            for pkt in packets:
                pkt.time = pkt.time + offset

        all_packets.extend(packets)

    # 保存
    try:
        wrpcap(output_file, all_packets)
    except Exception as e:
        print(f"错误: 保存文件失败 - {e}", file=sys.stderr)
        sys.exit(1)

    # 输出统计
    print(f"\n# PCAP 合并完成\n")
    print("## 合并文件列表\n")
    for i, stat in enumerate(file_stats, 1):
        print(f"{i}. `{os.path.basename(stat['path'])}` ({stat['count']} 包)")
    print(f"\n## 合并结果\n")
    print(f"- **总包数**: {len(all_packets)} 包")
    print(f"- **时间戳调整**: {'是' if adjust_timestamp else '否'}")
    print(f"- **输出文件**: `{output_file}`\n")


def main():
    parser = argparse.ArgumentParser(
        description="PCAP 合并工具 - 将多个 PCAP 文件合并为一个",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 合并多个文件（按顺序追加）
  python pcap_merge.py file1.pcap file2.pcap file3.pcap

  # 指定输出文件
  python pcap_merge.py file1.pcap file2.pcap file3.pcap -o merged.pcap

  # 禁用时间戳调整
  python pcap_merge.py file1.pcap file2.pcap --no-adjust-ts

  # 使用通配符
  python pcap_merge.py *.pcap -o all_merged.pcap
"""
    )

    parser.add_argument("pcap_files", nargs="+",
                        help="要合并的 PCAP 文件（至少 2 个，按顺序合并）")
    parser.add_argument("-o", "--output", default=None,
                        help="输出文件路径（默认: merged_{timestamp}.pcap）")
    parser.add_argument("--no-adjust-ts", action="store_true",
                        help="禁用时间戳自动调整")

    args = parser.parse_args()

    # 检查文件数量
    if len(args.pcap_files) < 2:
        print("错误: 至少需要 2 个 PCAP 文件进行合并", file=sys.stderr)
        sys.exit(1)

    # 生成默认输出文件名
    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = f"merged_{timestamp}.pcap"

    merge_multiple_pcaps(
        args.pcap_files,
        args.output,
        adjust_timestamp=not args.no_adjust_ts
    )


if __name__ == "__main__":
    main()
