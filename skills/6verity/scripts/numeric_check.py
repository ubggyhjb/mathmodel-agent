#!/usr/bin/env python3
"""数值一致性校验（跨平台，Windows/Linux 通用）。

用法:
    python numeric_check.py --paper-dir paper --results reports/RESULTS_REPORT.md
    python numeric_check.py --paper-dir paper --results results.json

功能:
  1. 从论文正文（*.typ / *.tex，跳过注释）抽取全部数值 token（含百分号、科学计数法）。
  2. 从结果记录（Markdown 或 JSON）抽取全部数值 token。
  3. 报告论文中出现但结果记录中找不到的数值（疑似编造，需人工核对），
     以及结果记录中的关键数值未被论文引用的情况。

注意: 这是启发式检查。论文合法引用题面常数、模板编号等会被列为 WARN，
需人工确认，不应直接判定论文错误。
"""
import json
import re
import sys
from pathlib import Path

# Windows 控制台/管道下强制 UTF-8 输出，避免中文乱码
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

NUM_RE = re.compile(
    r"(?<![\w.])"                      # 前面不是标识符字符
    r"\d+(?:,\d{3})*(?:\.\d+)?|\.\d+"  # 整数/千分位/小数
    r"(?:[eE][+-]?\d+)?"                # 科学计数法
    r"%?"                               # 百分号
)

SKIP_BLOCK = re.compile(r"<!--.*?-->", re.S)
LATEX_COMMENT = re.compile(r"(?<!\\)%.*$")
TYPST_COMMENT = re.compile(r"//.*$")


def norm_number(raw: str) -> str:
    """归一化数值 token：去千分位逗号、统一小数、去尾随 %。"""
    s = raw.strip().lower()
    percent = s.endswith("%")
    s = s[:-1] if percent else s
    s = s.replace(",", "")
    if "e" in s:
        mant, _, exp = s.partition("e")
        s = f"{float(mant):g}e{int(exp)}"
    else:
        try:
            f = float(s)
            s = f"{f:g}"
        except ValueError:
            pass
    return (s + "%") if percent else s


def clean_text(text: str, suffix: str) -> str:
    """按文件类型去掉注释，避免把 %（LaTeX）误用于 md/txt。"""
    text = SKIP_BLOCK.sub("", text)
    lines = []
    for line in text.splitlines():
        if suffix == ".tex":
            # 先去掉真正的行内注释（\% 由 lookbehind 保护），再还原转义百分号
            line = LATEX_COMMENT.sub("", line)
            line = line.replace(r"\%", "%")
        elif suffix == ".typ":
            line = TYPST_COMMENT.sub("", line)
        # .md / .txt / .json: % 不是注释，保留
        lines.append(line)
    return "\n".join(lines)


def extract_numbers(text: str, suffix: str = "") -> set[str]:
    out: set[str] = set()
    for line in clean_text(text, suffix).splitlines():
        for m in NUM_RE.finditer(line):
            out.add(norm_number(m.group(0)))
    return out


def read_all_text(path: Path) -> str:
    if path.is_dir():
        parts = []
        for p in sorted(path.rglob("*")):
            if p.is_file() and p.suffix.lower() in (".typ", ".tex", ".md", ".txt"):
                try:
                    parts.append(p.read_text(encoding="utf-8", errors="replace"))
                except OSError as e:
                    print(f"  [skip] 无法读取 {p}: {e}")
        return "\n".join(parts)
    return path.read_text(encoding="utf-8", errors="replace")


def extract_numbers_from(path: Path) -> set[str]:
    if path.is_dir():
        out: set[str] = set()
        for p in sorted(path.rglob("*")):
            if p.is_file() and p.suffix.lower() in (".typ", ".tex", ".md", ".txt"):
                try:
                    out |= extract_numbers(
                        p.read_text(encoding="utf-8", errors="replace"),
                        p.suffix.lower(),
                    )
                except OSError as e:
                    print(f"  [skip] 无法读取 {p}: {e}")
        return out
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        print(f"  [skip] 无法读取 {path}: {e}")
        return set()
    return extract_numbers(text, path.suffix.lower())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--paper-dir", required=True)
    ap.add_argument("--results", required=True)
    ap.add_argument("--strict", action="store_true", help="论文中缺失于结果记录的数值视为 FAIL")
    ns = ap.parse_args()
    paper_dir, results_path = Path(ns.paper_dir), Path(ns.results)

    print(f"论文目录: {paper_dir}")
    print(f"结果记录: {results_path}")
    print("=" * 60)

    paper_nums = extract_numbers_from(paper_dir)
    results_nums = extract_numbers_from(results_path)
    if results_path.suffix == ".json":
        # JSON 里数字已由正则抽取，但把顶层标量值也加入更稳
        try:
            data = json.loads(results_path.read_text(encoding="utf-8", errors="replace"))
            for v in _walk_values(data):
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    results_nums.add(norm_number(str(v)))
        except json.JSONDecodeError:
            pass

    missing = sorted(paper_nums - results_nums)
    uncited = sorted(results_nums - paper_nums)

    print(f"论文数值 token: {len(paper_nums)}")
    print(f"结果记录数值 token: {len(results_nums)}")
    print("-" * 60)
    if missing:
        print(f"[WARN] 论文中出现但结果记录未出现的数值（{len(missing)} 个，需人工核对来源）:")
        for n in missing:
            print(f"  - {n}")
    else:
        print("[OK] 论文中所有数值都能在结果记录中找到。")
    print("-" * 60)
    if uncited:
        print(f"[INFO] 结果记录中有但论文未引用的数值（{len(uncited)} 个，可能遗漏展示）:")
        for n in uncited:
            print(f"  - {n}")
    else:
        print("[INFO] 结果记录中的数值全部被论文引用。")
    print("=" * 60)
    print("结论: 本检查为启发式，WARN 项需人工确认后决定是否修改论文。")
    return 1 if ns.strict and missing else 0
def _walk_values(node):
    if isinstance(node, dict):
        for v in node.values():
            yield from _walk_values(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_values(v)
    else:
        yield node


if __name__ == "__main__":
    sys.exit(main())
