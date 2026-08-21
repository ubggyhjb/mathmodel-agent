#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""appendix_source_list.py — v4.1（R-10）：附录源码清单自动生成。

扫描 code/ 下全部源文件（+ artifact_manifest.json 若存在），生成 LaTeX 片段
paper/appendix_source_list.tex（\subsubsection* 标题 + lstinputlisting 全量引入），
供 A_code.tex \\input 使用——禁止人工手写清单后长期漂移。

用法：
  python appendix_source_list.py --workspace <项目根> [--out paper/appendix_source_list.tex]
  python appendix_source_list.py --check --workspace <项目根>
    # 校验 A_code.tex 中引用的 src 集合 == code/ 实际文件集合（不含生成器自身）
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import gate_common as gc

EXCLUDE = {"__pycache__", "appendix_source_list.py"}  # 生成器自身不进清单


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


def render(ws: Path) -> str:
    lines = ["% appendix_source_list.tex — 由 appendix_source_list.py 自动生成（禁止手写清单）", "%"]
    for name in code_files(ws):
        title = name.replace("_", "\\_").replace(".py", "")
        lines.append(f"\\subsubsection*{{{title}.py}}")
        lines.append(f"\\lstinputlisting[language=Python]{{../code/{name}}}")
        lines.append("")
    return "\n".join(lines)


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
    listed = set(re.findall(r"lstinputlisting(?:\[[^\]]*\])?\{\.\./code/([^}]+)\}", text))
    missing = [f for f in actual if f not in listed]
    extra = [f for f in listed if f not in actual]
    bad = []
    if missing:
        bad.append(f"code/ 存在但附录未引用：{missing}")
    if extra:
        bad.append(f"附录引用但 code/ 不存在：{extra}")
    if bad:
        for b in bad:
            print("  [FAIL]", b)
        print("APPENDIX_SOURCE_LIST: FAIL（R-10：附录清单与 code/ 不一致，请重新生成）")
        return 1
    print(f"APPENDIX_SOURCE_LIST: PASS（{len(actual)} 个源文件全部一致）")
    return 0


def main(argv=None):
    gc.force_utf8()
    ap = argparse.ArgumentParser(description="v4.1 附录源码清单自动生成")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--out", default="paper/appendix_source_list.tex")
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
