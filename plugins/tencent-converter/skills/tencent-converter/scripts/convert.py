#!/usr/bin/env python3
"""
Tencent Converter - 腾讯文档/表格转 Markdown 独立版本

支持两种数据类型:
  - doc: 文档类型 (opendoc 响应)
    三步流水线: parser.py → format_parser.py → to_markdown.py
  - sheet: 表格类型 (dop-api/get/sheet 响应或浏览器数据)
    直接转换: sheet_parser.py → sheet_converter.py

特点：
  - 自动检测输入类型
  - 直接函数调用，无需 subprocess
  - 所有依赖内置，可独立发布
  - 支持 URL 直接获取数据（需 Cookie）
  - 支持多工作表输出
"""

import argparse
import json
import re
import sys
from pathlib import Path

# 添加脚本目录到 sys.path 以支持直接运行
_SCRIPT_DIR = Path(__file__).parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from parser import parse_opendoc
from format_parser import parse_format
from to_markdown import convert_to_markdown
from sheet_enums import detect_data_type
from sheet_converter import convert_sheet_to_markdown


# 非法文件名字符
ILLEGAL_FILENAME_CHARS = r'[<>:"/\\|?*]'


def sanitize_filename(name: str, max_length: int = 200) -> str:
    """清理文件名，移除非法字符并限制长度"""
    # 移除非法字符
    name = re.sub(ILLEGAL_FILENAME_CHARS, '_', name)
    # 移除首尾空白和点
    name = name.strip('. ')
    # 限制长度
    if len(name) > max_length:
        name = name[:max_length]
    return name or "unnamed"


def detect_url_type(url: str) -> str:
    """检测 URL 类型

    Returns:
        "doc", "sheet", 或 "unknown"
    """
    if "/doc/" in url:
        return "doc"
    elif "/sheet/" in url:
        return "sheet"
    return "unknown"


def get_sheet_title(data: dict) -> str:
    """从 API 响应中获取表格标题"""
    try:
        client_vars = data.get("clientVars", {})
        return client_vars.get("padTitle", "未命名表格")
    except (KeyError, TypeError):
        return "未命名表格"


def run_doc_pipeline(
    input_file: Path, output_file: Path, keep_intermediate: bool, verbose: bool,
    page_url: str | None = None, cleanup_source: bool = False
) -> None:
    """运行文档转换流水线"""
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


def escape_cell(text: str) -> str:
    """转义单元格值"""
    if not text:
        return ""
    # 换行符替换为 <br>
    text = text.replace("\n", "<br>")
    # 转义管道符
    text = text.replace("|", "\\|")
    return text


def generate_sheet_markdown(sheet) -> str:
    """生成单个工作表的 Markdown 内容

    Args:
        sheet: SheetInfo 对象

    Returns:
        Markdown 格式的表格内容
    """
    parts = [f"## {sheet.sheet_name}\n\n"]

    if not sheet.cells:
        parts.append("*Empty sheet*\n")
        return "".join(parts)

    # 构建单元格映射
    cell_map = {(c.row, c.col): c for c in sheet.cells}
    max_row = max(c.row for c in sheet.cells)
    max_col = max(c.col for c in sheet.cells)

    # 生成表格
    for row in range(max_row + 1):
        cells = []
        for col in range(max_col + 1):
            cell = cell_map.get((row, col))
            if cell:
                cells.append(escape_cell(cell.value))
            else:
                cells.append('')
        parts.append("| " + " | ".join(cells) + " |\n")

        # 在表头后添加分隔行
        if row == 0:
            parts.append("| " + " | ".join(["---" for _ in range(max_col + 1)]) + " |\n")

    return "".join(parts)


