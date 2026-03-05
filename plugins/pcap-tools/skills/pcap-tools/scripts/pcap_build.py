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
import random
import sys
import time
from datetime import datetime
from typing import Optional

from scapy.all import Ether, IP, TCP, Raw, wrpcap

from utils.network import (
    get_ip_generator,
    generate_random_mac,
    generate_random_client_port,
    DEFAULT_HTTP_PORT,
)


# 默认选项配置
DEFAULT_OPTIONS = {
    'keep_alive': False,
    'interval': 0.01,
    'interval_randomness': 0.5,
    'mtu': 1500,
    'flow_gap': 0.5
}


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
        self.max_payload_size = mtu - 40  # IP(20) + TCP(20) headers
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
            chunk_size = min(self.max_payload_size, data_len - offset)
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


def extract_traffic_flows_from_json(
    json_data: dict,
    request_field_key: str = 'request_data_base64',
    response_field_key: str = 'response_data_base64'
) -> list:
    """从 JSON 数据中提取流量（新格式）

    支持新格式：
    {
      "traffic_flows": [
        {
          "network_params": {...},
          "packets": [
            {"request_data_base64": "...", "response_data_base64": "..."}
          ]
        }
      ]
    }

    Args:
        json_data: JSON 数据字典
        request_field_key: 请求字段的键名
        response_field_key: 响应字段的键名

    Returns:
        列表，每项包含 {'network_params': dict, 'packets': [{'request': bytes, 'response': bytes}]}

    Raises:
        ValueError: JSON 数据格式错误
        binascii.Error: Base64 解码失败
    """
    if not isinstance(json_data, dict):
        raise ValueError(f"JSON 数据格式错误，期望字典类型")

    traffic_flows_raw = json_data.get('traffic_flows', [])
    if not traffic_flows_raw:
        raise ValueError("JSON 中缺少 traffic_flows 数组或数组为空")

    traffic_flows = []

    for flow_index, flow_item in enumerate(traffic_flows_raw, 1):
        # 提取 network_params（必需）
        network_params = flow_item.get('network_params')
        if network_params is None:
            raise ValueError(f"第 {flow_index} 个流量缺少必需的 network_params")

        # 验证必需字段
        if 'src_ip' not in network_params or 'dst_ip' not in network_params:
            raise ValueError(f"第 {flow_index} 个流量的 network_params 缺少 src_ip 或 dst_ip")

        # 提取 packets 数组
        packets_raw = flow_item.get('packets', [])
        if not packets_raw:
            raise ValueError(f"第 {flow_index} 个流量缺少 packets 数组或数组为空")

        packets = []
        for pkt_index, pkt_item in enumerate(packets_raw, 1):
            request_base64 = pkt_item.get(request_field_key)
            response_base64 = pkt_item.get(response_field_key)

            if not request_base64 or not response_base64:
                raise ValueError(
                    f"第 {flow_index} 个流量的第 {pkt_index} 个包缺少 "
                    f"'{request_field_key}' 或 '{response_field_key}'"
                )

            try:
                request_bytes = base64.b64decode(request_base64)
                response_bytes = base64.b64decode(response_base64)
            except binascii.Error as e:
                raise binascii.Error(
                    f"第 {flow_index} 个流量的第 {pkt_index} 个包 Base64 解码失败: {e}"
                )

            packets.append({
                'request': request_bytes,
                'response': response_bytes
            })

        traffic_flows.append({
            'network_params': network_params,
            'packets': packets
        })

    return traffic_flows


def resolve_network_params(network_params: dict) -> dict:
    """解析网络参数，处理特殊值

    Args:
        network_params: 原始网络参数

    Returns:
        解析后的网络参数（所有特殊值已转换为具体值）
    """
    resolved = {}

    # 解析 IP 地址
    for key in ['src_ip', 'dst_ip']:
        value = network_params.get(key)
        if value in ('WAN', 'LAN'):
            resolved[key] = get_ip_generator(value)()
        else:
            resolved[key] = value

    # 解析端口
    src_port = network_params.get('src_port')
    if src_port is None or src_port == 'CLIENT':
        resolved['src_port'] = generate_random_client_port()
    else:
        resolved['src_port'] = src_port

    dst_port = network_params.get('dst_port')
    if dst_port is None:
        resolved['dst_port'] = DEFAULT_HTTP_PORT
    else:
        resolved['dst_port'] = dst_port

    # 解析 MAC 地址
    for key in ['src_mac', 'dst_mac']:
        value = network_params.get(key)
        if value is None or value == 'RANDOM':
            resolved[key] = generate_random_mac()
        else:
            resolved[key] = value

    return resolved


