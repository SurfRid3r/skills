#!/usr/bin/env python3
"""通过 Cookie 获取腾讯表格 dop-api/get/sheet API 响应"""

import argparse
import json
import re
import sys
from pathlib import Path

# 添加脚本目录到 sys.path
_SCRIPT_DIR = Path(__file__).parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import requests

from sheet_enums import TabInfo


def parse_sheet_url(url: str) -> tuple[str, str, str]:
    """从表格 URL 提取 id, scode, tab 参数

    支持格式:
    - https://doc.weixin.qq.com/sheet/{id}?scode={scode}&tab={tab}
    - https://doc.weixin.qq.com/sheet/{id}?scode={scode}
    - https://doc.weixin.qq.com/sheet/{id}
    """
    # 尝试匹配带 scode 和 tab 的格式
    match = re.search(r'/sheet/([^?/]+)\?scode=([^&]+)(&tab=([^&]+))?', url)
    if match:
        doc_id = match.group(1)
        scode = match.group(2)
        tab = match.group(4) or ""
        return doc_id, scode, tab

    # 尝试匹配不带参数的格式
    match = re.search(r'/sheet/([^?/]+)', url)
    if match:
        return match.group(1), "", ""

    raise ValueError(f"无法解析表格 URL: {url}")


def get_xsrf_token(cookies: dict) -> str:
    """从 cookies 中提取 xsrf token"""
    return cookies.get("TOK", "")


def parse_tabs_response(data: dict, verbose: bool = False) -> list[TabInfo]:
    """解析 tabs API 响应

    Args:
        data: /dop-api/get/tabs API 响应数据
        verbose: 是否输出详细信息

    Returns:
        TabInfo 列表
    """
    tabs: list[TabInfo] = []

    if data.get("retcode", 0) != 0:
        return tabs

    header = data.get("header", [])
    if not header:
        return tabs

    # 工作表信息在 header[0].d 中
    tab_list = header[0].get("d", [])
    for tab in tab_list:
        if isinstance(tab, dict):
            tabs.append(TabInfo(
                tab_id=tab.get("id", ""),
                tab_name=tab.get("name", ""),
                hidden=tab.get("hidden", False),
            ))

    if verbose:
        print(f"发现 {len(tabs)} 个工作表")
        for tab in tabs:
            status = "隐藏" if tab.hidden else "可见"
            print(f"  - [{status}] {tab.tab_name} ({tab.tab_id})")

    return tabs


def fetch_tabs(
    doc_id: str,
    xsrf: str,
    cookies: dict,
    verbose: bool = False
) -> list[TabInfo]:
    """调用 /dop-api/get/tabs 获取工作表列表

    Args:
        doc_id: 文档 ID
        xsrf: xsrf token（从 cookies 中的 TOK 获取）
        cookies: cookie 字典
        verbose: 是否输出详细信息

    Returns:
        TabInfo 列表
    """
    api_url = "https://doc.weixin.qq.com/dop-api/get/tabs"
    params = {
        "padId": doc_id,
        "xsrf": xsrf,
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": f"https://doc.weixin.qq.com/sheet/{doc_id}",
        "Accept": "application/json, text/plain, */*",
    }

    if verbose:
        print(f"获取工作表列表: {api_url}")

    response = requests.get(api_url, params=params, cookies=cookies, headers=headers)
    response.raise_for_status()

    return parse_tabs_response(response.json(), verbose)


