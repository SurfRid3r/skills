#!/usr/bin/env python3
"""
腾讯文档表格 API 解析器

解析 dop-api/get/sheet API 响应数据。
解码流程: related_sheet (Base64) → zlib 解压 → protobuf 解析

详细字段映射和富文本定位逻辑见 references/sheet_parsing_logic.md
"""

import base64
import json
import re
import sys
import zlib
from pathlib import Path
from typing import Optional

try:
    from .parser import parse_protobuf_message, PbField
    from .sheet_enums import SheetInfo, SheetCell, HyperlinkInfo
except ImportError:
    from parser import parse_protobuf_message, PbField
    from sheet_enums import SheetInfo, SheetCell, HyperlinkInfo


class SheetApiParser:
    """表格 API 响应解析器"""

    def __init__(self, api_response: dict):
        self.api_response = api_response
        self._raw_data: bytes = b""
        self._fields: list[PbField] = []
        self._api_max_row: int = 0
        self._api_max_col: int = 0
        self._extract_range_info()

    def parse(self) -> list[SheetInfo]:
        """解析 API 响应"""
        related_sheet = self._extract_related_sheet()
        if not related_sheet:
            return []

        try:
            decoded = base64.b64decode(related_sheet)
            decompressed = zlib.decompress(decoded)
            self._raw_data = decompressed
            self._fields = parse_protobuf_message(decompressed)
        except Exception as e:
            print(f"Error decoding related_sheet: {e}", file=sys.stderr)
            return []

        return self._parse_sheets()

    def _extract_range_info(self) -> None:
        """从 API 响应提取范围信息"""
        try:
            if "data" in self.api_response:
                data = self.api_response.get("data", {})
                text_list = data.get("initialAttributedText", {}).get("text", [])
                if text_list and isinstance(text_list, list):
                    self._api_max_row = text_list[0].get("max_row", 0)
                    self._api_max_col = text_list[0].get("max_col", 0)
                    return

            if "clientVars" in self.api_response:
                cv = self.api_response.get("clientVars", {})
                ccv = cv.get("collab_client_vars", {})
                text_list = ccv.get("initialAttributedText", {}).get("text", [])
                if text_list and isinstance(text_list, list):
                    self._api_max_row = text_list[0].get("max_row", 0)
                    self._api_max_col = text_list[0].get("max_col", 0)
        except (KeyError, TypeError, IndexError):
            pass

    def _extract_related_sheet(self) -> Optional[str]:
        """从 API 响应提取 related_sheet Base64 数据"""
        try:
            if "data" in self.api_response:
                data = self.api_response.get("data", {})
                text_list = data.get("initialAttributedText", {}).get("text", [])
                if text_list and isinstance(text_list, list):
                    return text_list[0].get("related_sheet")

            if "clientVars" in self.api_response:
                cv = self.api_response.get("clientVars", {})
                ccv = cv.get("collab_client_vars", {})
                text_list = ccv.get("initialAttributedText", {}).get("text", [])
                if text_list and isinstance(text_list, list):
                    return text_list[0].get("related_sheet")
        except (KeyError, TypeError, IndexError):
            pass
        return None

    def _parse_sheets(self) -> list[SheetInfo]:
        """解析工作表列表"""
        sheet_metadata: dict[str, str] = {}
        for field in self._fields:
            if field.field_number != 1:
                continue

            for sheet_field in field.get_all_nested_fields(5):
                meta_field = sheet_field.get_nested_field(5)
                if meta_field and meta_field.nested_fields:
                    sheet_id = ""
                    sheet_name = ""
                    for nf in meta_field.nested_fields:
                        if nf.field_number == 3:
                            id_field = nf.get_nested_field(1)
                            if id_field and id_field.raw_bytes:
                                sheet_id = id_field.raw_bytes.decode('utf-8', errors='ignore')
                        elif nf.field_number == 4:
                            name_field = nf.get_nested_field(1)
                            if name_field and name_field.raw_bytes:
                                sheet_name = name_field.raw_bytes.decode('utf-8', errors='ignore')

                    if sheet_id:
                        sheet_metadata[sheet_id] = sheet_name or sheet_id

        sheets = []
        for field in self._fields:
            if field.field_number != 1:
                continue

            for sheet_field in field.get_all_nested_fields(5):
                cell_field = sheet_field.get_nested_field(19)
                if not cell_field:
                    continue

                range_field = cell_field.get_nested_field(3)
                if not range_field:
                    continue

                sheet_id = ""
                for nf in range_field.nested_fields:
                    if nf.field_number == 1 and nf.raw_bytes:
                        sheet_id = nf.raw_bytes.decode('utf-8', errors='ignore')

                if not sheet_id:
                    continue

                sheet_name = sheet_metadata.get(sheet_id, sheet_id)
                cells = self._parse_cell_data(cell_field)

                actual_max_row = 0
                actual_max_col = 0
                for cell in cells:
                    if cell.row > actual_max_row:
                        actual_max_row = cell.row
                    if cell.col > actual_max_col:
                        actual_max_col = cell.col

                sheets.append(SheetInfo(
                    sheet_id=sheet_id,
                    sheet_name=sheet_name,
                    cells=cells,
                    state=1,
                    max_row=actual_max_row,
                    max_col=actual_max_col,
                ))

        return sheets

    def _parse_cell_data(self, cell_field: PbField) -> list[SheetCell]:
        """
        解析单元格数据

        位置映射规则:
        - Field 19.6.1 → row (0-based)
        - Field 19.6.2 → col (0-based)
        - Field 19.6.3.2.1 → text_idx (指向 F19.5.1 纯文本)
        - Field 19.6.3.4.1 → rich_text_idx (指向 F19.4.F1 引用表)

        富文本结构:
        - F19.4 → 引用表 (rich_text_idx → F2 索引的映射)
          - F19.4.F1[i].F9.F1 → F2 索引 (1-based)，缺失则默认 F2[0]
        - F19.5.F2 → 富文本项列表
          - F19.5.F2[k] → 第 k 个富文本项的段落列表
        - rich_text_idx 是 F19.4 引用表的索引 (1-based)

        增量编码逻辑:
        - text_idx=0 始终位于 (0, 0)，是隐式的
        - 当 row 有值时，重置当前行，current_col 重置为 -1
        - 当 col 有值时使用该值，否则 current_col += 1
        """
        cells = []
        text_list: list[str] = []
        # rich_text_idx (1-based) -> f2_index (0-based)
        rich_text_to_f2: dict[int, int] = {}
        # F2 项列表: [[(text, url), ...], ...]
        f2_items: list[list[tuple[str, str]]] = []

        # === 步骤 1: 解析 F19.4 引用表 ===
        ref_table_field = cell_field.get_nested_field(4)
        if ref_table_field and ref_table_field.nested_fields:
            for idx, ref_entry in enumerate(ref_table_field.nested_fields, start=1):
                if ref_entry.field_number == 1:
                    f9 = ref_entry.get_nested_field(9)
                    if f9 and f9.nested_fields:
                        f1 = f9.get_nested_field(1)
                        if f1 and f1.wire_type == 0:
                            rich_text_to_f2[idx] = f1.value - 1  # 转为 0-based
                    else:
                        # F9 缺失，默认映射到 F2[0]
                        rich_text_to_f2[idx] = 0

        # === 步骤 2: 解析 F19.5 文本内容 ===
        text_field = cell_field.get_nested_field(5)
        if text_field and text_field.nested_fields:
            for tf in text_field.nested_fields:
                if tf.field_number == 1 and tf.raw_bytes:
                    # F1 → 纯文本项
                    text = self._extract_text_from_protobuf(tf.raw_bytes)
                    text_list.append(text)
                elif tf.field_number == 2:
                    # F2 → 富文本项
                    paragraphs = self._parse_rich_text_item(tf)
                    f2_items.append(paragraphs)

        # === 步骤 3: 解析 F19.6 位置映射 ===
        pos_fields = cell_field.get_all_nested_fields(6)

        # 处理隐式的第一个单元格 (text_idx=0 位于 0,0)
        if text_list:
            raw_text = text_list[0]
            cells.append(SheetCell(row=0, col=0, value=raw_text))

        current_row = 0
        current_col = 0

        for pos_field in pos_fields:
            if not pos_field.nested_fields:
                continue

            row = None
            col = None
            text_idx = None
            rich_text_idx = None
            cell_type = 4  # 默认普通单元格
            direct_f2_index = None  # F3.1=6 时，F3.2.1 是 F2 的直接索引

            for nf in pos_field.nested_fields:
                # Field 1 → row
                if nf.field_number == 1 and nf.wire_type == 0:
                    row = nf.value
                # Field 2 → col
                elif nf.field_number == 2 and nf.wire_type == 0:
                    col = nf.value
                # Field 3 → 单元格类型和索引
                elif nf.field_number == 3 and nf.nested_fields:
                    # F3.1 → 单元格类型标记 (4=普通, 6=富文本)
                    f1_type = nf.get_nested_field(1)
                    if f1_type and f1_type.wire_type == 0:
                        cell_type = f1_type.value

                    # F3.2 → text_idx 或直接 F2 索引
                    f2 = nf.get_nested_field(2)
                    has_f2 = f2 is not None
                    if f2 and f2.nested_fields:
                        f1_inner = f2.get_nested_field(1)
                        if f1_inner and f1_inner.wire_type == 0:
                            if cell_type == 6:
                                # F3.1=6: F3.2.1 是 F2 的直接 0-based 索引
                                direct_f2_index = f1_inner.value
                            else:
                                # F3.1!=6: F3.2.1 是纯文本索引
                                text_idx = f1_inner.value

                    # F3.4 → rich_text_idx（通过引用表映射）
                    f4 = nf.get_nested_field(4)
                    if f4 and f4.nested_fields:
                        f1_val = f4.get_nested_field(1)
                        if f1_val and f1_val.wire_type == 0:
                            # 只有当 F3.2 存在时，rich_text_idx 才表示内容
                            if has_f2:
                                rich_text_idx = f1_val.value

            # 跳过 text_idx=0，已处理
            if text_idx is not None and text_idx == 0:
                continue

            # 行处理
            if row is not None:
                current_row = row
                current_col = -1

            # 列处理
            if col is not None:
                current_col = col
            else:
                current_col += 1

            # 构建单元格值
            cell_value = ""
            hyperlinks: list[HyperlinkInfo] = []

            # 获取基础文本（如果有）
            base_text = ""
            if text_idx is not None and 0 <= text_idx < len(text_list):
                base_text = text_list[text_idx]

            # === 步骤 4: 构建单元格值 ===
            if cell_type == 6:
                # 富文本单元格：优先使用直接 F2 索引
                paragraphs = None
                if direct_f2_index is not None and 0 <= direct_f2_index < len(f2_items):
                    # 使用直接 F2 索引
                    paragraphs = f2_items[direct_f2_index]
                elif rich_text_idx is not None:
                    # 使用引用表映射（兼容旧逻辑）
                    f2_index = rich_text_to_f2.get(rich_text_idx, 0)
                    if 0 <= f2_index < len(f2_items):
                        paragraphs = f2_items[f2_index]

                if paragraphs:
                    parts: list[str] = []
                    for display_text, url in paragraphs:
                        # 空段落（换行符）转换为 <br>
                        if not display_text.strip():
                            parts.append("<br>")
                            continue
                        if url:
                            parts.append(f"[{display_text}]({url})")
                            hyperlinks.append(HyperlinkInfo(url=url, display_text=display_text))
                        else:
                            parts.append(display_text)
                    cell_value = " ".join(parts)
            elif base_text:
                # 普通单元格：使用纯文本
                cell_value = base_text
            elif rich_text_idx is not None:
                # 兼容：没有 cell_type 但有 rich_text_idx
                f2_index = rich_text_to_f2.get(rich_text_idx, 0)
                if 0 <= f2_index < len(f2_items):
                    paragraphs = f2_items[f2_index]
                    parts: list[str] = []
                    for display_text, url in paragraphs:
                        if not display_text.strip():
                            parts.append("<br>")
                            continue
                        if url:
                            parts.append(f"[{display_text}]({url})")
                            hyperlinks.append(HyperlinkInfo(url=url, display_text=display_text))
                        else:
                            parts.append(display_text)
                    cell_value = " ".join(parts)

            if cell_value:
                cells.append(SheetCell(
                    row=current_row,
                    col=current_col,
                    value=cell_value,
                    hyperlinks=hyperlinks,
                ))

        return cells

    def _parse_rich_text_item(self, field: PbField) -> list[tuple[str, str]]:
        """
        解析富文本项 (F19.5.F2)，提取所有文本段和超链接

        结构:
          F2 → 富文本项
            F3 → 文本段列表项（多个 F3）
              F3.F1 → 文本内容
              F5 → 类型标记（1=有超链接，3=无超链接）
              F7.F11.F1 → 超链接 URL

        Returns:
            [(display_text, url), ...] 所有文本段列表
        """
        segments: list[tuple[str, str]] = []

        if not field.nested_fields:
            return segments

        # 遍历 F3（文本段列表项）
        for f3_item in field.nested_fields:
            if f3_item.field_number != 3 or not f3_item.nested_fields:
                continue

            text = ""
            url = ""

            for nf in f3_item.nested_fields:
                if nf.field_number == 3 and nf.nested_fields:
                    # F3.F1 → 文本内容
                    f1 = nf.get_nested_field(1)
                    if f1 and f1.raw_bytes:
                        text = f1.raw_bytes.decode('utf-8', errors='ignore')
                        # 保留换行符，过滤其他控制字符
                        text = ''.join(c for c in text if ord(c) >= 32 or c == '\n' or ord(c) > 127)
                elif nf.field_number == 7 and nf.nested_fields:
                    # F7.F11.F1 → 超链接 URL
                    f11 = nf.get_nested_field(11)
                    if f11 and f11.nested_fields:
                        f1 = f11.get_nested_field(1)
                        if f1 and f1.raw_bytes:
                            url = f1.raw_bytes.decode('utf-8', errors='ignore')

            segments.append((text, url))

        return segments

    def _extract_text_from_protobuf(self, raw_bytes: bytes) -> str:
        """从嵌套的 protobuf 消息中提取文本"""
        inner_fields = parse_protobuf_message(raw_bytes)

        for inner in inner_fields:
            if inner.field_number == 1 and inner.raw_bytes:
                text = inner.raw_bytes.decode('utf-8', errors='ignore')
                return self._clean_text(text)

        raw_text = raw_bytes.decode('utf-8', errors='ignore')
        return self._clean_text(raw_text)

    def _clean_text(self, text: str) -> str:
        """清理单元格文本，移除控制字符"""
        text = text.lstrip('\n')
        return ''.join(c for c in text if ord(c) >= 32 or c == '\n' or ord(c) > 127)


