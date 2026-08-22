#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_all_gates.py — v4.4 一键聚合门禁（gate registry 单一事实源驱动）。

执行列表完全来自 workflow_spec.yaml 的 `gates:` registry（v4.4 P0-10）：
  每项 id/script/args/report/required/strict_aware 由该表声明；本文件只做解析与编排，
  禁止在代码中再维护一份门禁清单（README/计数/VERIFY_SUMMARY 均由 registry 派生）。

用法：
  python run_all_gates.py --workspace <项目根> [--strict] [--skip layout,refs]
                          [--report reports/gates/gates_report.json]
退出码：0 总体 PASS；1 总体 FAIL。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import gate_common as gc
import workflow_spec as wfs


def check_workflow_order(ws: Path):
    """聚合器级检查：decision_log 的阶段执行历史必须与 workflow_spec.yaml 一致。
    结果写入聚合报告 workflow_order 字段；不一致则总体 FAIL。"""
    spec = wfs.load_spec(wfs.repo_root(Path(__file__).resolve().parent))
    expected = [str(s.get("skill", "")) for s in spec.get("stages", []) if s.get("skill")]
    if not expected:
        return {"ok": False, "message": "workflow_spec.yaml 无 stages（版本或结构异常）"}
    dl = gc.load_json(ws / "state" / "decision_log.json", None)
    if not isinstance(dl, dict):
        return {"ok": True, "message": "decision_log 不存在（由 decision 门处理，跳过顺序校验）"}
    stages = dl.get("stages") or {}
    actual = [k for k in stages if k != "1start-mathmodel"]
    # 允许旧项目缺 brainstorm；不允许缺失 v4 核心阶段或顺序颠倒
    core = [e for e in expected if e != "brainstorm-mathmodel"]
    if actual != expected and actual != core:
        return {"ok": False,
                "message": f"decision_log 执行历史 {actual} 与 workflow_spec {expected} 不一致（v4 阶段顺序需与 spec 对齐）"}
    return {"ok": True, "message": f"执行历史与 workflow_spec 一致（{len(actual)} 阶段）"}


def gate_specs(ws: Path, strict: bool, repo_root: Path):
    """v4.4：从 workflow_spec.yaml 的 gates registry 解析执行列表（单一事实源）。"""
    spec = wfs.load_spec(repo_root)
    scripts = Path(__file__).resolve().parent
    registry = wfs.gates_registry(spec)
    if not registry:
        raise ValueError("workflow_spec.yaml 缺 gates registry（v4.4：run_all_gates 只解析该表，"
                         "禁止硬编码执行列表）")
    out = []
    for g in registry:
        args = []
        for a in g["args"]:
            args.append(str(repo_root) if a == "__REPO_ROOT__" else a)
        args = ["--workspace", str(ws), *args]
        if g["strict_aware"] and strict:
            args.append("--strict")
        out.append((g["id"], scripts / g["script"], args, g["report"], g["required"]))
    return out


def run_gate(ws, name, script, args):
    try:
        proc = subprocess.run(
            [sys.executable, str(script), *args], capture_output=True,
            text=True, encoding="utf-8", errors="replace", cwd=str(ws), timeout=1800)
    except Exception as exc:
        return {"exit_code": 2, "status": "ERROR", "stdout_tail": f"运行异常: {exc}"}
    out = (proc.stdout or "") + (proc.stderr or "")
    status = "PASS" if proc.returncode == 0 else ("ERROR" if proc.returncode >= 2 else "FAIL")
    return {"exit_code": proc.returncode, "status": status, "stdout_tail": out[-1500:]}


def semantic_problems(name, result, ws, gspecs):
    problems = []
    report_rel = next((g[3] for g in gspecs if g[0] == name), None)
    doc = gc.load_json(Path(ws) / report_rel, None) if report_rel else None

    if name == "layout_gate":
        if doc is None:
            problems.append("layout_gate 未产出 JSON 报告")
        else:
            if not doc.get("executed"):
                problems.append(f"layout_gate executed=False（engine={doc.get('engine')} 无源适配器）")
            if not doc.get("supported"):
                problems.append(f"layout_gate supported=False（engine={doc.get('engine')} 不支持）")
            if not doc.get("coverage", {}).get("source_refs"):
                problems.append("layout_gate coverage.source_refs=False（源引用检查未执行）")
    elif name == "trace_numbers":
        if doc is None:
            problems.append("trace_numbers 未产出 JSON 报告")
        else:
            n = doc.get("summary", {}).get("paper_numbers", 0)
            if n == 0:
                problems.append("trace_numbers 输入为空：论文可追溯数字 token 数为 0（引擎/入口未对齐）")
    elif name == "style_audit":
        if doc is None:
            problems.append("style_audit 未产出 JSON 报告")
        else:
            pages = doc.get("coverage", {}).get("pdf_pages", 0)
            if pages == 0:
                problems.append("style_audit 未解析到 PDF 页面（coverage.pdf_pages=0）")
    elif name == "verify_refs":
        if doc is None:
            problems.append("verify_refs 未产出 JSON 报告")
    elif name in ("methodology", "leakage", "figure_story", "text_integrity", "idea_contracts",
                  "visual_review_gate", "figure_spec"):
        if doc is None:
            problems.append(f"{name} 未产出 JSON 报告")
    return problems


