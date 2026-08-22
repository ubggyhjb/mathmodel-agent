#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""methodology_gate.py — v3 Methodology Review 门（7methodology-review 的自动化部分）。

检查论文"模型定义是否成立"的方法学审稿项（对应 _mathmode.docx 一、二、三、四、五、八、九条）：
  DGP aud:             reports/methodology/data_generating_process.json 必须存在（strict），
                       并核对重复测量/删失/缺失/时间依赖等结构标记。
  assumptions:        reports/methodology/statistical_assumptions.json + 论文假设词交叉验证：
                       repeated_measurement=true 时"相互独立"必须带"随机效应/条件"修饰，否则 FAIL。
  censoring audit:    存在 interval censoring 时候选模型（Turnbull / interval Weibull /
                       log-normal / AFT）须在论文出现；插值恢复事件时间必须标"近似"
                      且做区间删失模型对比，否则 FAIL。
  degeneracy test:    reports/methodology/optimization_degeneracy.json：
                      |full - constraint_only| 相对差 < eps 且多组一致 → 标记
                      "解由约束边界决定"，论文若把该目标函数包装为核心创新 → WARN。
  model necessity:    reports/methodology/model_necessity.json：Primary ≥60% /
                      Baseline ≤20% / Robustness ≤20%（按正文内容份额）；
                      Rejected 模型不得出现在正文（须移入附录），否则 FAIL。
  sample size:        reports/methodology/sample_sizes.json：n < minimum_group_n（默认 max(20,5%N)）
                      或 CI 宽（ci_width_weeks > 上限，默认 4 周）→ exploratory 标记；
                      此时论文用"最佳时点"式强结论 → FAIL，应写"推荐窗口"。
  conclusion strength: 强结论词（最佳时点/精确决定/稳定表明/确定为）在弱证据
                      （小样本/宽 CI/exploratory）下 → FAIL；探索性结果必须用
                      "初步结果提示/可作为参考"级表述。

