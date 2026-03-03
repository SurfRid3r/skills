#!/usr/bin/env python3
"""
PCAP 构建工具

将 JSON 格式的 HTTP 数据转换为 PCAP 文件。
支持 TCP 三次握手、HTTP 流量、四次挥手的完整构建。
"""

import argparse
import base64
import binascii
import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from scapy.all import Ether, IP, TCP, Raw, wrpcap

from utils.network import (
    validate_ip_address,
    validate_mac_address,
    generate_random_public_ip,
    generate_random_private_ip,
    generate_random_mac,
    generate_random_client_port,
    NETWORK_TYPE_PRESETS,
    get_ip_generator,
    DEFAULT_HTTP_PORT,
    MIN_EPHEMERAL_PORT,
    MAX_EPHEMERAL_PORT,
)


class FileWalker:
    """文件遍历器：递归遍历指定目录下的所有文件

    支持按文件后缀过滤，自动创建对应的输出目录结构
    """

    def __init__(self, input_dir: str, output_dir: Optional[str] = None, suffix: Optional[str] = None):
        self.input_dir = input_dir
        if output_dir:
            self.output_dir = output_dir
        else:
            clean_input_path = input_dir.rstrip('/\\')
            self.output_dir = f"{clean_input_path}_{int(time.time())}"
        self.suffix = suffix

        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

    def __iter__(self):
        return self.generate_paths()

    def generate_paths(self):
        """生成输入和输出文件路径的迭代器"""
        for root, dirs, files in os.walk(self.input_dir):
            for file in files:
                if self.suffix is None or file.endswith(self.suffix):
                    input_path = os.path.join(root, file)
                    relative_path = os.path.relpath(input_path, self.input_dir)
                    output_path = os.path.join(self.output_dir, relative_path)
                    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                    yield input_path, output_path, file


