#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""idea_gate.py — v4.3 Idea Contract 门（Brainstorm 结构化产出校验）。

检查 reports/contracts/ 三件套（§12）：
  QUESTION_CONTRACT.json / IDEA_CANDIDATES.json / IDEA_DECISION.json
规则（每条对应任务书 v4.3 §12 与 T65-T69）：
  T65: 候选缺 required_assumptions 或 failure_conditions（不可证伪的候选）-> FAIL；
       IDEA_DECISION 缺失 -> FAIL。
  T68: Brainstorm 文本出现实验结论词（结果表明/显著提升/最终证明/该方法有效解决/
       最佳模型为）-> FAIL——Brainstorm 只许说"值得测试/需验证"。
  T66: IDEA_DECISION.rejected 的候选进入 FINAL_MODEL_SPEC（spec.idea_id 或
       model.family 命中）-> FAIL——rejected idea 隔离，只可进历史附录。
  T67: primary 为 advanced_alternative 但无 minimal sufficient 对照证据
       （无 minimal 候选或缺 evidence_against_minimal）-> FAIL——复杂方案必须
       证明比最简单方案值得。
  T69: QUESTION_CONTRACT 声明删失结构（interval/left/right censoring），而 primary
       用 exact-event OLS/线性回归且无 baseline_only/approximation 标记 -> FAIL。

用法：python idea_gate.py --workspace <项目根> [--strict]
输出：reports/gates/idea_gate.json；退出码 0 PASS / 1 FAIL / 2 ERROR。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import gate_common as gc

CONTRACT_REL = "reports/contracts/QUESTION_CONTRACT.json"
CANDIDATES_REL = "reports/contracts/IDEA_CANDIDATES.json"
DECISION_REL = "reports/contracts/IDEA_DECISION.json"
SPEC_REL = "reports/FINAL_MODEL_SPEC.json"

RESULT_CLAIM_WORDS = ["结果表明", "显著提升", "最终证明", "该方法有效解决", "最佳模型为"]
CENSORING_KEYS = ("interval_censoring", "left_censoring", "right_censoring")
EXACT_FAMILY_PAT = re.compile(r"exact|ols|linear\s*regression|线性回归|岭回归|ridge", re.I)
TIERS = {"minimal_sufficient_solution", "recommended_solution", "advanced_alternative"}
CENSORING_WORDS = ("区间删失", "左删失", "右删失", "interval", "censoring")


def _ok(check, msg):
    return {"level": "OK", "check": check, "message": msg}


def _warn(check, msg):
    return {"level": "WARN", "check": check, "message": msg}


def _violation(findings, check, msg, strict):
    findings.append({"level": "FAIL" if strict else "WARN", "check": check, "message": msg})


def _text_of(obj, deep=True):
    """收集 JSON 中全部文本（用于 T68 结论词扫描）。"""
    out = []
    if isinstance(obj, dict):
        for v in obj.values():
            out.extend(_text_of(v, deep))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(_text_of(v, deep))
    elif isinstance(obj, str):
        out.append(obj)
    return out


def check_question_contract(qc, findings, strict):
    if not isinstance(qc, dict) or not isinstance(qc.get("questions"), list) or not qc["questions"]:
        _violation(findings, "question_contract",
                   f"{CONTRACT_REL} 缺失或 questions 为空——题意契约未产出，候选方案无法对照题意",
                   strict)
        return {}
    findings.append(_ok("question_contract",
                        f"题意契约已产出：{len(qc['questions'])} 问（决策目标/分析单位/数据结构已登记）"))
    return {str(q.get("question_id", "")): q for q in qc["questions"]}