def fetch_single_sheet(
    doc_id: str,
    tab_id: str,
    xsrf: str,
    cookies: dict,
    verbose: bool = False
) -> dict:
    """获取单个工作表数据

    Args:
        doc_id: 文档 ID
        tab_id: 工作表 ID
        xsrf: xsrf token
        cookies: cookie 字典
        verbose: 是否输出详细信息

    Returns:
        工作表 API 响应数据
    """
    # 使用 opendoc API（与浏览器相同）
    api_url = "https://doc.weixin.qq.com/dop-api/opendoc"
    params = {
        "id": doc_id,
        "tab": tab_id,
        "outformat": "1",
        "normal": "1",
        "noEscape": "1",
        "startrow": "0",
        "endrow": "-1",
        "xsrf": xsrf,
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": f"https://doc.weixin.qq.com/sheet/{doc_id}",
        "Accept": "text/ejs-data, application/json, text/plain, */*",
    }

    if verbose:
        print(f"  获取工作表: {tab_id}")

    response = requests.get(api_url, params=params, cookies=cookies, headers=headers)
    response.raise_for_status()

    # 检查 Content-Type 决定解析方式
    content_type = response.headers.get('Content-Type', '')
    if 'ejs-data' in content_type:
        return parse_ejs_response(response.text, verbose=False)
    else:
        return response.json()


def fetch_all_sheets(
    url: str,
    cookies: dict,
    verbose: bool = False
) -> dict:
    """获取表格的所有可见工作表数据

    Args:
        url: 表格 URL
        cookies: cookie 字典
        verbose: 是否输出详细信息

    Returns:
        包含所有工作表数据的字典:
        {
            "padTitle": "表格标题",
            "doc_id": "xxx",
            "sheets": [
                {
                    "tab_id": "BB08J2",
                    "tab_name": "工作计划",
                    "data": {...}  # opendoc API 响应
                },
                ...
            ]
        }
    """
    doc_id, scode, _ = parse_sheet_url(url)
    xsrf = get_xsrf_token(cookies)

    if verbose:
        print(f"文档 ID: {doc_id}")
        print("正在获取工作表列表...")

    # 1. 获取工作表列表
    tabs = fetch_tabs(doc_id, xsrf, cookies, verbose)

    if not tabs:
        print("警告: 未找到任何工作表", file=sys.stderr)
        return {"padTitle": "", "doc_id": doc_id, "sheets": []}

    # 2. 过滤可见工作表
    tabs = [t for t in tabs if t.is_visible]
    if verbose:
        print(f"可见工作表: {len(tabs)} 个")

    # 3. 遍历获取每个工作表数据
    all_sheets = []
    pad_title = ""

    for i, tab in enumerate(tabs):
        if verbose:
            print(f"\n[{i+1}/{len(tabs)}] 获取: {tab.tab_name} (tab={tab.tab_id})")

        try:
            sheet_data = fetch_single_sheet(doc_id, tab.tab_id, xsrf, cookies, verbose)

            # 从第一个工作表获取表格标题
            if i == 0:
                pad_title = get_sheet_title(sheet_data)

            all_sheets.append({
                "tab_id": tab.tab_id,
                "tab_name": tab.tab_name,
                "data": sheet_data,
            })
        except Exception as e:
            print(f"  错误: 获取 {tab.tab_name} 失败: {e}", file=sys.stderr)
            continue

    return {
        "padTitle": pad_title,
        "doc_id": doc_id,
        "sheets": all_sheets,
    }


def parse_cookie_file(cookie_file: Path) -> dict:
    """解析 cookie 文件

    支持格式:
    1. Netscape 格式 (每行: domain flag path secure name value)
    2. 原始格式 (name=value; name2=value2)
    3. 每行一个 name=value
    """
    cookies = {}
    content = cookie_file.read_text().strip()

    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        # 尝试 Netscape 格式: domain flag path secure expiry name value
        parts = line.split('\t')
        if len(parts) >= 7:
            cookies[parts[5]] = parts[6]
        elif '=' in line:
            # 尝试原始格式: name=value; name2=value2 或单个 name=value
            if ';' in line:
                for pair in line.split(';'):
                    if '=' in pair:
                        name, value = pair.strip().split('=', 1)
                        cookies[name] = value
            else:
                name, value = line.split('=', 1)
                cookies[name] = value

    return cookies


