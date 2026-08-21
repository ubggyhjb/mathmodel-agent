#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""figure_story.py — v3 Figure Story 门（_mathmode.docx 十二、十五、十六条的自动化部分）。

每张正式主图必须先有 Figure Story 定义：
  reports/figure_story_manifest.json（数组，schema 见 7methodology-review SKILL）：
    id / main_message / audience_takeaway / panels / unique_information /
    redundant_with / visual_priority(primary|secondary|appendix) / files[] / caption

检查：
  1. manifest 必须存在且每个条目 main_message 非空（strict FAIL）；
  2. 论文实际引用的图（\includegraphics / image() / figures/*.pdf|png）必须登记在 manifest
     （以 files 文件名匹配；未登记 → strict FAIL；figures/ 下未采用文件 → WARN 待删）；
  3. visual_priority=primary 的数量 > max_primary（默认 6）→ WARN（核心图应 ≤5-6 张）；
  4. redundant_with 涉及的两张图同时出现在正文 → WARN（去重建议）；
  5. unique_information 为空 → WARN（图未说明独有信息，可能冗余）。

用法：python figure_story.py --workspace <项目根> [--strict]
输出：reports/gates/figure_story.json；退出码 0 PASS / 1 FAIL / 2 ERROR。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import gate_common as gc

MANIFEST_REL = "reports/figure_story_manifest.json"
VALID_PRIORITY = {"primary", "secondary", "appendix"}


def collect_paper_figures(ws: Path) -> list:
    """论文源（tex/typ）中引用的图像文件名。"""
    used = []
    paper = ws / "paper"
    if paper.is_dir():
        for p in sorted(paper.rglob("*")):
            if p.suffix.lower() not in (".tex", ".typ"):
                continue
            try:
                t = p.read_text(encoding="utf-8")
            except Exception:
                continue
            for m in re.finditer(r"(?:includegraphics|image)\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}", t):
                stem = Path(m.group(1).strip()).name
                used.append(stem)
            for m in re.finditer(r"image\(\s*\"([^\"]+)\"", t):
                stem = Path(m.group(1).strip()).name
                used.append(stem)
    return used


def collect_figure_dir(ws: Path) -> list:
    figs = ws / "figures"
    out = []
    if figs.is_dir():
        for p in sorted(figs.iterdir()):
            if p.suffix.lower() in (".pdf", ".png"):
                out.append(p.name)
    return out


def main(argv=None):
    gc.force_utf8()
    ap = argparse.ArgumentParser(description="v3 Figure Story 门禁")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--report", default=None)
    args = ap.parse_args(argv)

    ws = Path(args.workspace).resolve()
    findings = []
    manifest = gc.load_json(ws / MANIFEST_REL, None)
    if not isinstance(manifest, list):
        findings.append({"level": "FAIL" if args.strict else "WARN", "check": "manifest",
                         "message": f"{MANIFEST_REL} 缺失或非数组：主图未做 Figure Story 定义（7methodology-review 强制）"})
        manifest = []

    by_files = {}
    for item in manifest:
        idx = item.get("id", "?")
        if not item.get("main_message", "").strip():
            findings.append({"level": "FAIL" if args.strict else "WARN", "check": "purpose",
                             "message": f"Figure {idx} 缺 main_message（优先确定『这张图要证明什么』再画）"})
        if item.get("visual_priority") not in VALID_PRIORITY:
            findings.append({"level": "WARN", "check": "priority",
                             "message": f"Figure {idx} visual_priority={item.get('visual_priority')!r} 非法（primary|secondary|appendix）"})
        if not item.get("unique_information", "").strip():
            findings.append({"level": "WARN", "check": "redundancy",
                             "message": f"Figure {idx} 未声明 unique_information——若删除后无独有信息应删除"})
        for f in item.get("files", []):
            by_files[Path(f).stem] = idx

    used = collect_paper_figures(ws)
    used_stems = {Path(u).stem for u in used}
    unregistered = sorted(used_stems - set(by_files))
    if unregistered:
        findings.append({"level": "FAIL" if args.strict else "WARN", "check": "coverage",
                         "message": f"正文引用但未登记 Figure Story 的图：{unregistered[:10]}"})
    dir_files = {Path(x).stem for x in collect_figure_dir(ws)}
    unused = sorted(dir_files - used_stems - set(by_files))
    if unused:
        findings.append({"level": "WARN", "check": "cleanup",
                         "message": f"figures/ 下未被正文采用也未登记的图（建议删除）：{unused[:10]}"})

    primaries = [it for it in manifest if it.get("visual_priority") == "primary"]
    max_primary = 6
    if len(primaries) > max_primary:
        findings.append({"level": "WARN", "check": "focus",
                         "message": f"primary 图 {len(primaries)} 张 > {max_primary}（核心图应聚焦受控数量，其余 min 图降级 secondary/appendix）"})

    # 冗余对：互相 redundant_with 且都出现在正文
    for a in manifest:
        for b in a.get("redundant_with", []):
            if b in [x.get("id") for x in manifest]:
                findings.append({"level": "WARN", "check": "redundancy",
                                 "message": f"Figure {a.get('id')} 与 {b} 互为冗余声明——确认合并/删除后无独有信息"})

    fails = [f for f in findings if f["level"] == "FAIL"]
    warns = [f for f in findings if f["level"] == "WARN"]
    report = {
        "gate": "figure_story", "schema_version": 1, "workspace": str(ws),
        "strict": args.strict, "engine": gc.manifest_engine(ws),
        "manifest": MANIFEST_REL, "n_manifest": len(manifest),
        "n_primary": len(primaries), "n_used": len(used_stems),
        "findings": findings, "summary": {"fails": len(fails), "warns": len(warns)},
        "note": "先定义 Figure Story（main_message/panel/unique_information）再出图；WARN 级去重建议在 Paper Simplification Pass 处置。",
    }
    out = Path(args.report).resolve() if args.report else ws / "reports" / "gates" / "figure_story.json"
    gc.save_json(out, report)
    for f in findings:
        print(f"  [{f['level']}] {f['check']}: {f['message']}")
    print(f"FIGURE_STORY: {'PASS' if not fails else 'FAIL'}（{len(fails)} FAIL / {len(warns)} WARN） -> {out}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
