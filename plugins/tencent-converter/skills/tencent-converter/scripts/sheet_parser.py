#!/usr/bin/env python3
"""
腾讯文档表格解析器 - 统一入口

支持两种数据源:
1. API 数据 (dop-api/get/sheet) - 委托给 sheet_api_parser.py
2. 浏览器数据 (SpreadsheetApp.workbook.worksheetManager.sheetList)

浏览器数据结构:
{
  "name": "工作表名称",
  "id": "BB08J2",
  "cellDataGrid": {
    "usedRange": {"startRow": 0, "endRow": 10, "startCol": 0, "endCol": 5},
    "data": {
      "0": {"0": {"v": "值", "t": 4, "hyperlink": {...}}}
    }
  }
}
"""

import json
import sys
from pathlib import Path
from typing import Optional

try:
    from .sheet_enums import (
        SheetData, SpreadsheetData, CellData, HyperlinkInfo,
        detect_data_type, CELL_TYPE_STRING
    )
    from .sheet_api_parser import SheetApiParser
except ImportError:
    from sheet_enums import (
        SheetData, SpreadsheetData, CellData, HyperlinkInfo,
        detect_data_type, CELL_TYPE_STRING
    )
    from sheet_api_parser import SheetApiParser


def parse_sheet_data(input_file: str, output_file: Optional[str] = None, verbose: bool = False) -> SpreadsheetData:
    """
    统一解析入口

    Args:
        input_file: 输入 JSON 文件路径
        output_file: 输出 JSON 文件路径 (可选)
        verbose: 是否显示详细信息

    Returns:
        SpreadsheetData 对象
    """
    input_path = Path(input_file)

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    data_type = detect_data_type(data)

    if verbose:
        print(f"  数据类型: {data_type}")

    if data_type == "sheet":
        # 检查是 API 数据还是浏览器数据
        # API 数据特征: retcode 或 clientVars (含 related_sheet)
        if "retcode" in data or _has_related_sheet_in_data(data):
            # API 数据
            return _parse_api_data(data, output_file, verbose)
        else:
            # 浏览器数据
            return _parse_browser_data(data, output_file, verbose)
    else:
        raise ValueError(f"不支持的数据类型: {data_type}")


def _has_related_sheet_in_data(data: dict) -> bool:
    """检查数据中是否包含 related_sheet (API 格式)"""
    # 格式1: data.initialAttributedText.text[0].related_sheet
    try:
        iat = data.get("data", {}).get("initialAttributedText", {})
        text_list = iat.get("text", [])
        if text_list and isinstance(text_list[0], dict) and "related_sheet" in text_list[0]:
            return True
    except (KeyError, TypeError, IndexError):
        pass

    # 格式2: clientVars.collab_client_vars.initialAttributedText.text[0].related_sheet
    try:
        cv = data.get("clientVars", {})
        ccv = cv.get("collab_client_vars", {})
        text_list = ccv.get("initialAttributedText", {}).get("text", [])
        if text_list and isinstance(text_list[0], dict) and "related_sheet" in text_list[0]:
            return True
    except (KeyError, TypeError, IndexError):
        pass

    return False


def _parse_api_data(data: dict, output_file: Optional[str], verbose: bool) -> SpreadsheetData:
    """解析 API 数据

    支持两种格式:
    1. retcode 格式: data.initialAttributedText.text[0].related_sheet
    2. clientVars 格式: clientVars.collab_client_vars.initialAttributedText.text[0].related_sheet
    """
    parser = SheetApiParser(data)
    sheet_infos = parser.parse()

    if verbose and sheet_infos:
        print(f"  解析到 {len(sheet_infos)} 个工作表")

    # 转换为 SheetData 格式
    sheets: list[SheetData] = []
    for info in sheet_infos:
        if not info.is_visible:
            if verbose:
                print(f"  跳过隐藏工作表: {info.sheet_name}")
            continue

        # 检查是否有单元格数据
        if not info.cells:
            if verbose:
                print(f"  跳过空工作表: {info.sheet_name}")
            continue

        # 构建单元格矩阵
        cells = _build_cell_matrix(info.cells, info.max_row, info.max_col)

        sheets.append(SheetData(
            name=info.sheet_name,
            id=info.sheet_id,
            state=info.state,
            used_range={
                "startRow": 0,
                "endRow": info.max_row,
                "startCol": 0,
                "endCol": info.max_col,
            },
            cells=cells,
        ))

    result = SpreadsheetData(sheets=sheets)

    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

    return result


