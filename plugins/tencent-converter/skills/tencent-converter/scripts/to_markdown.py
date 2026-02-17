#!/usr/bin/env python3
"""
腾讯文档 result.json 到 Markdown 转换器

使用方式：
    python3 to_markdown.py result.json -o output.md
"""
import argparse
from pathlib import Path

from markdown_generator import TencentDocToMarkdown


def convert_to_markdown(input_file: str, output_file: str | None, verbose: bool = False, stats: bool = False, page_url: str | None = None) -> str:
    """将 result.json 转换为 Markdown

    Args:
        input_file: result.json 文件路径
        output_file: 输出 Markdown 文件路径（可选）
        verbose: 是否显示详细信息
        stats: 是否显示统计信息
        page_url: 文档在线链接，用于生成 meta 信息

    Returns:
        Markdown 内容
    """
    converter = TencentDocToMarkdown(input_file)
    markdown = converter.convert(page_url)

    if verbose or stats:
        stat_info = converter.get_statistics()
        print("\n统计信息:")
        print(f"  总章节数: {stat_info['total_sections']}")
        print(f"  标题数: {stat_info['heading_count']}")
        print(f"  段落数: {stat_info['paragraph_count']}")
        print(f"  列表数: {stat_info['list_count']}")
        print(f"  代码块数: {stat_info['code_block_count']}")
        print(f"  图片数: {stat_info['image_count']}")
        print(f"  超链接数: {stat_info['hyperlink_count']}")

        if verbose and stat_info['images_list']:
            print("\n图片列表:")
            for i, img in enumerate(stat_info['images_list']):
                url = img.get('url', '')
                width = img.get('width')
                height = img.get('height')
                size = f" ({width}x{height})" if width and height else ""
                print(f"  [{i + 1}] {url}{size}")

    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown)
        print(f"\n输出已保存: {output_path}")

    return markdown


def main():
    parser = argparse.ArgumentParser(description="腾讯文档 result.json 到 Markdown 转换器")
    parser.add_argument("input", help="输入文件路径 (result.json)")
    parser.add_argument("-o", "--output", help="输出文件路径 (.md)")
    parser.add_argument("-s", "--stats", action="store_true", help="显示统计信息")
    parser.add_argument("-v", "--verbose", action="store_true", help="显示详细信息")

    args = parser.parse_args()

    print("=" * 60)
    print("腾讯文档到 Markdown 转换器")
    print("=" * 60)
    print(f"输入: {args.input}")

    markdown = convert_to_markdown(args.input, args.output, args.verbose, args.stats)

    print(f"Markdown 长度: {len(markdown)} 字符")

    if not args.output:
        print("\n" + markdown[:1000])
        if len(markdown) > 1000:
            print(f"\n... (还有 {len(markdown) - 1000} 字符)")


if __name__ == "__main__":
    main()
