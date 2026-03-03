#!/usr/bin/env python3
"""build 命令 - JSON 转 PCAP 包装器"""

import sys
from typing import Optional

# 由于 scripts 目录不是正式的 Python 包，使用直接导入
# 当从主脚本运行时，pcap_build 模块在 sys.path 中可被找到
try:
    from pcap_build import build_pcap_from_json
except ImportError:
    # 如果直接导入失败，尝试添加父目录到路径
    import os
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    from pcap_build import build_pcap_from_json


def cmd_build(
    input_path: str,
    output_path: Optional[str] = None,
    req_key: str = 'request_data_base64',
    res_key: str = 'response_data_base64',
    net_type: str = 'wan-lan',
    src_ip: Optional[str] = None,
    dst_ip: Optional[str] = None,
    src_port: Optional[int] = None,
    dst_port: Optional[int] = None,
    src_mac: Optional[str] = None,
    dst_mac: Optional[str] = None,
    interval: float = 0.01,
    interval_rand: float = 0.5,
    keep_alive: bool = False,
    mtu: int = 1500
) -> None:
    """将 JSON 文件或目录转换为 PCAP 文件

    Args:
        input_path: 输入 JSON 文件或目录路径
        output_path: 输出文件或目录路径
        req_key: JSON 请求字段键
        res_key: JSON 响应字段键
        net_type: 网络类型预设 (wan-lan/lan-wan/wan-wan/lan-lan)
        src_ip: 源 IP
        dst_ip: 目的 IP
        src_port: 源端口
        dst_port: 目的端口
        src_mac: 源 MAC
        dst_mac: 目的 MAC
        interval: 包时间间隔（秒）
        interval_rand: 间隔随机度（0-1）
        keep_alive: 长连接模式
        mtu: MTU 大小
    """
    result = build_pcap_from_json(
        input_path=input_path,
        output_path=output_path,
        req_key=req_key,
        res_key=res_key,
        net_type=net_type,
        src_ip=src_ip,
        dst_ip=dst_ip,
        src_port=src_port,
        dst_port=dst_port,
        src_mac=src_mac,
        dst_mac=dst_mac,
        interval=interval,
        interval_rand=interval_rand,
        keep_alive=keep_alive,
        mtu=mtu
    )

    if result['failed']:
        sys.exit(1)
