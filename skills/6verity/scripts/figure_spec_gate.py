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
    specs_dir = ws / SPECS_DIR
    for m in manifest:
        if not isinstance(m, dict):
            continue
        fid = str(m.get("id", ""))
        is_primary = str(m.get("visual_priority", "")) == "primary"
        spec_path = specs_dir / f"{fid}.figure.json"
        spec = gc.load_json(spec_path, None)
        if is_primary and not isinstance(spec, dict):
            _violation(findings, "figure_spec",
                       f"primary 图 {fid} 缺 {SPECS_DIR}/{fid}.figure.json——正式主图必须有"
                       f"视觉设计规范（T90）", strict)
            continue
        if not isinstance(spec, dict):
            continue  # secondary/appendix 无 spec 合法（T90 只强制 primary）
        missing = [f for f in REQUIRED_SPEC_FIELDS if not spec.get(f)]
        if is_primary and missing:
            _violation(findings, "figure_spec",
                       f"primary 图 {fid} 的 FIGURE_SPEC 缺字段：{missing}（T90）", strict)
            continue
        if str(spec.get("figure_id", "")) != fid:
            _violation(findings, "figure_spec",
                       f"{fid}.figure.json 的 figure_id={spec.get('figure_id')} 与清单 id 不一致", strict)
        # renderer 契约（§22/T93 对全部声明渲染器的图；primary 加 auto/fallback 强校验）
        renderer = str(spec.get("renderer", ""))
        if renderer == "auto":
            fallback = spec.get("renderer_fallback")
            if not fallback:
                _violation(findings, "renderer_repro",
                           f"图 {fid} renderer=auto 但未记录 renderer_fallback——"
                           f"渲染器不得静默切换（实际用什么必须在 spec 里写明）", strict)
            elif fallback not in ("python_matplotlib", "r_ggplot2", "tikz", "svg_inkscape"):
                _violation(findings, "renderer_repro",
                           f"图 {fid} renderer_fallback={fallback!r} 非法", strict)
        if renderer == "r_ggplot2" and not (ws / "renv.lock").is_file():
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


def check_render_provenance(ws, strict, findings):
    """v4.4（P1-17 / T118）：declared renderer 必须由 RENDER_PROVENANCE 执行证据证明。
    - 声明 renderer=r_ggplot2 的图必须在 repro/RENDER_PROVENANCE.json 有 entry；
    - renderer_declared 必须与 FIGURE_SPEC 一致；
    - renderer_actual != renderer_declared 时：fallback_used=true + fallback_reason 必填（WARN）；
      若同时仍声称"正式 R 渲染"（manifest note）-> FAIL；
    - 无 RENDDER_PROVENANCE 文件 -> FAIL（声明无执行证据）。"""
    prov = gc.load_json(ws / "repro" / "RENDER_PROVENANCE.json", None)
    manifest = gc.load_json(ws / MANIFEST_REL, None) or []
    specs_dir = ws / SPECS_DIR
    r_figs = []
    for m in manifest:
        if not isinstance(m, dict):
            continue
        fid = str(m.get("id", ""))
        spec = gc.load_json(specs_dir / f"{fid}.figure.json", None)
        if isinstance(spec, dict) and str(spec.get("renderer", "")) == "r_ggplot2":
            r_figs.append((fid, m))
    if not r_figs:
        return
    if not isinstance(prov, dict) or not isinstance(prov.get("entries"), list):
        _violation(findings, "render_provenance",
                   f"存在 {len(r_figs)} 张声明 r_ggplot2 的图但无 repro/RENDER_PROVENANCE.json——"
                   f"declared renderer 无执行证据（P1-17/T118）", strict)
        return
    entries = {str(e.get("figure_id", "")): e for e in prov["entries"] if isinstance(e, dict)}
    for fid, m in r_figs:
        e = entries.get(fid)
        if not isinstance(e, dict):
            _violation(findings, "render_provenance",
                       f"图 {fid} 声明 renderer=r_ggplot2 但 RENDER_PROVENANCE 无 entry——未记录实际渲染器（T118）",
                       strict)
            continue
        declared = str(e.get("renderer_declared", ""))
        actual = str(e.get("renderer_actual", ""))
        fallback = bool(e.get("fallback_used"))
        reason = str(e.get("fallback_reason", "") or "")
        spec = gc.load_json(specs_dir / f"{fid}.figure.json", None)
        spec_renderer = str((spec or {}).get("renderer", ""))
        if declared != spec_renderer:
            _violation(findings, "render_provenance",
                       f"图 {fid} RENDER_PROVENANCE.renderer_declared={declared!r} 与 FIGURE_SPEC "
                       f"renderer={spec_renderer!r} 不一致（P1-17）", strict)
        if actual != declared:
            if not fallback:
                _violation(findings, "render_provenance",
                           f"图 {fid} renderer_actual={actual!r} != declared={declared!r} 且 "
                           f"fallback_used 未置位——渲染器静默切换（T118）", strict)
            else:
                if not reason:
                    _violation(findings, "render_provenance",
                               f"图 {fid} fallback 但无 fallback_reason——必须显式记录（P1-17）", strict)
                else:
                    note_txt = str(m.get("note", "")) + str((spec or {}).get("note", ""))
                    if re.search(r"R/ggplot2 渲染|正式渲染器为 R|renderer= r_ggplot2", note_txt):
                        _violation(findings, "render_provenance",
                                   f"图 {fid} 实际 fallback（{reason}）但 manifest/spec 仍声称 R 渲染——"
                                   f"声明与执行矛盾（P1-17）", strict)
                    findings.append(_warn("render_provenance",
                                          f"图 {fid} 实际 renderer={actual}（fallback: {reason}）——"
                                          f"R 路由未验证，显式记录"))
        else:
            findings.append(_ok("render_provenance", f"图 {fid} declared==actual=={declared}（执行证据一致）"))


