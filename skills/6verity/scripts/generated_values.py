#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""generated_values.py — v4 论文数值同源生成器（任务书 7 条）。

由 reports/value_map.json 声明（哪个结果 key -> 哪个 LaTeX 宏），从 results/*.json
读取实际值生成 paper/generated_values.tex：

    \\newcommand{\\QTwoGTwoLow}{14.2}
    \\newcommand{\\QFourAUPRC}{0.456}

论文只写 \\QTwoGTwoLow，不再手抄裸数字——数字天然绑定结果 key（trace 按命令/来源校验）。

value_map.json schema：
{
  "format": "{:.1f}",
  "macros": [
    {"name": "QTwoGTwoLow", "file": "results/p2_ic.json", "key": "G2.recommended.low",
     "format": "{:.1f}", "validate_range": [10, 30]}
  ]
}

用法：
  python generated_values.py --workspace <项目根>            # 生成/更新 generated_values.tex
  python generated_values.py --workspace <项目根> --check    # 校验 tex 与 results 一致
退出码：0 PASS；1 校验不一致或 key 缺失；2 配置缺失/错误。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import gate_common as gc

MAP_REL = "reports/value_map.json"
OUT_REL = "paper/generated_values.tex"


def _find(doc, key):
    cur = doc
    for part in str(key).split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit():
            cur = cur[int(part)]
        else:
            return None
    return cur


def load_map(ws: Path):
    doc = gc.load_json(ws / MAP_REL, None)
    if not isinstance(doc, dict) or not isinstance(doc.get("macros"), list):
        return None
    return doc


def render(ws: Path, doc: dict) -> list:
    """返回 (line, name, resolved_value, macro_text) 列表。"""
    out = []
    fmt_default = str(doc.get("format", "{:.2f}"))
    for m in doc["macros"]:
        name = str(m.get("name", "")).strip()
        rel = str(m.get("file", "")).strip().lstrip("/\\")
        key = str(m.get("key", "")).strip()
        if not name or not rel or not key:
            continue
        d = gc.load_json(ws / rel, None)
        val = _find(d, key) if isinstance(d, dict) else None
        fmt = str(m.get("format", fmt_default))
        text = "-".join(["-" * 8, "missing"])
        if val is None:
            text = "MISSING"
        else:
            try:
                text = fmt.format(float(val))
            except (TypeError, ValueError):
                text = str(val)
        macro = f"\\newcommand{{\\{name}}}{{{text}}}"
        out.append((name, key, rel, val, macro))
    return out


def main(argv=None):
    gc.force_utf8()
    ap = argparse.ArgumentParser(description="v4 论文数值同源生成器")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--out", default=OUT_REL)
    args = ap.parse_args(argv)

    ws = Path(args.workspace).resolve()
    doc = load_map(ws)
    if doc is None:
        print(f"ERROR: {MAP_REL} 缺失或无 macros（先由 5writing 声明 value_map）")
        return 2
    rows = render(ws, doc)
    missing = [r for r in rows if r[3] is None]
    if missing:
        for name, key, rel, _, _ in missing:
            print(f"  [FAIL] {name}: {rel}#{key} 在结果 JSON 中不存在")
        print(f"GENERATED_VALUES: FAIL（{len(missing)} 个宏无来源）")
        return 1

    out_path = ws / OUT_REL
    body = ["% generated_values.tex — 由 generated_values.py 自动生成（禁止手工编辑）",
            "% 来源: reports/value_map.json + results/*.json", ""]
    body += [f"% {k}  <-  {rel}#{key}" for name, key, rel, _, _ in rows]
    body += [macro for _, _, _, _, macro in rows]
    body.append("")
    if not args.check:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(body), encoding="utf-8")
        print(f"GENERATED_VALUES: 生成 {len(rows)} 个宏 -> {out_path.relative_to(ws)}")
        return 0

    # --check：与现有 tex 比对
    if not out_path.is_file():
        print(f"GENERATED_VALUES: FAIL（{out_path.relative_to(ws)} 不存在，先运行生成模式）")
        return 1
    tex = out_path.read_text(encoding="utf-8")
    bad = []
    for name, key, rel, val, macro in rows:
        if macro not in tex:
            bad.append(macro)
    if bad:
        print(f"  [FAIL] generated_values.tex 与结果不一致，缺少/不符宏: {len(bad)}")
        for b in bad[:5]:
            print("   ", b)
        print("GENERATED_VALUES: FAIL")
        return 1
    print(f"GENERATED_VALUES: PASS（{len(rows)} 个宏与 results 一致）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
