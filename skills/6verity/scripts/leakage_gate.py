#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""leakage_gate.py — v4 ML Leakage 门（任务书 二十六、二十七条）。

四级：
  1. 登记核验：reports/methodology/ml_operation_scope.json（声明式证明，strict 必须存在）；
  2. 论文表述核验：全量数据选阈值等泄漏性表述 -> FAIL；
  3. 运行时证明（v4 新增）：results/leakage_audit.json —— 每折记录
     outer_train/outer_test/inner_threshold 的 groups hash + 结论，
     程序断言不相交/含于；audit 存在而违规 -> FAIL；audit 缺失 -> WARN
     （要求代码阶段实际输出，不得只靠声明）；
  4. 代码启发式（v4：按文件保留边界，不再是全项目拼接；仅 WARN 人工复核）。

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
AUDIT_REL = "results/leakage_audit.json"
EXPECTED_OPS = ["standardization", "imputation", "feature_selection", "oversampling",
                "class_weight", "hyperparameter_selection", "threshold_selection",
                "calibration", "pruning_rule", "final_metrics"]
ALLOWED_DATA = {"training_fold", "inner_cv", "outer_test"}


def scan_code_files(ws: Path) -> list:
    """按文件扫描 code/*.py（保留文件边界，供逐文件启发式）。"""
    code = ws / "code"
    out = []
    if code.is_dir():
        for p in sorted(code.rglob("*.py")):
            try:
                out.append((p.name, p.read_text(encoding="utf-8")))
            except Exception:
                continue
    return out


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


def check_runtime_audit(ws, strict, findings):
    """v4 运行时 fold provenance：leakage_audit.json 的实际执行证据。"""
    doc = gc.load_json(ws / AUDIT_REL, None)
    if not isinstance(doc, dict):
        findings.append({"level": "WARN", "check": "runtime",
                         "message": f"{AUDIT_REL} 缺失：仅声明式证明（scope），无运行时 fold 隔离证据；"
                                    f"v4 要求代码每折输出 train/test/threshold groups 断言"})
        return
    if not isinstance(doc.get("folds"), list) or not doc["folds"]:
        findings.append({"level": "FAIL" if strict else "WARN", "check": "runtime",
                         "message": "leakage_audit.json 存在但 folds 为空——未实际执行逐折断言"})
        return
    bad = []
    for f in doc["folds"]:
        if isinstance(f, dict):
            if f.get("outer_train_test_disjoint") is False:
                bad.append(f"fold {f.get('fold')}: 外层 train∩test 非空（组级泄露）")
            if f.get("threshold_within_train") is False:
                bad.append(f"fold {f.get('fold')}: 阈值组不在训练折内")
    if bad:
        gc_violation(findings, "runtime", "；".join(bad), strict)
    else:
        findings.append({"level": "OK", "check": "runtime",
                         "message": f"运行时 provenance 通过：{len(doc['folds'])} 折 train/test 不相交、阈值⊆train"})
    # 每折必须声明 group hash（缺字段视为未证明）
    no_hash = [f.get("fold") for f in doc["folds"]
               if isinstance(f, dict) and not f.get("outer_train_groups_hash")]
    if no_hash:
        findings.append({"level": "WARN", "check": "runtime",
                         "message": f"fold {no_hash} 缺 outer_train_groups_hash——组级隔离未可复验"})


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
    """逐文件启发式（v4 保留文件边界；仅 WARN，人工复核销号）。"""
    for fname, code in scan_code_files(ws):
        split_pos = [m.start() for m in re.finditer(r"train_test_split|KFold|GroupKFold|StratifiedGroupKFold", code)]
        if not split_pos:
            continue
        first_split = min(split_pos)
        for m in re.finditer(r"(StandardScaler\s*\(\)\s*\.\s*(fit|fit_transform)|Imputer\s*\([^)]*\)\s*\.\s*fit)", code):
            if m.start() < first_split:
                findings.append({"level": "WARN", "check": "code",
                                 "message": f"{fname}: 疑似泄露——{m.group(0)[:40]} 出现在数据划分之前，"
                                            f"人工确认是否仅训练折内（辅助提示，非严谨检测）"})
        for m in re.finditer(r"(roc_curve|precision_recall_curve|confusion_matrix)\s*\(", code):
            if m.start() < first_split:
                findings.append({"level": "WARN", "check": "code",
                                 "message": f"{fname}: 疑似泄露——{m.group(0)} 在数据划分前计算"
                                            f"（可能基于全量标签），阈值选择须内层 CV（辅助提示）"})


def gc_violation(findings, check, msg, strict):
    findings.append({"level": "FAIL" if strict else "WARN", "check": check, "message": msg})


def main(argv=None):
    gc.force_utf8()
    ap = argparse.ArgumentParser(description="v4 ML Leakage 门禁")
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
    check_runtime_audit(ws, args.strict, findings)
    check_code_heuristics(ws, findings)

    fails = [f for f in findings if f["level"] == "FAIL"]
    warns = [f for f in findings if f["level"] == "WARN"]
    report = {
        "gate": "leakage", "schema_version": 2, "workspace": str(ws),
        "strict": args.strict, "engine": gc.manifest_engine(ws),
        "scope_file": (ws / SCOPE_REL).is_file(),
        "runtime_audit_file": (ws / AUDIT_REL).is_file(),
        "findings": findings,
        "summary": {"fails": len(fails), "warns": len(warns)},
        "note": "代码启发式（check=code）为 WARN：误报率高，人工确认后销号；FAIL 来自声明/论文/运行时证据违规。",
    }
    out = Path(args.report).resolve() if args.report else ws / "reports" / "gates" / "leakage_gate.json"
    gc.save_json(out, report)
    for f in findings:
        print(f"  [{f['level']}] {f['check']}: {f['message']}")
    print(f"LEAKAGE: {'PASS' if not fails else 'FAIL'}（{len(fails)} FAIL / {len(warns)} WARN） -> {out}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
