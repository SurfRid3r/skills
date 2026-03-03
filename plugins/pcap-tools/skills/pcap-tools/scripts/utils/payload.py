#!/usr/bin/env python3
"""Payload 处理工具函数"""

from scapy.all import Raw


def format_payload(payload: bytes, use_hex: bool = False) -> str:
    """格式化 payload 为十六进制或 UTF-8 文本

    Args:
        payload: 原始 payload 字节
        use_hex: 是否使用十六进制格式

    Returns:
        格式化后的字符串
    """
    if use_hex:
        return payload.hex()
    return payload.decode("utf-8", errors="replace")


def print_payload_packet(pkt, use_hex: bool, full_output: bool) -> None:
    """打印单个数据包的 payload

    Args:
        pkt: scapy 数据包
        use_hex: 是否使用十六进制格式
        full_output: 是否显示完整内容（不截断）
    """
    print("**Payload**:")
    print("```")
    formatted = format_payload(pkt[Raw].load, use_hex)
    if not full_output and len(formatted) > 500:
        formatted = formatted[:500] + "...(截断)"
    print(formatted)
    print("```\n")
