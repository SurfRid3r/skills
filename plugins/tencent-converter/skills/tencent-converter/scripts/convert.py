#!/usr/bin/env python3
"""
Tencent Converter - 腾讯文档/表格转 Markdown 独立版本

支持两种数据类型:
  - doc: 文档类型 (opendoc 响应) - 三步流水线
  - sheet: 表格类型 (dop-api/get/sheet 响应或浏览器数据) - 直接转换
"""

import argparse
import json
import re
import sys
import tempfile
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
from utils import (
    generate_front_matter,
    generate_sheet_front_matter,
    escape_cell,
    DEFAULT_DOC_NAME,
    DEFAULT_SHEET_OUTPUT_NAME,
    FALLBACK_SHEET_TITLE,
)


# 非法文件名字符
ILLEGAL_FILENAME_CHARS = r'[<>:"/\\|?*]'


def sanitize_filename(name: str, max_length: int = 200) -> str:
    """清理文件名，移除非法字符并限制长度"""
    name = re.sub(ILLEGAL_FILENAME_CHARS, '_', name)
    name = name.strip('. ')
    if len(name) > max_length:
        name = name[:max_length]
    return name or "unnamed"


def detect_url_type(url: str) -> str:
    """检测 URL 类型: "doc", "sheet", 或 "unknown" """
    if "/doc/" in url:
        return "doc"
    if "/sheet/" in url:
        return "sheet"
    return "unknown"


def get_sheet_title(data: dict) -> str:
    """从 API 响应中获取表格标题"""
    try:
        return data.get("clientVars", {}).get("padTitle", FALLBACK_SHEET_TITLE)
    except (KeyError, TypeError):
        return FALLBACK_SHEET_TITLE


def _print_banner(title: str, lines: list[str]) -> None:
    """打印带边框的标题"""
    print("=" * 60)
    print(title)
    print("=" * 60)
    for line in lines:
        print(line)


def _cleanup_file(file_path: Path, verbose: bool, label: str = "file") -> None:
    """删除文件（如果存在）"""
    if file_path and file_path.exists():
        file_path.unlink()
        if verbose:
            print(f"[Cleanup] Removed {label}: {file_path}")


def run_doc_pipeline(
    input_file: Path, output_file: Path, keep_intermediate: bool, verbose: bool,
    page_url: str | None = None, cleanup_source: bool = False
) -> str | None:
    """运行文档转换流水线，返回文档标题"""
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
    _, title = convert_to_markdown(str(result_file), str(output_file), verbose, page_url=page_url, doc_type="doc")

    # 清理中间文件
    if not keep_intermediate:
        _cleanup_file(intermediate_file, verbose, "intermediate")
        _cleanup_file(result_file, verbose, "result")

    # 清理源文件
    if cleanup_source:
        _cleanup_file(input_file, verbose, "source")

    return title


def generate_sheet_markdown(sheet) -> str:
    """生成单个工作表的 Markdown 内容"""
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
        cells = [
            escape_cell(cell.value) if (cell := cell_map.get((row, col))) else ''
            for col in range(max_col + 1)
        ]
        parts.append("| " + " | ".join(cells) + " |\n")

        # 在表头后添加分隔行
        if row == 0:
            parts.append("| " + " | ".join(["---"] * (max_col + 1)) + " |\n")

    return "".join(parts)


def _is_api_format(data: dict) -> bool:
    """检查是否是 API 数据格式"""
    try:
        # 检查 clientVars 格式
        cv = data.get('clientVars', {})
        ccv = cv.get('collab_client_vars', {})
        text_list = ccv.get('initialAttributedText', {}).get('text', [])
        if text_list and isinstance(text_list, list) and text_list[0].get('related_sheet'):
            return True

        # 检查 data 格式
        text_list = data.get('data', {}).get('initialAttributedText', {}).get('text', [])
        if text_list and isinstance(text_list, list) and text_list[0].get('related_sheet'):
            return True
    except (KeyError, TypeError, IndexError):
        pass
    return False