def run_sheet_pipeline(
    input_file: Path, output_file: Path, verbose: bool, cleanup_source: bool = False,
    sheet_name: str | None = None
) -> None:
    """运行表格转换流水线（单文件输出）"""
    if verbose:
        print(f"\n[Sheet] Converting spreadsheet...")
        print(f"  输入: {input_file}")

    # 检测数据类型
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    data_type = detect_data_type(data)
    if verbose:
        print(f"  数据类型: {data_type}")

    if data_type == "sheet":
        # 检查是否是 API 数据格式
        is_api_format = False
        try:
            cv = data.get('clientVars', {})
            ccv = cv.get('collab_client_vars', {})
            text_list = ccv.get('initialAttributedText', {}).get('text', [])
            if text_list and isinstance(text_list, list) and text_list[0].get('related_sheet'):
                is_api_format = True
        except (KeyError, TypeError, IndexError):
            pass

        # 检查直接格式
        if not is_api_format:
            try:
                text_list = data.get('data', {}).get('initialAttributedText', {}).get('text', [])
                if text_list and isinstance(text_list, list) and text_list[0].get('related_sheet'):
                    is_api_format = True
            except (KeyError, TypeError, IndexError):
                pass

        if is_api_format:
            # 使用 API 解析器
            from sheet_api_parser import parse_sheet_api
            sheets = parse_sheet_api(str(input_file), verbose=verbose)

            # 过滤指定工作表
            if sheet_name:
                sheets = [s for s in sheets if s.sheet_name == sheet_name]
                if not sheets:
                    print(f"错误: 找不到工作表 '{sheet_name}'")
                    return

            # 转换为 Markdown
            parts = []
            for i, sheet in enumerate(sheets):
                if i > 0:
                    parts.append("\n\n---\n\n")
                parts.append(generate_sheet_markdown(sheet))
        else:
            # 使用浏览器数据解析器
            convert_sheet_to_markdown(str(input_file), str(output_file), verbose)

            # 清理源文件
            if cleanup_source and input_file.exists():
                input_file.unlink()
                if verbose:
                    print(f"[Cleanup] Removed source: {input_file}")
            return
    else:
        # 使用浏览器数据解析器
        convert_sheet_to_markdown(str(input_file), str(output_file), verbose)

        # 清理源文件
        if cleanup_source and input_file.exists():
            input_file.unlink()
            if verbose:
                print(f"[Cleanup] Removed source: {input_file}")
        return

    # 保存输出
    markdown = "".join(parts)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(markdown)

    if verbose:
        print(f"  输出: {output_file}")

    # 清理源文件
    if cleanup_source and input_file.exists():
        input_file.unlink()
        if verbose:
            print(f"[Cleanup] Removed source: {input_file}")


def run_sheet_multi_output(
    input_file: Path,
    output_dir: Path,
    sheet_name: str | None = None,
    verbose: bool = False,
    cleanup_source: bool = False,
) -> list[Path]:
    """输出多个工作表到指定目录

    Args:
        input_file: 输入 JSON 文件
        output_dir: 输出目录
        sheet_name: 指定工作表名称（None 表示全部可见工作表）
        verbose: 详细输出
        cleanup_source: 是否清理源文件

    Returns:
        生成的文件路径列表
    """
    if verbose:
        print(f"\n[Sheet] Converting spreadsheet (multi-output)...")
        print(f"  输入: {input_file}")
        print(f"  输出目录: {output_dir}")

    # 读取数据
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 检查是否是 --all-tabs 格式的数据
    if "sheets" in data and isinstance(data.get("sheets"), list):
        return _process_all_tabs_data(data, output_dir, sheet_name, verbose, cleanup_source, input_file)

    # 获取表格标题作为子目录名
    pad_title = get_sheet_title(data)
    safe_title = sanitize_filename(pad_title)
    actual_output_dir = output_dir / safe_title
    actual_output_dir.mkdir(parents=True, exist_ok=True)

    if verbose:
        print(f"  表格标题: {pad_title}")
        print(f"  实际输出目录: {actual_output_dir}")

    # 解析工作表
    from sheet_api_parser import parse_sheet_api
    sheets = parse_sheet_api(str(input_file), verbose=verbose)

    # 过滤可见工作表
    visible_sheets = [s for s in sheets if s.is_visible]

    # 如果指定工作表名称，只处理该工作表
    if sheet_name:
        visible_sheets = [s for s in visible_sheets if s.sheet_name == sheet_name]
        if not visible_sheets:
            print(f"错误: 找不到工作表 '{sheet_name}'")
            return []

    if verbose:
        print(f"  可见工作表: {len(visible_sheets)} 个")
        for s in visible_sheets:
            print(f"    - {s.sheet_name}")

    # 为每个工作表生成 Markdown
    output_files = []
    for sheet in visible_sheets:
        safe_sheet_name = sanitize_filename(sheet.sheet_name)
        output_file = actual_output_dir / f"{safe_sheet_name}.md"

        markdown = generate_sheet_markdown(sheet)
        output_file.write_text(markdown, encoding='utf-8')
        output_files.append(output_file)

        if verbose:
            print(f"  生成: {output_file}")

    print(f"已生成 {len(output_files)} 个文件到: {actual_output_dir}")

    # 清理源文件
    if cleanup_source and input_file.exists():
        input_file.unlink()
        if verbose:
            print(f"[Cleanup] Removed source: {input_file}")

    return output_files


