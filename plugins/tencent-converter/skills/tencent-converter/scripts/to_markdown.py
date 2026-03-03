#!/usr/bin/env python3
"""
腾讯文档 result.json 到 Markdown 转换器

使用方式：
    python3 to_markdown.py result.json -o output.md
"""
import argparse
import sys
from pathlib import Path

# 添加脚本目录到 sys.path
_SCRIPT_DIR = Path(__file__).parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from markdown_generator import TencentDocToMarkdown


def convert_to_markdown(
    input_file: str,
    output_file: str | None,
    verbose: bool = False,
    stats: bool = False,
    page_url: str | None = None,
    doc_type: str = "doc"
) -> tuple[str, str | None]:
    """将 result.json 转换为 Markdown，返回 (Markdown 内容, 文档标题) 元组"""
    converter = TencentDocToMarkdown(input_file)
    markdown = converter.convert(page_url, doc_type)
    title = converter.get_title()

    if verbose or stats:
        stat_info = converter.get_statistics()
        print("\n统计信息:")
        for key, label in [
            ("total_sections", "总章节数"),
            ("heading_count", "标题数"),
            ("paragraph_count", "段落数"),
            ("list_count", "列表数"),
            ("code_block_count", "代码块数"),
            ("image_count", "图片数"),
            ("hyperlink_count", "超链接数"),
        ]:
            print(f"  {label}: {stat_info[key]}")

        if verbose and stat_info['images_list']:
            print("\n图片列表:")
            for i, img in enumerate(stat_info['images_list'], 1):
                url = img.get('url', '')
                size = f" ({img['width']}x{img['height']})" if img.get('width') else ""
                print(f"  [{i}] {url}{size}")

    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding='utf-8')
        print(f"\n输出已保存: {output_path}")

    return markdown, title


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

    markdown, title = convert_to_markdown(args.input, args.output, args.verbose, args.stats)

    print(f"Markdown 长度: {len(markdown)} 字符")
    if title:
        print(f"文档标题: {title}")

    if not args.output:
        preview = markdown[:1000]
        print("\n" + preview)
        if len(markdown) > 1000:
            print(f"\n... (还有 {len(markdown) - 1000} 字符)")


if __name__ == "__main__":
    main()
