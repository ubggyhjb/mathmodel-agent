#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""leakage_gate.py — v3 ML Leakage 门（_mathmode.docx 六、七条）。

登记制 + 启发式两级：
  1. 登记核验：reports/methodology/ml_operation_scope.json 必须存在（strict），
     至少覆盖 standardization / imputation / feature selection / oversampling /
     class weight / hyperparameter / threshold / calibration / pruning rule / final metrics
     各操作的 allowed_data（training_fold | inner_cv | outer_test）。
     任何操作 allowed_data=outer_test 除 final metrics 外 → FAIL。
  2. 论文表述核验：出现
       "使用所有样本/全体样本/全部测试标签选择阈值"
       "所有 OOF 阈值" / "按全体样本确定阈值"
     式表述 → FAIL。
  3. 代码启发式（WARN 级，人工复核）：扫描 code/*.py 中
       - fit/scale/select/percentile 调用出现在 train_test_split / KFold 之前（可能泄外层信息）
       - 阈值计算基于全量标签（roc_curve/confusion_matrix 在 split 之前）
     WARN 不 FAIL：代码启发式误报率高，按 skill 要求人工确认后销号。

用法：python leakage_gate.py --workspace <项目根> [--strict]
输出：reports/gates/leakage_gate.json；退出码 0 PASS / 1 FAIL / 2 ERROR。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import gate_common as gc

SCOPE_REL = "reports/methodology/ml_operation_scope.json"
EXPECTED_OPS = ["standardization", "imputation", "feature_selection", "oversampling",
                "class_weight", "hyperparameter_selection", "threshold_selection",
                "calibration", "pruning_rule", "final_metrics"]
ALLOWED_DATA = {"training_fold", "inner_cv", "outer_test"}


def scan_code(ws: Path) -> str:
    code = ws / "code"
    chunks = []
    if code.is_dir():
        for p in sorted(code.rglob("*.py")):
            try:
                chunks.append(p.read_text(encoding="utf-8"))
            except Exception:
                continue
    return "\n".join(chunks)


def check_scope(scope, strict, findings):
    if not isinstance(scope, dict):
        gc_violation(findings, "scope", f"{SCOPE_REL} 缺失：ML 操作数据范围未登记", strict)
        return
    ops = scope.get("operations", [])
    by_op = {o.get("operation"): o for o in ops}
    missing = [e for e in EXPECTED_OPS if e not in by_op]
    if missing:
        gc_violation(findings, "scope", f"ml_operation_scope.json 缺少操作登记：{missing}", strict)
    for op in ops:
        allowed = str(op.get("allowed_data", "")).lower()
        if allowed not in ALLOWED_DATA:
            gc_violation(findings, "scope", f"操作 {op.get('operation')} 的 allowed_data={allowed!r} 非法", strict)
        elif op.get("operation") != "final_metrics" and allowed == "outer_test":
            gc_violation(findings, "scope",
                         f"操作 {op.get('operation')} 使用了外层测试数据（allowed_data=outer_test）", strict)
    for op in ops:
        if op.get("operation") == "threshold_selection" and str(op.get("allowed_data", "")) not in ("inner_cv",):
            findings.append({"level": "WARN", "check": "scope",
                             "message": f"threshold_selection allowed_data={op.get('allowed_data')}；"
                                        f"规范为 inner_cv（禁止全体 OOF 选阈值后回报性能）"})


def check_paper_claims(ws, strict, findings):
    paper = ws / "paper"
    text = ""
    if paper.is_dir():
        parts = []
        for p in sorted(paper.rglob("*")):
            if p.suffix.lower() not in (".tex", ".typ"):
                continue
            try:
                t = re.sub(r"(?m)%.*$", "", p.read_text(encoding="utf-8"))
                parts.append(t)
            except Exception:
                continue
        text = " ".join(parts)
    bad_pat = r"(使用|基于|按|采用)?(所有|全体|全量|全部|整个)(样本|数据|数据集|测试集|OOF|oof)(上)?(选择|确定|计算|选取|搜索)(阈值|剪枝|超参|参数)"
    for m in re.finditer(bad_pat, text):
        gc_violation(findings, "paper", f"论文泄漏性表述：『{m.group(0)[:50]}』——阈值/参数须在内层 CV 或训练折内确定", strict)
    if "inside" not in text and "内层" in text and "阈值" in text:
        findings.append({"level": "OK", "check": "paper", "message": "论文出现内层 CV 阈值表述（人工确认嵌套结构）"})


def check_code_heuristics(ws, findings):
    code = scan_code(ws)
    if not code:
        return
    split_before = [
        (r"StandardScaler\s*\(\)\s*\.\s*(fit|fit_transform)", "标准化"),
    ]
    # split 位置定位
    split_pos = [m.start() for m in re.finditer(r"train_test_split|KFold|GroupKFold|StratifiedGroupKFold", code)]
    for pat, label in split_before:
        for m in re.finditer(pat, code):
            if not any(pos > m.end() for pos in split_pos) and split_pos:
                continue
            # 若该 fit 出现在任何 split 之前 → 潜在泄露
            if split_pos and m.start() < min(split_pos):
                findings.append({"level": "WARN", "check": "code",
                                 "message": f"疑似泄露：{label} fit 出现在数据划分之前（line 附近），人工确认是否仅训练折内"})
    # 全量标签阈值计算
    for m in re.finditer(r"(roc_curve|precision_recall_curve|confusion_matrix)\s*\(", code):
        if split_pos and m.start() < min(split_pos):
            findings.append({"level": "WARN", "check": "code",
                             "message": f"疑似泄露：{m.group(0)} 在数据划分前计算（可能基于全量标签），阈值选择须内层 CV"})


def gc_violation(findings, check, msg, strict):
    findings.append({"level": "FAIL" if strict else "WARN", "check": check, "message": msg})


def main(argv=None):
    gc.force_utf8()
    ap = argparse.ArgumentParser(description="v3 ML Leakage 门禁")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--report", default=None)
    args = ap.parse_args(argv)

    ws = Path(args.workspace).resolve()
    findings = []
    scope = gc.load_json(ws / SCOPE_REL, None)
    if scope is None and args.strict:
        gc_violation(findings, "scope", f"{SCOPE_REL} 缺失：未登记 ML 数据使用范围（7methodology-review 强制）", args.strict)
    else:
        check_scope(scope, args.strict, findings)
    check_paper_claims(ws, args.strict, findings)
    check_code_heuristics(ws, findings)

    fails = [f for f in findings if f["level"] == "FAIL"]
    warns = [f for f in findings if f["level"] == "WARN"]
    report = {
        "gate": "leakage", "schema_version": 1, "workspace": str(ws),
        "strict": args.strict, "engine": gc.manifest_engine(ws),
        "scope_file": (ws / SCOPE_REL).is_file(),
        "findings": findings,
        "summary": {"fails": len(fails), "warns": len(warns)},
        "note": "代码启发式（check=code）为 WARN：误报率高，人工确认后销号；FAIL 仅来自声明/论文表述违规。",
    }
    out = Path(args.report).resolve() if args.report else ws / "reports" / "gates" / "leakage_gate.json"
    gc.save_json(out, report)
    for f in findings:
        print(f"  [{f['level']}] {f['check']}: {f['message']}")
    print(f"LEAKAGE: {'PASS' if not fails else 'FAIL'}（{len(fails)} FAIL / {len(warns)} WARN） -> {out}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