def _process_all_tabs_data(
    data: dict,
    output_dir: Path,
    sheet_name: str | None,
    verbose: bool,
    cleanup_source: bool,
    input_file: Path | None = None,
) -> list[Path]:
    """处理 --all-tabs 格式的数据

    Args:
        data: fetch_all_sheets 返回的数据
        output_dir: 输出目录
        sheet_name: 指定工作表名称
        verbose: 详细输出
        cleanup_source: 是否清理源文件
        input_file: 源文件路径（用于清理）

    Returns:
        生成的文件路径列表
    """
    import tempfile
    from sheet_api_parser import parse_sheet_api

    pad_title = data.get("padTitle", "未命名表格")
    safe_title = sanitize_filename(pad_title)
    actual_output_dir = output_dir / safe_title
    actual_output_dir.mkdir(parents=True, exist_ok=True)

    if verbose:
        print(f"  表格标题: {pad_title}")
        print(f"  实际输出目录: {actual_output_dir}")

    sheets_data = data.get("sheets", [])

    # 如果指定工作表名称，只处理该工作表
    if sheet_name:
        sheets_data = [s for s in sheets_data if s.get("tab_name") == sheet_name]
        if not sheets_data:
            print(f"错误: 找不到工作表 '{sheet_name}'")
            return []

    if verbose:
        print(f"  工作表数量: {len(sheets_data)} 个")
        for s in sheets_data:
            print(f"    - {s.get('tab_name')}")

    output_files = []
    for sheet_info in sheets_data:
        tab_name = sheet_info.get("tab_name", "未命名")
        sheet_data = sheet_info.get("data", {})

        if not sheet_data:
            if verbose:
                print(f"  跳过空工作表: {tab_name}")
            continue

        # 保存临时文件供解析器使用
        temp_file = Path(tempfile.mktemp(suffix=".json"))
        temp_file.write_text(json.dumps(sheet_data, ensure_ascii=False), encoding='utf-8')

        try:
            # 解析工作表
            sheets = parse_sheet_api(str(temp_file), verbose=False)
            if not sheets:
                if verbose:
                    print(f"  跳过无法解析的工作表: {tab_name}")
                continue

            # 取第一个工作表（应该只有一个）
            sheet = sheets[0]

            # 生成 Markdown
            safe_sheet_name = sanitize_filename(tab_name)
            output_file = actual_output_dir / f"{safe_sheet_name}.md"

            markdown = generate_sheet_markdown(sheet)
            output_file.write_text(markdown, encoding='utf-8')
            output_files.append(output_file)

            if verbose:
                print(f"  生成: {output_file}")

        except Exception as e:
            print(f"  错误: 处理 {tab_name} 失败: {e}", file=sys.stderr)
        finally:
            # 清理临时文件
            if temp_file.exists():
                temp_file.unlink()

    print(f"已生成 {len(output_files)} 个文件到: {actual_output_dir}")

    # 清理源文件
    if cleanup_source and input_file and input_file.exists():
        input_file.unlink()
        if verbose:
            print(f"[Cleanup] Removed source: {input_file}")

    return output_files


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tencent Converter - 腾讯文档/表格转 Markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", nargs="?", help="Input JSON file path (opendoc response or sheet data)")
    parser.add_argument(
        "-o", "--output", help="Output Markdown file path"
    )
    parser.add_argument(
        "--output-dir", metavar="DIR", help="Output directory for multi-sheet mode (sheet only)"
    )
    parser.add_argument(
        "--type", "-t", choices=["doc", "sheet", "auto"], default="auto",
        help="Input type: doc (document), sheet (spreadsheet), or auto (auto-detect, default)"
    )
    parser.add_argument(
        "--keep-intermediate",
        action="store_true",
        help="Keep intermediate files (intermediate.json, result.json) - doc only"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Explicitly clean up intermediate files (default behavior)"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show verbose output"
    )
    parser.add_argument(
        "--page-url", metavar="URL", help="Document online URL for meta info - doc only"
    )
    parser.add_argument(
        "--cleanup-source", action="store_true", help="Remove source JSON after conversion"
    )
    parser.add_argument(
        "--url", metavar="URL", help="Tencent doc/sheet URL to fetch data from"
    )
    parser.add_argument(
        "--cookie", metavar="FILE", help="Cookie file path (required when using --url)"
    )
    parser.add_argument(
        "--sheet-name", metavar="NAME", help="Specific sheet name to convert (sheet only)"
    )
    parser.add_argument(
        "--all-tabs", action="store_true",
        help="Fetch all worksheets from spreadsheet URL (sheet only, requires --url)"
    )
    args = parser.parse_args()

    # 验证参数
    if args.url:
        if not args.cookie:
            print("错误: 使用 --url 时必须提供 --cookie 参数")
            sys.exit(1)
    elif not args.input:
        print("错误: 必须提供 input 文件路径或 --url 参数")
        sys.exit(1)

    # 验证输出参数
    if not args.output and not args.output_dir:
        print("错误: 必须提供 -o/--output 或 --output-dir 参数")
        sys.exit(1)

    # 处理 URL 模式
    temp_json_file = None
    if args.url:
        url_type = detect_url_type(args.url)
        if url_type == "unknown":
            print(f"错误: 无法识别 URL 类型: {args.url}")
            sys.exit(1)

        print("=" * 60)
        print("Tencent Converter - 从 URL 获取数据")
        print("=" * 60)
        print(f"URL: {args.url}")
        print(f"类型: {url_type}")

        # 获取数据
        cookie_path = Path(args.cookie)
        if not cookie_path.exists():
            print(f"错误: Cookie 文件不存在: {cookie_path}")
            sys.exit(1)

        if url_type == "doc":
            from fetch_opendoc import fetch_opendoc, parse_cookie_file, validate_opendoc_response
            cookies = parse_cookie_file(cookie_path)
            try:
                data = fetch_opendoc(args.url, cookies, args.verbose)
                # 验证响应有效性
                is_valid, error_msg = validate_opendoc_response(data)
                if not is_valid:
                    print(f"错误: {error_msg}")
                    print("提示: 请更新 cookies.txt 文件或重新登录腾讯文档")
                    sys.exit(1)
            except Exception as e:
                print(f"获取文档数据失败: {e}")
                sys.exit(1)
        else:  # sheet
            from fetch_sheet import fetch_sheet_data, fetch_all_sheets, parse_cookie_file, validate_sheet_response
            cookies = parse_cookie_file(cookie_path)
            try:
                if args.all_tabs:
                    # 获取所有工作表
                    data = fetch_all_sheets(args.url, cookies, args.verbose)
                    print(f"获取工作表: {len(data.get('sheets', []))} 个")
                else:
                    # 获取单个工作表
                    data = fetch_sheet_data(args.url, cookies, args.verbose)
                    # 验证响应有效性
                    is_valid, error_msg = validate_sheet_response(data)
                    if not is_valid:
                        print(f"错误: {error_msg}")
                        print("提示: 请更新 cookies.txt 文件或重新登录腾讯文档")
                        sys.exit(1)
            except Exception as e:
                print(f"获取表格数据失败: {e}")
                sys.exit(1)

        # 保存临时文件
        import tempfile
        temp_json_file = Path(tempfile.mktemp(suffix=".json"))
        temp_json_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        input_file = temp_json_file
        input_type = url_type

        print(f"数据已获取: {input_file}")
    else:
        input_file = Path(args.input)
        if not input_file.exists():
            print(f"Error: Input file not found: {input_file}")
            sys.exit(1)

        # 检测输入类型
        input_type = args.type
        if input_type == "auto":
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            input_type = detect_data_type(data)

    # 确定输出模式
    use_multi_output = args.output_dir and input_type == "sheet"

    if use_multi_output:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        print("=" * 60)
        print("Tencent Converter - 腾讯表格转 Markdown (多工作表)")
        print("=" * 60)
        print(f"Input: {input_file}")
        print(f"Output Dir: {output_dir}")
        print(f"Type: {input_type}")
        if args.sheet_name:
            print(f"Sheet Name: {args.sheet_name}")
        if args.cleanup_source:
            print("Cleanup source: enabled")

        output_files = run_sheet_multi_output(
            input_file, output_dir,
            sheet_name=args.sheet_name,
            verbose=args.verbose,
            cleanup_source=args.cleanup_source,
        )

        print("\n" + "=" * 60)
        print(f"Conversion complete: {len(output_files)} files generated")
        print("=" * 60)
    else:
        if not args.output:
            print("错误: 单文件模式需要 -o/--output 参数")
            sys.exit(1)

        output_file = Path(args.output)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        print("=" * 60)
        print("Tencent Converter - 腾讯文档/表格转 Markdown")
        print("=" * 60)
        print(f"Input: {input_file}")
        print(f"Output: {output_file}")
        print(f"Type: {input_type}")

        if input_type == "doc":
            print(f"Keep intermediate: {args.keep_intermediate}")
            if args.page_url:
                print(f"Page URL: {args.page_url}")
        if args.sheet_name:
            print(f"Sheet Name: {args.sheet_name}")
        if args.cleanup_source:
            print("Cleanup source: enabled")

        # 根据类型运行不同的流水线
        if input_type == "sheet":
            run_sheet_pipeline(
                input_file, output_file, args.verbose,
                cleanup_source=args.cleanup_source,
                sheet_name=args.sheet_name,
            )
        else:
            run_doc_pipeline(
                input_file, output_file, args.keep_intermediate, args.verbose,
                page_url=args.page_url, cleanup_source=args.cleanup_source
            )

        print("\n" + "=" * 60)
        print(f"Conversion complete: {output_file}")
        print("=" * 60)

    # 清理临时文件
    if temp_json_file and temp_json_file.exists():
        temp_json_file.unlink()
        if args.verbose:
            print(f"[Cleanup] Removed temp file: {temp_json_file}")


if __name__ == "__main__":
    main()
