#!/usr/bin/env python3
"""通过 Cookie 获取腾讯文档 opendoc API 响应"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("错误: 需要安装 requests 库")
    print("运行: pip install requests")
    sys.exit(1)


def parse_url(url: str) -> tuple[str, str]:
    """从 URL 提取 id 和 scode 参数

    支持格式:
    - https://doc.weixin.qq.com/doc/{id}?scode={scode}
    - https://doc.weixin.qq.com/doc/{id}
    """
    # 尝试匹配带 scode 的格式
    match = re.search(r'/doc/([^?/]+)\?scode=([^&]+)', url)
    if match:
        return match.group(1), match.group(2)

    # 尝试匹配不带 scode 的格式
    match = re.search(r'/doc/([^?/]+)', url)
    if match:
        return match.group(1), ""

    raise ValueError(f"无法解析 URL: {url}")


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


def validate_opendoc_response(data: dict) -> tuple[bool, str]:
    """验证 opendoc 响应数据是否有效

    Returns:
        (is_valid, error_message)
    """
    # 检查是否有错误返回
    if "errcode" in data and data["errcode"] != 0:
        return False, f"API 错误: {data.get('errmsg', '未知错误')} (code: {data['errcode']})"

    # 检查 clientVars 是否存在
    client_vars = data.get("clientVars", {})
    if not client_vars:
        return False, "响应缺少 clientVars，可能是 Cookie 无效或已过期"

    # 检查用户信息
    user_info = client_vars.get("userInfo", {})
    if not user_info:
        return False, "响应缺少用户信息，Cookie 可能已过期"

    # 检查文档内容
    collab_vars = client_vars.get("collab_client_vars", {})
    iat = collab_vars.get("initialAttributedText", {})
    text = iat.get("text", "")

    # text 应该是非空列表（有内容）或非空字符串
    if isinstance(text, list):
        if len(text) == 0 or (len(text) > 0 and isinstance(text[0], str) and len(text[0]) == 0):
            return False, "文档内容为空，可能需要重新登录获取新 Cookie"
    elif isinstance(text, str) and len(text) == 0:
        # 空字符串可能是正常的（新文档），但如果 rev > 0 则不正常
        rev = collab_vars.get("rev", 0)
        if rev > 0:
            return False, f"文档有 {rev} 个版本但内容为空，Cookie 可能已过期"

    return True, ""


def fetch_opendoc(url: str, cookies: dict, verbose: bool = False) -> dict:
    """调用 opendoc API 获取文档数据"""
    doc_id, scode = parse_url(url)

    api_url = "https://doc.weixin.qq.com/dop-api/opendoc"
    params = {
        "id": doc_id,
        "scode": scode,
        "outformat": "1",       # 请求完整 JSON 格式
        "normal": "1",          # 标准模式
        "noEscape": "1",        # 不转义
        "doc_chunk_flag": "0",  # 不分块
        "commandsFormat": "1",  # 命令格式
    }
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


def main():
    parser = argparse.ArgumentParser(
        description="通过 Cookie 获取腾讯文档 opendoc API 响应",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s -u "https://doc.weixin.qq.com/doc/xxx?scode=yyy" -c cookies.txt -o output/opendoc.json

Cookie 文件格式支持:
  - Netscape 格式 (curl -c 输出)
  - 原始格式 (name=value; name2=value2)
  - 每行一个 name=value
        """
    )
    parser.add_argument("-u", "--url", required=True, help="腾讯文档 URL")
    parser.add_argument("-c", "--cookie", required=True, help="Cookie 文件路径")
    parser.add_argument("-o", "--output", required=True, help="输出 JSON 文件路径")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")
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

    # 获取 opendoc 响应
    try:
        data = fetch_opendoc(args.url, cookies, args.verbose)
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

    # 验证响应有效性
    is_valid, error_msg = validate_opendoc_response(data)
    if not is_valid:
        print(f"错误: {error_msg}")
        print("提示: 请更新 cookies.txt 文件或重新登录腾讯文档")
        return 1

    # 保存响应
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    print(f"已保存: {output_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
