#!/usr/bin/env python3
"""
腾讯文档表格转 Markdown 转换器

将 SheetData 转换为 Markdown 表格格式。

输出格式:
```markdown
## 工作表名称

| 列1 | 列2 | 列3 |
|-----|-----|-----|
| 数据 | 数据 | 数据 |

---

## 另一个工作表

| ... |
```
"""

import sys
from pathlib import Path
from typing import Optional

try:
    from .sheet_enums import SheetData, SpreadsheetData, CellData
    from .sheet_parser import parse_sheet_data
except ImportError:
    from sheet_enums import SheetData, SpreadsheetData, CellData
    from sheet_parser import parse_sheet_data


class SheetToMarkdown:
    """表格转 Markdown 转换器"""

    def __init__(self, spreadsheet: SpreadsheetData):
        self.spreadsheet = spreadsheet

    def convert(self) -> str:
        """
        转换所有工作表为 Markdown

        Returns:
            Markdown 字符串
        """
        parts = []

        for i, sheet in enumerate(self.spreadsheet.sheets):
            if i > 0:
                parts.append("\n\n---\n\n")

            parts.append(self._sheet_to_markdown(sheet))

        return "".join(parts)

    def _sheet_to_markdown(self, sheet: SheetData) -> str:
        """转换单个工作表"""
        parts = []

        # 工作表标题
        parts.append(f"## {sheet.name}\n\n")

        # 空工作表
        if sheet.is_empty or not sheet.cells:
            parts.append("*Empty sheet*\n")
            return "".join(parts)

        # 使用工作表的实际列数
        col_count = sheet.col_count

        # 生成表格
        # 表头 (第一行)
        if sheet.cells:
            header_cells = sheet.cells[0][:col_count]
            parts.append("|")
            for cell in header_cells:
                parts.append(f" {self._format_cell(cell)} |")
            parts.append("\n")

            # 分隔符
            parts.append("|")
            for _ in range(col_count):
                parts.append("-----|")
            parts.append("\n")

            # 数据行
            for row in sheet.cells[1:]:
                parts.append("|")
                for cell in row[:col_count]:
                    parts.append(f" {self._format_cell(cell)} |")
                parts.append("\n")

        return "".join(parts)

    def _format_cell(self, cell: CellData) -> str:
        """格式化单元格"""
        if cell.hyperlink:
            # 超链接格式: [显示文本](URL)
            display = cell.hyperlink.display_text or cell.value
            return f"[{self._escape_cell(display)}]({cell.hyperlink.url})"

        return self._escape_cell(cell.value)

    def _escape_cell(self, text: str) -> str:
        """转义单元格特殊字符"""
        if not text:
            return ""

        # 换行符替换为 <br>
        text = text.replace("\n", "<br>")

        # 转义管道符
        text = text.replace("|", "\\|")

        # 移除其他控制字符
        result = []
        for char in text:
            if ord(char) >= 32 or ord(char) > 127:
                result.append(char)
            elif char in "\t":
                result.append(" ")

        return "".join(result)


def convert_sheet_to_markdown(input_file: str, output_file: str, verbose: bool = False) -> str:
    """
    转换表格为 Markdown

    Args:
        input_file: 输入 JSON 文件路径
        output_file: 输出 Markdown 文件路径
        verbose: 是否显示详细信息

    Returns:
        Markdown 字符串
    """
    if verbose:
        print(f"  输入: {input_file}")

    # 解析数据
    spreadsheet = parse_sheet_data(input_file, verbose=verbose)

    if verbose:
        print(f"  工作表数量: {len(spreadsheet.sheets)}")

    # 转换为 Markdown
    converter = SheetToMarkdown(spreadsheet)
    markdown = converter.convert()

    # 保存输出
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown)

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
            # 显示前 500 字符
            preview = markdown[:500]
            if len(markdown) > 500:
                preview += "\n..."
            print(preview)

    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