def parse_ejs_response(text: str, verbose: bool = False) -> dict:
    """解析 EJS 分块格式响应

    EJS 格式 (可能有多个块):
    head
    json
    <length>
    <json content>
    [head
    json
    <length>
    <json content>
    ...]

    只解析第一个 JSON 块，合并多个块的 topLevel 字段。
    """
    if not text.startswith('head\njson\n'):
        raise ValueError(f"未知的响应格式，期望 EJS")

    result = {}
    pos = 0

    while pos < len(text):
        # 找到下一个块
        if not text[pos:].startswith('head\njson\n'):
            break

        # 解析块头
        parts = text[pos:].split('\n', 3)
        if len(parts) < 4:
            break

        try:
            length = int(parts[2])
        except ValueError:
            break

        # 提取 JSON 内容
        json_content = parts[3][:length] if length > 0 else parts[3]

        try:
            data = json.loads(json_content)
            if verbose:
                print(f"解析块: {pos}, 长度: {length}, keys: {list(data.keys())[:5]}")

            # 合并数据 - 第一个块作为基础，后续块合并顶层字段
            if not result:
                result = data
            else:
                for key, value in data.items():
                    if key not in result:
                        result[key] = value
                    elif isinstance(result[key], dict) and isinstance(value, dict):
                        result[key].update(value)

        except json.JSONDecodeError:
            pass

        # 移动到下一个块
        pos += len('head\njson\n') + len(parts[2]) + 1 + length

    if not result:
        raise ValueError("未能从 EJS 响应中解析出任何数据")

    return result


def validate_sheet_response(data: dict) -> tuple[bool, str]:
    """验证表格 API 响应数据是否有效

    Returns:
        (is_valid, error_message)
    """
    # 检查是否有错误返回
    if "errcode" in data and data["errcode"] != 0:
        return False, f"API 错误: {data.get('errmsg', '未知错误')} (code: {data['errcode']})"

    if "retcode" in data and data["retcode"] != 0:
        return False, f"API 错误: retcode={data['retcode']}"

    # 检查 clientVars 是否存在
    client_vars = data.get("clientVars", {})
    if not client_vars:
        return False, "响应缺少 clientVars，可能是 Cookie 无效或已过期"

    # 检查用户信息
    user_info = client_vars.get("userInfo", {})
    if not user_info:
        return False, "响应缺少用户信息，Cookie 可能已过期"

    # 检查表格内容
    collab_vars = client_vars.get("collab_client_vars", {})
    iat = collab_vars.get("initialAttributedText", {})
    text = iat.get("text", [])

    # text 应该是非空列表，且第一个元素包含 related_sheet
    if isinstance(text, list) and len(text) > 0:
        first_text = text[0]
        if isinstance(first_text, dict):
            if not first_text.get("related_sheet"):
                return False, "表格数据为空或格式不正确"
        elif isinstance(first_text, str) and len(first_text) == 0:
            return False, "表格内容为空，可能需要重新登录获取新 Cookie"

    return True, ""


def fetch_sheet_data(url: str, cookies: dict, verbose: bool = False) -> dict:
    """调用 dop-api/opendoc API 获取表格数据（与浏览器相同）"""
    doc_id, scode, tab = parse_sheet_url(url)

    # 使用与浏览器相同的 opendoc API
    api_url = "https://doc.weixin.qq.com/dop-api/opendoc"
    params = {
        "id": doc_id,
        "scode": scode,
        "outformat": "1",      # 请求完整 JSON 格式
        "normal": "1",         # 标准模式
        "noEscape": "1",       # 不转义
        "startrow": "0",       # 起始行
        "endrow": "-1",        # 结束行 (-1 表示全部)
    }
    if tab:
        params["tab"] = tab

    # 添加 xsrf 参数（从 Cookie 中的 TOK 获取）
    xsrf = cookies.get("TOK", "")
    if xsrf:
        params["xsrf"] = xsrf

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": url,
        "Accept": "text/ejs-data, application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    if verbose:
        print(f"API URL: {api_url}")
        print(f"Doc ID: {doc_id}")
        print(f"Scode: {scode[:10]}..." if scode else "Scode: (empty)")
        print(f"Tab: {tab or '(empty)'}")
        print(f"Cookies: {len(cookies)} 个")

    response = requests.get(api_url, params=params, cookies=cookies, headers=headers)

    if verbose:
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type')}")

    response.raise_for_status()

    # 检查 Content-Type 决定解析方式
    content_type = response.headers.get('Content-Type', '')
    if 'ejs-data' in content_type:
        return parse_ejs_response(response.text, verbose)
    else:
        return response.json()