def run_sheet_pipeline(
    input_file: Path, output_file: Path, verbose: bool, cleanup_source: bool = False,
    sheet_name: str | None = None, page_url: str | None = None
) -> tuple[str | None, str | None]:
    """运行表格转换流水线（单文件输出），返回 (表格标题, 子表名称)"""
    if verbose:
        print(f"\n[Sheet] Converting spreadsheet...")
        print(f"  输入: {input_file}")

    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    data_type = detect_data_type(data)
    if verbose:
        print(f"  数据类型: {data_type}")

    pad_title = get_sheet_title(data)
    first_sheet_name = None

    # 准备 metadata
    metadata = {"title": pad_title}

    # 非 API 格式直接使用浏览器数据解析器
    if data_type != "sheet" or not _is_api_format(data):
        convert_sheet_to_markdown(str(input_file), str(output_file), verbose, page_url, metadata)
        _cleanup_file(input_file, cleanup_source and input_file.exists(), "source")
        return pad_title, first_sheet_name

    # API 格式处理
    from sheet_api_parser import parse_sheet_api
    sheets = parse_sheet_api(str(input_file), verbose=verbose)

    visible_sheets = [s for s in sheets if s.is_visible]
    if visible_sheets:
        first_sheet_name = visible_sheets[0].sheet_name

    if sheet_name:
        sheets = [s for s in sheets if s.sheet_name == sheet_name]
        if not sheets:
            print(f"错误: 找不到工作表 '{sheet_name}'")
            return pad_title, None
        first_sheet_name = sheet_name

    # 转换为 Markdown
    parts = []
    # 添加 front matter
    front_matter = generate_front_matter(
        title=pad_title,
        source=page_url,
        doc_type="sheet",
    )
    parts.append(front_matter)

    for i, sheet in enumerate(sheets):
        if i > 0:
            parts.append("\n\n---\n\n")
        parts.append(generate_sheet_markdown(sheet))

    output_file.write_text("".join(parts), encoding='utf-8')
    if verbose:
        print(f"  输出: {output_file}")

    _cleanup_file(input_file, cleanup_source, "source")
    return pad_title, first_sheet_name


def run_sheet_multi_output(
    input_file: Path,
    output_dir: Path,
    sheet_name: str | None = None,
    verbose: bool = False,
    cleanup_source: bool = False,
    page_url: str | None = None,
) -> list[Path]:
    """输出多个工作表到指定目录，返回生成的文件路径列表"""
    if verbose:
        print(f"\n[Sheet] Converting spreadsheet (multi-output)...")
        print(f"  输入: {input_file}")
        print(f"  输出目录: {output_dir}")

    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 检查是否是 --all-tabs 格式的数据
    if "sheets" in data and isinstance(data.get("sheets"), list):
        return _process_all_tabs_data(data, output_dir, sheet_name, verbose, cleanup_source, input_file, page_url)

    pad_title = get_sheet_title(data)
    safe_title = sanitize_filename(pad_title)
    actual_output_dir = output_dir / safe_title
    actual_output_dir.mkdir(parents=True, exist_ok=True)

    if verbose:
        print(f"  表格标题: {pad_title}")
        print(f"  实际输出目录: {actual_output_dir}")

    from sheet_api_parser import parse_sheet_api
    sheets = parse_sheet_api(str(input_file), verbose=verbose)

    visible_sheets = [s for s in sheets if s.is_visible]

    if sheet_name:
        visible_sheets = [s for s in visible_sheets if s.sheet_name == sheet_name]
        if not visible_sheets:
            print(f"错误: 找不到工作表 '{sheet_name}'")
            return []

    if verbose:
        print(f"  可见工作表: {len(visible_sheets)} 个")
        for s in visible_sheets:
            print(f"    - {s.sheet_name}")

    output_files = []
    metadata = {"title": pad_title}
    for sheet in visible_sheets:
        safe_sheet_name = sanitize_filename(sheet.sheet_name)
        output_file = actual_output_dir / f"{safe_sheet_name}.md"
        # 为每个工作表生成带 front matter 的内容
        front_matter = generate_front_matter(
            title=metadata.get("title"),
            source=page_url,
            doc_type="sheet",
        )
        content = front_matter + generate_sheet_markdown(sheet)
        output_file.write_text(content, encoding='utf-8')
        output_files.append(output_file)
        if verbose:
            print(f"  生成: {output_file}")

    print(f"已生成 {len(output_files)} 个文件到: {actual_output_dir}")
    _cleanup_file(input_file, cleanup_source, "source")
    return output_files