约定：本门输入（reports/methodology/*.json）由 7methodology-review skill 在建模前/中生成，
缺失即为 model definition 未审计，strict 下 FAIL（不判伪 PASS）。

用法：
  python methodology_gate.py --workspace <项目根> [--strict] [--policy style_policy.json]
输出：reports/gates/methodology_gate.json；退出码 0 PASS / 1 FAIL / 2 ERROR。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import gate_common as gc

M_DIR_REL = "reports/methodology/"
REQUIRED_INPUTS = [
    "data_generating_process.json",
    "statistical_assumptions.json",
    "model_necessity.json",
    "sample_sizes.json",
]

# ---------- 论文文本提取（LaTeX / Typst 通用简化） ----------

def scan_paper_text(ws: Path) -> str:
    """拼接 paper/ 下所有 .tex/.typ 的可见文本（剥离命令/注释/环境标记）。"""
    paper = ws / "paper"
    chunks = []
    if paper.is_dir():
        for p in sorted(paper.rglob("*")):
            if p.suffix.lower() not in (".tex", ".typ"):
                continue
            try:
                t = p.read_text(encoding="utf-8")
            except Exception:
                continue
            t = re.sub(r"(?m)(?<!\\)%.*$", "", t)                    # latex 注释
            t = re.sub(r"(?m)//.*$", "", t)                   # typst 注释
            t = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^{}]*\})?", " ", t)  # latex 命令
            t = re.sub(r"#[a-zA-Z-]+", " ", t)                # typst 函数
            t = re.sub(r"[{}\[\]]", " ", t)
            t = re.sub(r"\s+", " ", t)
            chunks.append(t)
    return " ".join(chunks)


def has_phrase(text: str, phrases) -> bool:
    return any(p in text for p in phrases)


# ---------- DGP / assumptions ----------

def check_dgp(dgp, text, strict, findings):
    if not isinstance(dgp, dict):
        _violation(findings, "dgp", "data_generating_process.json 缺失或非对象，建模前未审计数据生成机制", strict)
        return
    rep = dgp.get("repeated_measurement", False)
    if rep:
        findings.append(_ok("dgp", f"repeated_measurement=true（{dgp.get('group_id_field', '?')} 内相关），已识别重复测量结构"))
    cens = dgp.get("censoring") or {}
    kinds = [k for k in ("left", "interval", "right") if cens.get(k)]
    findings.append(_ok("dgp", f"删失结构: {kinds or '无'}；截断={cens.get('truncation', False)}"))
    if cens.get("interval"):
        findings.append(_ok("dgp", "存在区间删失：候选模型须含 Turnbull / interval Weibull / log-normal / AFT"))


def check_assumptions(assump, dgp, text, strict, findings):
    if not isinstance(assump, dict):
        _violation(findings, "assumptions", "statistical_assumptions.json 缺失，统计假设未登记", strict)
        return
    rep = bool((dgp or {}).get("repeated_measurement", False))
    # 假设词交叉验证：重复测量 + "相互独立"（无随机效应/条件修饰）→ FAIL
    if rep:
        bad = [m for m in re.finditer(r"[^。；]{0,30}相互独立[^。；]{0,30}", text)]
        for m in bad:
            seg = m.group(0)
            if not re.search(r"随机效应|条件|固定效应|随机截距|其间(的)?相关性|cluster", seg):
                _violation(findings, "assumptions",
                           f"repeated_measurement=true 但论文出现无修饰的『相互独立』：{seg[:60]}",
                           strict)
        if any(re.search(r"随机效应", s) for s in [m.group(0) for m in bad]):
            findings.append(_ok("assumptions", "『相互独立』带随机效应/条件修饰，允许（条件残差近似独立）"))
    # 正态性/无偏词 与 distribution 声明交叉
    dist = str(assump.get("distribution", "")).lower()
    if ("正态" in text or "normal" in text.lower()) and dist and "normal" not in dist and "正态" not in dist:
        findings.append(_warn("assumptions", f"论文出现『正态』措辞，但声明 distribution={dist}，需口径一致"))
    if "无偏" in text and str(assump.get("missingness_assumption", "")).lower() in ("mcar", "mar"):
        findings.append(_ok("assumptions", "缺失机制声明存在，遗漏/无偏口径需人工确认"))


# ---------- Censoring audit ----------

def check_censoring(dgp, text, strict, findings):
    cens = (dgp or {}).get("censoring") or {}
    if not cens.get("interval") and not cens.get("left") and not cens.get("right"):
        return
    cand = ["turnbull", "区间删失", "interval-censored", "interval weibull", "interval log-normal",
            "interval aft", "afrm", "afr"]
    if cens.get("interval") and not has_phrase(text, cand):
        _violation(findings, "censoring",
                   "存在区间删失但论文未出现候选模型（Turnbull / interval-censored Weibull / log-normal / AFT）",
                   strict)
    elif cens.get("interval"):
        findings.append(_ok("censoring", "区间删失候选模型在论文中出现"))
    # 插值恢复精确事件时间：必须标近似 + 区间删失模型对比
    if cens.get("interval") and has_phrase(text, ["插值", "线性插值", "interpolat"]):
        if not has_phrase(text, ["近似", "近似地", "approximately", "作为近似"]):
            _violation(findings, "censoring", "使用插值恢复事件时间但未明确标注『近似』", strict)
        if not has_phrase(text, ["区间删失", "interval-censored", "turnbull"]):
            findings.append(_warn("censoring", "插值恢复时间且未发现区间删失模型对比——建议报告对最终决策的影响"))


# ---------- Optimization degeneracy ----------

def check_degeneracy(deg, text, strict, findings):
    if not isinstance(deg, dict):
        findings.append(_warn("degeneracy", "optimization_degeneracy.json 缺失：优化问题未做 objective/constraint/full 三角对比"))
        return
    eps = float(deg.get("eps", 0.05))
    flagged = []
    for pr in deg.get("problems", []):
        wf, wc = pr.get("full"), pr.get("constraint_only")
        if wf is None or wc is None:
            continue
        try:
            wf, wc = float(wf), float(wc)
            base = max(abs(wc), 1e-9)
            rel = abs(wf - wc) / base
        except (TypeError, ValueError):
            continue
        pr["rel_gap"] = round(rel, 4)
        if rel < eps:
            flagged.append(pr.get("id", "?"))
    if flagged and len(flagged) >= 1:
        msg = (f"问题 {flagged} 的 |full - constraint| 相对差 < {eps}：最终解主要由约束边界决定，"
               f"目标函数对最终决策贡献有限；禁止将该目标函数包装为核心创新")
        findings.append(_warn("degeneracy", msg))
        if has_phrase(text, ["风险最小化创新", "创新点：风险", "核心创新.*目标函数"]):
            _violation(findings, "degeneracy", "退化问题仍将目标函数包装为核心创新表述", strict)
        else:
            findings.append(_ok("degeneracy", "未发现将退化目标函数包装为核心创新的表述"))
    elif deg.get("problems"):
        findings.append(_ok("degeneracy", f"{len(deg['problems'])} 个优化问题完成三角对比，无约束主导退化"))


# ---------- Model necessity ----------

INCLUDED_ROLES = {"Primary", "Baseline", "Robustness"}
APPENDIX_WORDS = ["附录", "appendix", "A_code"]


def check_necessity(nec, text, strict, findings):
    if not isinstance(nec, dict):
        _violation(findings, "necessity", "model_necessity.json 缺失：未做模型必要性分类", strict)
        return
    models = nec.get("models", [])
    if not models:
        _violation(findings, "necessity", "model_necessity.json 模型清单为空", strict)
        return
    share = nec.get("content_share", {})
    p, b, r = share.get("primary", -1), share.get("baseline", -1), share.get("robustness", -1)
    ok = True
    if p >= 0 and p < 0.60:
        _violation(findings, "necessity", f"Primary model 内容份额 {p:.0%} < 60%", strict)
        ok = False
    if b >= 0 and b > 0.20:
        _violation(findings, "necessity", f"Baseline 内容份额 {b:.0%} > 20%", strict)
        ok = False
    if r >= 0 and r > 0.20:
        _violation(findings, "necessity", f"Robustness 内容份额 {r:.0%} > 20%", strict)
        ok = False
    if ok:
        findings.append(_ok("necessity", f"模型内容份额 primary={p:.0%} baseline={b:.0%} robustness={r:.0%} 达标"))
    for m in models:
        role = m.get("role")
        if role == "Rejected":
            if m.get("id") and m.get("id") in text and not has_phrase(text, APPENDIX_WORDS):
                _violation(findings, "necessity",
                           f"被拒模型「{m.get('id')}」仍出现在正文（Req: 移入附录或缩写）", strict)
    for m in models:
        if m.get("role") and m.get("role") not in (set(INCLUDED_ROLES) | {"Rejected"}):
            findings.append(_warn("necessity", f"模型「{m.get('id')}」角色 {m.get('role')} 不在 Primary/Baseline/Robustness/Rejected 分类内"))


# ---------- Sample size / uncertainty ----------

def check_sample_size(ss, nec, text, strict, findings):
    if not isinstance(ss, dict):
        _violation(findings, "sample_size", "sample_sizes.json 缺失：未做分组样本量与不确定性门禁", strict)
        return
    groups = ss.get("groups", [])
    min_n = int(ss.get("minimum_group_n", 20))
    ci_lim = float(ss.get("ci_width_limit_weeks", 4.0))
    weak_groups = []
    strong_words = ["最佳时点", "最优时点", "精确决定", "稳定表明", "确定为", "必须为"]
    for g in groups:
        n = int(g.get("n", 0))
        n0 = int(g.get("effective_n", n))
        flags = []
        if n0 < min_n:
            flags.append(f"n={n0} < {min_n}")
        ci = g.get("ci_width_weeks")
        if ci is not None and float(ci) > ci_lim:
            flags.append(f"CI 宽 {ci} 周 > {ci_lim} 周")
        if flags:
            g["exploratory"] = True
            weak_groups.append(g.get("id", "?"))
            findings.append(_warn("sample_size", f"组「{g.get('id')}」{'; '.join(flags)} → 标记 exploratory，"
                                                 f"输出应写『推荐窗口』而非单点强结论"))
        elif g.get("exploratory"):
            g["exploratory"] = True
            weak_groups.append(g.get("id", "?"))
    if weak_groups and has_phrase(text, strong_words):
        _violation(findings, "sample_size",
                   f"弱证据组 {weak_groups} 仍使用强结论词（最佳时点/精确决定/稳定表明）——应写『推荐窗口』",
                   strict)
    elif weak_groups:
        findings.append(_ok("sample_size", "弱证据组未使用强结论词，或用『推荐窗口』口径"))


# ---------- Conclusion strength ----------

STRONG_WORDS = ["最佳时点", "最优时点", "精确决定", "稳定表明", "确定为"]


def check_conclusion_strength(ss, text, strict, findings):
    strong_hits = [w for w in STRONG_WORDS if w in text]
    if not strong_hits:
        findings.append(_ok("conclusion", "未发现『最佳时点/精确决定』类强结论词"))
        return
    weak = False
    if isinstance(ss, dict):
        for g in ss.get("groups", []):
            if g.get("exploratory") or int(g.get("n", 0)) < int(ss.get("minimum_group_n", 20)):
                weak = True
                break
    if weak:
        _violation(findings, "conclusion", f"弱证据（小样本/宽 CI/exploratory）下使用强结论词：{strong_hits}", strict)
    else:
        findings.append(_ok("conclusion", f"强结论词 {strong_hits} 有足量证据支撑（需人工复核样本量与 CI）"))


# ---------- v4 FINAL_MODEL_SPEC 模型契约（per-problem 审查） ----------
#
# 契约 = 7methodology-review 产出的 reports/FINAL_MODEL_SPEC.json（schema 见
# docs/FINAL_MODEL_SPEC.schema.md）。审查不是"全文出现关键词"，而是：
#   1. 同一 outcome.id 在不同问题中的 observation_mechanism 必须一致
#      （不一致且无 mechanism_change_rationale -> FAIL，抓"Q2 区间删失 / Q3 精确+右删失"）；
#   2. 每问题章节（paper_section）必须出现该问题 likelihood_evidence 证据词；
#   3. results/*.json 必须携带 model_spec_sha256 且与本契约 SHA256 一致；
#   4. 论文正文必须声明消费了 FINAL_MODEL_SPEC（WARN 级）。
SPEC_REL = "reports/FINAL_MODEL_SPEC.json"
MECHANISM_WORDS = {
    "left_censoring": ["左删失", "left-censored", "left censoring"],
    "interval_censoring": ["区间删失", "interval-censored", "interval censoring"],
    "right_censoring": ["右删失", "right-censored", "right censoring"],
    "truncation": ["截断"],
}


def read_cleaned_rel(ws: Path, rel: str) -> str:
    """读取 paper/ 下某文件并清洗为纯文本（与 scan_paper_text 同一套简化）。"""
    p = ws / "paper" / rel
    if not p.is_file():
        return ""
    try:
        t = p.read_text(encoding="utf-8")
    except Exception:
        return ""
    t = re.sub(r"(?m)(?<!\\)%.*$", "", t)
    t = re.sub(r"(?m)//.*$", "", t)
    t = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^{}]*\})?", " ", t)
    t = re.sub(r"#[a-zA-Z-]+", " ", t)
    t = re.sub(r"[{}\[\]]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t


def problem_section_paths(ws: Path, problem: dict) -> list:
    """解析某问题对应的论文章节文件（优先 spec.paper_section，其次 glob 猜测）。"""
    rel = str(problem.get("paper_section", "")).strip()
    if rel:
        return [rel] if (ws / "paper" / rel).is_file() else []
    pid = str(problem.get("problem_id", ""))
    num = re.sub(r"\D", "", pid)
    pattern = f"*problem{num}*" if num else "*"
    out = []
    paper = ws / "paper"
    if paper.is_dir():
        for p in sorted(paper.rglob(pattern)):
            if p.suffix.lower() in (".tex", ".typ"):
                out.append(p.relative_to(paper).as_posix())
    return out


def check_model_spec(spec, ws, text, strict, findings):
    if not isinstance(spec, dict) or not isinstance(spec.get("problems"), list) or not spec["problems"]:
        _violation(findings, "model_spec",
                   "FINAL_MODEL_SPEC.json 缺失或 problems 为空：方法审查后未产出可执行模型契约（v4 强制）",
                   strict)
        return
    problems = spec["problems"]
    findings.append(_ok("model_spec", f"契约已产出：{len(problems)} 个问题，contract_rev={spec.get('contract_rev', '?')}"))
    for p in problems:
        pid = str(p.get("problem_id", "?"))
        mech = p.get("observation_mechanism") or {}
        # 1) 机制声明词逐节核验
        secs = problem_section_paths(ws, p)
        if not secs:
            _violation(findings, "model_spec",
                       f"问题 {pid} 未找到论文章节（声明 paper_section 或按 *problem{N}* 匹配失败）——无法逐问题核验",
                       strict)
            continue
        sec_text = " ".join(read_cleaned_rel(ws, s) for s in secs).lower()
        missing_mech = []
        for field, words in MECHANISM_WORDS.items():
            if field == "truncation":
                continue
            if mech.get(field) and not any(w in sec_text for w in words):
                missing_mech.append(field)
        if missing_mech:
            _violation(findings, "model_spec",
                       f"问题 {pid} 章节（{secs[0]}）未出现契约声明的删失机制词：{missing_mech}",
                       strict)
        # 2) likelihood 证据词逐节核验（不许全文兜底；按"证据组"口径：每组至少一词出现；
        #    组由上一步 observation_mechanism 声明决定——声明了哪种删失才要求那种证据词）
        lik = str(p.get("likelihood", "")).strip()
        EVIDENCE_PAIRS = {
            "left_censoring": ["左删失", "left-censored"],
            "interval_censoring": ["区间删失", "interval-censored", "interval censoring"],
            "right_censoring": ["右删失", "right-censored"],
        }
        lik_groups = []
        if lik in ("interval", "exact") and lik == "interval":
            lik_groups = [EVIDENCE_PAIRS[k] for k in ("left_censoring", "interval_censoring", "right_censoring")
                          if mech.get(k)]
            if not lik_groups:
                lik_groups = [EVIDENCE_PAIRS["interval_censoring"]]
        elif lik == "exact":
            lik_groups = [["精确", "exact"]]
        ev = [str(e) for e in (p.get("likelihood_evidence") or []) if str(e).strip()]
        if lik_groups:
            missing_groups = [g for g in lik_groups if not any(w.lower() in sec_text for w in g)]
            if missing_groups:
                _violation(findings, "model_spec",
                           f"问题 {pid} 章节（{secs[0]}）缺少契约证据词组：{missing_groups}（likelihood={lik}）——"
                           f"该问可能沿用了过时模型表述",
                           strict)
            else:
                findings.append(_ok("model_spec", f"问题 {pid} 章节出现契约证据词组 {len(lik_groups)} 组"))
        elif ev and lik not in ("", "none"):
            missing_ev = [e for e in ev if e.lower() not in sec_text]
            if missing_ev:
                _violation(findings, "model_spec",
                           f"问题 {pid} 章节（{secs[0]}）缺少契约证据词：{missing_ev}（likelihood={lik}）",
                           strict)
            else:
                findings.append(_ok("model_spec", f"问题 {pid} 章节出现契约证据词 {ev[:3]}"))
        elif lik not in ("", "none") and not ev:
            findings.append(_warn("model_spec", f"问题 {pid} 未声明 likelihood_evidence——逐节核验降级为弱检查"))

    # 3) 同一 outcome.id 跨问题机制一致性（抓 false-pass 的关键规则）
    groups = {}
    for p in problems:
        oid = (p.get("outcome") or {}).get("id")
        if oid:
            groups.setdefault(str(oid), []).append(p)
    for oid, plist in groups.items():
        def _mech_core(m):
            # 只比较机制类字段（忽略 note/说明等自由文本）
            return {k: bool((m or {}).get(k)) for k in
                    ("left_censoring", "interval_censoring", "right_censoring", "truncation")}
        base = _mech_core(plist[0].get("observation_mechanism"))
        for p in plist[1:]:
            cur = _mech_core(p.get("observation_mechanism"))
            if cur != base and not str(p.get("mechanism_change_rationale", "")).strip():
                _violation(findings, "model_spec",
                           f"同一目标变量 {oid} 在问题 {plist[0].get('problem_id')} 与 {p.get('problem_id')} "
                           f"的观测机制不一致且无 mechanism_change_rationale——疑似该问沿用旧口径",
                           strict)

    # 4) result JSON 的 model_spec_sha256 校验（v4.3：registry 驱动，禁止"部分绑定即可过门"）
    spec_hash = gc.sha256_file(ws / SPEC_REL)
    check_result_binding(ws, spec, spec_hash, findings, strict)
    # 4b) v4.3：spec v2 语义一致性（distribution/feature_set_id/variable ID/active figure）
    if isinstance(spec, dict) and int(spec.get("schema_version", 1) or 1) >= 2:
        check_spec_v2_semantics(ws, spec, findings, strict)

    # 5) 论文声明消费契约 + contract_rev 失效传播（任务书 二十四条）
    if "FINAL_MODEL_SPEC" not in text and "final_model_spec" not in text.lower():
        findings.append(_warn("model_spec", "论文未声明消费 FINAL_MODEL_SPEC——建议在模型方法章节注明契约版本"))
    cur_rev = int(spec.get("contract_rev", 0) or 0)
    revs = [int(r) for r in re.findall(r"FINAL_MODEL_SPEC.{0,40}?rev\s*[=:]\s*(\d+)", text, re.S)]
    if revs and cur_rev:
        if max(revs) < cur_rev:
            _violation(findings, "model_spec",
                       f"论文声明的模型契约 rev={max(revs)} 落后于当前契约 rev={cur_rev}——"
                       f"摘要/方法/结果/小结/优缺点/灵敏度/结论中依赖该模型的段落可能仍用旧口径（stale）",
                       strict)
        else:
            findings.append(_ok("model_spec", f"论文注明契约版本 rev={max(revs)}，与当前契约一致"))


REGISTRY_ROLES = {"paper_authority", "model_output", "figure_source",
                  "external_registry", "diagnostic", "support"}


def _spec_hash_of(doc):
    """结果 JSON 的 model_spec_sha256 取值：顶层（v4 旧口径）与 _meta（v4.3 §15）双口径。"""
    if not isinstance(doc, dict):
        return None
    h = doc.get("model_spec_sha256")
    if h:
        return h
    meta = doc.get("_meta")
    if isinstance(meta, dict):
        return meta.get("model_spec_sha256")
    return None


def check_result_binding(ws, spec, spec_hash, findings, strict):
    """v4.3（任务书 P0 第 4 节 / T70）：model_spec_sha256 绑定由 results/RESULT_REGISTRY.json 驱动——
    所有 requires_model_spec_binding=true 的结果必须逐个绑定当前 spec hash；
    不存在"目录中只要有一部分 JSON 带 hash 就通过"的启发式判断。
    registry 缺失时退回旧启发式并 WARN（正式项目要求登记全部结果文件）。"""
    res_dir = ws / "results"
    if not res_dir.is_dir():
        return
    res_jsons = sorted(p for p in res_dir.glob("*.json") if p.name != "RESULT_REGISTRY.json")
    reg_path = res_dir / "RESULT_REGISTRY.json"
    registry = gc.load_json(reg_path, None)
    if not isinstance(registry, dict) or not isinstance(registry.get("artifacts"), list):
        with_spec = []
        for rj in res_jsons:
            doc = gc.load_json(rj, None)
            if _spec_hash_of(doc) is not None:
                with_spec.append((rj, _spec_hash_of(doc)))
        if res_jsons and not with_spec:
            _violation(findings, "model_spec",
                       f"results/ 已有 {len(res_jsons)} 个 JSON 但均未写 model_spec_sha256，"
                       f"且缺 results/RESULT_REGISTRY.json（v4 强制：结果必须绑定契约）",
                       strict)
        for rj, h in with_spec:
            if h != spec_hash:
                _violation(findings, "model_spec",
                           f"{rj.name} 的 model_spec_sha256 与当前契约不一致——结果由旧模型定义生成",
                           strict)
        findings.append(_warn("model_spec",
                              "results/RESULT_REGISTRY.json 缺失：绑定检查退回启发式（仅检测带 hash 文件），"
                              "建议登记全部结果文件并标记 authority 角色"))
        return
    arts = registry["artifacts"]
    seen = set()
    for i, a in enumerate(arts):
        rel = str(a.get("file", ""))
        role = str(a.get("role", ""))
        if not rel:
            _violation(findings, "model_spec", f"RESULT_REGISTRY artifact[{i}] 缺 file 字段", strict)
            continue
        seen.add(rel)
        rp = ws / rel
        if not rp.is_file():
            _violation(findings, "model_spec", f"REGISTRY 登记文件不存在：{rel}（dangling 条目）", strict)
            continue
        if role and role not in REGISTRY_ROLES:
            findings.append(_warn("model_spec",
                                  f"REGISTRY 条目 {rel} 的 role={role} 不在已知角色集 {sorted(REGISTRY_ROLES)}"))
        requires = bool(a.get("requires_model_spec_binding"))
        doc = gc.load_json(rp, None)
        has = _spec_hash_of(doc) is not None
        if requires:
            if not has:
                _violation(findings, "model_spec",
                           f"{rel}（role={role}）要求绑定当前契约但未写 model_spec_sha256——部分绑定不允许",
                           strict)
            elif _spec_hash_of(doc) != spec_hash:
                _violation(findings, "model_spec",
                           f"{rel} 的 model_spec_sha256 与当前契约不一致——结果由旧模型定义生成",
                           strict)
            else:
                findings.append(_ok("model_spec", f"{rel} 绑定当前契约 ({spec_hash[:12]})"))
        elif has:
            findings.append(_warn("model_spec",
                                  f"{rel} 写有 model_spec_sha256 但 registry 标记 requires_model_spec_binding=false——声明矛盾"))
    names = {rel.split("/")[-1] for rel in seen}
    for rj in res_jsons:
        if rj.name in names:
            continue
        doc = gc.load_json(rj, None)
        if _spec_hash_of(doc) is not None:
            _violation(findings, "model_spec",
                       f"{rj.name} 写有 model_spec_sha256 但未在 RESULT_REGISTRY 登记——绑定无法判定角色",
                       strict)
        else:
            findings.append(_warn("model_spec",
                                  f"results/{rj.name} 未在 RESULT_REGISTRY 登记（无法判定是否 paper-authority）"))


def check_spec_v2_semantics(ws, spec, findings, strict):
    """v4.3（P0-01~P0-04 / T71-T74）：spec v2 语义一致性——
    契约字段 ↔ 结果 _meta ↔ variables.json 登记 ↔ figure_manifest 四方对账。
    只检查 schema_version>=2 的契约；v1 契约保持旧规则（向后兼容）。"""
    problems = spec.get("problems") or []
    if not problems:
        return
    variables = gc.load_json(ws / "reports" / "variables.json", None)
    if not isinstance(variables, dict):
        variables = None
    manifest = gc.load_json(ws / "figures" / "figure_manifest.json", None)
    if not isinstance(manifest, list):
        manifest = None
    for p in problems:
        pid = str(p.get("problem_id", "?"))
        model = p.get("model") or {}
        feats = p.get("features") or {}
        # (a) 变量 ID 登记与可用性（T73）
        for v in feats.get("included") or []:
            vid = str(v.get("id", "")) if isinstance(v, dict) else str(v)
            if not vid:
                continue
            if variables is None:
                _violation(findings, "model_spec",
                           f"问题 {pid} features.included 引用变量 {vid}，但 reports/variables.json 缺失——"
                           f"变量必须统一登记 variable ID", strict)
            elif vid not in variables:
                _violation(findings, "model_spec",
                           f"问题 {pid} features.included 引用未登记变量 {vid}（variables.json 无此 ID）", strict)
            elif str((variables.get(vid) or {}).get("availability", "available")) == "unavailable":
                _violation(findings, "model_spec",
                           f"问题 {pid} primary feature set 引用 availability=unavailable 的变量 {vid}", strict)
        for v in feats.get("excluded") or []:
            vid = str(v.get("id", "")) if isinstance(v, dict) else str(v)
            if not vid:
                continue
            if variables is not None and vid not in variables:
                findings.append(_warn("model_spec",
                                      f"问题 {pid} features.excluded 引用未登记变量 {vid}（建议登记并说明排除理由）"))
        # (b) active figure conformance（T74）
        fig_ids = [str(f) for f in (p.get("figure_ids") or []) if str(f).strip()]
        if fig_ids and manifest is None:
            _violation(findings, "model_spec",
                       f"问题 {pid} 声明 figure_ids {fig_ids}，但 figures/figure_manifest.json 缺失", strict)
        elif fig_ids:
            ids = {str(m.get("id")): m for m in manifest if isinstance(m, dict)}
            for fid in fig_ids:
                m = ids.get(fid)
                if m is None:
                    _violation(findings, "model_spec",
                               f"问题 {pid} figure_ids 引用不存在于 figure_manifest 的图 {fid}（已删除/未登记）",
                               strict)
                    continue
                status = str(m.get("status", "")).lower()
                if status in ("deleted", "superseded"):
                    _violation(findings, "model_spec",
                               f"问题 {pid} figure_ids 引用 status={status} 的图 {fid}", strict)
                if any(str(s) == fid for s in (m.get("supersedes") or [])):
                    findings.append(_warn("model_spec",
                                          f"图 {fid} 被 {m.get('id')} supersedes——确认真实正文是否仍引用该图"))
        # (c) primary result 无 active figure / 未声明 -> WARN
        if (p.get("result_keys") or []) and not fig_ids and not p.get("no_figure_required"):
            findings.append(_warn("model_spec",
                                  f"问题 {pid} 有 result_keys 但无 figure_ids 且未声明 no_figure_required——"
                                  f"primary result 建议至少一个 active figure"))
    # (d) 结果 _meta 语义一致（T71/T72）：对 registry 中 requires 绑定且 hash 正确的文件按问题对账
    _check_result_metadata(ws, spec, findings, strict)


def _check_result_metadata(ws, spec, findings, strict):
    problems = {str(p.get("problem_id")): p for p in (spec.get("problems") or [])}
    registry = gc.load_json(ws / "results" / "RESULT_REGISTRY.json", None)
    if not isinstance(registry, dict):
        return  # 无 registry 时绑定检查已降级；语义对账随之不可判定
    spec_hash = gc.sha256_file(ws / SPEC_REL)
    for a in registry.get("artifacts") or []:
        if not bool(a.get("requires_model_spec_binding")):
            continue
        rp = ws / str(a.get("file", ""))
        doc = gc.load_json(rp, None)
        if not isinstance(doc, dict) or _spec_hash_of(doc) != spec_hash:
            continue  # 缺失/不匹配已在 check_result_binding 报
        pid = str(a.get("problem_id", "") or "")
        div = str((doc.get("_meta") or {}).get("problem_id", "") or "")
        if pid and div and pid != div:
            _violation(findings, "model_spec",
                       f"{a.get('file')} _meta.problem_id={div} 与 REGISTRY 登记 {pid} 不一致", strict)
        key = pid or div
        p = problems.get(key)
        if p is None:
            continue
        meta = doc.get("_meta") or {}
        model = p.get("model") or {}
        feats = p.get("features") or {}
        fam = str(model.get("family", "") or "")
        dist = str(model.get("distribution", "") or "")
        fsid = str(feats.get("feature_set_id", "") or "")
        if fam and str(meta.get("model_family", "") or "") != fam:
            _violation(findings, "model_spec",
                       f"{a.get('file')} _meta.model_family={meta.get('model_family')} 与契约 {key} "
                       f"model.family={fam} 不一致", strict)
        if dist and str(meta.get("model_distribution", "") or "") != dist:
            _violation(findings, "model_spec",
                       f"{a.get('file')} _meta.model_distribution={meta.get('model_distribution')} 与契约 {key} "
                       f"model.distribution={dist} 不一致", strict)
        if fsid and str(meta.get("feature_set_id", "") or "") != fsid:
            _violation(findings, "model_spec",
                       f"{a.get('file')} _meta.feature_set_id={meta.get('feature_set_id')} 与契约 {key} "
                       f"features.feature_set_id={fsid} 不一致", strict)


def _parse_ts(s: str):
    import datetime as _dt
    s = str(s).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            t = _dt.datetime.strptime(s, fmt)
            if t.tzinfo is None:
                t = t.replace(tzinfo=_dt.timezone.utc)
            return t.timestamp()
        except ValueError:
            continue
    return None


def _artifact_ts(ws, rel: str):
    """结果文件生成时间：优先 _meta.generated_at / generated_at，否则 mtime。"""
    p = ws / rel
    if not p.is_file():
        return None
    doc = gc.load_json(p, None)
    if isinstance(doc, dict):
        meta = doc.get("_meta") or {}
        g = meta.get("generated_at") or doc.get("generated_at")
        if g:
            t = _parse_ts(g)
            if t is not None:
                return t
    import datetime as _dt
    return _dt.datetime.fromtimestamp(p.stat().st_mtime,
                                      tz=_dt.timezone.utc).timestamp()


PRE_SPECIFIED_WORDS = ("预指定", "预先指定", "事前指定", "pre-specified", "pre_specified")


def check_selection_decisions(ws, spec, text, findings, strict):
    """v4.3（P0-05 / T75/T76）：科学决策账本——"预指定"必须有可验证的时序证据；
    one-se 规则必须偏向更简单模型（无例外）。"""
    dec_path = ws / "reports" / "decisions" / "MODEL_SELECTION_DECISION.json"
    decisions = gc.load_json(dec_path, None)
    decs = []
    if isinstance(decisions, dict):
        decs = [d for d in (decisions.get("decisions") or []) if isinstance(d, dict)]
    pre_used = bool(re.search(r"预指定|预先指定|事前指定|pre[- ]?specified", text, re.I))
    spec_pre = any(str((p.get("selection") or {}).get("model_family", "")) == "pre_specified"
                   or str((p.get("selection") or {}).get("feature_selection", "")) == "pre_specified"
                   for p in (spec.get("problems") or []) if isinstance(p, dict))
    if (pre_used or spec_pre) and not decs:
        _violation(findings, "decision",
                   "论文/契约声明『预指定』但缺 reports/decisions/MODEL_SELECTION_DECISION.json——"
                   "预指定无法从支撑材料证明（P0-05/T75）", strict)
        return
    for d in decs:
        did = str(d.get("decision_id", "?"))
        frozen = _parse_ts(str(d.get("frozen_at", "")))
        if frozen is None:
            findings.append(_warn("decision",
                                  f"{did} 缺可解析 frozen_at——预指定时序无法验证"))
            continue
        for rel in [str(r) for r in (d.get("before_result_artifacts") or []) if str(r)]:
            t = _artifact_ts(ws, rel)
            if t is None:
                _violation(findings, "decision",
                           f"{did} 声明 before_result_artifacts={rel} 但文件不存在/无时间戳——"
                           f"冻结时序不可证明", strict)
            elif frozen > t:
                _violation(findings, "decision",
                           f"{did} frozen_at={d.get('frozen_at')} 晚于结果 {rel}（生成 {t:.0f} vs 冻结 {frozen:.0f}）——"
                           f"『预指定』实际是事后合理化（P0-05/T75）", strict)
        rule = str(d.get("selection_rule", ""))
        sel_cx = d.get("selected_complexity")
        best_cx = d.get("complexity_of_best_simple")
        if rule == "one_se_choose_simpler" and isinstance(sel_cx, (int, float)) and isinstance(best_cx, (int, float)):
            if sel_cx > best_cx and not (d.get("exceptions") or []):
                _violation(findings, "decision",
                           f"{did} selection_rule=one_se_choose_simpler 但选择复杂度更高模型 "
                           f"（selected={sel_cx} vs one-SE 内更简 {best_cx}）且未声明 exceptions——"
                           f"one-SE 应偏向更简单模型（P0-05/T76）", strict)
            elif sel_cx > best_cx:
                findings.append(_warn("decision",
                                      f"{did} 选择更复杂模型（{sel_cx}>{best_cx}）但有 exceptions "
                                      f"{[str(e) for e in d.get('exceptions')]}——人工确认例外充分"))


def check_typed_uncertainty(ws, spec, findings, strict):
    """v4.3（§7/T79）：sampling CI 不得直接充当"推荐/决策窗口"——除非结果 JSON
    声明了 decision_window.construction_rule。"""
    text = scan_paper_text(ws)
    if "推荐窗口" not in text and "决策窗口" not in text:
        return
    res_dir = ws / "results"
    if not res_dir.is_dir():
        return
    # 收集带 uncertainty 结构的结果文件（优先 registry 绑定文件）
    res_jsons = sorted(p for p in res_dir.glob("*.json") if p.name != "RESULT_REGISTRY.json")
    docs = []
    for rj in res_jsons:
        doc = gc.load_json(rj, None)
        if isinstance(doc, dict) and isinstance(doc.get("uncertainty"), dict):
            docs.append((rj.name, doc))
    if not docs:
        findings.append(_warn("uncertainty",
                              "论文出现『推荐/决策窗口』但无任何结果 JSON 声明 typed uncertainty——"
                              "窗口构造规则未机器化"))
        return
    for name, doc in docs:
        u = doc.get("uncertainty") or {}
        dw = u.get("decision_window") if isinstance(u.get("decision_window"), dict) else None
        if dw is None:
            continue
        rule = dw.get("construction_rule")
        if rule:
            continue
        sid = (doc.get("_meta") or {}).get("problem_id", "")
        # 该问题语境：寻找"（95% 置信|CI…）…推荐窗口"或"推荐窗口 … 置信"邻近表述
        hit = re.search(r"[^。；]{0,80}(?:95\s*%|置信|CI)[^。；]{0,40}(?:推荐窗口|决策窗口)", text) \
            or re.search(r"[^。；]{0,40}(?:推荐窗口|决策窗口)[^。；]{0,80}(?:95\s*%|置信|CI)", text)
        if hit:
            _violation(findings, "uncertainty",
                       f"{name}（问题 {sid or '?'}）声明 sampling_ci 但 decision_window.construction_rule 为空，"
                       f"而论文将『置信区间』与『推荐/决策窗口』混用：…{hit.group(0)[:80]}…"
                       f"——CI 不得直接充当推荐窗口（§7/T79）", strict)
        else:
            findings.append(_warn("uncertainty",
                                  f"{name} 的 decision_window.construction_rule 为空——建议补齐窗口构造规则或"
                                  f"论文避免『推荐窗口』措辞"))


def check_failure_events(ws, findings, strict):
    """v4.3（§16/§18）：failure-driven rollback——machine-readable 失败事件。
    reports/methodology/failure_events.json 中 severity∈{blocker,critical} 且 status=open
    的事件阻止最终 PASS（控制面 BLOCKER）。"""
    events = gc.load_json(ws / "reports" / "methodology" / "failure_events.json", None)
    if not isinstance(events, dict) or not isinstance(events.get("events"), list):
        return
    for e in events["events"]:
        sev = str(e.get("severity", "")).lower()
        st = str(e.get("status", "")).lower()
        if sev in ("blocker", "critical") and st != "resolved":
            _violation(findings, "failure_events",
                       f"failure event {e.get('code', '?')}（severity={sev}, status={st}）未关闭——"
                       f"按 control_plane 回滚到 {e.get('return_to', '?')}，禁止继续推向论文阶段（§16）",
                       strict)


def conditional_required_inputs(dgp, spec, mdir, strict, findings):
    """v4（任务书 6 条）：方法学输入条件必需（适用就硬 FAIL，不适用不机械要求）。
       - DGP 存在删除失      -> censoring_report.json 必须存在；
       - 存在分类/监督学习问题 -> ml_operation_scope.json 必须存在；
       - 存在时间事件/优化决策 -> optimization_degeneracy.json 必须存在。"""
    cens = (dgp or {}).get("censoring") or {}
    has_censoring = any(cens.get(k) for k in ("left", "interval", "right"))
    kinds = []
    for p in (spec or {}).get("problems", []) or []:
        ot = str((p.get("outcome") or {}).get("type", ""))
        lik = str(p.get("likelihood", ""))
        kinds.append((ot, lik))
    has_ml = any(ot == "binary" for ot, _ in kinds) or bool(
        spec and re.search(r"交叉验证|cross.?valid|nested", json.dumps(spec, ensure_ascii=False)[:4000], re.I))
    has_opt = any(ot == "time_to_event" or lik == "interval" for ot, lik in kinds)

    checks = [
        (has_censoring, "censoring_report.json", "DGP 声明存在删失（left/interval/right）"),
        (has_opt, "optimization_degeneracy.json", "存在时间事件/区间删失优化决策问题"),
        (has_ml, "ml_operation_scope.json", "存在分类（监督学习）问题"),
    ]
    for cond, name, why in checks:
        if cond and not (mdir / name).is_file():
            _violation(findings, "conditional_input",
                       f"条件必需输入缺失：{why} -> {M_DIR_REL}{name} 必须存在（7methodology-review 强制）",
                       strict)
    return findings


def _ok(check, msg):
    return {"level": "OK", "check": check, "message": msg}


def _warn(check, msg):
    return {"level": "WARN", "check": check, "message": msg}


def _violation(findings, check, msg, strict):
    findings.append({"level": "FAIL" if strict else "WARN", "check": check, "message": msg})


def check_parsimony_reopen(ws, spec, findings, strict):
    """v4.2（P1-03/T61）：parsimony_reopen——更简单 ablation 不差于 primary 时必须重新评估。

    触发条件：results/*.json 顶层键（含键名 ablation/simpler/ablation_simpler 等）存在；
    处置：若存在 reports/methodology/parsimony_review.json（或 FINAL_MODEL_SPEC.parsimony_review）
    且 strategy ∈ {one_se_rule, complexity_penalty, pre_specified_interpretability} → 通过；
    否则 FAIL（strict）：不能一边说"全特征最优"一边报告简化模型均值更高而不解释。
    """
    results = ws / "results"
    hits = []
    if results.is_dir():
        for p in sorted(results.glob("*.json")):
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(doc, dict):
                continue
            for k, v in doc.items():
                if re.search(r"(ablation|simpler)", k, re.I) and isinstance(v, (dict, list)):
                    hits.append(f"{p.name}::{k}")
    if not hits:
        return
    review = gc.load_json(ws / "reports" / "methodology" / "parsimony_review.json", None)
    if review is None and isinstance(spec, dict):
        review = spec.get("parsimony_review")
    valid = isinstance(review, dict) and str(review.get("strategy", "")) in (
        "one_se_rule", "complexity_penalty", "pre_specified_interpretability")
    if valid:
        findings.append(_ok("parsimony",
                            f"简化模型差异已审查（strategy={review.get('strategy')}，"
                            f"decision={str(review.get('decision', ''))[:60]}）——触发项 {hits[:4]}"))
    else:
        _violation(findings, "parsimony",
                   f"发现简化/消融结果 {hits[:4]}（或与 primary 性能相当）但无 parsimony_review 记录"
                   f"（strategy=one_se_rule|complexity_penalty|pre_specified_interpretability）——"
                   f"必须重新打开 primary 选择解释（P1-03/T61）", strict)


def main(argv=None):
    gc.force_utf8()
    ap = argparse.ArgumentParser(description="v3 Methodology Review 门禁")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--report", default=None)
    args = ap.parse_args(argv)

    ws = Path(args.workspace).resolve()
    mdir = ws / M_DIR_REL
    findings = []
    missing = []

    def load(name):
        p = mdir / name
        doc = gc.load_json(p, None)
        if doc is None:
            missing.append(name)
        return doc

    dgp = load("data_generating_process.json")
    assump = load("statistical_assumptions.json")
    deg = load("optimization_degeneracy.json")
    nec = load("model_necessity.json")
    ss = load("sample_sizes.json")
    cens_repo = load("censoring_report.json")
    spec = gc.load_json(ws / SPEC_REL, None)

    text = scan_paper_text(ws)

    if missing and args.strict:
        for name in missing:
            _violation(findings, "input", f"必要输入缺失：{M_DIR_REL}{name}", strict=args.strict)

    # v4：模型契约 per-problem 审查（契约缺失在 strict 下 FAIL）
    check_model_spec(spec, ws, text, args.strict, findings)
    # v4：条件必需输入（任务书 6 条：适用就硬 FAIL，不适用不机械要求）
    conditional_required_inputs(dgp, spec, mdir, args.strict, findings)
    # v4.2（P1-03/T61）：parsimony reopen——更简 ablation 不差于 primary 必须解释
    check_parsimony_reopen(ws, spec, findings, args.strict)
    # v4.3（P0-05/T75/T76）：科学决策账本（预指定时序 / one-SE 方向）
    check_selection_decisions(ws, spec, text, findings, args.strict)
    # v4.3（§7/T79）：typed uncertainty——CI 不得直接充当推荐窗口
    check_typed_uncertainty(ws, spec, findings, args.strict)
    # v4.3（§16/§18）：failure-driven rollback——未关闭的 BLOCKER/CRITICAL 阻止 PASS
    check_failure_events(ws, findings, args.strict)

    if dgp is not None:
        check_dgp(dgp, text, args.strict, findings)
    if assump is not None:
        check_assumptions(assump, dgp, text, args.strict, findings)
    if cens_repo is not None:
        # censoring_report.json 显式报告优先
        if cens_repo.get("interpolation_used"):
            if not cens_repo.get("interpolation_labeled_approximate"):
                _violation(findings, "censoring", "插值恢复事件时间但 interpolation_labeled_approximate=false", args.strict)
            if not cens_repo.get("interval_model_comparison_done"):
                _violation(findings, "censoring", "使用插值但未与区间删失模型比较（interval_model_comparison_done=false）", args.strict)
        if cens_repo.get("candidate_models"):
            for cm in cens_repo["candidate_models"]:
                if cm.lower() in ("turnbull", "interval_weibull", "interval_lognormal", "interval_aft") \
                        and cm not in text.lower() and "区间删失" not in text.lower():
                    findings.append(_warn("censoring", f"候选模型 {cm} 未在论文正文出现（可仅在附录/方法说明）"))
    else:
        check_censoring(dgp, text, args.strict, findings)
    if deg is not None:
        check_degeneracy(deg, text, args.strict, findings)
    if nec is not None:
        check_necessity(nec, text, args.strict, findings)
    if ss is not None:
        check_sample_size(ss, nec, text, args.strict, findings)
        check_conclusion_strength(ss, text, args.strict, findings)
    else:
        check_conclusion_strength(None, text, args.strict, findings)

    fails = [f for f in findings if f["level"] == "FAIL"]
    warns = [f for f in findings if f["level"] == "WARN"]
    report = {
        "gate": "methodology", "schema_version": 1, "workspace": str(ws),
        "strict": args.strict, "engine": gc.manifest_engine(ws),
        "inputs": {k: (True if (mdir / k).is_file() else False) for k in REQUIRED_INPUTS + ["optimization_degeneracy.json", "censoring_report.json"]},
        "model_spec_present": isinstance(spec, dict),
        "missing_inputs": missing,
        "findings": findings,
        "summary": {"fails": len(fails), "warns": len(warns), "checks": len(findings)},
        "note": "门禁输入由 7methodology-review skill 生成；FAIL 项先修建模/论文，禁止改判放行。",
    }
    out = Path(args.report).resolve() if args.report else ws / "reports" / "gates" / "methodology_gate.json"
    gc.save_json(out, report)

    for f in findings:
        print(f"  [{f['level']}] {f['check']}: {f['message']}")
    print(f"METHODOLOGY: {'PASS' if not fails else 'FAIL'}（{len(fails)} FAIL / {len(warns)} WARN） -> {out}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
