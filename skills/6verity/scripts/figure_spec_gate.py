#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""figure_spec_gate.py — v4.3 Scientific Figure System 门（§23-27 / T90-T94）。

检查"正式 Figure 有发表级视觉设计规范 + 可复现渲染"：
  T90: manifest 中 visual_priority=primary 的图必须存在 figures/specs/<id>.figure.json
       （figure_id/claim_id/figure_role/evidence_type/renderer/layout/visual_encoding/
        label_budget/final_width_mm 齐全）-> 缺 FAIL。
  T92: visual_encoding: primary 与 comparators 使用等权重彩色、baseline 也彩色
       -> WARN（语义层级：primary=强色 / comparators=灰 / baseline=浅灰虚线）。
  T93: renderer=r_ggplot2 但缺 renv.lock / R 依赖声明 -> FAIL（R 必须带来可复现性）。
  T94: figure/脚本引用用户本机字体绝对路径 -> FAIL（不绑定本机字体，交由系统探测）。

用法：python figure_spec_gate.py --workspace <项目根> [--strict]
输出：reports/gates/figure_spec_gate.json；退出码 0 PASS / 1 FAIL / 2 ERROR。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import gate_common as gc

MANIFEST_REL = "figures/figure_manifest.json"
SPECS_DIR = "figures/specs"
REQUIRED_SPEC_FIELDS = ("figure_id", "claim_id", "figure_role", "evidence_type",
                        "renderer", "layout", "visual_encoding", "label_budget",
                        "final_width_mm")
GRAY_WORDS = ("gray", "grey", "灰")
ABS_FONT_RE = re.compile(
    r"(?:[A-Za-z]:\\Users\\|/Users/|/home/)[^'\"\s)]*(?:\.ttf|\.otf|\.ttc|Fonts)")
GRAYSCALE_RE = re.compile(r"(gray|greyscale|grayscale|gray_scale|grey|灰阶|灰度)", re.I)


def _ok(check, msg):
    return {"level": "OK", "check": check, "message": msg}


def _warn(check, msg):
    return {"level": "WARN", "check": check, "message": msg}


def _violation(findings, check, msg, strict):
    findings.append({"level": "FAIL" if strict else "WARN", "check": check, "message": msg})


def check_figure_specs(ws, strict, findings):
    manifest = gc.load_json(ws / MANIFEST_REL, None)
    if not isinstance(manifest, list):
        _violation(findings, "figure_spec", f"{MANIFEST_REL} 缺失——无法判定 primary 图（T90）", strict)
        return
    primaries = [m for m in manifest if isinstance(m, dict)
                 and str(m.get("visual_priority", "")) == "primary"]
    if not primaries:
        findings.append(_warn("figure_spec", "manifest 无 visual_priority=primary 的图——跳过 T90 强制"))
        return
    specs_dir = ws / SPECS_DIR
    for m in primaries:
        fid = str(m.get("id", ""))
        spec_path = specs_dir / f"{fid}.figure.json"
        spec = gc.load_json(spec_path, None)
        if not isinstance(spec, dict):
            _violation(findings, "figure_spec",
                       f"primary 图 {fid} 缺 {SPECS_DIR}/{fid}.figure.json——正式主图必须有"
                       f"视觉设计规范（T90）", strict)
            continue
        missing = [f for f in REQUIRED_SPEC_FIELDS if not spec.get(f)]
        if missing:
            _violation(findings, "figure_spec",
                       f"primary 图 {fid} 的 FIGURE_SPEC 缺字段：{missing}（T90）", strict)
            continue
        if str(spec.get("figure_id", "")) != fid:
            _violation(findings, "figure_spec",
                       f"{fid}.figure.json 的 figure_id={spec.get('figure_id')} 与清单 id 不一致", strict)
        renderer = str(spec.get("renderer", ""))
        if renderer == "r_ggplot2":
            has_renv = (ws / "renv.lock").is_file() or \
                       any((ws / "R").rglob("*.R")) and (ws / "requirements_r.txt").is_file()
            if not (ws / "renv.lock").is_file():
                _violation(findings, "renderer_repro",
                           f"图 {fid} renderer=r_ggplot2 但缺 renv.lock——R 必须带来可复现性"
                           f"（renv restore 可恢复，T93）", strict)
        # T92：语义配色——primary/comparators/baseline 不可等权重彩色
        ve = spec.get("visual_encoding") or {}
        primary_c = str(ve.get("primary", "") or "")
        comparators = str(ve.get("comparators", "") or "")
        baseline = str(ve.get("baseline", "") or "")
        if comparators and not GRAYSCALE_RE.search(comparators):
            findings.append(_warn("figure_spec",
                                  f"图 {fid} comparators={comparators!r} 非灰阶——"
                                  f"primary 强色/comparators 灰阶/baseline 浅灰虚线 的语义层级（T92）"))
        if baseline and not GRAYSCALE_RE.search(baseline):
            findings.append(_warn("figure_spec",
                                  f"图 {fid} baseline={baseline!r} 非灰阶——基线应浅灰虚线（T92）"))
        findings.append(_ok("figure_spec", f"图 {fid} FIGURE_SPEC 齐全（renderer={renderer}，"
                                           f"layout={str(spec.get('layout'))[:40]}…）"))