def _process_all_tabs_data(
    data: dict,
    output_dir: Path,
    sheet_name: str | None,
    verbose: bool,
    cleanup_source: bool,
    input_file: Path | None = None,
    page_url: str | None = None,
) -> list[Path]:
    """处理 --all-tabs 格式的数据，返回生成的文件路径列表"""
    from sheet_api_parser import parse_sheet_api

    pad_title = data.get("padTitle", FALLBACK_SHEET_TITLE)
    safe_title = sanitize_filename(pad_title)
    actual_output_dir = output_dir / safe_title
    actual_output_dir.mkdir(parents=True, exist_ok=True)

    if verbose:
        print(f"  表格标题: {pad_title}")
        print(f"  实际输出目录: {actual_output_dir}")

    sheets_data = data.get("sheets", [])

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
    metadata = {"title": pad_title}
    for sheet_info in sheets_data:
        tab_name = sheet_info.get("tab_name", "未命名")
        sheet_data = sheet_info.get("data", {})

        if not sheet_data:
            if verbose:
                print(f"  跳过空工作表: {tab_name}")
            continue

        temp_file = Path(tempfile.mktemp(suffix=".json"))
        temp_file.write_text(json.dumps(sheet_data, ensure_ascii=False), encoding='utf-8')

        try:
            sheets = parse_sheet_api(str(temp_file), verbose=False)
            if not sheets:
                if verbose:
                    print(f"  跳过无法解析的工作表: {tab_name}")
                continue

            sheet = sheets[0]
            safe_sheet_name = sanitize_filename(tab_name)
            output_file = actual_output_dir / f"{safe_sheet_name}.md"
            # 为每个工作表生成带 front matter 的内容
            front_matter = generate_sheet_front_matter(metadata, page_url)
            content = front_matter + generate_sheet_markdown(sheet)
            output_file.write_text(content, encoding='utf-8')
            output_files.append(output_file)

            if verbose:
                print(f"  生成: {output_file}")

        except Exception as e:
            print(f"  错误: 处理 {tab_name} 失败: {e}", file=sys.stderr)
        finally:
            _cleanup_file(temp_file, False, "temp")

    print(f"已生成 {len(output_files)} 个文件到: {actual_output_dir}")
    if input_file:
        _cleanup_file(input_file, cleanup_source, "source")
    return output_files