class PacketBuilder:
    """TCP 数据包构建器：将 HTTP 字节串构建为 TCP 数据包

    支持自定义网络五元组和时序参数，MTU 分片功能，长短连接控制
    """

    def __init__(
        self,
        src_ip: str,
        dst_ip: str,
        src_port: int,
        dst_port: int,
        src_mac: str,
        dst_mac: str,
        interval: float = 0.01,
        interval_randomness: float = 0.5,
        mtu: int = 1500,
        is_keep_alive: bool = False,
        start_timestamp: Optional[float] = None
    ):
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.src_port = src_port
        self.dst_port = dst_port
        self.src_mac = src_mac
        self.dst_mac = dst_mac
        self.interval = interval
        self.interval_randomness = interval_randomness
        self.buffers = []
        self.mtu = mtu
        self.is_keep_alive = is_keep_alive
        self.current_timestamp = start_timestamp if start_timestamp else time.time()

    def _get_random_interval(self) -> float:
        """获取随机时间间隔"""
        if self.interval_randomness > 0:
            random_factor = 1.0 + random.uniform(-self.interval_randomness, self.interval_randomness)
            return self.interval * random_factor
        return self.interval

    def _split_data_by_mtu(self, data: bytes) -> list:
        """按 MTU 分片数据"""
        chunks = []
        data_len = len(data)
        offset = 0

        while offset < data_len:
            # 计算当前分片大小（考虑 IP 和 TCP 头部）
            ip_header_size = 20
            tcp_header_size = 20
            max_payload_size = self.mtu - ip_header_size - tcp_header_size

            chunk_size = min(max_payload_size, data_len - offset)
            chunk = data[offset:offset + chunk_size]
            chunks.append(chunk)
            offset += chunk_size

        return chunks

    def insert_three_way_handshake(self) -> None:
        """插入三次握手数据包"""
        # 生成新的随机序列号和确认号
        self.current_seq = random.randint(1000000000, 4294967295 // 2)
        self.current_ack = random.randint(1000000000, 4294967295 // 2)

        # SYN 包
        syn_packet = (
            Ether(src=self.src_mac, dst=self.dst_mac) /
            IP(src=self.src_ip, dst=self.dst_ip) /
            TCP(sport=self.src_port, dport=self.dst_port, seq=self.current_seq, flags='S')
        )
        syn_packet.time = self.current_timestamp
        self.buffers.append(syn_packet)
        self.current_timestamp += self._get_random_interval()

        # SYN-ACK 包
        syn_ack_packet = (
            Ether(src=self.dst_mac, dst=self.src_mac) /
            IP(src=self.dst_ip, dst=self.src_ip) /
            TCP(sport=self.dst_port, dport=self.src_port, seq=self.current_ack,
                ack=self.current_seq + 1, flags='SA')
        )
        syn_ack_packet.time = self.current_timestamp
        self.buffers.append(syn_ack_packet)
        self.current_timestamp += self._get_random_interval()

        # ACK 包
        ack_packet = (
            Ether(src=self.src_mac, dst=self.dst_mac) /
            IP(src=self.src_ip, dst=self.dst_ip) /
            TCP(sport=self.src_port, dport=self.dst_port, seq=self.current_seq + 1,
                ack=self.current_ack + 1, flags='A')
        )
        ack_packet.time = self.current_timestamp
        self.buffers.append(ack_packet)
        self.current_timestamp += self._get_random_interval()

        # 更新序列号
        self.current_seq += 1
        self.current_ack += 1

    def insert_four_way_wave(self) -> None:
        """插入四次挥手数据包"""
        # FIN 包
        fin_packet = (
            Ether(src=self.src_mac, dst=self.dst_mac) /
            IP(src=self.src_ip, dst=self.dst_ip) /
            TCP(sport=self.src_port, dport=self.dst_port, seq=self.current_seq,
                ack=self.current_ack, flags='FA')
        )
        fin_packet.time = self.current_timestamp
        self.buffers.append(fin_packet)
        self.current_timestamp += self._get_random_interval()

        # ACK 包
        ack_packet = (
            Ether(src=self.dst_mac, dst=self.src_mac) /
            IP(src=self.dst_ip, dst=self.src_ip) /
            TCP(sport=self.dst_port, dport=self.src_port, seq=self.current_ack,
                ack=self.current_seq + 1, flags='A')
        )
        ack_packet.time = self.current_timestamp
        self.buffers.append(ack_packet)
        self.current_timestamp += self._get_random_interval()

        # FIN 包（服务端）
        fin_packet2 = (
            Ether(src=self.dst_mac, dst=self.src_mac) /
            IP(src=self.dst_ip, dst=self.src_ip) /
            TCP(sport=self.dst_port, dport=self.src_port, seq=self.current_ack,
                ack=self.current_seq + 1, flags='FA')
        )
        fin_packet2.time = self.current_timestamp
        self.buffers.append(fin_packet2)
        self.current_timestamp += self._get_random_interval()

        # ACK 包
        ack_packet2 = (
            Ether(src=self.src_mac, dst=self.dst_mac) /
            IP(src=self.src_ip, dst=self.dst_ip) /
            TCP(sport=self.src_port, dport=self.dst_port, seq=self.current_seq + 1,
                ack=self.current_ack + 1, flags='A')
        )
        ack_packet2.time = self.current_timestamp
        self.buffers.append(ack_packet2)
        self.current_timestamp += self._get_random_interval()

        # 更新序列号和确认号
        self.current_seq += 1
        self.current_ack += 1

    def insert_http_flow(self, http_flow: dict) -> None:
        """插入 HTTP 流量数据包（按 MTU 分片）

        Args:
            http_flow: 包含 'request' 和 'response' 的字典
        """
        request_data = http_flow['request']
        response_data = http_flow['response']

        # 分片请求数据
        request_chunks = self._split_data_by_mtu(request_data)
        for chunk in request_chunks:
            request_packet = (
                Ether(src=self.src_mac, dst=self.dst_mac) /
                IP(src=self.src_ip, dst=self.dst_ip) /
                TCP(sport=self.src_port, dport=self.dst_port, seq=self.current_seq,
                    ack=self.current_ack, flags='PA') /
                Raw(load=chunk)
            )
            request_packet.time = self.current_timestamp
            self.buffers.append(request_packet)
            self.current_seq += len(chunk)
            self.current_timestamp += self._get_random_interval()

        # 服务端确认收到请求数据
        request_ack_packet = (
            Ether(src=self.dst_mac, dst=self.src_mac) /
            IP(src=self.dst_ip, dst=self.src_ip) /
            TCP(sport=self.dst_port, dport=self.src_port, seq=self.current_ack,
                ack=self.current_seq, flags='A')
        )
        request_ack_packet.time = self.current_timestamp
        self.buffers.append(request_ack_packet)
        self.current_timestamp += self._get_random_interval()

        # 分片响应数据
        response_chunks = self._split_data_by_mtu(response_data)
        for chunk in response_chunks:
            response_packet = (
                Ether(src=self.dst_mac, dst=self.src_mac) /
                IP(src=self.dst_ip, dst=self.src_ip) /
                TCP(sport=self.dst_port, dport=self.src_port, seq=self.current_ack,
                    ack=self.current_seq, flags='PA') /
                Raw(load=chunk)
            )
            response_packet.time = self.current_timestamp
            self.buffers.append(response_packet)
            self.current_ack += len(chunk)
            self.current_timestamp += self._get_random_interval()

        # 客户端确认收到响应数据
        response_ack_packet = (
            Ether(src=self.src_mac, dst=self.dst_mac) /
            IP(src=self.src_ip, dst=self.dst_ip) /
            TCP(sport=self.src_port, dport=self.dst_port, seq=self.current_seq,
                ack=self.current_ack, flags='A')
        )
        response_ack_packet.time = self.current_timestamp
        self.buffers.append(response_ack_packet)
        self.current_timestamp += self._get_random_interval()

    def build_tcp_packets(self, http_flows: list) -> list:
        """处理 HTTP 流量列表，按照长短连接模式构建 TCP 数据包

        Args:
            http_flows: HTTP 流量列表，格式为 [{'request': bytes, 'response': bytes}, ...]

        Returns:
            构建好的 scapy.Packet 列表
        """
        if isinstance(http_flows, dict):
            http_flows = [http_flows]

        # 清空缓冲区
        self.buffers = []

        # 插入三次握手
        self.insert_three_way_handshake()

        # 处理 HTTP 流量
        for flow_index, http_flow in enumerate(http_flows, 1):
            # 如果不是长连接且不是第一个流量，需要重新建立连接
            if not self.is_keep_alive and flow_index > 1:
                self.insert_four_way_wave()
                self.insert_three_way_handshake()

            # 插入 HTTP 流量
            self.insert_http_flow(http_flow)

            # 在两个 HTTP 流量之间插入额外延迟
            if flow_index < len(http_flows):
                self.current_timestamp += self.interval * 10

        # 插入四次挥手
        self.insert_four_way_wave()

        return self.buffers


def extract_http_flows_from_json(
    json_data: dict,
    request_field_key: str,
    response_field_key: str
) -> list:
    """从 JSON 数据中提取 HTTP 流量

    支持两种 JSON 格式：
      1. 顶层字典直接包含请求/响应字段
      2. 顶层字典包含 'traffic_flows' 列表，每项包含请求/响应字段

    Args:
        json_data: JSON 数据字典
        request_field_key: 请求字段的键名
        response_field_key: 响应字段的键名

    Returns:
        HTTP 流量列表，格式为 [{'request': bytes, 'response': bytes}, ...]

    Raises:
        ValueError: JSON 数据格式错误
        KeyError: 缺少必需字段
        binascii.Error: Base64 解码失败
    """
    if not isinstance(json_data, dict):
        raise ValueError(f"JSON 数据格式错误，期望字典类型，实际类型: {type(json_data).__name__}")

    traffic_items = json_data.get('traffic_flows', [json_data])
    http_flows = []

    for flow_index, traffic_item in enumerate(traffic_items, 1):
        request_base64 = traffic_item.get(request_field_key)
        response_base64 = traffic_item.get(response_field_key)

        if not request_base64 or not response_base64:
            raise KeyError(
                f"第 {flow_index} 组流量缺少必需字段 '{request_field_key}' 或 '{response_field_key}'"
            )

        try:
            request_bytes = base64.b64decode(request_base64)
            response_bytes = base64.b64decode(response_base64)
        except binascii.Error as e:
            raise binascii.Error(f"第 {flow_index} 组流量 Base64 解码失败: {e}")
        except Exception as e:
            raise Exception(f"第 {flow_index} 组流量解码异常: {type(e).__name__} - {e}")

        http_flows.append({
            'request': request_bytes,
            'response': response_bytes
        })

    return http_flows


def generate_network_params(
    src_ip: Optional[str],
    dst_ip: Optional[str],
    src_port: Optional[int],
    dst_port: Optional[int],
    src_mac: Optional[str],
    dst_mac: Optional[str],
    net_type: str = 'wan-lan'
) -> dict:
    """生成网络参数

    根据网络类型预设和用户指定的参数，生成完整的网络五元组。

    Args:
        src_ip: 源 IP（None 则使用预设）
        dst_ip: 目的 IP（None 则使用预设）
        src_port: 源端口（None 则随机客户端端口）
        dst_port: 目的端口（None 则默认 80）
        src_mac: 源 MAC（None 则随机）
        dst_mac: 目的 MAC（None 则随机）
        net_type: 网络类型预设

    Returns:
        包含完整网络参数的字典
    """
    # 获取预设
    preset_src, preset_dst = NETWORK_TYPE_PRESETS.get(net_type, ('WAN', 'LAN'))

    # 解析源 IP
    if src_ip is None:
        src_ip_resolved = get_ip_generator(preset_src)()
    elif src_ip in ('WAN', 'LAN'):
        src_ip_resolved = get_ip_generator(src_ip)()
    else:
        src_ip_resolved = src_ip

    # 解析目的 IP
    if dst_ip is None:
        dst_ip_resolved = get_ip_generator(preset_dst)()
    elif dst_ip in ('WAN', 'LAN'):
        dst_ip_resolved = get_ip_generator(dst_ip)()
    else:
        dst_ip_resolved = dst_ip

    # 解析端口
    if src_port is None:
        src_port_resolved = generate_random_client_port()
    else:
        src_port_resolved = src_port

    if dst_port is None:
        dst_port_resolved = DEFAULT_HTTP_PORT
    else:
        dst_port_resolved = dst_port

    # 解析 MAC
    if src_mac is None or src_mac == 'RANDOM':
        src_mac_resolved = generate_random_mac()
    else:
        src_mac_resolved = src_mac

    if dst_mac is None or dst_mac == 'RANDOM':
        dst_mac_resolved = generate_random_mac()
    else:
        dst_mac_resolved = dst_mac

    return {
        'src_ip': src_ip_resolved,
        'dst_ip': dst_ip_resolved,
        'src_port': src_port_resolved,
        'dst_port': dst_port_resolved,
        'src_mac': src_mac_resolved,
        'dst_mac': dst_mac_resolved
    }


def validate_network_params(
    src_ip: Optional[str],
    dst_ip: Optional[str],
    src_port: Optional[int],
    dst_port: Optional[int],
    src_mac: Optional[str],
    dst_mac: Optional[str],
    interval: float,
    interval_randomness: float
) -> None:
    """校验网络参数

    Raises:
        SystemExit: 参数不合法时退出程序
    """
    # 校验 IP 地址
    if src_ip and src_ip not in ('WAN', 'LAN'):
        if not validate_ip_address(src_ip):
            print(f"错误: 源 IP 地址格式错误: {src_ip}", file=sys.stderr)
            sys.exit(1)

    if dst_ip and dst_ip not in ('WAN', 'LAN'):
        if not validate_ip_address(dst_ip):
            print(f"错误: 目的 IP 地址格式错误: {dst_ip}", file=sys.stderr)
            sys.exit(1)

    # 校验端口
    if src_port is not None:
        if not (1 <= src_port <= MAX_EPHEMERAL_PORT):
            print(f"错误: 源端口范围错误: {src_port}，应为 1-65535", file=sys.stderr)
            sys.exit(1)

    if dst_port is not None:
        if not (1 <= dst_port <= MAX_EPHEMERAL_PORT):
            print(f"错误: 目的端口范围错误: {dst_port}，应为 1-65535", file=sys.stderr)
            sys.exit(1)

    # 校验 MAC 地址
    if src_mac and src_mac != 'RANDOM':
        normalized_mac = validate_mac_address(src_mac)
        if normalized_mac is None:
            print(f"错误: 源 MAC 地址格式错误: {src_mac}", file=sys.stderr)
            sys.exit(1)

    if dst_mac and dst_mac != 'RANDOM':
        normalized_mac = validate_mac_address(dst_mac)
        if normalized_mac is None:
            print(f"错误: 目的 MAC 地址格式错误: {dst_mac}", file=sys.stderr)
            sys.exit(1)

    # 校验时间间隔
    if interval <= 0:
        print(f"错误: 时间间隔必须大于 0: {interval}", file=sys.stderr)
        sys.exit(1)

    # 校验随机度
    if not (0 <= interval_randomness <= 1):
        print(f"错误: 时间间隔随机度范围错误: {interval_randomness}，应为 0.0-1.0", file=sys.stderr)
        sys.exit(1)


def build_pcap_from_json(
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
) -> dict:
    """将 JSON 文件或目录转换为 PCAP 文件

    Args:
        input_path: 输入 JSON 文件或目录路径
        output_path: 输出文件或目录路径（可选）
        req_key: JSON 请求字段键
        res_key: JSON 响应字段键
        net_type: 网络类型预设
        src_ip: 源 IP（可选）
        dst_ip: 目的 IP（可选）
        src_port: 源端口（可选）
        dst_port: 目的端口（可选）
        src_mac: 源 MAC（可选）
        dst_mac: 目的 MAC（可选）
        interval: 包时间间隔（秒）
        interval_rand: 间隔随机度（0-1）
        keep_alive: 长连接模式
        mtu: MTU 大小

    Returns:
        包含处理统计的字典
    """
    # 校验参数
    validate_network_params(
        src_ip, dst_ip, src_port, dst_port, src_mac, dst_mac,
        interval, interval_rand
    )

    # 确定输出路径
    if output_path is None:
        clean_input_path = input_path.rstrip('/\\')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"{clean_input_path}_{timestamp}"

    # 生成网络参数模板
    network_template = generate_network_params(
        src_ip, dst_ip, src_port, dst_port, src_mac, dst_mac, net_type
    )

    # 输出配置信息
    print(f"网络类型: {net_type}")
    print(f"网络配置模板: 源IP:{network_template['src_ip'] if src_ip else '随机'} -> "
          f"目的IP:{network_template['dst_ip'] if dst_ip else '随机'}")
    print(f"端口配置: 源端口:{src_port or '随机'} -> 目的端口:{dst_port or DEFAULT_HTTP_PORT}")
    print(f"时间间隔: {interval}秒 (随机度: {interval_rand * 100}%)")
    print(f"MTU 大小: {mtu}字节")
    print(f"连接模式: {'长连接' if keep_alive else '短连接'}")

    # 统计
    total_files = 0
    success_files = 0
    failed_files = []

    # 判断是文件还是目录
    if os.path.isfile(input_path):
        # 单文件处理
        input_files = [(input_path, output_path, os.path.basename(input_path))]
    else:
        # 目录遍历
        file_walker = FileWalker(input_path, output_path, suffix='.json')
        input_files = list(file_walker)

    for input_file_path, output_file_path, file_name in input_files:
        total_files += 1

        # 为每个文件生成随机的网络五元组
        random_params = generate_network_params(
            src_ip, dst_ip, src_port, dst_port, src_mac, dst_mac, net_type
        )

        # 创建数据包构建器
        packet_builder = PacketBuilder(
            src_ip=random_params['src_ip'],
            dst_ip=random_params['dst_ip'],
            src_port=random_params['src_port'],
            dst_port=random_params['dst_port'],
            src_mac=random_params['src_mac'],
            dst_mac=random_params['dst_mac'],
            interval=interval,
            interval_randomness=interval_rand,
            mtu=mtu,
            is_keep_alive=keep_alive
        )

        # 读取和解析 JSON 文件
        try:
            with open(input_file_path, 'r', encoding='utf-8') as json_file:
                json_data = json.load(json_file)
        except FileNotFoundError:
            print(f"错误: 文件不存在: {input_file_path}", file=sys.stderr)
            failed_files.append((file_name, "文件不存在"))
            continue
        except json.JSONDecodeError as e:
            print(f"错误: JSON 格式错误: {input_file_path}", file=sys.stderr)
            failed_files.append((file_name, f"JSON 格式错误: {e}"))
            continue
        except Exception as e:
            print(f"错误: 读取文件异常: {input_file_path}", file=sys.stderr)
            failed_files.append((file_name, str(e)))
            continue

        # 提取 HTTP 流量
        try:
            http_flows = extract_http_flows_from_json(json_data, req_key, res_key)
        except (ValueError, KeyError, binascii.Error, Exception) as e:
            print(f"错误: HTTP 流量提取失败: {input_file_path}: {e}", file=sys.stderr)
            failed_files.append((file_name, str(e)))
            continue

        # 构建 TCP 数据包
        try:
            tcp_packets = packet_builder.build_tcp_packets(http_flows)
        except Exception as e:
            print(f"错误: TCP 数据包构建失败: {input_file_path}: {e}", file=sys.stderr)
            failed_files.append((file_name, str(e)))
            continue

        # 生成 PCAP 文件
        pcap_file_path = os.path.splitext(output_file_path)[0] + '.pcap'
        try:
            wrpcap(pcap_file_path, tcp_packets)
            print(f"成功: 生成 PCAP 文件: {pcap_file_path}")
            success_files += 1
        except Exception as e:
            print(f"错误: 生成 PCAP 文件异常: {pcap_file_path}: {e}", file=sys.stderr)
            failed_files.append((file_name, str(e)))

    # 输出统计
    print(f"处理完成: 总文件数 {total_files}，成功 {success_files}，失败 {len(failed_files)}")

    return {
        'total': total_files,
        'success': success_files,
        'failed': failed_files,
        'output_path': output_path
    }


def main():
    parser = argparse.ArgumentParser(
        description="PCAP 构建工具 - 将 JSON 格式 HTTP 数据转换为 PCAP 包",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 单文件转换
  python pcap_build.py traffic.json

  # 指定输出路径
  python pcap_build.py traffic.json -o output.pcap

  # 目录批量处理
  python pcap_build.py ./json_dir/ -o ./output/

  # 使用网络类型预设
  python pcap_build.py traffic.json --net-type lan-wan

  # 自定义网络参数
  python pcap_build.py traffic.json --src-ip 10.0.0.1 --dst-ip 192.168.1.100 --dst-port 8080

  # 长连接模式
  python pcap_build.py traffic.json -k

网络类型预设:
  wan-lan: 外网 -> 内网（默认）
  lan-wan: 内网 -> 外网
  wan-wan: 外网 -> 外网
  lan-lan: 内网 -> 内网
"""
    )

    parser.add_argument("input_path", help="输入 JSON 文件或目录路径")
    parser.add_argument("-o", "--output", default=None,
                        help="输出路径（默认: {input}_{timestamp}）")
    parser.add_argument("--req-key", default="request_data_base64",
                        help="JSON 请求字段键（默认: request_data_base64）")
    parser.add_argument("--res-key", default="response_data_base64",
                        help="JSON 响应字段键（默认: response_data_base64）")
    parser.add_argument("--net-type", default="wan-lan",
                        choices=['wan-lan', 'lan-wan', 'wan-wan', 'lan-lan'],
                        help="网络类型预设（默认: wan-lan）")
    parser.add_argument("--src-ip", default=None,
                        help="源 IP（IP 地址或 WAN/LAN）")
    parser.add_argument("--dst-ip", default=None,
                        help="目的 IP（IP 地址或 WAN/LAN）")
    parser.add_argument("--src-port", type=int, default=None,
                        help="源端口（默认: 随机）")
    parser.add_argument("--dst-port", type=int, default=None,
                        help="目的端口（默认: 80）")
    parser.add_argument("--src-mac", default=None,
                        help="源 MAC（默认: 随机）")
    parser.add_argument("--dst-mac", default=None,
                        help="目的 MAC（默认: 随机）")
    parser.add_argument("-i", "--interval", type=float, default=0.01,
                        help="包时间间隔/秒（默认: 0.01）")
    parser.add_argument("--interval-rand", type=float, default=0.5,
                        help="间隔随机度 0-1（默认: 0.5）")
    parser.add_argument("-k", "--keep-alive", action="store_true",
                        help="长连接模式")
    parser.add_argument("--mtu", type=int, default=1500,
                        help="MTU 大小（默认: 1500）")

    args = parser.parse_args()

    build_pcap_from_json(
        input_path=args.input_path,
        output_path=args.output,
        req_key=args.req_key,
        res_key=args.res_key,
        net_type=args.net_type,
        src_ip=args.src_ip,
        dst_ip=args.dst_ip,
        src_port=args.src_port,
        dst_port=args.dst_port,
        src_mac=args.src_mac,
        dst_mac=args.dst_mac,
        interval=args.interval,
        interval_rand=args.interval_rand,
        keep_alive=args.keep_alive,
        mtu=args.mtu
    )


if __name__ == '__main__':
    main()
