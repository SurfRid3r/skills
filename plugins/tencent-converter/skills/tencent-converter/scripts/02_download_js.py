#!/usr/bin/env python3
"""
腾讯文档 JS 文件下载脚本

下载并格式化关键的腾讯文档 JavaScript 文件，用于分析解析逻辑。

注意: 本脚本使用正则表达式进行 JS 代码结构分析（类定义、函数提取），
这是合法用途，不违反项目禁止使用正则解析 Protobuf 数据的原则。
"""

import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path


def check_prettier() -> bool:
    """检查 prettier 是否已安装"""
    result = subprocess.run(
        ["prettier", "--version"],
        capture_output=True,
        text=True,
        timeout=5
    )
    return result.returncode == 0


def install_prettier() -> bool:
    """安装 prettier"""
    print("正在安装 prettier...")
    result = subprocess.run(
        ["npm", "install", "-g", "prettier"],
        capture_output=True,
        timeout=120
    )
    if result.returncode == 0:
        print("ok prettier 安装完成")
        return True
    print(f"fail prettier 安装失败: {result.stderr.decode()}")
    print("请手动安装: npm install -g prettier")
    return False


def format_js_with_prettier(file_path: Path) -> bool:
    """使用 prettier 格式化 JS 文件"""
    if not check_prettier() and not install_prettier():
        return False

    result = subprocess.run(
        ["prettier", "--write", str(file_path)],
        capture_output=True,
        timeout=30
    )
    if result.returncode == 0:
        print(f"  ok 已格式化: {file_path.name}")
        return True
    print(f"  fail 格式化失败: {result.stderr.decode()}")
    return False


def download_file(url: str, output_path: Path) -> bool:
    """下载文件"""
    if not url.startswith('http'):
        url = 'https://' + url

    print(f"  下载: {url}")
    try:
        urllib.request.urlretrieve(url, output_path)
        return True
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        print(f"  fail 下载失败: {e}")
        return False


def extract_js_urls_from_page(html_content: str) -> dict[str, str]:
    """从页面 HTML 中提取 JS 文件 URL"""
    script_pattern = r'<script[^>]+src=["\']([^"\']+)["\']'
    scripts = re.findall(script_pattern, html_content)

    js_urls = {}
    for script_url in scripts:
        if 'public-firstload-pc' not in script_url:
            continue

        # 提取文件名
        parts = script_url.split('/')
        filename = next((p for p in reversed(parts) if p.endswith('.js')), None)
        if filename:
            js_urls[filename] = script_url

    return js_urls


def analyze_js_structure(file_path: Path) -> dict:
    """分析 JS 文件结构"""
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    result = {
        "file": str(file_path),
        "size": len(content),
        "lines": content.count('\n'),
        "classes": [],
        "functions": [],
        "keywords": {}
    }

    # 查找类定义
    class_pattern = r'class\s+(\w+)\s*(?:extends\s+(\w+))?'
    for match in re.finditer(class_pattern, content):
        result["classes"].append({
            "name": match.group(1),
            "extends": match.group(2)
        })

    # 查找函数定义
    func_pattern = r'(?:function\s+(\w+)|(\w+)\s*\([^)]*\)\s*{|=>)'
    for match in re.finditer(func_pattern, content):
        func_name = match.group(1) or match.group(2)
        if func_name and func_name not in result["functions"]:
            result["functions"].append(func_name)

    # 统计关键词
    keywords = ["TextPool", "protobuf", "decode", "parse", "render",
                "initialAttributedText", "collab_client_vars",
                "\\r", "\\f", "\\x1e", "ZeroSpace"]
    for keyword in keywords:
        count = content.count(keyword)
        if count > 0:
            result["keywords"][keyword] = count

    return result


def save_analysis(output_dir: Path, analyses: list[dict]):
    """保存分析结果到 markdown"""
    output_dir.mkdir(parents=True, exist_ok=True)
    analysis_file = output_dir / "analysis.md"

    with open(analysis_file, 'w', encoding='utf-8') as f:
        f.write("# 腾讯文档 JS 文件分析报告\n\n")
        f.write("## 文件列表\n\n")

        for analysis in analyses:
            f.write(f"### {Path(analysis['file']).name}\n\n")
            f.write(f"- 大小: {analysis['size']} 字节\n")
            f.write(f"- 行数: {analysis['lines']}\n")

            if analysis['classes']:
                f.write(f"\n#### 类定义 ({len(analysis['classes'])})\n\n")
                for cls in analysis['classes'][:20]:
                    ext = f" extends {cls['extends']}" if cls['extends'] else ""
                    f.write(f"- `class {cls['name']}{ext}`\n")

            if analysis['keywords']:
                f.write(f"\n#### 关键词统计\n\n")
                for kw, count in sorted(analysis['keywords'].items(), key=lambda x: -x[1]):
                    f.write(f"- `{kw}`: {count} 次\n")

            f.write("\n---\n\n")

    print(f"分析报告已保存: {analysis_file}")


def load_from_local(js_dir: Path) -> list[Path]:
    """从本地目录加载已有的 JS 文件"""
    js_files = list(js_dir.glob("*.js"))

    if not js_files:
        print(f"未找到 JS 文件: {js_dir}")
        return []

    print(f"找到 {len(js_files)} 个 JS 文件:")
    for js_file in js_files:
        print(f"  - {js_file.name} ({js_file.stat().st_size} 字节)")

    return js_files


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='下载并分析腾讯文档 JS 文件')
    parser.add_argument('-o', '--output', default='tencent_js', help='输出目录')
    parser.add_argument('-l', '--local', help='从本地目录加载已有的 JS 文件')
    parser.add_argument('--no-format', action='store_true', help='跳过 prettier 格式化')
    parser.add_argument('--format-only', action='store_true', help='仅格式化现有文件')
    args = parser.parse_args()

    output_dir = Path(args.output)

    print("=" * 60)
    print("腾讯文档 JS 文件下载与分析")
    print("=" * 60)

    js_files = []

    if args.local:
        local_dir = Path(args.local)
        js_files = load_from_local(local_dir)
        output_dir = local_dir
    elif args.format_only:
        js_files = list(output_dir.glob("*.js"))
        print(f"格式化 {output_dir} 中的 {len(js_files)} 个文件")
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

        print("\n提示: 请使用浏览器开发者工具获取 JS 文件")
        print("步骤:")
        print("1. 打开目标腾讯文档")
        print("2. 打开开发者工具 -> Sources 面板")
        print("3. 查找包含 TextPool 的 JS 文件")
        print("4. 保存到本地目录")
        print(f"\n然后运行: python {__file__} -l <js目录>")
        print(f"或者直接将 JS 文件放在 tencent_js/ 目录后运行:")
        print(f"  python {__file__} --format-only")

        existing_files = list(output_dir.glob("*.js"))
        if existing_files:
            print(f"\n发现 {len(existing_files)} 个已有文件，将进行分析")
            js_files = existing_files
        else:
            print("\n未找到 JS 文件，退出")
            sys.exit(0)

    # 格式化 JS 文件
    if not args.no_format and js_files:
        print("\n格式化 JS 文件:")
        for js_file in js_files:
            format_js_with_prettier(js_file)

    # 分析 JS 文件
    if js_files:
        print("\n分析 JS 文件:")
        analyses = []
        for js_file in js_files:
            print(f"  分析: {js_file.name}")
            analyses.append(analyze_js_structure(js_file))

        save_analysis(output_dir, analyses)

    print("\n完成!")


if __name__ == "__main__":
    main()