def main(argv=None):
    gc.force_utf8()
    ap = argparse.ArgumentParser(description="一键聚合运行 6verity 门禁")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--skip", default="", help="逗号分隔 gate_id，跳过不跑")
    ap.add_argument("--report", default=None)
    args = ap.parse_args(argv)

    ws = Path(args.workspace).resolve()
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    report_file = Path(args.report).resolve() if args.report else ws / "reports" / "gates" / "gates_report.json"
    engine = gc.manifest_engine(ws)
    repo_root = wfs.repo_root(Path(__file__).resolve().parent)

    try:
        gspecs = gate_specs(ws, args.strict, repo_root)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2

    # v4：验证器完全只读。禁止在此修改 decision_log / 任何被验对象（writer updates,
    # verifier verifies）。若 decision 门 freshness 因产物更新而 FAIL，正确动作是
    # 由写者（当前阶段）更新 decision_log.last_updated，而不是让验证器代劳。
    gates_out = {}
    for name, script, gate_args, report_rel, required in gspecs:
        if name in skip:
            gates_out[name] = {"status": "SKIPPED", "exit_code": None, "ran_at": gc.iso_now(),
                               "report": None, "problems": [], "required": required}
            continue
        print(f"==> 运行门禁: {name}（{script.name}）")
        r = run_gate(ws, name, script, gate_args)
        r["ran_at"] = gc.iso_now()
        r["report"] = report_rel
        r["problems"] = semantic_problems(name, r, ws, gspecs)
        if r["exit_code"] != 0 or r["problems"]:
            r["status"] = "FAIL" if r["status"] == "PASS" else r["status"]
        r["required"] = required
        gates_out[name] = r
        print(f"    exit={r['exit_code']} status={r['status']}"
              + (f" problems={r['problems']}" if r.get("problems") else ""))

    summary = {
        "total": len(gates_out),
        "passed": sum(1 for g in gates_out.values() if g["status"] == "PASS"),
        "failed": sum(1 for g in gates_out.values() if g["status"] in ("FAIL", "ERROR")),
        "skipped": sum(1 for g in gates_out.values() if g["status"] == "SKIPPED"),
        # v4.4：SKIPPED 是可选项，不参与 PASS 判定（active 全 PASS 即 PASS）
        "overall": "PASS" if gates_out and all(g["status"] == "PASS" for g in gates_out.values()
                                              if g["status"] != "SKIPPED") else "FAIL",
    }
    wo = check_workflow_order(ws)
    if not wo["ok"]:
        summary["overall"] = "FAIL"
        summary["workflow_order"] = "FAIL"
    agg = {
        "gate": "run_all_gates", "workspace": str(ws), "engine": engine,
        "strict": args.strict, "ran_at": gc.iso_now(), "gates": gates_out,
        "workflow_order": wo, "summary": summary, "report": str(report_file),
    }
    try:
        gc.save_json(report_file, agg)
    except Exception as exc:
        print(f"WARN 写聚合报告失败: {report_file} ({exc})", file=sys.stderr)

    run_doc = gc.load_json(gc.runtime_path(ws), {})
    if not isinstance(run_doc, dict):
        run_doc = {}
    run_doc["schema_version"] = gc.SCHEMA_VERSION
    run_doc["workspace"] = str(ws)
    run_doc["engine"] = engine
    run_doc["last_run"] = gc.iso_now()
    run_doc.setdefault("gates", {})
    for name, g in gates_out.items():
        run_doc["gates"][name] = {
            "status": g["status"], "exit_code": g.get("exit_code"),
            "ran_at": g.get("ran_at"), "report": g.get("report"),
            "problems": g.get("problems", []),
        }
    run_doc.setdefault("snapshot", {})["last"] = {
        "workspace": str(ws), "engine": engine,
        "inputs": gc.dir_snapshot(ws / "paper", {".tex", ".typ"}),
        "results": gc.dir_snapshot(ws / "results", {".json", ".csv", ".xlsx"}),
    }
    try:
        gc.save_json(gc.runtime_path(ws), run_doc)
    except Exception as exc:
        print(f"WARN 写运行记录失败: {exc}", file=sys.stderr)

    print("")
    for name, g in gates_out.items():
        print(f"  {name:<20} -> {g['status']}")
    print(f"  {'workflow_order':<20} -> {'PASS' if wo['ok'] else 'FAIL'} ({wo['message']})")
    print(f"OVERALL: {summary['overall']}（{summary['passed']}/{summary['total']} 通过）")
    print(f"聚合报告: {report_file}")
    print(f"运行记录: {gc.runtime_path(ws)}")
    return 0 if summary["overall"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
