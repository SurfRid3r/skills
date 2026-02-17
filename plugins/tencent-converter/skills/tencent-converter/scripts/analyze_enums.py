#!/usr/bin/env python3
"""
腾讯文档 Mutations 枚举值统计分析脚本

功能:
1. 解析 case1/case2 结果文件
2. 提取所有 status_code 及上下文
3. 分析控制字符出现模式
4. 生成统计报告
"""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EnumContext:
    """枚举值上下文信息"""
    value: int
    ty: str
    ty_code: int
    bi: int = None
    ei: int = None
    has_author: bool = False
    has_image: bool = False
    raw_content: str = ""
    mutation_index: int = -1


@dataclass
class ControlCharContext:
    """控制字符上下文信息"""
    char: str
    code: int
    position_in_text: int
    text_snippet: str
    mutation_index: int
    surrounding_context: str = ""


@dataclass
class EnumStats:
    """枚举值统计"""
    status_codes: dict[int, list[EnumContext]] = field(default_factory=dict)
    ty_codes: dict[int, list[EnumContext]] = field(default_factory=dict)
    control_chars: list[ControlCharContext] = field(default_factory=list)
    text_samples: dict[int, list[str]] = field(default_factory=dict)


class EnumAnalyzer:
    """枚举值分析器"""

    KNOWN_STATUS_CODES = {
        1: "MS_MUTATION", 2: "MS_MUTATION", 3: "MS_MUTATION", 4: "MS_MUTATION_STYLE",
        5: "MS_MUTATION", 6: "MS_MUTATION", 7: "MS_MUTATION",
        101: "REVISION_RANGE", 102: "RUN_PROPERTY", 103: "FONT_PROPERTY",
        109: "LINK_PROPERTY", 110: "CODE_BLOCK", 111: "COMMENT",
        112: "NUMBERING", 115: "PICTURE_PROPERTY",
    }

    CONTROL_CHARS = {
        0x0d: "\\r", 0x1c: "\\x1c", 0x0f: "\\x0f", 0x1d: "\\x1d", 0x08: "\\b", 0x1e: "\\x1e",
    }

    def __init__(self):
        self.stats = EnumStats()

    def load_result(self, result_path: str) -> dict:
        with open(result_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def analyze_mutations(self, data: dict) -> EnumStats:
        for idx, mut in enumerate(data.get("mutations", [])):
            self._analyze_single_mutation(mut, idx)
        self._analyze_initial_text(data, data.get("mutations", []))
        return self.stats

    def _analyze_single_mutation(self, mut: dict, idx: int):
        ty = mut.get("ty", "")
        ty_code = mut.get("ty_code", 0)
        status_code = mut.get("status_code")
        bi = mut.get("bi")
        ei = mut.get("ei")
        author = mut.get("author", "")
        image_info = mut.get("image_info")

        context = EnumContext(
            value=ty_code, ty=ty, ty_code=ty_code, bi=bi, ei=ei,
            has_author=bool(author), has_image=bool(image_info),
            raw_content=str(mut), mutation_index=idx
        )

        if ty_code not in self.stats.ty_codes:
            self.stats.ty_codes[ty_code] = []
        self.stats.ty_codes[ty_code].append(context)

        if status_code is not None:
            context = EnumContext(
                value=status_code, ty=ty, ty_code=ty_code, bi=bi, ei=ei,
                has_author=bool(author), has_image=bool(image_info),
                raw_content=str(mut), mutation_index=idx
            )
            if status_code not in self.stats.status_codes:
                self.stats.status_codes[status_code] = []
            self.stats.status_codes[status_code].append(context)

    def _analyze_initial_text(self, data: dict, mutations: list[dict]):
        for idx, mut in enumerate(mutations):
            if mut.get("ty") == "is" and "s" in mut:
                self._scan_control_chars(mut["s"], idx)
                self._collect_text_samples(mut, idx)
                break

    def _scan_control_chars(self, text: str, mutation_idx: int):
        for pos, char in enumerate(text):
            code = ord(char)
            if code in self.CONTROL_CHARS or (code < 0x20 and code not in (0x09, 0x0a)):
                start = max(0, pos - 10)
                end = min(len(text), pos + 11)
                self.stats.control_chars.append(ControlCharContext(
                    char=char if code >= 0x20 else f"\\x{code:02x}",
                    code=code,
                    position_in_text=pos,
                    text_snippet=repr(text[pos:min(pos + 20, len(text))]),
                    mutation_index=mutation_idx,
                    surrounding_context=text[start:end]
                ))

    def _collect_text_samples(self, mut: dict, idx: int):
        if "s" not in mut:
            return

        text = mut["s"]
        bi = mut.get("bi", 0)
        segments = []
        current = ""

        for char in text:
            code = ord(char)
            if code == 0x0d:  # \r 段落分隔
                if current:
                    segments.append(current)
                current = ""
            elif code < 0x20 and code not in (0x09, 0x0a):
                if current:
                    segments.append(current)
                segments.append(f"[CTRL:{code:02x}]")
                current = ""
            else:
                current += char

        if current:
            segments.append(current)

        if bi not in self.stats.text_samples:
            self.stats.text_samples[bi] = []
        self.stats.text_samples[bi].extend(segments)

    def generate_report(self) -> str:
        """生成统计报告"""
        lines = [
            "# 腾讯文档 Mutations 枚举值分析报告",
            "",
            "## 生成时间",
            "自动生成 - 基于 mutations 数据分析",
            "",
            "## 1. Status Code 统计",
            "",
            "| Code | 名称 | 出现次数 | 含义推断 |",
            "|------|------|----------|----------|",
        ]

        for code, contexts in sorted(self.stats.status_codes.items()):
            count = len(contexts)
            known_name = self.KNOWN_STATUS_CODES.get(code, "未知")
            inference = self._infer_status_code_meaning(code, contexts)
            lines.append(f"| {code} | {known_name} | {count} | {inference} |")

        lines.extend(["", "## 2. Status Code 详细分析", ""])

        for code, contexts in sorted(self.stats.status_codes.items()):
            known_name = self.KNOWN_STATUS_CODES.get(code, "未知")
            lines.extend([
                f"### status_code = {code} ({known_name})",
                "",
                f"- **出现次数**: {len(contexts)}",
            ])

            bis = [c.bi for c in contexts if c.bi is not None]
            eis = [c.ei for c in contexts if c.ei is not None]
            if bis:
                lines.append(f"- **bi 范围**: {min(bis)} - {max(bis)}")
            if eis:
                lines.append(f"- **ei 范围**: {min(eis)} - {max(eis)}")

            with_author = sum(1 for c in contexts if c.has_author)
            lines.append(f"- **包含 author**: {with_author}/{len(contexts)}")

            with_image = sum(1 for c in contexts if c.has_image)
            if with_image > 0:
                lines.append(f"- **包含图片**: {with_image} 个")

            lines.extend([
                "",
                "**示例 mutation**:",
                "```json",
                contexts[0].raw_content[:500] if contexts else "",
                "```" if not contexts or len(contexts[0].raw_content) <= 500 else "...(truncated)\n```",
                "",
            ])

        # ty_code 统计
        lines.extend([
            "## 3. Ty Code 统计",
            "",
            "| Code | 类型 | 出现次数 |",
            "|------|------|----------|",
        ])

        for code in sorted(self.stats.ty_codes.keys()):
            contexts = self.stats.ty_codes[code]
            ty_name = contexts[0].ty if contexts else "unknown"
            lines.append(f"| {code} | {ty_name} | {len(contexts)} |")

        # 控制字符统计
        lines.extend(["", "## 4. 控制字符分析", ""])

        char_groups = defaultdict(list)
        for cc in self.stats.control_chars:
            char_groups[cc.code].append(cc)

        for code in sorted(char_groups.keys()):
            contexts = char_groups[code]
            char_repr = self.CONTROL_CHARS.get(code, f"\\x{code:02x}")
            positions_str = ", ".join(str(cc.position_in_text) for cc in contexts[:5])
            if len(contexts) > 5:
                positions_str += f" ... (共 {len(contexts)} 个位置)"

            lines.extend([
                f"### 0x{code:02x} ({char_repr})",
                "",
                f"- **出现次数**: {len(contexts)}",
                f"- **位置**: {positions_str}",
                "",
                "**上下文示例**:",
                "```",
            ])

            for cc in contexts[:3]:
                lines.append(f"  位置 {cc.position_in_text}: {cc.text_snippet}")
            if len(contexts) > 3:
                lines.append(f"  ... 还有 {len(contexts) - 3} 个")
            lines.extend(["```", ""])

        # 文本样本
        lines.extend([
            "## 5. 文本分段样本",
            "",
            "从初始文本中提取的内容段落:",
            "",
        ])

        for bi in sorted(self.stats.text_samples.keys()):
            segments = self.stats.text_samples[bi]
            lines.append(f"### bi={bi} 的内容")
            lines.append("")
            for seg in segments[:10]:
                if seg.startswith("[CTRL:"):
                    lines.append(f"- `{seg}`")
                elif seg.strip():
                    lines.append(f"- {repr(seg[:50])}")
            if len(segments) > 10:
                lines.append(f"- ... 还有 {len(segments) - 10} 个段落")
            lines.append("")

        return "\n".join(lines)

    def _infer_status_code_meaning(self, code: int, contexts: list[EnumContext]) -> str:
        """推断 status_code 的含义"""
        if code in self.KNOWN_STATUS_CODES:
            return self.KNOWN_STATUS_CODES[code]

        with_image = sum(1 for c in contexts if c.has_image)
        with_author = sum(1 for c in contexts if c.has_author)

        if with_image > 0:
            return f"包含图片 ({with_image} 个)"
        if with_author > len(contexts) // 2:
            return "用户相关属性"

        return "未知"


def analyze_file(result_path: str, output_dir: str = None):
    """分析单个结果文件"""
    analyzer = EnumAnalyzer()

    print(f"分析文件: {result_path}")
    data = analyzer.load_result(result_path)
    print(f"  Mutations: {data.get('mutations_count', 0)}")

    stats = analyzer.analyze_mutations(data)
    report = analyzer.generate_report()

    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        md_file = output_path / "enum_analysis.md"
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"  报告已保存: {md_file}")

        json_data = {
            "status_codes": {str(k): len(v) for k, v in stats.status_codes.items()},
            "ty_codes": {str(k): len(v) for k, v in stats.ty_codes.items()},
            "control_chars": [
                {"code": cc.code, "char": cc.char, "position": cc.position_in_text, "context": cc.text_snippet}
                for cc in stats.control_chars
            ],
            "text_segments": {str(k): v for k, v in stats.text_samples.items()},
        }

        json_file = output_path / "enum_stats.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        print(f"  统计已保存: {json_file}")

    return stats


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="腾讯文档 Mutations 枚举值统计分析")
    parser.add_argument("input", nargs="+", help="输入文件路径 (result.json)")
    parser.add_argument("-o", "--output", help="输出目录")

    args = parser.parse_args()

    print("=" * 60)
    print("腾讯文档 Mutations 枚举值分析")
    print("=" * 60)

    for input_path in args.input:
        analyze_file(input_path, args.output)

    print("\n分析完成!")


if __name__ == "__main__":
    main()