def parse_sheet_api(input_file: str, output_file: Optional[str] = None, verbose: bool = False) -> list[SheetInfo]:
    """解析表格 API 响应文件"""
    input_path = Path(input_file)

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if verbose:
        print(f"  输入文件: {input_path}")

    parser = SheetApiParser(data)
    sheets = parser.parse()

    if verbose:
        print(f"  工作表数量: {len(sheets)}")
        for sheet in sheets:
            print(f"    - {sheet.sheet_name} ({sheet.sheet_id}): {len(sheet.cells)} 个单元格")

    if output_file:
        output_data = {
            "sheets": [s.to_dict() for s in sheets],
        }
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        if verbose:
            print(f"  输出文件: {output_file}")

    return sheets


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='腾讯文档表格 API 解析器')
    parser.add_argument('input', help='输入文件路径 (.json)')
    parser.add_argument('-o', '--output', help='输出文件路径')
    parser.add_argument('-v', '--verbose', action='store_true', help='显示详细信息')

    args = parser.parse_args()

    print("=" * 60)
    print("腾讯文档表格 API 解析器")
    print("=" * 60)

    sheets = parse_sheet_api(args.input, args.output, args.verbose)

    print(f"\n解析完成: {len(sheets)} 个工作表")
    for sheet in sheets:
        visible = "可见" if sheet.is_visible else "隐藏"
        print(f"  [{visible}] {sheet.sheet_name}: {len(sheet.cells)} 个单元格")


if __name__ == "__main__":
    main()
