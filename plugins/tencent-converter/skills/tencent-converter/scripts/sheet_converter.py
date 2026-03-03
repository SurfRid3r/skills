#!/usr/bin/env python3
"""
腾讯文档表格转 Markdown 转换器

将 SheetData 转换为 Markdown 表格格式。
"""

import sys
from pathlib import Path

try:
    from .sheet_enums import SheetData, SpreadsheetData, CellData
    from .sheet_parser import parse_sheet_data
    from .utils import generate_front_matter, escape_cell
except ImportError:
    from sheet_enums import SheetData, SpreadsheetData, CellData
    from sheet_parser import parse_sheet_data
    from utils import generate_front_matter, escape_cell


class SheetToMarkdown:
    """表格转 Markdown 转换器"""

    def __init__(self, spreadsheet: SpreadsheetData):
        self.spreadsheet = spreadsheet

    def convert(self, page_url: str | None = None, metadata: dict | None = None) -> str:
        """转换所有工作表为 Markdown"""
        parts = []

        # 生成 YAML Front Matter
        if metadata or page_url:
            front_matter = generate_front_matter(
                title=metadata.get("title") if metadata else None,
                source=page_url,
                doc_type="sheet",
                created=metadata.get("created") if metadata else None,
                modified=metadata.get("modified") if metadata else None,
            )
            parts.append(front_matter)

        for i, sheet in enumerate(self.spreadsheet.sheets):
            if i > 0:
                parts.append("\n\n---\n\n")
            parts.append(self._sheet_to_markdown(sheet))
        return "".join(parts)

    def _sheet_to_markdown(self, sheet: SheetData) -> str:
        """转换单个工作表"""
        if sheet.is_empty or not sheet.cells:
            return f"## {sheet.name}\n\n*Empty sheet*\n"

        parts = [f"## {sheet.name}\n\n"]
        col_count = sheet.col_count

        # 表头
        parts.append("| " + " | ".join(self._format_cell(c) for c in sheet.cells[0][:col_count]) + " |\n")
        parts.append("| " + " | ".join(["---"] * col_count) + " |\n")

        # 数据行
        for row in sheet.cells[1:]:
            parts.append("| " + " | ".join(self._format_cell(c) for c in row[:col_count]) + " |\n")

        return "".join(parts)

    def _format_cell(self, cell: CellData) -> str:
        """格式化单元格"""
        if cell.hyperlink:
            display = cell.hyperlink.display_text or cell.value
            return f"[{escape_cell(display)}]({cell.hyperlink.url})"
        return escape_cell(cell.value)


def convert_sheet_to_markdown(
    input_file: str,
    output_file: str,
    verbose: bool = False,
    page_url: str | None = None,
    metadata: dict | None = None
) -> str:
    """转换表格为 Markdown，返回 Markdown 字符串"""
    if verbose:
        print(f"  输入: {input_file}")

    spreadsheet = parse_sheet_data(input_file, verbose=verbose)

    if verbose:
        print(f"  工作表数量: {len(spreadsheet.sheets)}")

    converter = SheetToMarkdown(spreadsheet)
    markdown = converter.convert(page_url, metadata)

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding='utf-8')

    if verbose:
        print(f"  输出: {output_file}")

    return markdown


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='腾讯文档表格转 Markdown')
    parser.add_argument('input', help='输入文件路径 (.json)')
    parser.add_argument('-o', '--output', required=True, help='输出 Markdown 文件路径')
    parser.add_argument('-v', '--verbose', action='store_true', help='显示详细信息')

    args = parser.parse_args()

    print("=" * 60)
    print("腾讯文档表格转 Markdown")
    print("=" * 60)

    try:
        markdown = convert_sheet_to_markdown(args.input, args.output, args.verbose)

        print("\n" + "=" * 60)
        print(f"转换完成: {args.output}")
        print("=" * 60)

        if args.verbose:
            print("\n预览:")
            print("-" * 40)
            preview = markdown[:500]
            if len(markdown) > 500:
                preview += "\n..."
            print(preview)

    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
