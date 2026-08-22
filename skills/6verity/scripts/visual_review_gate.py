#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""visual_review_gate.py — v4.3 Visual Review Execution Closure 门（§29B / T100-T103）。

三层职责拆分（§29B.4）：
  visual_review_prepare  -> 渲染 contact sheet / 可疑三页上下文 / 单图预览（现有 visual_review.py）
  Reviewer C             -> 产出 reports/page_visual_review.json（逐页结构化裁决）
  本 gate                -> 校验 SHA 对齐 + 覆盖完整 + 未关闭 BLOCKER/MAJOR veto + 重审状态

规则：
  T100: visual_review.json 的 reviewed_pdf_sha256 与当前 PDF 一致，但缺
        page_visual_review.json 或 coverage_complete=false -> Final visual review FAIL。
  T101: reviewed_pages 必须覆盖 expected_pages（缺页/多页 -> FAIL）。
  T102: page_visual_review.json 存在未关闭 BLOCKER（如 orphan spill）-> FAIL
        （视觉提交阻断使用 veto 语义，不得被盲评总分"平均掉"——本 gate 不读总分）。
  T103: --root <repo> 时校验 Reviewer roster 单一事实源：workflow_spec.yaml final_review
        必须有 C=科学编辑与视觉审稿人；6verity/SKILL.md 执行席位不得把视觉席替换为
        "创新与决策效用"席（reviewer_roster_drift -> FAIL）。

用法：
  python visual_review_gate.py --workspace <项目根> [--strict] [--root <仓库根>]
输出：reports/gates/visual_review_gate.json；退出码 0 PASS / 1 FAIL / 2 ERROR。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import gate_common as gc

VISUAL_REVIEW_REL = "reports/visual_review.json"
PAGE_REVIEW_REL = "reports/page_visual_review.json"
PDF_REL = "paper/main.pdf"
BLOCKER_SEVERITIES = {"BLOCKER", "CRITICAL", "blocker", "critical"}

try:
    import fitz
except ImportError:
    fitz = None


def _violation(findings, check, msg, strict):
    findings.append({"level": "FAIL" if strict else "WARN", "check": check, "message": msg})


def _ok(check, msg):
    return {"level": "OK", "check": check, "message": msg}


def _warn(check, msg):
    return {"level": "WARN", "check": check, "message": msg}


