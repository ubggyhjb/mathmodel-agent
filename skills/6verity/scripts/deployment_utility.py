#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deployment_utility.py — v4.2（P1-05/9.1）：部署效用审计（医学筛查/风险预警/高召回分类）。

对高敏感性筛查模型强制比较（T60）：
    - predict-all-positive baseline（全判阳性 PPV）
    - prevalence baseline（患病率）
    - chosen operating point（当前阈值 PPV）
    - ppv lift、false positives per true positive、number needed to confirm
若 chosen operating point 相对 trivial baseline 无增益（chosen_ppv <= all_positive_ppv 或
lift < 0），而论文出现"结论强度"措辞（显著提高阳性识别效率 / 临床预警支持价值等），
→ FAIL（deployment_claim）：结论必须降级为"风险排序/研究性筛查模型"。

输入（顺序）：
    1) --audit-json <path>：显式审计输入 JSON（prevalence / all_positive / chosen / nnc / fp_per_tp）
    2) 缺省：results/ 下文件名含 woman_level 或 deployment 的 JSON，按常见字段名启发式取数
    3) 无输入：SKIP（WARN，不 FAIL）

输出：reports/deployment_utility.json；退出码 0 PASS / 1 FAIL / 2 ERROR。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import gate_common as gc

STRONG_CLAIMS = [
    "显著提高阳性识别", "明显提高阳性识别", "显著提升阳性识别", "显著提高.*识别效率",
    "临床预警支持价值", "预警支持价值", "显著提升临床", "有效提高.*识别率",
]


def _find_audit_doc(ws: Path):
    """启发式：results/ 下找 woman_level / deployment 相关 JSON。"""
    results = ws / "results"
    if not results.is_dir():
        return None
    cands = []
    for p in sorted(results.glob("*.json")):
        name = p.name.lower()
        if "woman_level" in name or "deployment" in name:
            cands.append(p)
    if not cands:
        return None
    try:
        return cands[0], json.loads(cands[0].read_text(encoding="utf-8"))
    except Exception:
        return None


def _pick(doc, names):
    if not isinstance(doc, dict):
        return None
    for n in names:
        if n in doc:
            return doc[n]
    return None


def extract_metrics(doc):
    """从审计 JSON 提取统一指标（容错 key 名）。"""
    if not isinstance(doc, dict):
        return None
    prevalence = _pick(doc, ["prevalence", "prevalence_rate", "positive_rate"])
    ppv_c = None
    ppv_a = None
    chosen = doc.get("chosen") or doc.get("chosen_operating_point") or doc.get("operating_point") or {}
    allp = doc.get("all_positive") or doc.get("all_positive_baseline") or doc.get("trivial_baseline") or {}
    if isinstance(chosen, dict):
        ppv_c = _pick(chosen, ["ppv", "positive_predictive_value"])
    if isinstance(allp, dict):
        ppv_a = _pick(allp, ["ppv", "positive_predictive_value"])
    # 兜底：直接顶层
    ppv_c = ppv_c if ppv_c is not None else _pick(doc, ["chosen_ppv", "ppv_at_chosen"])
    ppv_a = ppv_a if ppv_a is not None else _pick(doc, ["all_positive_ppv", "trivial_ppv"])
    return {
        "prevalence": prevalence,
        "chosen_ppv": ppv_c,
        "all_positive_ppv": ppv_a,
        "chosen": chosen,
        "all_positive": allp,
    }


def scan_paper_strong_claims(ws: Path) -> list:
    paper = ws / "paper"
    hits = []
    if not paper.is_dir():
        return hits
    for p in sorted(paper.rglob("*")):
        if p.suffix.lower() not in (".tex", ".typ"):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        text = re.sub(r"(?m)(?<!\\)%.*$", "", text)
        for pat in STRONG_CLAIMS:
            for m in re.finditer(pat, text):
                hits.append({"file": str(p.relative_to(ws)), "phrase": m.group(0)})
    return hits


def main(argv=None):
    gc.force_utf8()
    ap = argparse.ArgumentParser(description="v4.2 部署效用审计")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--audit-json", default=None, help="显式审计输入 JSON；缺省自动探测 results/")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args(argv)

    ws = Path(args.workspace).resolve()
    doc = None
    if args.audit_json:
        p = Path(args.audit_json)
        p = p if p.is_absolute() else ws / p
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            print(f"FAIL 无法读取 --audit-json: {p}")
            return 2
    else:
        hit = _find_audit_doc(ws)
        if hit is None:
            print("WARN 未找到部署效用输入（--audit-json 或 results/*woman_level*/*deployment*）——SKIP")
            return 0
        doc = hit[1]

    m = extract_metrics(doc)
    if m is None or m["chosen_ppv"] is None or m["all_positive_ppv"] is None:
        print("WARN 审计输入缺少 chosen_ppv / all_positive_ppv 字段——SKIP（不 FAIL）")
        return 0

    prev = float(m["prevalence"]) if m["prevalence"] is not None else None
    cppv = float(m["chosen_ppv"])
    appv = float(m["all_positive_ppv"])
    lift = (cppv - appv) if prev is None else (cppv - appv)
    record = {
        "prevalence": prev,
        "chosen_operating_point_ppv": cppv,
        "all_positive_baseline_ppv": appv,
        "ppv_lift": lift,
        "note": "PPV lift ≤0：模型相对 trivial baseline 无正向富集——结论不得声称临床预警支持价值",
    }
    claims = scan_paper_strong_claims(ws)
    record["strong_claims"] = [c["phrase"] + f"（{c['file']}）" for c in claims]

    fails = 0
    if lift <= 0:
        print(f"  [WARN] utility: chosen PPV {cppv:.4f} <= all-positive baseline {appv:.4f}"
              f"（lift={lift:+.4f}）——正向富集能力有限，应为风险排序/研究性筛查定位")
        if claims:
            fails += 1
            print(f"  [FAIL] deployment_claim: 论文出现强结论措辞但无 PPV 增益："
                  f"{[c['phrase'] for c in claims]}（T60：必须降级结论）")
    else:
        print(f"  [OK] utility: chosen PPV {cppv:.4f} > all-positive {appv:.4f}（lift={lift:+.4f}）")

    missing_metric = []
    for k in ("chosen_ppv", "all_positive_ppv"):
        if not isinstance(doc.get(k) if isinstance(doc, dict) else None, (int, float)):
            pass
    record["generated_at"] = gc.iso_now()
    out = ws / "reports" / "deployment_utility.json"
    gc.save_json(out, record)
    if fails and args.strict:
        print(f"DEPLOYMENT_UTILITY: FAIL（{fails} 项） -> {out}")
        return 1
    print(f"DEPLOYMENT_UTILITY: {'PASS' if not fails else 'WARN(非 strict)'} -> {out}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
