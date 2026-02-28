#!/usr/bin/env python3
"""
腾讯文档表格 - 数据模型和枚举定义

定义表格解析和转换所需的数据结构。
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class HyperlinkInfo:
    """超链接信息"""
    url: str
    display_text: str = ""


@dataclass
class TabInfo:
    """工作表标签信息（从 /dop-api/get/tabs 获取）"""
    tab_id: str       # 工作表 ID (如 "BB08J2")
    tab_name: str     # 工作表名称
    hidden: bool      # 是否隐藏

    @property
    def is_visible(self) -> bool:
        """工作表是否可见"""
        return not self.hidden

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "tab_id": self.tab_id,
            "tab_name": self.tab_name,
            "hidden": self.hidden,
        }


@dataclass
class SheetCell:
    """单元格数据"""
    row: int
    col: int
    value: str = ""
    hyperlinks: list[HyperlinkInfo] = field(default_factory=list)

    def to_dict(self) -> dict:
        """转换为字典"""
        result = {
            "row": self.row,
            "col": self.col,
            "value": self.value,
        }
        if self.hyperlinks:
            result["hyperlinks"] = [
                {"url": h.url, "display_text": h.display_text}
                for h in self.hyperlinks
            ]
        return result


@dataclass
class SheetInfo:
    """
    API 解析结果 - 单个工作表信息

    从 dop-api/get/sheet API 响应解析的数据结构。
    """
    sheet_id: str
    sheet_name: str
    cells: list[SheetCell] = field(default_factory=list)
    state: int = 1  # 1=可见, 2=隐藏
    max_row: int = 0
    max_col: int = 0

    @property
    def is_visible(self) -> bool:
        """工作表是否可见"""
        return self.state == 1

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "sheet_id": self.sheet_id,
            "sheet_name": self.sheet_name,
            "state": self.state,
            "max_row": self.max_row,
            "max_col": self.max_col,
            "cells": [c.to_dict() for c in self.cells],
        }


@dataclass
class CellData:
    """浏览器数据解析结果 - 单元格数据"""
    row: int
    col: int
    value: str = ""
    hyperlink: Optional[HyperlinkInfo] = None


@dataclass
class SheetData:
    """
    浏览器数据解析结果 - 工作表数据

    从浏览器 SpreadsheetApp.workbook.worksheetManager.sheetList 解析的数据结构。
    """
    name: str
    id: str
    used_range: dict = field(default_factory=dict)  # {startRow, endRow, startCol, endCol}
    cells: list[list[CellData]] = field(default_factory=list)
    state: int = 1  # 1=可见, 2=隐藏

    @property
    def is_empty(self) -> bool:
        """endRowIndex=-1 表示空工作表"""
        end_row = self.used_range.get("endRow", -1)
        return end_row < 0

    @property
    def is_visible(self) -> bool:
        """工作表是否可见"""
        return self.state == 1

    @property
    def row_count(self) -> int:
        """行数"""
        if self.is_empty:
            return 0
        return self.used_range.get("endRow", 0) + 1

    @property
    def col_count(self) -> int:
        """列数"""
        if self.is_empty:
            return 0
        return self.used_range.get("endCol", 0) + 1

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "name": self.name,
            "id": self.id,
            "state": self.state,
            "used_range": self.used_range,
            "cells": [
                [
                    {"row": c.row, "col": c.col, "value": c.value,
                     "hyperlink": {"url": c.hyperlink.url, "display_text": c.hyperlink.display_text}
                     if c.hyperlink else None}
                    for c in row
                ]
                for row in self.cells
            ],
        }


@dataclass
class SpreadsheetData:
    """电子表格数据 - 包含多个工作表"""
    sheets: list[SheetData] = field(default_factory=list)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "sheets": [s.to_dict() for s in self.sheets],
        }


# 数据类型常量
CELL_TYPE_STRING = 4  # 字符串类型
CELL_TYPE_NUMBER = 1  # 数字类型
CELL_TYPE_BOOL = 2    # 布尔类型
CELL_TYPE_DATE = 3    # 日期类型

# 单元格内容类型 (F19.6.3.1)
CELL_CONTENT_TYPE_NORMAL = 4    # 普通单元格 (纯文本)
CELL_CONTENT_TYPE_RICH = 6      # 富文本单元格 (包含超链接等)


def detect_data_type(data: dict) -> str:
    """
    检测数据类型

    Args:
        data: JSON 数据字典或列表

    Returns:
        "sheet" 或 "doc"
    """
    # 如果是列表，检查第一个元素
    if isinstance(data, list):
        if data and isinstance(data[0], dict):
            # 检查是否是简化的工作表格式
            if _is_simplified_sheet(data[0]):
                return "sheet"
        return "doc"

    # Sheet API 响应: retcode + related_sheet
    if "retcode" in data:
        if _has_related_sheet(data):
            return "sheet"

    # clientVars 格式的 Sheet API 响应 (opendoc 返回的 sheet 数据)
    if "clientVars" in data:
        if _has_related_sheet_in_client_vars(data):
            return "sheet"
        # 如果没有 related_sheet，可能是 doc 类型
        # 检查是否有 doc 特征
        if _has_doc_features(data):
            return "doc"
        # 默认检查 padType
        cv = data.get("clientVars", {})
        pad_type = cv.get("padType", "")
        if pad_type == "sheet":
            return "sheet"

    # 浏览器 Sheet 数据: sheetList / cellDataGrid
    if "sheetList" in data or _has_cell_grid(data):
        return "sheet"

    # 简化的工作表格式
    if _is_simplified_sheet(data):
        return "sheet"

    return "doc"


def _has_related_sheet_in_client_vars(data: dict) -> bool:
    """检查 clientVars 格式中是否包含 related_sheet 数据"""
    try:
        cv = data.get("clientVars", {})
        ccv = cv.get("collab_client_vars", {})
        text_list = ccv.get("initialAttributedText", {}).get("text", [])
        if text_list and isinstance(text_list, list):
            first_text = text_list[0]
            if isinstance(first_text, dict) and "related_sheet" in first_text:
                return True
    except (KeyError, TypeError, IndexError):
        pass
    return False


def _has_doc_features(data: dict) -> bool:
    """检查是否是文档类型"""
    try:
        cv = data.get("clientVars", {})
        ccv = cv.get("collab_client_vars", {})
        text_list = ccv.get("initialAttributedText", {}).get("text", [])
        if text_list and isinstance(text_list, list):
            first_text = text_list[0]
            # 如果是字符串，说明是文档类型
            if isinstance(first_text, str):
                return True
    except (KeyError, TypeError, IndexError):
        pass
    return False


def _is_simplified_sheet(data: dict) -> bool:
    """检查是否是简化的工作表格式"""
    # 简化格式特征: 包含 cells 数组和 usedRange
    if "cells" in data and isinstance(data.get("cells"), list):
        return True
    return False


def _has_related_sheet(data: dict) -> bool:
    """检查是否包含 related_sheet 数据"""
    try:
        text_list = data.get("data", {}).get("initialAttributedText", {}).get("text", [])
        if text_list and isinstance(text_list, list):
            return "related_sheet" in text_list[0]
    except (KeyError, TypeError, IndexError):
        pass
    return False


def _has_cell_grid(data: dict) -> bool:
    """检查是否包含 cellDataGrid 数据"""
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "cellDataGrid" in item:
                return True
    return False


if __name__ == "__main__":
    # 测试数据模型
    print("=== SheetCell ===")
    cell = SheetCell(row=0, col=0, value="测试")
    print(f"  {cell.to_dict()}")

    cell_with_link = SheetCell(
        row=1, col=1, value="[链接](https://example.com)",
    )
    cell_with_link.hyperlinks.append(HyperlinkInfo(url="https://example.com", display_text="示例"))
    print(f"  {cell_with_link.to_dict()}")

    print("\n=== SheetInfo ===")
    sheet = SheetInfo(
        sheet_id="test123",
        sheet_name="测试工作表",
        cells=[cell, cell_with_link],
        max_row=10,
        max_col=5,
    )
    print(f"  is_visible: {sheet.is_visible}")
    print(f"  cells count: {len(sheet.cells)}")

    print("\n=== SheetData ===")
    sheet_data = SheetData(
        name="工作表1",
        id="BB08J2",
        used_range={"startRow": 0, "endRow": 10, "startCol": 0, "endCol": 5},
    )
    print(f"  is_empty: {sheet_data.is_empty}")
    print(f"  row_count: {sheet_data.row_count}")
    print(f"  col_count: {sheet_data.col_count}")

    empty_sheet = SheetData(
        name="空工作表",
        id="EMPTY",
        used_range={"startRow": 0, "endRow": -1, "startCol": 0, "endCol": -1},
    )
    print(f"  empty_sheet.is_empty: {empty_sheet.is_empty}")
