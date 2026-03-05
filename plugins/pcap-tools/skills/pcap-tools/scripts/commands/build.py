#!/usr/bin/env python3
"""
build 命令 - JSON 转 PCAP 包装器
"""
import sys
from typing import Optional

try:
    from pcap_build import build_pcap_from_json
except ImportError:
    import os
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    from pcap_build import build_pcap_from_json


def cmd_build(
    input_path: str,
    output_path: Optional[str] = None
) -> None:
    """将 JSON 文件转换为 PCAP 文件

    Args:
        input_path: 输入 JSON 文件路径
        output_path: 输出文件路径（可选）
    """
    result = build_pcap_from_json(
        input_path=input_path,
        output_path=output_path
    )