def _run_auto_output_conversion(
    input_file: Path,
    input_type: str,
    args: argparse.Namespace,
    temp_json_file: Path | None,
) -> None:
    """运行自动命名输出的转换（未指定 -o 参数时）"""
    temp_output = Path(tempfile.mktemp(suffix=".md"))

    if input_type == "doc":
        _print_banner("Tencent Converter - 腾讯文档转 Markdown", [
            f"Input: {input_file}",
            f"Type: {input_type}",
            "Output: 自动检测标题后确定...",
        ])
        title = run_doc_pipeline(
            input_file, temp_output, args.keep_intermediate, args.verbose,
            page_url=args.page_url, cleanup_source=args.cleanup_source
        )
        default_name = DEFAULT_DOC_NAME
        name = title
    else:
        _print_banner("Tencent Converter - 腾讯表格转 Markdown", [
            f"Input: {input_file}",
            f"Type: {input_type}",
            "Output: 自动检测子表名称后确定...",
        ])
        pad_title, sheet_name = run_sheet_pipeline(
            input_file, temp_output, args.verbose,
            cleanup_source=args.cleanup_source,
            sheet_name=args.sheet_name,
            page_url=args.page_url,
        )
        default_name = DEFAULT_SHEET_OUTPUT_NAME
        name = sheet_name or pad_title

    # 确定输出文件名（使用当前目录，与表格转换一致）
    output_file = Path(".") / (f"{sanitize_filename(name)}.md" if name else default_name)
    temp_output.rename(output_file.resolve())

    print("\n" + "=" * 60)
    print(f"Conversion complete: {output_file}")
    print("=" * 60)

    if temp_json_file:
        _cleanup_file(temp_json_file, args.verbose, "temp file")


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
        "--output-dir", metavar="DIR", help="Output directory (default: current directory)"
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
        "--page-url", metavar="URL", help="Document/sheet online URL for meta info"
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
        "--doc-name", metavar="NAME", help="Document name for output filename (doc only, default: auto-detect from content)"
    )
    parser.add_argument(
        "--all-tabs", action="store_true",
        help="Fetch all worksheets from spreadsheet URL (sheet only, requires --url)"
    )
    parser.add_argument(
        "--revision", "-r", type=int, metavar="REV",
        help="Local revision number for incremental update check (skip if unchanged)"
    )
    args = parser.parse_args()

    # 参数规范化：处理向后兼容性
    if args.output:
        output_path = Path(args.output)
        # 从 -o 提取目录
        if not args.output_dir and output_path.parent != Path("."):
            args.output_dir = str(output_path.parent)

    # 验证参数
    if args.url:
        if not args.cookie:
            print("错误: 使用 --url 时必须提供 --cookie 参数")
            sys.exit(1)
    elif not args.input:
        print("错误: 必须提供 input 文件路径或 --url 参数")
        sys.exit(1)

    # 注意：-o 参数现在是可选的，文档类型会自动使用标题作为文件名

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
                if args.sheet_name:
                    # 指定了工作表名称，获取单个
                    data = fetch_sheet_data(args.url, cookies, args.verbose)
                    # 验证响应有效性
                    is_valid, error_msg = validate_sheet_response(data)
                    if not is_valid:
                        print(f"错误: {error_msg}")
                        print("提示: 请更新 cookies.txt 文件或重新登录腾讯文档")
                        sys.exit(1)
                else:
                    # 默认获取所有工作表
                    data = fetch_all_sheets(args.url, cookies, args.verbose)
                    print(f"获取工作表: {len(data.get('sheets', []))} 个")
            except Exception as e:
                print(f"获取表格数据失败: {e}")
                sys.exit(1)

        # 增量更新检查：如果提供了 --revision，检查是否需要更新
        if args.revision is not None:
            remote_rev = data.get("clientVars", {}).get("collab_client_vars", {}).get("rev")
            if remote_rev == args.revision:
                print(f"已是最新版本 (revision: {remote_rev})，无需更新")
                sys.exit(0)
            print(f"检测到新版本 ({args.revision} -> {remote_rev})，正在更新...")

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

    # 确定输出模式：表格默认多表输出，只有指定 -o 单文件时才用单文件模式
    use_multi_output = input_type == "sheet" and not args.output and not args.output_dir

    if use_multi_output:
        # 多表模式（表格默认）
        output_dir = Path(args.output_dir) if args.output_dir else Path(".")
        output_dir.mkdir(parents=True, exist_ok=True)

        info_lines = [f"Input: {input_file}", f"Output Dir: {output_dir}", f"Type: {input_type}"]
        if args.sheet_name:
            info_lines.append(f"Sheet Name: {args.sheet_name}")
        if args.cleanup_source:
            info_lines.append("Cleanup source: enabled")
        _print_banner("Tencent Converter - 腾讯表格转 Markdown (多工作表)", info_lines)

        output_files = run_sheet_multi_output(
            input_file, output_dir,
            sheet_name=args.sheet_name,
            verbose=args.verbose,
            page_url=args.page_url,
            cleanup_source=args.cleanup_source,
        )

        print("\n" + "=" * 60)
        print(f"Conversion complete: {len(output_files)} files generated")
        print("=" * 60)

    elif args.output:
        # 单文件模式（指定 -o，向后兼容）
        output_file = Path(args.output)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        info_lines = [f"Input: {input_file}", f"Output: {output_file}", f"Type: {input_type}"]
        if input_type == "doc":
            info_lines.append(f"Keep intermediate: {args.keep_intermediate}")
            if args.page_url:
                info_lines.append(f"Page URL: {args.page_url}")
        if args.sheet_name:
            info_lines.append(f"Sheet Name: {args.sheet_name}")
        if args.cleanup_source:
            info_lines.append("Cleanup source: enabled")
        _print_banner("Tencent Converter - 腾讯文档/表格转 Markdown", info_lines)

        if input_type == "sheet":
            run_sheet_pipeline(
                input_file, output_file, args.verbose,
                cleanup_source=args.cleanup_source,
                sheet_name=args.sheet_name,
                page_url=args.page_url,
            )
        else:
            run_doc_pipeline(
                input_file, output_file, args.keep_intermediate, args.verbose,
                page_url=args.page_url, cleanup_source=args.cleanup_source
            )

        print("\n" + "=" * 60)
        # 输出 revision 信息（便于增量更新）
        if args.url:
            revision = data.get("clientVars", {}).get("collab_client_vars", {}).get("rev")
            if revision:
                print(f"revision: {revision}")
        print(f"Conversion complete: {output_file}")
        print("=" * 60)

    elif input_type == "doc" and args.output_dir:
        # 文档使用 --output-dir 模式
        # 1. 先运行 pipeline 获取标题
        # 2. 确定文件名：--doc-name > 标题 > 默认名
        # 3. 输出到 {output_dir}/{name}.md
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        info_lines = [f"Input: {input_file}", f"Output Dir: {output_dir}", f"Type: {input_type}"]
        if args.doc_name:
            info_lines.append(f"Doc Name: {args.doc_name}")
        if args.cleanup_source:
            info_lines.append("Cleanup source: enabled")
        _print_banner("Tencent Converter - 腾讯文档转 Markdown", info_lines)

        # 先转换到临时文件获取标题
        temp_output = Path(tempfile.mktemp(suffix=".md"))
        title = run_doc_pipeline(
            input_file, temp_output, args.keep_intermediate, args.verbose,
            page_url=args.page_url, cleanup_source=args.cleanup_source
        )

        # 确定文件名
        if args.doc_name:
            doc_name = args.doc_name
        elif title:
            doc_name = title
        else:
            doc_name = DEFAULT_DOC_NAME

        output_file = output_dir / f"{sanitize_filename(doc_name)}.md"
        temp_output.rename(output_file.resolve())

        print("\n" + "=" * 60)
        print(f"Conversion complete: {output_file}")
        print("=" * 60)

    elif input_type == "sheet" and args.output_dir:
        # 表格使用 --output-dir 模式（与 use_multi_output 相同逻辑）
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        info_lines = [f"Input: {input_file}", f"Output Dir: {output_dir}", f"Type: {input_type}"]
        if args.sheet_name:
            info_lines.append(f"Sheet Name: {args.sheet_name}")
        if args.cleanup_source:
            info_lines.append("Cleanup source: enabled")
        _print_banner("Tencent Converter - 腾讯表格转 Markdown (多工作表)", info_lines)

        output_files = run_sheet_multi_output(
            input_file, output_dir,
            sheet_name=args.sheet_name,
            verbose=args.verbose,
            page_url=args.page_url,
            cleanup_source=args.cleanup_source,
        )

        print("\n" + "=" * 60)
        print(f"Conversion complete: {len(output_files)} files generated")
        print("=" * 60)

    else:
        # 自动命名输出模式（当前目录 + 标题）
        _run_auto_output_conversion(input_file, input_type, args, temp_json_file)
        return

    # 清理临时文件
    if temp_json_file:
        _cleanup_file(temp_json_file, args.verbose, "temp file")


if __name__ == "__main__":
    main()