def check_candidates(cands, qc_by_q, findings, strict):
    if not isinstance(cands, dict) or not isinstance(cands.get("candidates"), list) or not cands["candidates"]:
        _violation(findings, "idea_candidates",
                   f"{CANDIDATES_REL} 缺失或 candidates 为空——未生成备选方案契约（T65）", strict)
        return []
    findings.append(_ok("idea_candidates",
                        f"候选契约已产出：{len(cands['candidates'])} 条候选（含强度/弱点/失败条件/三档）"))
    # T65：required_assumptions / failure_conditions 强制必填
    for c in cands["candidates"]:
        if not isinstance(c, dict):
            continue
        iid = str(c.get("idea_id", "?"))
        assume = c.get("required_assumptions")
        fail = c.get("failure_conditions")
        if not isinstance(assume, list) or not assume:
            _violation(findings, "idea_candidates",
                       f"候选 {iid} 缺 required_assumptions（非空数组）——没有显式假设的方案不可评估（T65）",
                       strict)
        if not isinstance(fail, list) or not fail:
            _violation(findings, "idea_candidates",
                       f"候选 {iid} 缺 failure_conditions（非空数组）——没有失败条件的方案不可证伪（T65）",
                       strict)
        tier = str(c.get("tier", ""))
        if tier and tier not in TIERS:
            _violation(findings, "idea_candidates",
                       f"候选 {iid} 的 tier={tier} 非法（应为 {sorted(TIERS)}）", strict)
        if not c.get("method_family"):
            findings.append(_warn("idea_candidates", f"候选 {iid} 缺 method_family 字段"))
    return cands["candidates"]


def check_no_result_claims(cands, ws, findings, strict):
    """T68：Brainstorm 阶段禁止实验结论式表达。"""
    texts = _text_of(cands)
    report = ws / "reports" / "BRAINSTORM_REPORT.md"
    if report.is_file():
        try:
            texts.append(report.read_text(encoding="utf-8"))
        except Exception:
            pass
    blob = "\n".join(texts)
    for w in RESULT_CLAIM_WORDS:
        for m in re.finditer(re.escape(w), blob):
            ctx = blob[max(0, m.start() - 30):m.end() + 30].replace("\n", " ")
            _violation(findings, "idea_claims",
                       f"Brainstorm 出现实验结论词『{w}』：…{ctx}…——候选阶段只可写"
                       f"『值得测试/需通过…验证/作为 baseline』（T68）", strict)


def check_rejected_isolation(dec, spec, findings, strict):
    """T66：rejected 候选不得进入 FINAL_MODEL_SPEC。"""
    rejected = set(str(x) for x in (dec.get("rejected") or []) if str(x).strip())
    if not rejected or not isinstance(spec, dict):
        return
    probs = spec.get("problems") or []
    for p in probs:
        pid = str(p.get("problem_id", "?"))
        refs = [p.get("idea_id"), p.get("primary_model"), (p.get("model") or {}).get("family")]
        for ref in refs:
            if not ref:
                continue
            r = str(ref)
            if r in rejected:
                _violation(findings, "rejected_isolation",
                           f"问题 {pid} 的 FINAL_MODEL_SPEC 引用 {r}，但该候选已在 IDEA_DECISION.rejected 中——"
                           f"被淘汰方案不得作为正式模型（T66）", strict)


def check_minimal_evidence(dec, cands, findings, strict):
    """T67：复杂 primary 需 minimal sufficient 对照证据。"""
    if not isinstance(dec, dict) or not dec.get("primary"):
        return
    by_q = {}
    for c in cands:
        if isinstance(c, dict):
            by_q.setdefault(str(c.get("question_id", "")), []).append(c)
    for qid, pid in (dec.get("primary") or {}).items():
        primary = next((c for c in by_q.get(str(qid), []) if str(c.get("idea_id", "")) == str(pid)), None)
        if primary is None:
            continue
        tier = str(primary.get("tier", ""))
        if tier != "advanced_alternative":
            continue
        # 复杂方案必须有 minimal sufficient 作为对照基线
        minimal = [c for c in by_q.get(str(qid), [])
                   if str(c.get("tier", "")) == "minimal_sufficient_solution"]
        if not minimal:
            _violation(findings, "minimal_evidence",
                       f"问题 {qid} primary={pid} 为 advanced_alternative，但无 minimal_sufficient_solution 对照——"
                       f"复杂方案应先证明简单方案不足（T67）", strict)
            continue
        ev = primary.get("evidence_against_minimal")
        if not isinstance(ev, list) or not ev:
            _violation(findings, "minimal_evidence",
                       f"问题 {qid} primary={pid}（advanced）未提供 evidence_against_minimal——"
                       f"无法证明优于 minimal solution（T67）", strict)
        else:
            findings.append(_ok("minimal_evidence",
                                f"问题 {qid} primary 为 advanced：已提供 {len(ev)} 条 minimal 反证"))