def _build_cell_matrix(cells: list, max_row: int, max_col: int) -> list[list[CellData]]:
    """构建单元格矩阵"""
    # 创建空矩阵
    matrix: list[list[CellData]] = [
        [CellData(row=r, col=c) for c in range(max_col + 1)]
        for r in range(max_row + 1)
    ]

    # 填充数据
    for cell in cells:
        if 0 <= cell.row <= max_row and 0 <= cell.col <= max_col:
            # 从 hyperlinks 列表提取第一个超链接（如果有）
            hyperlink = cell.hyperlinks[0] if cell.hyperlinks else None
            matrix[cell.row][cell.col] = CellData(
                row=cell.row,
                col=cell.col,
                value=cell.value,
                hyperlink=hyperlink,
            )

    return matrix


def _parse_browser_data(data: dict | list, output_file: Optional[str], verbose: bool) -> SpreadsheetData:
    """解析浏览器数据"""
    sheets: list[SheetData] = []

    # 数据可能是列表或单个对象
    sheet_list = data if isinstance(data, list) else [data]

    for sheet in sheet_list:
        if not isinstance(sheet, dict):
            continue

        sheet_data = _parse_browser_sheet(sheet)
        if sheet_data:
            if not sheet_data.is_visible:
                if verbose:
                    print(f"  跳过隐藏工作表: {sheet_data.name}")
                continue

            if sheet_data.is_empty:
                if verbose:
                    print(f"  跳过空工作表: {sheet_data.name}")
                continue

            sheets.append(sheet_data)

    result = SpreadsheetData(sheets=sheets)

    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

    return result


def _parse_browser_sheet(sheet: dict) -> Optional[SheetData]:
    """解析单个浏览器工作表数据

    支持两种数据格式:
    1. 原始浏览器数据: 包含 cellDataGrid.data 字段
    2. 简化格式: 直接包含 cells 数组
    """
    name = sheet.get("name", "")
    sheet_id = sheet.get("id", "")
    state = sheet.get("state", 1)  # 默认可见

    # 检查是否是简化格式 (直接包含 cells 数组)
    if "cells" in sheet and isinstance(sheet["cells"], list):
        return _parse_simplified_sheet(sheet, name, sheet_id, state)

    # 原始浏览器数据格式
    cell_grid = sheet.get("cellDataGrid", {})
    used_range = cell_grid.get("usedRange", {})
    data = cell_grid.get("data", {})

    # 检查是否为空
    end_row = used_range.get("endRow", -1)
    if end_row < 0:
        return SheetData(
            name=name,
            id=sheet_id,
            state=state,
            used_range=used_range,
            cells=[],
        )

    # 构建单元格矩阵
    start_row = used_range.get("startRow", 0)
    end_row = used_range.get("endRow", 0)
    start_col = used_range.get("startCol", 0)
    end_col = used_range.get("endCol", 0)

    # 创建矩阵
    cells: list[list[CellData]] = [
        [CellData(row=r, col=c) for c in range(end_col - start_col + 1)]
        for r in range(end_row - start_row + 1)
    ]

    # 填充数据
    for row_key, row_data in data.items():
        try:
            row_idx = int(row_key) - start_row
            if row_idx < 0 or row_idx >= len(cells):
                continue
        except ValueError:
            continue

        if not isinstance(row_data, dict):
            continue

        for col_key, cell_data in row_data.items():
            try:
                col_idx = int(col_key) - start_col
                if col_idx < 0 or col_idx >= len(cells[row_idx]):
                    continue
            except ValueError:
                continue

            if not isinstance(cell_data, dict):
                continue

            # 提取单元格值
            value = cell_data.get("v", "")
            if value is None:
                value = ""

            # 转换为字符串
            if not isinstance(value, str):
                value = str(value)

            # 提取超链接
            hyperlink = None
            link_data = cell_data.get("hyperlink")
            if link_data and isinstance(link_data, dict):
                url = link_data.get("url", "")
                display_text = link_data.get("display_text", value)
                if url:
                    hyperlink = HyperlinkInfo(url=url, display_text=display_text)

            cells[row_idx][col_idx] = CellData(
                row=row_idx,
                col=col_idx,
                value=value,
                hyperlink=hyperlink,
            )

    return SheetData(
        name=name,
        id=sheet_id,
        state=state,
        used_range=used_range,
        cells=cells,
    )


