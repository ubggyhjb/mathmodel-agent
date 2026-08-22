#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""appendix_source_list.py — v4.2（G-07/R-10 强化）：附录源码清单自动生成 + 一致性校验。

- render：扫描 code/ 下全部源文件，生成 LaTeX 片段 paper/appendix_source_list.tex：
    1) 描述表（tabular：文件名 + 从各源文件 docstring 首行自动提取的说明）；
    2) \subsubsection* 标题 + \lstinputlisting 全量引入。
  供 A_code.tex \\input 使用——禁止人工手写清单后长期漂移。

- check：把 A_code.tex 中的直接 \lstinputlisting 与 \input/include 递归展开的
  appendix_source_list.tex 片段合并，得到"附录实际引入的 src 集合"，与 code/
  实际文件集合比对（旧版只查 A_code 直接 listing：按推荐方式 \\input{fragment}
  时反而误报全部缺失——T56）。校验：
    - 附录引入集合 == code/ 集合（T54：附录 8 个但 ZIP 有 13 个 -> FAIL）；
    - 若 fragment 存在但 A_code 从未 \\input 它 -> WARN（提示接入清单片段）。

用法：
  python appendix_source_list.py --workspace <项目根> [--out paper/appendix_source_list.tex]
  python appendix_source_list.py --check --workspace <项目根>
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import gate_common as gc

EXCLUDE = {"__pycache__", "appendix_source_list.py"}  # 生成器自身不进清单
FRAGMENT_REL = "paper/appendix_source_list.tex"

LISTING_RE = re.compile(r"\\lstinputlisting(?:\[[^\]]*\])?\{([^}]+)\}")
INPUT_RE = re.compile(r"\\input\s*\{([^}]+)\}")
INCLUDE_RE = re.compile(r"\\include\s*\{([^}]+)\}")


def code_files(ws: Path) -> list:
    code = ws / "code"
    if not code.is_dir():
        return []
    out = []
    for p in sorted(code.rglob("*.py")):
        if p.name in EXCLUDE or any(part in EXCLUDE for part in p.parts):
            continue
        out.append(p.name)
    return out


def _docstring_summary(path: Path) -> str:
    """取源文件 docstring 第一行作为清单说明（无则空）。"""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    m = re.search(r'"""\s*\n?([^\n"]+)"""', text) or re.search(r'"""(?:\s*\n)?([^\n"]+)', text)
    if not m:
        return ""
    return m.group(1).strip()[:60].replace("\\", "\\\\").replace("_", "\\_").replace("%", "\\%")


def render(ws: Path) -> str:
    names = code_files(ws)
    lines = [
        "% appendix_source_list.tex — 由 appendix_source_list.py 自动生成（禁止手写清单）",
        "% 描述表与 listing 使用同一 manifest（code/ 目录扫描）自动生成，二者永不漂移。",
        "%",
        "\\begin{center}",
        "  {\\fontsize{12pt}{14.4pt}\\heiti 支撑材料源码文件清单}\\\\[0.4em]",
        "  \\begin{tabular}{p{2.8cm}p{11.0cm}}",
        "    \\toprule",
        "    \\textbf{文件} & \\textbf{说明} \\\\",
        "    \\midrule",
    ]
    for name in names:
        summary = _docstring_summary(ws / "code" / name)
        disp = name.replace("_", "\\_")
        lines.append(f"    {disp} & {summary if summary else '（无 docstring 说明）'} \\\\")
    lines += [
        "    \\bottomrule",
        "  \\end{tabular}",
        "\\end{center}",
        "\\vspace{0.8em}",
        "",
    ]
    for name in names:
        title = name.replace("_", "\\_").replace(".py", "")
        lines.append(f"\\subsubsection*{{{title}.py}}")
        lines.append(f"\\lstinputlisting[language=Python]{{../code/{name}}}")
        lines.append("")
    return "\n".join(lines)


def _resolve_input(ws: Path, text: str) -> set:
    """A_code.tex 文本 + 递归展开 \\input/\\include 片段后的 listing src 集合。"""
    srcs = set(LISTING_RE.findall(text))
    frag = ws / FRAGMENT_REL
    if frag.is_file():
        try:
            frag_text = frag.read_text(encoding="utf-8")
        except Exception:
            frag_text = ""
        srcs |= set(LISTING_RE.findall(frag_text))
    return srcs


def check(ws: Path, strict: bool):
    a_code = ws / "paper" / "sections" / "A_code.tex"
    actual = code_files(ws)
    if not actual:
        print("INFO code/ 为空或不存在，跳过附录清单校验")
        return 0
    if not a_code.is_file():
        print("FAIL A_code.tex 不存在")
        return 1
    text = a_code.read_text(encoding="utf-8", errors="replace")
    listed = set()
    for m in LISTING_RE.finditer(text):
        listed.add(Path(m.group(1).strip()).name)
    # 递归展开 \input/\include（相对 A_code.tex 所在目录解析；兼容 ../appendix_source_list 无后缀）
    for m in list(INPUT_RE.finditer(text)) + list(INCLUDE_RE.finditer(text)):
        inc = m.group(1).strip()
        p = a_code.parent / inc
        if not p.suffix:
            p = p.with_suffix(".tex")
        if p.is_file():
            listed |= {Path(x).name for x in LISTING_RE.findall(p.read_text(encoding="utf-8", errors="replace"))}
    # 兜底：生成片段按约定位置存在时也并入（G-07：check 与 render 契约统一）
    frag = ws / FRAGMENT_REL
    if frag.is_file():
        listed |= {Path(x).name for x in LISTING_RE.findall(frag.read_text(encoding="utf-8", errors="replace"))}
    bad = []
    missing = [f for f in actual if f not in listed]
    extra = [f for f in listed if f not in actual]
    if missing:
        bad.append(f"code/ 存在但附录未引用：{missing}")
    if extra:
        bad.append(f"附录引用但 code/ 不存在：{extra}")
    if bad:
        for b in bad:
            print("  [FAIL]", b)
        print("APPENDIX_SOURCE_LIST: FAIL（R-10：附录清单与 code/ 不一致，请重新生成）")
        return 1
    # 若片段文件存在但 A_code 未接入 -> WARN（G-07：check 与 render 契约统一）
    frag = ws / FRAGMENT_REL
    if frag.is_file() and not any("appendix_source_list" in m.group(1) for m in INPUT_RE.finditer(text)):
        print("  [WARN] appendix_source_list.tex 已生成但 A_code.tex 未 \\input 它——"
              "清单仍可能手工漂移（建议接入生成片段）")
    print(f"APPENDIX_SOURCE_LIST: PASS（{len(actual)} 个源文件全部一致 + {len(listed)} 个引入）")
    return 0


def main(argv=None):
    gc.force_utf8()
    ap = argparse.ArgumentParser(description="v4.2 附录源码清单自动生成 + 一致性校验")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--out", default=FRAGMENT_REL)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    ws = Path(args.workspace).resolve()
    if args.check:
        return check(ws, True)
    out = ws / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(ws), encoding="utf-8")
    print(f"APPENDIX_SOURCE_LIST: 生成 {out.relative_to(ws)}（{len(code_files(ws))} 个源文件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