def build_pcap_from_json(
    input_path: str,
    output_path: Optional[str] = None
) -> dict:
    """将 JSON 文件转换为 PCAP 文件

    Args:
        input_path: 输入 JSON 文件路径
        output_path: 输出文件路径（可选）

    Returns:
        包含处理统计的字典
    """
    # 确定输出路径
    if output_path is None:
        clean_input_path = input_path.rstrip('/\\')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"{clean_input_path}_{timestamp}.pcap"

    # 读取 JSON 文件
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"文件不存在: {input_path}")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"JSON 格式错误: {e.msg}", e.doc, e.pos)

    # 合并选项（JSON 中的 options 覆盖默认值）
    options = {**DEFAULT_OPTIONS, **json_data.get('options', {})}

    # 提取选项参数
    keep_alive = options['keep_alive']
    interval = options['interval']
    interval_rand = options['interval_randomness']
    mtu = options['mtu']
    flow_gap = options['flow_gap']

    # 校验时间间隔参数
    if interval <= 0:
        raise ValueError(f"时间间隔必须大于 0: {interval}")
    if not (0 <= interval_rand <= 1):
        raise ValueError(f"时间间隔随机度范围错误: {interval_rand}，应为 0.0-1.0")

    # 提取流量
    traffic_flows = extract_traffic_flows_from_json(json_data)

    # 输出配置信息
    print(f"流量数量: {len(traffic_flows)} 个 TCP 连接")
    print(f"连接模式: {'长连接' if keep_alive else '短连接'}")
    print(f"时间间隔: {interval}秒 (随机度: {interval_rand * 100}%)")
    print(f"MTU 大小: {mtu}字节")

    # 构建所有数据包
    all_packets = []
    current_timestamp = time.time()

    for flow_index, flow in enumerate(traffic_flows):
        # 解析网络参数
        resolved_params = resolve_network_params(flow['network_params'])

        # 创建数据包构建器
        builder = PacketBuilder(
            src_ip=resolved_params['src_ip'],
            dst_ip=resolved_params['dst_ip'],
            src_port=resolved_params['src_port'],
            dst_port=resolved_params['dst_port'],
            src_mac=resolved_params['src_mac'],
            dst_mac=resolved_params['dst_mac'],
            interval=interval,
            interval_randomness=interval_rand,
            mtu=mtu,
            is_keep_alive=keep_alive,
            start_timestamp=current_timestamp
        )

        # 构建 TCP 数据包
        flow_packets = builder.build_tcp_packets(flow['packets'])
        all_packets.extend(flow_packets)

        # 更新下一条流的起始时间戳
        if flow_index < len(traffic_flows) - 1:
            current_timestamp = builder.current_timestamp + flow_gap

    # 保存 PCAP 文件
    wrpcap(output_path, all_packets)
    print(f"成功: 生成 PCAP 文件: {output_path}")
    print(f"总包数: {len(all_packets)} 包")

    return {
        'output_path': output_path,
        'total_flows': len(traffic_flows),
        'total_packets': len(all_packets)
    }


def main():
    parser = argparse.ArgumentParser(
        description="PCAP 构建工具 - 将 JSON 格式 HTTP 数据转换为 PCAP 包",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python pcap_build.py traffic.json
  python pcap_build.py traffic.json -o output.pcap

JSON 格式:
  {
    "options": {
      "keep_alive": false,
      "interval": 0.01,
      "interval_randomness": 0.5,
      "mtu": 1500,
      "flow_gap": 0.5
    },
    "traffic_flows": [
      {
        "network_params": {
          "src_ip": "10.0.0.1",
          "dst_ip": "192.168.1.100",
          "src_port": 54321,
          "dst_port": 80
        },
        "packets": [
          {"request_data_base64": "...", "response_data_base64": "..."}
        ]
      }
    ]
  }

options 字段说明（全部可选）:
  keep_alive: 长连接模式（默认: false）
  interval: 包时间间隔/秒（默认: 0.01）
  interval_randomness: 间隔随机度 0-1（默认: 0.5）
  mtu: MTU 大小（默认: 1500）
  flow_gap: TCP 连接之间的时间间隔/秒（默认: 0.5）

特殊值说明:
  src_ip/dst_ip: WAN (随机公网IP), LAN (随机私网IP)
  src_port: CLIENT (随机客户端端口)
  src_mac/dst_mac: RANDOM (随机MAC地址)
"""
    )

    parser.add_argument("input_path", help="输入 JSON 文件路径")
    parser.add_argument("-o", "--output", default=None,
                        help="输出文件路径（默认: {input}_{timestamp}.pcap）")

    args = parser.parse_args()

    try:
        build_pcap_from_json(
            input_path=args.input_path,
            output_path=args.output
        )
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