def check_censoring_compat(qc_by_q, dec, cands, findings, strict):
    """T69：契约声明删失时，primary 禁止 exact-event OLS（除非近似/baseline 标记）。"""
    if not isinstance(dec, dict) or not dec.get("primary"):
        return
    by_q = {}
    for c in cands:
        if isinstance(c, dict):
            by_q.setdefault(str(c.get("question_id", "")), []).append(c)
    for qid, pid in (dec.get("primary") or {}).items():
        q = qc_by_q.get(str(qid))
        if not isinstance(q, dict):
            continue
        sds = q.get("special_data_structure") or q.get("observation_mechanism") or {}
        has_cens = False
        if isinstance(sds, list):
            has_cens = any(("censoring" in str(s).lower()) for s in sds)
        elif isinstance(sds, dict):
            has_cens = any(bool(sds.get(k)) for k in CENSORING_KEYS)
        if not has_cens:
            continue
        primary = next((c for c in by_q.get(str(qid), []) if str(c.get("idea_id", "")) == str(pid)), None)
        if primary is None:
            continue
        fam = str(primary.get("method_family", ""))
        is_exact = bool(EXACT_FAMILY_PAT.search(fam))
        exempt = bool(primary.get("baseline_only")) or bool(primary.get("approximation"))
        if is_exact and not exempt:
            _violation(findings, "censoring_compat",
                       f"问题 {qid} 契约声明删失数据（{sds}），但 primary={pid} 用精确事件模型 "
                       f"（method_family={fam}）且未标记 baseline_only/approximation——"
                       f"删失结构被忽略（T69）", strict)


def main(argv=None):
    gc.force_utf8()
    ap = argparse.ArgumentParser(description="v4.3 Idea Contract 门禁")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--report", default=None)
    args = ap.parse_args(argv)

    ws = Path(args.workspace).resolve()
    findings = []
    qc = gc.load_json(ws / CONTRACT_REL, None)
    cands = gc.load_json(ws / CANDIDATES_REL, None)
    dec = gc.load_json(ws / DECISION_REL, None)
    spec = gc.load_json(ws / SPEC_REL, None)
    if dec is None:
        _violation(findings, "idea_decision",
                   f"{DECISION_REL} 缺失——候选收敛决策未产出（accepted/rejected/primary 必须机器化，T65）",
                   args.strict)

    qc_by_q = check_question_contract(qc, findings, args.strict)
    clist = check_candidates(cands, qc_by_q, findings, args.strict)
    check_no_result_claims(cands or {}, ws, findings, args.strict)
    if dec is not None:
        check_rejected_isolation(dec, spec, findings, args.strict)
        check_minimal_evidence(dec, clist, findings, args.strict)
        check_censoring_compat(qc_by_q, dec, clist, findings, args.strict)

    fails = [f for f in findings if f["level"] == "FAIL"]
    warns = [f for f in findings if f["level"] == "WARN"]
    report = {
        "gate": "idea_contracts", "schema_version": 1, "workspace": str(ws),
        "strict": args.strict, "engine": gc.manifest_engine(ws),
        "inputs": {"question_contract": qc is not None, "idea_candidates": cands is not None,
                   "idea_decision": dec is not None},
        "findings": findings,
        "summary": {"fails": len(fails), "warns": len(warns), "checks": len(findings)},
        "note": "Brainstorm 三件套由 brainstorm-mathmodel 阶段机器化产出；FAIL 项先修收敛决策，禁止放宽。",
    }
    out = Path(args.report).resolve() if args.report else ws / "reports" / "gates" / "idea_gate.json"
    gc.save_json(out, report)
    for f in findings:
        print(f"  [{f['level']}] {f['check']}: {f['message']}")
    print(f"IDEA: {'PASS' if not fails else 'FAIL'}（{len(fails)} FAIL / {len(warns)} WARN） -> {out}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