def check_claim_ids_resolve(ws, strict, findings):
    """v4.4（P1-14）：FIGURE_SPEC.claim_id 与 CLAIM_PROVENANCE（统一 Claim Registry）互通。
    任一 spec 的 claim_id 在 registry 无对应 claim -> FAIL；claim 的 claim_id 必须对应已知 spec（防悬空）。"""
    prov = gc.load_json(ws / "repro" / "CLAIM_PROVENANCE.json", None)
    if not isinstance(prov, dict) or not isinstance(prov.get("claims"), list):
        _violation(findings, "claim_registry",
                   "缺 repro/CLAIM_PROVENANCE.json——统一 Claim Registry 未建立，FigureSpec claim_id 无法 resolve（P1-14）",
                   strict)
        return
    reg_ids = {str(c.get("claim_id", "")) for c in prov["claims"] if isinstance(c, dict)}
    specs_dir = ws / SPECS_DIR
    if not specs_dir.is_dir():
        return
    for p in sorted(specs_dir.glob("*.figure.json")):
        spec = gc.load_json(p, None)
        if not isinstance(spec, dict):
            continue
        cid = str(spec.get("claim_id", "") or "")
        if not cid:
            continue
        if cid not in reg_ids:
            _violation(findings, "claim_registry",
                       f"{p.name} 的 claim_id={cid} 在 CLAIM_PROVENANCE 无对应 claim——"
                       f"FigureSpec 与 ClaimRegistry 未连接（P1-14）", strict)
    for cid in reg_ids:
        if cid.endswith(".CLAIM"):
            # 兜底 ID 体系（无 spec 的旧图）不再允许：spec 已补全后 .CLAIM 应为 0
            _violation(findings, "claim_registry",
                       f"claim_id={cid} 为兜底编号——未与 FIGURE_SPEC 统一 ID 体系连接（P1-14）", strict)
    if reg_ids:
        findings.append(_ok("claim_registry", f"claim registry {len(reg_ids)} 个 claim_id 与 FIGURE_SPEC 互通"))


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
    check_render_provenance(ws, args.strict, findings)
    check_claim_ids_resolve(ws, args.strict, findings)
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
