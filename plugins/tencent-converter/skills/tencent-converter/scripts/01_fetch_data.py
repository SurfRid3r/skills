#!/usr/bin/env python3
"""
腾讯文档数据获取脚本

使用 chrome-devtools MCP 访问目标文档，拦截 opendoc API 请求，
提取 initialAttributedText.text[0] 并保存。
"""

import base64
import json
import sys
from pathlib import Path


def extract_initial_text_from_opendoc(opendoc_data: dict) -> str | None:
    """从 opendoc API 响应中提取 initialAttributedText.text[0]"""
    client_vars = opendoc_data.get('clientVars', {})
    collab_vars = client_vars.get('collab_client_vars', {})
    text_array = collab_vars.get('initialAttributedText', {}).get('text', [])

    if not text_array:
        print("错误: text 数组为空")
        return None

    base64_data = text_array[0]

    # 验证是否为有效的 Base64
    decoded = base64.b64decode(base64_data)
    print(f"验证: Base64 解码成功，数据长度: {len(decoded)} 字节")
    return base64_data


def save_opendoc_response(opendoc_data: dict, output_dir: Path) -> Path:
    """保存完整的 opendoc API 响应"""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "opendoc.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(opendoc_data, f, ensure_ascii=False, indent=2)

    print(f"已保存: {output_file}")
    return output_file


def save_decoded_protobuf(base64_data: str, output_dir: Path) -> Path:
    """Base64 解码并保存二进制数据"""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "decoded_protobuf.bin"

    decoded = base64.b64decode(base64_data)
    with open(output_file, 'wb') as f:
        f.write(decoded)

    print(f"已保存: {output_file} ({len(decoded)} 字节)")
    return output_file


def load_from_file(opendoc_json_path: str) -> tuple[dict, str]:
    """从本地 opendoc.json 文件加载数据"""
    with open(opendoc_json_path, 'r', encoding='utf-8') as f:
        opendoc_data = json.load(f)

    base64_data = extract_initial_text_from_opendoc(opendoc_data)
    if not base64_data:
        raise ValueError("无法从 opendoc.json 提取 initialAttributedText.text[0]")

    return opendoc_data, base64_data


def fetch_with_mcp(doc_url: str, output_dir: Path) -> tuple[dict, str]:
    """使用 chrome-devtools MCP 获取数据（需要 MCP 支持）"""
    print("警告: 此函数需要 chrome-devtools MCP 支持")
    print("请在支持 MCP 的环境中运行，或使用已有的 opendoc.json 文件")
    print()
    print("手动操作步骤:")
    print("1. 在浏览器中打开目标文档")
    print("2. 打开开发者工具 -> Network 面板")
    print("3. 查找 opendoc API 请求")
    print("4. 复制响应内容保存为 opendoc.json")
    print(f"5. 运行: python {__file__} <opendoc.json>")

    raise NotImplementedError("需要 chrome-devtools MCP 支持")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='获取腾讯文档 opendoc 数据')
    parser.add_argument('input', nargs='?', help='opendoc.json 文件路径')
    parser.add_argument('-o', '--output', default='output/case2', help='输出目录')
    parser.add_argument('-u', '--url', help='腾讯文档 URL（需要 MCP 支持）')
    args = parser.parse_args()

    output_dir = Path(args.output)

    print("=" * 60)
    print("腾讯文档数据获取")
    print("=" * 60)

    if args.input:
        print(f"从文件加载: {args.input}")
        opendoc_data, base64_data = load_from_file(args.input)
    else:
        try:
            opendoc_data, base64_data = fetch_with_mcp(args.url or '', output_dir)
        except NotImplementedError:
            print()
            print("错误: 未提供 opendoc.json 文件且 MCP 不可用")
            print()
            print("使用方法:")
            print("  1. 获取 opendoc.json（使用浏览器开发者工具）")
            print(f"  2. 运行: python {__file__} <opendoc.json>")
            sys.exit(1)

    print()
    print("数据验证:")
    print(f"  opendoc 数据: {'ok' if opendoc_data else 'fail'}")
    print(f"  Base64 数据: {'ok' if base64_data else 'fail'}")

    if not base64_data:
        print("\n错误: 无法提取 Base64 数据")
        sys.exit(1)

    print("\n保存文件:")
    save_opendoc_response(opendoc_data, output_dir)
    save_decoded_protobuf(base64_data, output_dir)
    print("\n完成!")


if __name__ == "__main__":
    main()