def check_visual_execution(ws, strict, findings):
    vr_path = ws / VISUAL_REVIEW_REL
    pr_path = ws / PAGE_REVIEW_REL
    vr = gc.load_json(vr_path, None)
    pr = gc.load_json(pr_path, None)
    if vr is None:
        _violation(findings, "visual_execution",
                   f"{VISUAL_REVIEW_REL} 缺失——视觉评审材料未准备（渲染 contact sheet/单图预览并绑定 PDF SHA）",
                   strict)
        return
    # 当前 PDF SHA
    pdf = ws / PDF_REL
    if not pdf.is_file() or fitz is None:
        findings.append(_warn("visual_execution",
                              "paper/main.pdf 不存在或 PyMuPDF 不可用——无法核对 reviewed_pdf_sha256"))
        return
    with fitz.open(str(pdf)) as doc:
        cur_pages = doc.page_count
    cur_sha = gc.sha256_file(pdf)
    bound_sha = str(vr.get("reviewed_pdf_sha256", "") or "")
    if bound_sha != cur_sha:
        _violation(findings, "visual_execution",
                   f"visual_review.json 绑定 SHA {bound_sha[:12]} 与当前 PDF {cur_sha[:12]} 不一致——"
                   f"评审材料对应旧版 PDF（§29B.3/T100）", strict)
        return
    # T100：缺 page_visual_review 或覆盖不完整 -> FAIL
    if pr is None:
        _violation(findings, "visual_execution",
                   "visual_review.json SHA 与当前 PDF 一致，但 reports/page_visual_review.json 缺失——"
                   "『SHA 对齐』不能证明逐页看过（T100）", strict)
        return
    if pr.get("reviewed_pdf_sha256") != cur_sha:
        _violation(findings, "visual_execution",
                   f"page_visual_review.json 绑定 SHA {str(pr.get('reviewed_pdf_sha256'))[:12]} "
                   f"与当前 PDF 不一致——重编译后旧评审自动 stale（§29B/T100）", strict)
    # ---- v4.4（§4.1/4.2）：精确页面集合 + gate 计算 coverage（不再读 self-declared boolean）----
    reviewed = sorted({int(x) for x in (pr.get("reviewed_pages") or [])})
    expected = list(range(1, cur_pages + 1))
    if reviewed != expected:
        _violation(findings, "visual_coverage",
                   f"reviewed_pages 集合不精确：缺 {sorted(set(expected) - set(reviewed))[:8]}"
                   f" / 多 {sorted(set(reviewed) - set(expected))[:8]}——必须逐页 1..{cur_pages}（T101）",
                   strict)
    elif int(pr.get("expected_pages", 0) or 0) != cur_pages:
        _violation(findings, "visual_coverage",
                   f"expected_pages={pr.get('expected_pages')} 与当前 PDF 页数 {cur_pages} 不一致——"
                   f"评审 scope 与交付物不对齐（T101）", strict)
    # 逐页 record（page/verdict/checks/issues）；coverage 由 gate 从 records 计算
    records = pr.get("page_records") or []
    if not isinstance(records, list) or not records:
        _violation(findings, "visual_coverage",
                   "page_visual_review.json 无 page_records（每页 {page, verdict, checks, issues}）——"
                   "coverage 不能由 self-declared boolean 声明，须由 gate 从逐页记录计算（§4.2/T115）",
                   strict)
    else:
        rec_by_page = {}
        for r in records:
            if isinstance(r, dict):
                pg = int(r.get("page", 0) or 0)
                if pg > 0:
                    rec_by_page.setdefault(pg, r)
        missing_rec = [p for p in expected if p not in rec_by_page]
        no_verdict = [p for p, r in rec_by_page.items() if not str(r.get("verdict", "")).strip()]
        if missing_rec:
            _violation(findings, "visual_coverage",
                       f"page_records 缺 {len(missing_rec)} 页：{missing_rec[:10]}……——"
                       f"coverage 由 gate 计算，缺页即 FAIL（§4.2/T115）", strict)
        if no_verdict:
            _violation(findings, "visual_coverage",
                       f"page_records 有 {len(no_verdict)} 页无 verdict：{no_verdict[:8]}（T115）", strict)
        if pr.get("coverage_complete") is not True:
            _violation(findings, "visual_coverage",
                       "page_visual_review.json 仍声明 coverage_complete 非 true（旧自报字段）——"
                       "以 gate 计算的 page_records 覆盖为准，self-declared 仅作交叉核对（T100）", strict)
    # ---- v4.4（§4.3/4.4）：结构化 resolution + MAJOR 政策 ----
    unresolved = []
    major_open = []
    for pf in pr.get("page_findings") or []:
        if not isinstance(pf, dict):
            continue
        sev_upper = str(pf.get("severity", "")).strip().upper()
        if sev_upper not in {"BLOCKER", "CRITICAL", "MAJOR"}:
            continue
        res = pf.get("resolution")
        if isinstance(res, dict):
            ok_res = (str(res.get("status", "")) == "fixed_and_rereviewed"
                      and str(res.get("fixed_pdf_sha256", "")) == cur_sha
                      and int(res.get("review_trip", 0) or 0) >= 1)
            if str(res.get("status", "")) == "waived":
                ok_res = bool(res.get("waived_by") and res.get("rule_ref"))
            if not ok_res:
                (unresolved if sev_upper in {"BLOCKER", "CRITICAL"} else major_open).append(
                    (pf.get("page"), pf.get("type", sev_upper), str(res)[:60]))
        elif res:  # 非空字符串但非结构化 -> 不是 resolution（§4.3）
            (unresolved if sev_upper in {"BLOCKER", "CRITICAL"} else major_open).append(
                (pf.get("page"), pf.get("type", sev_upper), f"非结构化：{str(res)[:40]}"))
        else:
            (unresolved if sev_upper in {"BLOCKER", "CRITICAL"} else major_open).append(
                (pf.get("page"), pf.get("type", sev_upper), ""))
    if unresolved:
        _violation(findings, "visual_veto",
                   f"未关闭视觉 BLOCKER/CRITICAL（结构化 resolution 缺失或 fixed SHA ≠ 当前）："
                   f"{unresolved}——veto 语义，不得被任一席总分平均掉（T102/T116）", strict)
    if not unresolved:
        findings.append(_ok("visual_veto", "无未关闭视觉 BLOCKER/CRITICAL（veto semantics 通过）"))
    if major_open:
        _violation(findings, "visual_major",
                   f"MAJOR 未关闭（须 fixed_and_rereviewed 或显式 waived_by+rule_ref）："
                   f"{major_open}——MAJOR 必须 fixed 或 explicitly waived（§4.4/T116）", strict)
    else:
        findings.append(_ok("visual_major", "MAJOR 均已 fixed_and_rereviewed 或显式 waiver"))
    findings.append(_ok("visual_coverage",
                        f"逐页评审覆盖 {len(reviewed)}/{cur_pages} 页（SHA={cur_sha[:12]}；"
                        f"records={len(records)}）"))


