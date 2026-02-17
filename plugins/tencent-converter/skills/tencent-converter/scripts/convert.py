#!/usr/bin/env python3
"""
Tencent Converter - 腾讯文档转 Markdown 独立版本

封装三步流水线的转换脚本:
  1. parser.py → intermediate.json
  2. format_parser.py → result.json
  3. to_markdown.py → output.md

特点：
  - 直接函数调用，无需 subprocess
  - 所有依赖内置，可独立发布
"""

import argparse
import json
import sys
from pathlib import Path

from parser import parse_opendoc
from format_parser import parse_format
from to_markdown import convert_to_markdown


def run_pipeline(
    input_file: Path, output_file: Path, keep_intermediate: bool, verbose: bool,
    page_url: str | None = None, cleanup_source: bool = False
) -> None:
    """运行三步流水线"""
    work_dir = input_file.parent
    base_name = input_file.stem.replace("_opendoc_response", "")

    # Step 1: parser → intermediate.json
    intermediate_file = work_dir / f"{base_name}_intermediate.json"
    if verbose:
        print(f"\n[Step 1] Parsing ultrabuf...")
    parse_opendoc(str(input_file), str(work_dir / base_name), verbose)

    # Step 2: format_parser → result.json
    result_file = work_dir / "result.json"
    if verbose:
        print(f"\n[Step 2] Parsing format...")
    parse_format(str(intermediate_file), str(result_file), verbose)

    # Step 3: markdown → output.md
    if verbose:
        print(f"\n[Step 3] Generating markdown...")
    convert_to_markdown(str(result_file), str(output_file), verbose, page_url=page_url)

    # 清理中间文件
    if not keep_intermediate:
        if intermediate_file.exists():
            intermediate_file.unlink()
            if verbose:
                print(f"[Cleanup] Removed: {intermediate_file}")
        if result_file.exists():
            result_file.unlink()
            if verbose:
                print(f"[Cleanup] Removed: {result_file}")

    # 清理源文件
    if cleanup_source and input_file.exists():
        input_file.unlink()
        if verbose:
            print(f"[Cleanup] Removed source: {input_file}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tencent Converter - 腾讯文档转 Markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s output/opendoc_response.json -o output/doc.md
  %(prog)s output/opendoc_response.json -o output/doc.md --keep-intermediate
  %(prog)s output/opendoc_response.json -o output/doc.md -v
        """,
    )
    parser.add_argument("input", help="opendoc_response.json file path")
    parser.add_argument(
        "-o", "--output", required=True, help="Output Markdown file path"
    )
    parser.add_argument(
        "--keep-intermediate",
        action="store_true",
        help="Keep intermediate files (intermediate.json, result.json)",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Explicitly clean up intermediate files (default behavior)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show verbose output"
    )
    parser.add_argument(
        "--page-url", metavar="URL", help="Document online URL for meta info"
    )
    parser.add_argument(
        "--cleanup-source", action="store_true", help="Remove source JSON after conversion"
    )
    args = parser.parse_args()

    input_file = Path(args.input)
    output_file = Path(args.output)

    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)

    # 确保输出目录存在
    output_file.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Tencent Converter - 腾讯文档转 Markdown")
    print("=" * 60)
    print(f"Input: {input_file}")
    print(f"Output: {output_file}")
    print(f"Keep intermediate: {args.keep_intermediate}")
    if args.page_url:
        print(f"Page URL: {args.page_url}")
    if args.cleanup_source:
        print("Cleanup source: enabled")

    run_pipeline(input_file, output_file, args.keep_intermediate, args.verbose,
                 page_url=args.page_url, cleanup_source=args.cleanup_source)

    print("\n" + "=" * 60)
    print(f"Conversion complete: {output_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()