def get_sheet_title(data: dict) -> str:
    """从 API 响应中获取表格标题

    Args:
        data: API 响应数据

    Returns:
        表格标题，如果无法获取则返回 "未命名表格"
    """
    try:
        client_vars = data.get("clientVars", {})
        pad_title = client_vars.get("padTitle", "")
        if pad_title:
            return pad_title
    except (KeyError, TypeError):
        pass
    return "未命名表格"


def main():
    parser = argparse.ArgumentParser(
        description="通过 Cookie 获取腾讯表格 dop-api/get/sheet API 响应",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 获取单个工作表
  %(prog)s -u "https://doc.weixin.qq.com/sheet/xxx?scode=yyy" -c cookies.txt -o output/sheet.json

  # 获取所有可见工作表
  %(prog)s -u "https://doc.weixin.qq.com/sheet/xxx?scode=yyy" -c cookies.txt --all-tabs -o output/all_sheets.json

Cookie 文件格式支持:
  - Netscape 格式 (curl -c 输出)
  - 原始格式 (name=value; name2=value2)
  - 每行一个 name=value
        """
    )
    parser.add_argument("-u", "--url", required=True, help="腾讯表格 URL")
    parser.add_argument("-c", "--cookie", required=True, help="Cookie 文件路径")
    parser.add_argument("-o", "--output", required=True, help="输出 JSON 文件路径")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")
    parser.add_argument("--title-only", action="store_true", help="仅输出表格标题")
    parser.add_argument("--all-tabs", action="store_true",
                        help="获取所有工作表（不仅仅是 URL 中指定的）")
    args = parser.parse_args()

    cookie_file = Path(args.cookie)
    output_file = Path(args.output)

    if not cookie_file.exists():
        print(f"错误: Cookie 文件不存在: {cookie_file}")
        return 1

    # 解析 cookie
    cookies = parse_cookie_file(cookie_file)
    if not cookies:
        print("错误: 未能从文件中解析出任何 cookie")
        return 1

    if args.verbose:
        print(f"加载了 {len(cookies)} 个 cookie")
        print(f"Cookie 名称: {', '.join(cookies.keys())}")

    # 获取表格数据
    try:
        if args.all_tabs:
            # 获取所有工作表
            data = fetch_all_sheets(
                args.url, cookies, args.verbose,
                include_hidden=args.include_hidden
            )

            # 仅输出标题
            if args.title_only:
                print(data.get("padTitle", "未命名表格"))
                return 0

            # 输出统计信息
            sheets = data.get("sheets", [])
            print(f"表格标题: {data.get('padTitle', '未命名表格')}")
            print(f"获取工作表: {len(sheets)} 个")
            for sheet in sheets:
                print(f"  - {sheet['tab_name']} ({sheet['tab_id']})")
        else:
            # 获取单个工作表
            data = fetch_sheet_data(args.url, cookies, args.verbose)

            # 仅输出标题
            if args.title_only:
                title = get_sheet_title(data)
                print(title)
                return 0

            # 验证响应有效性
            is_valid, error_msg = validate_sheet_response(data)
            if not is_valid:
                print(f"错误: {error_msg}")
                print("提示: 请更新 cookies.txt 文件或重新登录腾讯文档")
                return 1

            # 输出表格标题
            title = get_sheet_title(data)
            print(f"表格标题: {title}")

    except requests.HTTPError as e:
        print(f"HTTP 错误: {e}")
        return 1
    except requests.RequestException as e:
        print(f"网络错误: {e}")
        return 1
    except json.JSONDecodeError as e:
        print(f"JSON 解析错误: {e}")
        return 1
    except ValueError as e:
        print(f"参数错误: {e}")
        return 1

    # 保存响应
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    print(f"已保存: {output_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