def check_roster_drift(repo, findings, strict):
    """T103：Reviewer roster 唯一事实源 = workflow_spec.yaml final_review.personas。"""
    ws_path = repo / "workflow_spec.yaml"
    if not ws_path.is_file():
        _violation(findings, "roster_drift", "workflow_spec.yaml 缺失——无法核对 roster", strict)
        return
    try:
        import yaml
        spec = yaml.safe_load(ws_path.read_text(encoding="utf-8"))
    except Exception as exc:
        _violation(findings, "roster_drift", f"workflow_spec.yaml 解析失败: {exc}", strict)
        return
    personas = ((spec or {}).get("final_review") or {}).get("personas") or []
    c = next((p for p in personas if str(p.get("id", "")).upper() == "C"), None)
    if c is None:
        _violation(findings, "roster_drift", "workflow_spec final_review 无 personas C——视觉席缺失", strict)
    elif "视觉" not in str(c.get("name", "")) and "视觉" not in str(c.get("scope", "")):
        _violation(findings, "roster_drift",
                   f"workflow_spec final_review C（{c.get('name')}）无视觉职责——"
                   f"必须保留具有独立视觉否决权的 Reviewer C/visual seat（§29B.1）", strict)
    # 6verity/SKILL.md 执行席位不得以"创新席"替代视觉席
    skill = repo / "skills" / "6verity" / "SKILL.md"
    if not skill.is_file():
        findings.append(_warn("roster_drift", "6verity/SKILL.md 缺失——跳过执行席位核对"))
        return
    text = skill.read_text(encoding="utf-8", errors="replace")
    has_visual = bool(re.search(r"视觉.{0,40}审稿|视觉席|科学编辑.{0,20}视觉", text))
    has_innovation_seat = bool(re.search(r"创新与决策效用席|seat3_innovation", text))
    if has_innovation_seat and not has_visual:
        _violation(findings, "roster_drift",
                   "6verity/SKILL.md 执行席位用『创新与决策效用席』且无独立视觉席——"
                   "视觉职责被稀释（reviewer_roster_drift，T103）", strict)
    else:
        findings.append(_ok("roster_drift", "Reviewer roster 与 workflow_spec 一致（含独立视觉席 C）"))


def main(argv=None):
    gc.force_utf8()
    ap = argparse.ArgumentParser(description="v4.3 Visual Review Execution Closure 门禁")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--root", default=None, help="Agent 仓库根（T103 roster drift 检查）")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--report", default=None)
    args = ap.parse_args(argv)

    ws = Path(args.workspace).resolve()
    findings = []
    check_visual_execution(ws, args.strict, findings)
    if args.root:
        check_roster_drift(Path(args.root).resolve(), findings, args.strict)

    fails = [f for f in findings if f["level"] == "FAIL"]
    warns = [f for f in findings if f["level"] == "WARN"]
    report = {
        "gate": "visual_review", "schema_version": 1, "workspace": str(ws),
        "strict": args.strict,
        "inputs": {"visual_review": (ws / VISUAL_REVIEW_REL).is_file(),
                   "page_visual_review": (ws / PAGE_REVIEW_REL).is_file()},
        "findings": findings,
        "summary": {"fails": len(fails), "warns": len(warns), "checks": len(findings)},
        "note": "视觉裁决由 Reviewer C 产出 page_visual_review.json；本 gate 只做可证明执行校验（veto 语义）。",
    }
    out = Path(args.report).resolve() if args.report else ws / "reports" / "gates" / "visual_review_gate.json"
    gc.save_json(out, report)
    for f in findings:
        print(f"  [{f['level']}] {f['check']}: {f['message']}")
    print(f"VISUAL_REVIEW: {'PASS' if not fails else 'FAIL'}（{len(fails)} FAIL / {len(warns)} WARN） -> {out}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
