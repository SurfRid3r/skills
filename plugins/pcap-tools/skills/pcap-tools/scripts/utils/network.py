#!/usr/bin/env python3
"""网络参数工具函数"""

import random
import re
import ipaddress
from typing import Optional, Callable

# 预编译的 MAC 地址正则表达式
_MAC_PATTERN = re.compile(
    r'^([0-9A-Fa-f]{2})[:-]?([0-9A-Fa-f]{2})[:-]?([0-9A-Fa-f]{2})[:-]?'
    r'([0-9A-Fa-f]{2})[:-]?([0-9A-Fa-f]{2})[:-]?([0-9A-Fa-f]{2})$'
)

# 默认端口常量
DEFAULT_HTTP_PORT = 80
DEFAULT_HTTPS_PORT = 443
MIN_EPHEMERAL_PORT = 1024
MAX_EPHEMERAL_PORT = 65535


def validate_ip_address(ip_str: str) -> bool:
    """验证 IP 地址格式是否合法

    Args:
        ip_str: IP 地址字符串

    Returns:
        bool: 是否为有效的 IP 地址
    """
    try:
        ipaddress.ip_address(ip_str)
        return True
    except ValueError:
        return False


def validate_mac_address(mac_str: str) -> Optional[str]:
    """验证并规范化 MAC 地址

    支持多种分隔符：冒号、横线、点或无分隔符

    Args:
        mac_str: MAC 地址字符串

    Returns:
        规范化后的 MAC 地址（冒号分隔大写），无效时返回 None
    """
    match = _MAC_PATTERN.match(mac_str)
    if match:
        bytes_list = match.groups()
        return ':'.join(bytes_list).upper()
    return None


def generate_random_public_ip() -> str:
    """生成随机公网 IP 地址

    排除私有地址段和保留地址段

    Returns:
        随机公网 IP 地址字符串
    """
    # 私有地址段
    private_ranges = [
        (0x0A000000, 0x0AFFFFFF),  # 10.0.0.0/8
        (0xAC100000, 0xAC1FFFFF),  # 172.16.0.0/12
        (0xC0A80000, 0xC0A8FFFF),  # 192.168.0.0/16
    ]

    # 保留地址段
    reserved_ranges = [
        (0x00000000, 0x00FFFFFF),  # 0.0.0.0/8
        (0x7F000000, 0x7FFFFFFF),  # 127.0.0.0/8 (环回)
        (0xA9FE0000, 0xA9FEFFFF),  # 169.254.0.0/16 (链路本地)
        (0xC0000000, 0xC00000FF),  # 192.0.0.0/24
        (0xC0000200, 0xC00002FF),  # 192.0.2.0/24 (TEST-NET-1)
        (0xC6336400, 0xC63364FF),  # 198.51.100.0/24 (TEST-NET-2)
        (0xCB007100, 0xCB0071FF),  # 203.0.113.0/24 (TEST-NET-3)
        (0xE0000000, 0xEFFFFFFF),  # 224.0.0.0/4 (多播)
        (0xF0000000, 0xFFFFFFFF),  # 240.0.0.0/4 (保留)
    ]

    def is_valid_public_ip(ip_int: int) -> bool:
        for start, end in private_ranges:
            if start <= ip_int <= end:
                return False
        for start, end in reserved_ranges:
            if start <= ip_int <= end:
                return False
        return True

    while True:
        # 生成随机32位整数，排除0.x.x.x和224.x.x.x及以上
        ip_int = random.randint(0x01000000, 0xDFFFFFFF)
        if is_valid_public_ip(ip_int):
            octets = [
                (ip_int >> 24) & 0xFF,
                (ip_int >> 16) & 0xFF,
                (ip_int >> 8) & 0xFF,
                ip_int & 0xFF
            ]
            return '.'.join(map(str, octets))


def generate_random_private_ip() -> str:
    """生成随机私网 IP 地址

    从 10.0.0.0/8、172.16.0.0/12、192.168.0.0/16 中随机选择

    Returns:
        随机私网 IP 地址字符串
    """
    private_networks = [
        (0x0A000000, 0x0AFFFFFF),  # 10.0.0.0/8
        (0xAC100000, 0xAC1FFFFF),  # 172.16.0.0/12
        (0xC0A80000, 0xC0A8FFFF),  # 192.168.0.0/16
    ]

    network_start, network_end = random.choice(private_networks)
    ip_int = random.randint(network_start, network_end)

    octets = [
        (ip_int >> 24) & 0xFF,
        (ip_int >> 16) & 0xFF,
        (ip_int >> 8) & 0xFF,
        ip_int & 0xFF
    ]
    return '.'.join(map(str, octets))


def generate_random_mac() -> str:
    """生成随机 MAC 地址

    清除组播位和本地管理位，避免全0/全F首字节

    Returns:
        随机 MAC 地址字符串（冒号分隔小写）
    """
    while True:
        # 清除组播位（bit 0）和本地管理位（bit 1）
        first_byte = random.randint(0x00, 0xFF) & 0xFC
        if first_byte == 0x00 or first_byte == 0xFF:
            continue
        mac_parts = [f"{first_byte:02x}"] + [f"{random.randint(0, 255):02x}" for _ in range(5)]
        mac_address = ":".join(mac_parts)
        if mac_address != "00:00:00:00:00:00" and mac_address != "ff:ff:ff:ff:ff:ff":
            return mac_address


def generate_random_client_port() -> int:
    """生成随机客户端端口（临时端口范围）

    Returns:
        随机端口号 (1024-65535)
    """
    return random.randint(MIN_EPHEMERAL_PORT, MAX_EPHEMERAL_PORT)


def resolve_network_param(param: str, generator_func: Callable[[], str]) -> str:
    """解析网络参数

    如果参数是特殊值（如 WAN/LAN/RANDOM），则调用生成器函数；
    否则直接返回参数值。

    Args:
        param: 参数值（可能是特殊值或具体值）
        generator_func: 生成器函数（如 generate_random_public_ip）

    Returns:
        解析后的参数值
    """
    if param in ('WAN', 'LAN', 'RANDOM', 'CLIENT', 'SERVER'):
        return generator_func()
    return param


# 网络类型预设映射
NETWORK_TYPE_PRESETS = {
    'wan-lan': ('WAN', 'LAN'),  # 外网 -> 内网（默认）
    'lan-wan': ('LAN', 'WAN'),  # 内网 -> 外网
    'wan-wan': ('WAN', 'WAN'),  # 外网 -> 外网
    'lan-lan': ('LAN', 'LAN'),  # 内网 -> 内网
}


def get_ip_generator(ip_type: str):
    """根据 IP 类型返回对应的生成器函数

    Args:
        ip_type: IP 类型（WAN/LAN 或具体 IP 地址）

    Returns:
        生成器函数或返回固定 IP 的函数
    """
    if ip_type == 'WAN':
        return generate_random_public_ip
    elif ip_type == 'LAN':
        return generate_random_private_ip
    else:
        return lambda: ip_type  # 已经是具体 IP 地址