def check_abs_font_paths(ws, strict, findings):
    """T94：Figure/脚本不得依赖用户本机字体绝对路径。"""
    hits = []
    import os
    for root, dirs, files in os.walk(ws):
        if any(part in ("__pycache__", ".git", "runs", "node_modules") for part in Path(root).parts):
            continue
        if Path(root).name == "runs":
            dirs[:] = []
            continue
        for f in files:
            p = Path(root) / f
            if p.suffix.lower() not in (".py", ".r", ".tex", ".typ", ".js", ".ts", ".md"):
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in ABS_FONT_RE.finditer(text):
                hits.append(f"{p.relative_to(ws)}: {m.group(0)[:70]}")
    if hits:
        _violation(findings, "abs_font_path",
                   f"脚本引用本机字体绝对路径（禁止；应系统探测字体）：{hits[:5]}（T94）", strict)
    else:
        findings.append(_ok("abs_font_path", "无本机字体绝对路径引用（字体经系统探测）"))


def main(argv=None):
    gc.force_utf8()
    ap = argparse.ArgumentParser(description="v4.3 Scientific Figure System 门禁")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--report", default=None)
    args = ap.parse_args(argv)

    ws = Path(args.workspace).resolve()
    findings = []
    check_figure_specs(ws, args.strict, findings)
    check_abs_font_paths(ws, args.strict, findings)

    fails = [f for f in findings if f["level"] == "FAIL"]
    warns = [f for f in findings if f["level"] == "WARN"]
    report = {
        "gate": "figure_spec", "schema_version": 1, "workspace": str(ws),
        "strict": args.strict, "engine": gc.manifest_engine(ws),
        "inputs": {"manifest": (ws / MANIFEST_REL).is_file(),
                   "specs_dir": any((ws / SPECS_DIR).glob("*.figure.json")) if (ws / SPECS_DIR).is_dir() else False},
        "findings": findings,
        "summary": {"fails": len(fails), "warns": len(warns), "checks": len(findings)},
        "note": "FIGURE_SPEC 是视觉设计规范（figure_manifest 是论文事实与 provenance），两者关联不合并。",
    }
    out = Path(args.report).resolve() if args.report else ws / "reports" / "gates" / "figure_spec_gate.json"
    gc.save_json(out, report)
    for f in findings:
        print(f"  [{f['level']}] {f['check']}: {f['message']}")
    print(f"FIGURE_SPEC: {'PASS' if not fails else 'FAIL'}（{len(fails)} FAIL / {len(warns)} WARN） -> {out}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