def _parse_simplified_sheet(sheet: dict, name: str, sheet_id: str, state: int) -> Optional[SheetData]:
    """解析简化格式的工作表数据

    格式:
    {
      "name": "工作表名称",
      "id": "ygvk80",
      "usedRange": {"startRow": 0, "endRow": 24, "startCol": 0, "endCol": 3},
      "cells": [{"row": 0, "col": 0, "value": "值", "hyperlink": {...}}, ...]
    }
    """
    used_range = sheet.get("usedRange", {})
    cells_list = sheet.get("cells", [])

    # 检查是否为空
    end_row = used_range.get("endRow", -1)
    if end_row < 0 or not cells_list:
        return SheetData(
            name=name,
            id=sheet_id,
            state=state,
            used_range=used_range,
            cells=[],
        )

    # 计算实际使用的范围
    max_row = 0
    max_col = 0
    for cell in cells_list:
        if cell.get("row", 0) > max_row:
            max_row = cell["row"]
        if cell.get("col", 0) > max_col:
            max_col = cell["col"]

    # 创建矩阵
    cells: list[list[CellData]] = [
        [CellData(row=r, col=c) for c in range(max_col + 1)]
        for r in range(max_row + 1)
    ]

    # 填充数据
    for cell_data in cells_list:
        row = cell_data.get("row", 0)
        col = cell_data.get("col", 0)
        value = cell_data.get("value", "")

        # 转换为字符串
        if not isinstance(value, str):
            value = str(value)

        # 提取超链接
        hyperlink = None
        link_data = cell_data.get("hyperlink")
        if link_data and isinstance(link_data, dict):
            url = link_data.get("url", "")
            display_text = link_data.get("displayText") or link_data.get("display_text", value)
            if url:
                hyperlink = HyperlinkInfo(url=url, display_text=display_text)

        if 0 <= row <= max_row and 0 <= col <= max_col:
            cells[row][col] = CellData(
                row=row,
                col=col,
                value=value,
                hyperlink=hyperlink,
            )

    return SheetData(
        name=name,
        id=sheet_id,
        state=state,
        used_range={
            "startRow": 0,
            "endRow": max_row,
            "startCol": 0,
            "endCol": max_col,
        },
        cells=cells,
    )


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='腾讯文档表格解析器')
    parser.add_argument('input', help='输入文件路径 (.json)')
    parser.add_argument('-o', '--output', help='输出文件路径')
    parser.add_argument('-v', '--verbose', action='store_true', help='显示详细信息')

    args = parser.parse_args()

    print("=" * 60)
    print("腾讯文档表格解析器")
    print("=" * 60)

    try:
        result = parse_sheet_data(args.input, args.output, args.verbose)

        print(f"\n解析完成: {len(result.sheets)} 个工作表")
        for sheet in result.sheets:
            cell_count = sum(len(row) for row in sheet.cells)
            print(f"  - {sheet.name} ({sheet.id}): {sheet.row_count} 行 x {sheet.col_count} 列, {cell_count} 个单元格")

    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
