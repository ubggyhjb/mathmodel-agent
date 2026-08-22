#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_tests.py — v4 门禁回归测试（fixture + 负向 regression）。

覆盖历史事故与 v4 新增门（每个用例独立临时副本，跑完清理）：
  T01-T13   v2/v3 基线回归（trace/layout/style/decision/refs/聚合/whitespace）
  T14-T19   v3 三门 fixture（methodology/leakage/figure_story）
  T20-T31   v4 负向 regression（任务书 30 条：12 类已知缺陷必须稳定 FAIL）：
    T20 同一 outcome 跨问题观测机制不一致（Q2 区间删失 vs Q3 精确+右删失）-> FAIL
    T21 图 annotation value_key 无来源（旧数值残留）-> FAIL
    T22 多 panel 图 B panel 无 artist -> FAIL
    T23 文本/表格物理越界（layout_audit 合入后）-> FAIL
    T24 正文 `图 ??` -> FAIL；T25 关键词无分隔符 -> FAIL
    T26 panel 与 caption 不一致 -> FAIL
    T27 冗余图同处正文且无 keep_both_reason -> FAIL
    T28 verifier 必须只读（run_all_gates 不得写 decision_log）
    T29 单位未换算（raw==value 但 registry 声明 *100）-> FAIL
    T30 模型契约 contract_rev 过期（论文仍按旧 rev）-> FAIL
    T31 text_integrity 干净项目 -> PASS

用法：python run_tests.py [--workspace <真实项目>] [--skip-online]
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
# 真实项目基线（T01/T04/T06-T09/T12）需要一份已通过的竞赛项目；
# 开源环境未提供时这些用例自动 SKIP，其余 fixture 用例照常跑。
REAL_WS = os.environ.get("MATHMODEL_TEST_WS", "")
FIXTURE_METHOD = Path(__file__).resolve().parent / "tmp_methodology"
FIXTURE_TYPST = Path(__file__).resolve().parent / "tmp_trace"


def run(args, cwd=None):
    proc = subprocess.run([sys.executable, *map(str, args)], capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          cwd=str(cwd) if cwd else None)
    return proc


def report(tid, name, expect_pass, proc, notes=""):
    ok = (proc.returncode == 0) == expect_pass
    print(f"[{'PASS' if ok else 'FAIL'}] {tid} {name}: exit={proc.returncode} "
          f"expect={'0' if expect_pass else '!=0'}{' | ' + notes if notes else ''}")
    if not ok:
        print("  stdout tail:", (proc.stdout or "")[-400:].replace("\n", " | "))
        print("  stderr tail:", (proc.stderr or "")[-200:].replace("\n", " | "))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default=REAL_WS,
                    help="真实项目基线路径；缺省时基线类用例 SKIP（也可用环境变量 MATHMODEL_TEST_WS）")
    ap.add_argument("--skip-online", action="store_true")
    args = ap.parse_args()
    ws = Path(args.workspace) if args.workspace else None
    results = []
    skipped = []

    def need_ws(tid, name):
        if ws is None:
            skipped.append(f"{tid} {name}")
            print(f"[SKIP] {tid} {name}: 缺真实项目 workspace（--workspace 或 env MATHMODEL_TEST_WS）")
            return False
        return True

    # T01 trace latex 基线
    if need_ws("T01", "trace latex 基线"):
        results.append(report("T01", "trace latex 基线", True,
                              run([SCRIPTS / "trace_numbers.py", "--workspace", ws, "--strict"])))
    # T02 typst fixture
    if FIXTURE_TYPST.is_dir():
        results.append(report("T02", "trace typst 引擎", True,
                              run([SCRIPTS / "trace_numbers.py", "--workspace", FIXTURE_TYPST, "--strict"])))
    # T03 word 引擎无适配器
    with tempfile.TemporaryDirectory() as td:
        tws = Path(td)
        (tws / "paper").mkdir(parents=True)
        (tws / "paper" / "main.docx").write_text("x", encoding="utf-8")
        (tws / "results").mkdir()
        (tws / "project.manifest.json").write_text(
            '{"schema_version":1,"engine":"word","entry":"paper/main.docx","hil_policy":"disabled"}',
            encoding="utf-8")
        results.append(report("T03", "trace word 引擎 FAIL", False,
                              run([SCRIPTS / "trace_numbers.py", "--workspace", tws, "--strict"])))

    # T04 layout_gate latex 基线
    if need_ws("T04", "layout_gate latex 基线"):
        results.append(report("T04", "layout_gate latex 基线", True,
                              run([SCRIPTS / "layout_gate.py", "--workspace", ws, "--strict"])))
    # T05 unknown engine
    with tempfile.TemporaryDirectory() as td:
        tws = Path(td)
        (tws / "paper").mkdir(parents=True)
        (tws / "paper" / "main.docx").write_text("x", encoding="utf-8")
        (tws / "project.manifest.json").write_text(
            '{"schema_version":1,"engine":"unknown","entry":"paper/main.docx","hil_policy":"disabled"}',
            encoding="utf-8")
        results.append(report("T05", "layout_gate unknown strict FAIL", False,
                              run([SCRIPTS / "layout_gate.py", "--workspace", tws, "--strict"])))
    # T06 图源缺失（复制基线项目 paper，删除某被引图的 pdf 与 png 两种源）
    if need_ws("T06", "layout_gate 图源缺失 FAIL"):
        with tempfile.TemporaryDirectory() as td:
            tws = Path(td)
            shutil.copytree(ws / "paper", tws / "paper")
            shutil.copytree(ws / "figures", tws / "figures")
            shutil.copy2(ws / "project.manifest.json", tws / "project.manifest.json")
            # 动态选取一个同时有 pdf+png 的被引图源（旧硬编码 fig_network_mine1 为模型四专属）
            target = None
            for stem in sorted({p.stem for p in (ws / "figures").glob("*")}):
                if (ws / "figures" / f"{stem}.pdf").is_file() and (ws / "figures" / f"{stem}.png").is_file():
                    target = stem
                    break
            if target is None:
                skipped.append("T06 layout_gate 图源缺失 FAIL")
                print("[SKIP] T06: 基线项目无 pdf+png 成对图源（动态选择失败）")
            else:
                for name in (f"{target}.pdf", f"{target}.png"):
                    (tws / "figures" / name).unlink()
                results.append(report("T06", "layout_gate 图源缺失 FAIL", False,
                                      run([SCRIPTS / "layout_gate.py", "--workspace", tws, "--strict"])))

    # T07 style_audit 基线
    if need_ws("T07", "style_audit 基线"):
        results.append(report("T07", "style_audit 基线", True,
                              run([SCRIPTS / "style_audit.py", "--workspace", ws, "--strict"])))
    # T08 附录缺一源文件
    if need_ws("T08", "style_audit 附录缺源码 FAIL"):
        with tempfile.TemporaryDirectory() as td:
            tws = Path(td)
            shutil.copytree(ws / "paper", tws / "paper")
            shutil.copytree(ws / "code", tws / "code")
            shutil.copy2(ws / "project.manifest.json", tws / "project.manifest.json")
            # 移除附录里对 escape.py 的引入
            a_code = tws / "paper" / "sections" / "A_code.tex"
            text = a_code.read_text(encoding="utf-8")
            a_code.write_text(text.replace("\\lstinputlisting[language=Python]{../code/escape.py}", ""),
                              encoding="utf-8")
            results.append(report("T08", "style_audit 附录缺源码 FAIL", False,
                                  run([SCRIPTS / "style_audit.py", "--workspace", tws, "--strict"])))
    # T09 AI 声明改错
    if need_ws("T09", "style_audit AI 定句错误 FAIL"):
        with tempfile.TemporaryDirectory() as td:
            tws = Path(td)
            shutil.copytree(ws / "paper", tws / "paper")
            shutil.copytree(ws / "code", tws / "code")
            shutil.copytree(ws / "figures", tws / "figures")
            shutil.copy2(ws / "project.manifest.json", tws / "project.manifest.json")
            main_tex = tws / "paper" / "main.tex"
            text = main_tex.read_text(encoding="utf-8")
            main_tex.write_text(text.replace("详细使用情况见支撑材料。", "详细使用情况见附件。"),
                                encoding="utf-8")
            results.append(report("T09", "style_audit AI 定句错误 FAIL", False,
                                  run([SCRIPTS / "style_audit.py", "--workspace", tws, "--strict"])))

    # T10 decision freshness
    with tempfile.TemporaryDirectory() as td:
        tws = Path(td)
        (tws / "state").mkdir(parents=True)
        (tws / "reports").mkdir()
        (tws / "reports" / "ANALYSIS_MODELING_REPORT.md").write_text("x", encoding="utf-8")
        (tws / "plan.md").write_text("x", encoding="utf-8")
        (tws / "todo.md").write_text("x", encoding="utf-8")
        subprocess.run([sys.executable, str(SCRIPTS / "check_decision_log.py"),
                        "--workspace", tws, "--create"], capture_output=True)
        dl = tws / "state" / "decision_log.json"
        import json
        doc = json.loads(dl.read_text(encoding="utf-8"))
        doc["last_updated"] = "2000-01-01T00:00:00"
        for s in doc["stages"].values():
            s["status"] = "done"
        dl.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        (tws / "paper").mkdir()
        (tws / "paper" / "main.tex").write_text("% x", encoding="utf-8")
        results.append(report("T10", "decision freshness 过期 FAIL", False,
                              run([SCRIPTS / "check_decision_log.py", "--workspace", tws])))

    # T11 verify_refs 编造文献
    with tempfile.TemporaryDirectory() as td:
        tws = Path(td)
        (tws / "paper").mkdir(parents=True)
        (tws / "paper" / "main.tex").write_text(r"\cite{ref1}" + "\n", encoding="utf-8")
        (tws / "paper" / "references.tex").write_text(
            "\\begin{thebibliography}{9}\n"
            "\\bibitem{ref1} Nonexistent Author. This Nonexistent Paper 2099[J]. Fake Journal, 2099, 1(1).\n"
            "\\end{thebibliography}\n", encoding="utf-8")
        proc = run([SCRIPTS / "verify_refs.py", "--workspace", tws, "--strict"])
        if "网络不可用" in (proc.stdout or "") or "网络异常" in (proc.stdout or ""):
            results.append(report("T11", "verify_refs 编造文献（离线 SKIP）", True, proc, "offline"))
        else:
            results.append(report("T11", "verify_refs 编造文献 FAIL", False, proc))

    # T12 聚合门（v3：C 题项目已满足全部九门，全量跑；离线时 skip refs）
    if need_ws("T12", "run_all_gates 聚合"):
        skip_extra = "refs" if args.skip_online else ""
        results.append(report("T12", "run_all_gates 聚合", True,
                              run([SCRIPTS / "run_all_gates.py", "--workspace", ws, "--strict",
                                   "--skip", skip_extra])))

    # T13 whitespace_qa 大空带页检测（顶部/底部有字但中间空大半页，必须被标偏空）
    with tempfile.TemporaryDirectory() as td:
        import fitz
        pdf_path = Path(td) / "gap.pdf"
        doc = fitz.open()
        page = doc.new_page(width=595.27, height=841.89)
        page.insert_text((72, 80), "top content")
        page.insert_text((72, 770), "bottom content")
        doc.save(str(pdf_path))
        doc.close()
        results.append(report("T13", "whitespace_qa 大空带 FAIL", False,
                              run([SCRIPTS / "whitespace_qa.py", "--pdf", pdf_path, "--strict"])))

    # ---- v3 新门（T14-T19），基于 tmp_methodology fixture 的副本（不污染 fixture） ----

    def method_copy():
        td = tempfile.TemporaryDirectory()
        shutil.copytree(FIXTURE_METHOD, td.name, dirs_exist_ok=True)
        return td, Path(td.name)

    # T14 methodology fixture 基线 PASS
    td, tws = method_copy()
    try:
        results.append(report("T14", "methodology fixture PASS", True,
                              run([SCRIPTS / "methodology_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()
    # T15 methodology 假设词违规（无修饰『相互独立』）FAIL
    td, tws = method_copy()
    try:
        (tws / "paper" / "main.tex").write_text(
            "各孕妇的检测相互独立。\n\\includegraphics{figures/fig_q1}\n", encoding="utf-8")
        results.append(report("T15", "methodology 假设词违规 FAIL", False,
                              run([SCRIPTS / "methodology_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()
    # T16 leakage fixture PASS（scope 齐全且 threshold=inner_cv）
    td, tws = method_copy()
    try:
        results.append(report("T16", "leakage scope 合规 PASS", True,
                              run([SCRIPTS / "leakage_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()
    # T17 leakage threshold_selection=outer_test -> FAIL
    td, tws = method_copy()
    try:
        sp = tws / "reports" / "methodology" / "ml_operation_scope.json"
        import json as _json
        doc = _json.loads(sp.read_text(encoding="utf-8"))
        for op in doc["operations"]:
            if op["operation"] == "threshold_selection":
                op["allowed_data"] = "outer_test"
        sp.write_text(_json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        results.append(report("T17", "leakage 阈值用外层测试 FAIL", False,
                              run([SCRIPTS / "leakage_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()
    # T18 figure_story fixture PASS
    td, tws = method_copy()
    try:
        results.append(report("T18", "figure_story 登记齐全 PASS", True,
                              run([SCRIPTS / "figure_story.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()
    # T19 figure_story 缺 manifest -> FAIL
    td, tws = method_copy()
    try:
        (tws / "figures" / "figure_manifest.json").unlink()
        results.append(report("T19", "figure_story 缺 manifest FAIL", False,
                              run([SCRIPTS / "figure_story.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # ============ v4 regression 矩阵（任务书三十条：每个已知缺陷稳定 FAIL） ============

    def json_write(path, obj):
        import json as _j
        (Path(path)).write_text(_j.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

    # T20 同 outcome 跨问题机制不一致（Q2 区间删失 vs Q3 精确+右删失）-> methodology FAIL
    td, tws = method_copy()
    try:
        spec = json.loads((tws / "reports" / "FINAL_MODEL_SPEC.json").read_text(encoding="utf-8"))
        q2 = dict(spec["problems"][0])
        q2["problem_id"] = "Q2"
        q2["primary_model"] = "weibull_aft"
        q2["likelihood"] = "exact"
        q2["likelihood_evidence"] = ["精确事件"]
        q2["observation_mechanism"] = {"left_censoring": False, "interval_censoring": False,
                                       "right_censoring": True}
        q2["paper_section"] = "main.tex"
        q2["mechanism_change_rationale"] = ""
        spec["problems"].append(q2)
        json_write(tws / "reports" / "FINAL_MODEL_SPEC.json", spec)
        results.append(report("T20", "同 outcome 机制不一致 FAIL", False,
                              run([SCRIPTS / "methodology_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T21 图标注 value_key 无来源（旧结果数字残留在图）-> figure_story FAIL
    td, tws = method_copy()
    try:
        (tws / "figures").mkdir(exist_ok=True)
        json_write(tws / "figures" / "fig_q1.meta.json",
                   {"figure_id": "fig1", "generator": "make_figures.py", "generator_sha256": "x",
                    "source_results": [{"file": "results/p2_ic.json", "sha256": "y",
                                        "keys": ["G2.recommended.low"]}],
                    "annotations": [{"label": "G2 推荐", "value_key": "G2.recommended.low", "value": "16.3"}],
                    "panels": {}})
        results.append(report("T21", "annotation-key 无来源 FAIL", False,
                              run([SCRIPTS / "figure_story.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T22 空 panel B（artist 计数 0 < min_artist_count）-> figure_story FAIL
    td, tws = method_copy()
    try:
        (tws / "figures").mkdir(exist_ok=True)
        json_write(tws / "figures" / "fig_q1.meta.json",
                   {"figure_id": "fig1", "generator": "make_figures.py", "generator_sha256": "x",
                    "source_results": [], "annotations": [],
                    "panels": {"A": {"line_count": 2, "patch_count": 1},
                               "B": {"line_count": 0, "scatter_count": 0, "patch_count": 0}}})
        manifest = json.loads((tws / "figures" / "figure_manifest.json").read_text(encoding="utf-8"))
        manifest[0]["panels"] = [{"id": "B", "expected_marks": ["line:x", "line:y"],
                                  "min_artist_count": 3}]
        json_write(tws / "figures" / "figure_manifest.json", manifest)
        results.append(report("T22", "空白 panel FAIL", False,
                              run([SCRIPTS / "figure_story.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T23 物理越界（文本超出右边界 >15pt）-> layout_gate FAIL（physical 已合入）
    with tempfile.TemporaryDirectory() as td:
        tws = Path(td)
        (tws / "paper").mkdir(parents=True)
        (tws / "paper" / "main.tex").write_text("% 简单入口\n\\section{方法}\n", encoding="utf-8")
        (tws / "figures").mkdir()
        (tws / "project.manifest.json").write_text(
            '{"schema_version":1,"engine":"latex","entry":"paper/main.tex","hil_policy":"disabled"}',
            encoding="utf-8")
        import fitz
        doc = fitz.open()
        page = doc.new_page(width=595.27, height=841.89)
        page.insert_text((600, 400), "overflow text beyond right margin")  # x0=600 远超 524pt
        doc.save(str(tws / "paper" / "main.pdf"))
        doc.close()
        results.append(report("T23", "物理越界（表裁切类）FAIL", False,
                              run([SCRIPTS / "layout_gate.py", "--workspace", tws, "--strict"])))

    # T24 正文 `图 ??` -> text_integrity FAIL
    with tempfile.TemporaryDirectory() as td:
        tws = Path(td)
        (tws / "paper").mkdir(parents=True)
        (tws / "paper" / "main.tex").write_text(
            "结果见图 ??，且表 ?? 亦有引用。\n", encoding="utf-8")
        results.append(report("T24", "图 ?? 占位 FAIL", False,
                              run([SCRIPTS / "text_integrity.py", "--workspace", tws, "--strict"])))

    # T25 中文关键词无分隔符 -> text_integrity FAIL
    with tempfile.TemporaryDirectory() as td:
        tws = Path(td)
        (tws / "paper").mkdir(parents=True)
        (tws / "paper" / "main.tex").write_text(
            "\\abstractcn{摘要}{NIPT 个体增长曲线 生存分析 风险最小化 代价敏感分类 非整倍体判定}\n",
            encoding="utf-8")
        results.append(report("T25", "关键词无分隔 FAIL", False,
                              run([SCRIPTS / "text_integrity.py", "--workspace", tws, "--strict"])))

    # T26 caption 与 manifest 不一致 -> figure_story FAIL
    td, tws = method_copy()
    try:
        (tws / "paper" / "main.tex").write_text(
            "\\begin{figure}\\includegraphics{figures/fig_q1}\\caption{panel 为 M2/M3 的描述}"
            "\\label{fig:q1}\\end{figure}\n", encoding="utf-8")
        manifest = json.loads((tws / "figures" / "figure_manifest.json").read_text(encoding="utf-8"))
        manifest[0]["caption"] = "panel 为 M1/M2 的描述"
        json_write(tws / "figures" / "figure_manifest.json", manifest)
        results.append(report("T26", "caption mismatch FAIL", False,
                              run([SCRIPTS / "figure_story.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T27 冗余图同处正文且无 keep_both_reason -> figure_story FAIL
    td, tws = method_copy()
    try:
        (tws / "figures" / "fig_q2.pdf").write_bytes((tws / "figures" / "fig_q1.pdf").read_bytes())
        (tws / "paper" / "main.tex").write_text(
            "\\begin{figure}\\includegraphics{figures/fig_q1}\\caption{PR 曲线 A}\\label{fig:q1}\\end{figure}\n"
            "\\begin{figure}\\includegraphics{figures/fig_q2}\\caption{PR 曲线 B}\\label{fig:q2}\\end{figure}\n",
            encoding="utf-8")
        manifest = json.loads((tws / "figures" / "figure_manifest.json").read_text(encoding="utf-8"))
        manifest = [
            {"id": "fig_q1", "main_message": "PR 曲线", "visual_priority": "primary",
             "files": ["figures/fig_q1.pdf"], "redundant_with": ["fig_q2"], "unique_information": "x",
             "keep_both_reason": ""},
            {"id": "fig_q2", "main_message": "PR 曲线（重复）", "visual_priority": "primary",
             "files": ["figures/fig_q2.pdf"], "redundant_with": ["fig_q1"], "unique_information": "x",
             "keep_both_reason": ""},
        ]
        json_write(tws / "figures" / "figure_manifest.json", manifest)
        results.append(report("T27", "冗余图同正文 FAIL", False,
                              run([SCRIPTS / "figure_story.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T28 verifier 不得修改 decision_log（静态保障：run_all_gates 源码无写入）
    src = (SCRIPTS / "run_all_gates.py").read_text(encoding="utf-8")
    violates = bool(re.search(r"dl\[\s*[\"']last_updated", src)) or "save_json(dl_path" in src
    results.append(report("T28", "verifier 只读保障", True,
                          SimpleNamespace(returncode=0 if not violates else 1, stdout="", stderr=""),
                          "T28-verifier-只读"))

    # T29 单位未换算（raw==value 但 registry 声明 *100）-> figure_story FAIL
    td, tws = method_copy()
    try:
        (tws / "reports" / "variables.json").write_text(
            json.dumps({"Y_fraction": {"storage_unit": "fraction", "storage_range": [0, 1],
                                       "display": {"percent": {"transform": "*100", "unit": "%",
                                                                "threshold_raw": 0.04,
                                                                "threshold_display": 4.0}}}},
                       ensure_ascii=False), encoding="utf-8")
        (tws / "figures").mkdir(exist_ok=True)
        json_write(tws / "figures" / "fig_q1.meta.json",
                   {"figure_id": "fig1", "generator": "g", "generator_sha256": "x",
                    "source_results": [], "annotations": [{"label": "阈值", "value_key": "T",
                                                           "raw": 0.04, "value": 0.04}],
                    "axes": [{"ylabel": "Y浓度 (%)", "variable": "Y_fraction", "display": "percent"}],
                    "panels": {}})
        results.append(report("T29", "单位未换算 FAIL", False,
                              run([SCRIPTS / "figure_story.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T30 契约 rev 过期（论文声明的 rev 落后于契约）-> methodology FAIL
    td, tws = method_copy()
    try:
        spec = json.loads((tws / "reports" / "FINAL_MODEL_SPEC.json").read_text(encoding="utf-8"))
        spec["contract_rev"] = 3
        json_write(tws / "reports" / "FINAL_MODEL_SPEC.json", spec)
        (tws / "paper" / "main.tex").write_text(
            "本问按 FINAL_MODEL_SPEC rev=1 建模（旧口径）。\n"
            "删失结构为区间删失，候选模型采用 Turnbull 与 interval-censored Weibull。\n",
            encoding="utf-8")
        results.append(report("T30", "契约 rev 过期 FAIL", False,
                              run([SCRIPTS / "methodology_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T31 text_integrity good fixture PASS（关键词分隔 + 无占位符）
    with tempfile.TemporaryDirectory() as td:
        tws = Path(td)
        (tws / "paper").mkdir(parents=True)
        (tws / "paper" / "main.tex").write_text(
            "\\abstractcn{摘要正文}{NIPT；区间删失；检测时点优化；代价敏感分类}\n", encoding="utf-8")
        results.append(report("T31", "text_integrity 干净 PASS", True,
                              run([SCRIPTS / "text_integrity.py", "--workspace", tws, "--strict"])))

    # T32 trace 内置白名单必须带上下文（任务书 28 条）：
    #   a) 论文出现裸 20（无 ±20%/20% 上下文）且 results 无 20 -> FAIL（UNTRACED）
    #   b) 论文出现 ±20% 且 results 无真值 -> ALLOWED -> PASS
    for case_i, (txt, expect_pass) in enumerate([
        ("扰动幅度不超过 20 时结论不变。\n", False),
        ("扰动幅度不超过 ±20% 时结论不变。\n", True),
    ]):
        with tempfile.TemporaryDirectory() as td:
            tws = Path(td)
            (tws / "paper").mkdir(parents=True)
            (tws / "results").mkdir()
            (tws / "paper" / "main.tex").write_text(txt, encoding="utf-8")
            (tws / "project.manifest.json").write_text(
                '{"schema_version":1,"engine":"latex","entry":"paper/main.tex","hil_policy":"disabled"}',
                encoding="utf-8")
            results.append(report(f"T32.{case_i}", f"trace 白名单上下文 [{ '允许' if expect_pass else '拦截' }]",
                                  expect_pass,
                                  run([SCRIPTS / "trace_numbers.py", "--workspace", tws, "--strict"])))

    # T33 核心方法无 citation（任务书 25 条）：method_citation_map 指向不存在的 ref -> FAIL
    with tempfile.TemporaryDirectory() as td:
        tws = Path(td)
        (tws / "paper").mkdir(parents=True)
        (tws / "reports").mkdir()
        (tws / "paper" / "main.tex").write_text("\\section{方法}\n用了 Turnbull 估计。\n", encoding="utf-8")
        (tws / "paper" / "references.tex").write_text(
            "\\begin{thebibliography}{9}\n\\end{thebibliography}\n", encoding="utf-8")
        (tws / "reports" / "method_citation_map.json").write_text(
            json.dumps({"Turnbull estimator": ["ref_turnbull"]}, ensure_ascii=False), encoding="utf-8")
        results.append(report("T33", "核心方法无文献 FAIL", False,
                              run([SCRIPTS / "verify_refs.py", "--workspace", tws, "--strict"])))

    # ============ v4.1 false-pass regression（T34-T45，任务书 v4.1 第七条） ============

    # T34 axis 标"%"但数据仍为 fraction（raw==value 且 transform=*100）-> figure_story FAIL
    td, tws = method_copy()
    try:
        (tws / "reports" / "variables.json").write_text(
            json.dumps({"Y_fraction": {"storage_unit": "fraction", "storage_range": [0, 1],
                                       "display": {"percent": {"transform": "*100", "unit": "%",
                                                                "threshold_raw": 0.04,
                                                                "threshold_display": 4.0}}}},
                       ensure_ascii=False), encoding="utf-8")
        (tws / "figures").mkdir(exist_ok=True)
        json_write(tws / "figures" / "fig_q1.meta.json",
                   {"figure_id": "fig1", "generator": "g", "generator_sha256": "x",
                    "source_results": [], "annotations": [{"label": "阈值", "value_key": "T",
                                                           "role": "reference_threshold",
                                                           "raw": 0.04, "value": 0.04}],
                    "axes": [{"ylabel": "Y浓度 (%)", "variable": "Y_fraction", "display": "percent"}],
                    "panels": {}})
        results.append(report("T34", "percent/fraction 混用 FAIL", False,
                              run([SCRIPTS / "figure_story.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T35 panel metadata=M1/M2 而 caption 写 M2/M3 -> figure_story FAIL
    td, tws = method_copy()
    try:
        (tws / "paper" / "main.tex").write_text(
            "\\begin{figure}\\includegraphics{figures/fig_q1}\\caption{panel M2/M3 对比}"
            "\\label{fig:q1}\\end{figure}\n", encoding="utf-8")
        manifest = json.loads((tws / "figures" / "figure_manifest.json").read_text(encoding="utf-8"))
        manifest[0]["panels"] = [{"id": "A", "model_id": "M1"}, {"id": "B", "model_id": "M2"}]
        manifest[0]["caption"] = "panel 为 M2/M3 对比"
        json_write(tws / "figures" / "figure_manifest.json", manifest)
        results.append(report("T35", "panel/caption mismatch FAIL", False,
                              run([SCRIPTS / "figure_story.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T36 current recommendation 与 baseline 绑定同一 value_key -> figure_story FAIL
    td, tws = method_copy()
    try:
        (tws / "figures").mkdir(exist_ok=True)
        (tws / "results").mkdir()
        json_write(tws / "results" / "p2_ic.json", {"G2": {"recommended": {"low": 15.0}}})
        json_write(tws / "figures" / "fig_q1.meta.json",
                   {"figure_id": "fig1", "generator": "g", "generator_sha256": "x",
                    "source_results": [{"file": "results/p2_ic.json", "sha256": "", "keys": ["G2.recommended.low"]}],
                    "annotations": [
                        {"label": "当前推荐", "value_key": "G2.recommended.low",
                         "role": "current_recommendation", "value": 15.0},
                        {"label": "旧基线", "value_key": "G2.recommended.low",
                         "role": "baseline_interpolation", "value": 15.0}],
                    "panels": {}})
        results.append(report("T36", "当前推荐绑定基线 key FAIL", False,
                              run([SCRIPTS / "figure_story.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T37 主模型为 interval censoring 但图 caption 写 KM/Greenwood -> figure_story FAIL
    td, tws = method_copy()
    try:
        (tws / "paper" / "main.tex").write_text(
            "\\begin{figure}\\includegraphics{figures/fig_q1}\\caption{Kaplan--Meier 与 Greenwood 置信带}"
            "\\label{fig:q1}\\end{figure}\n", encoding="utf-8")
        manifest = json.loads((tws / "figures" / "figure_manifest.json").read_text(encoding="utf-8"))
        manifest[0]["caption"] = "Kaplan--Meier 与 Greenwood 置信带"
        json_write(tws / "figures" / "figure_manifest.json", manifest)
        # 契约声明 interval 主口径（likelihood=interval 已在 fixture spec）
        m = json.loads((tws / "reports" / "FINAL_MODEL_SPEC.json").read_text(encoding="utf-8"))
        json_write(tws / "reports" / "FINAL_MODEL_SPEC.json", m)
        results.append(report("T37", "interval 主口径 vs KM caption FAIL", False,
                              run([SCRIPTS / "figure_story.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T38 论文核心似然出现 S(U)-S(L) -> text_integrity FAIL
    with tempfile.TemporaryDirectory() as td:
        tws = Path(td)
        (tws / "paper").mkdir(parents=True)
        (tws / "paper" / "main.tex").write_text(
            "区间删失贡献为 $S(U_i)-S(L_i)$。\n", encoding="utf-8")
        results.append(report("T38", "似然反向表达 FAIL", False,
                              run([SCRIPTS / "text_integrity.py", "--workspace", tws, "--strict"])))

    # T39 LaTeX 正文残留 **text** / `code` -> text_integrity FAIL
    with tempfile.TemporaryDirectory() as td:
        tws = Path(td)
        (tws / "paper").mkdir(parents=True)
        (tws / "paper" / "main.tex").write_text(
            "区间删失为**主口径**，使用 `Thr=0.04` 阈值。\n", encoding="utf-8")
        results.append(report("T39", "Markdown 残留 FAIL", False,
                              run([SCRIPTS / "text_integrity.py", "--workspace", tws, "--strict"])))

    # T40 正文出现 FINAL_MODEL_SPEC / results/ / reports/ -> text_integrity FAIL
    with tempfile.TemporaryDirectory() as td:
        tws = Path(td)
        (tws / "paper").mkdir(parents=True)
        (tws / "reports").mkdir()
        (tws / "paper" / "main.tex").write_text(
            "按 FINAL_MODEL_SPEC rev=1 实现，结果见 results/p2_ic.json。\n", encoding="utf-8")
        results.append(report("T40", "内部术语泄漏 FAIL", False,
                              run([SCRIPTS / "text_integrity.py", "--workspace", tws, "--strict"])))

    # T41 声明的 panel 无 data artist（无 min_artist_count -> 默认 1）-> figure_story FAIL
    td, tws = method_copy()
    try:
        (tws / "figures").mkdir(exist_ok=True)
        json_write(tws / "figures" / "fig_q1.meta.json",
                   {"figure_id": "fig1", "generator": "g", "generator_sha256": "x",
                    "source_results": [], "annotations": [],
                    "panels": {"B": {"line_count": 0, "scatter_count": 0}}})
        manifest = json.loads((tws / "figures" / "figure_manifest.json").read_text(encoding="utf-8"))
        manifest[0]["panels"] = [{"id": "B", "expected_marks": ["line:x"]}]
        json_write(tws / "figures" / "figure_manifest.json", manifest)
        results.append(report("T41", "空 panel（默认 1 artist）FAIL", False,
                              run([SCRIPTS / "figure_story.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T42 forest 图使用伪区间 [0,|beta|] -> figure_story FAIL（meta.axes.note 含 pseudo_interval 或
    #        caption 称 forest 但 ci_declared 未声明）
    td, tws = method_copy()
    try:
        (tws / "figures").mkdir(exist_ok=True)
        json_write(tws / "figures" / "fig_q1.meta.json",
                   {"figure_id": "fig1", "generator": "g", "generator_sha256": "x",
                    "source_results": [], "annotations": [],
                    "axes": [{"ylabel": "效应", "variable": "beta", "display": "magnitude",
                              "note": "pseudo_interval_0_to_abs_beta"}],
                    "panels": {}})
        manifest = json.loads((tws / "figures" / "figure_manifest.json").read_text(encoding="utf-8"))
        manifest[0]["caption"] = "协变量效应森林图（0 至 |beta| 作为区间）"
        json_write(tws / "figures" / "figure_manifest.json", manifest)
        results.append(report("T42", "伪 forest CI FAIL", False,
                              run([SCRIPTS / "figure_story.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T43 sensitivity/limitations 依赖旧 contract rev -> methodology FAIL
    td, tws = method_copy()
    try:
        spec = json.loads((tws / "reports" / "FINAL_MODEL_SPEC.json").read_text(encoding="utf-8"))
        spec["contract_rev"] = 2
        json_write(tws / "reports" / "FINAL_MODEL_SPEC.json", spec)
        (tws / "paper" / "main.tex").write_text(
            "按 FINAL_MODEL_SPEC rev=1 建模，局限见正文。\n"
            "删失结构为区间删失，候选模型采用 Turnbull 与 interval-censored Weibull。\n",
            encoding="utf-8")
        results.append(report("T43", "旧契约 rev 残留 FAIL", False,
                              run([SCRIPTS / "methodology_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T44 附录 source list 与实际 code 不一致 -> style_audit / appendix_source_list FAIL
    path_ws = Path(tempfile.mkdtemp())
    try:
        (path_ws / "code").mkdir(parents=True)
        (path_ws / "paper" / "sections").mkdir(parents=True)
        (path_ws / "code" / "problem1.py").write_text("x", encoding="utf-8")
        (path_ws / "paper" / "sections" / "A_code.tex").write_text(
            "\\section*{附录}\n\\lstinputlisting{../code/problem2.py}\n", encoding="utf-8")
        results.append(report("T44", "附录清单不一致 FAIL", False,
                              run([SCRIPTS / "appendix_source_list.py", "--workspace", path_ws, "--check"])))
    finally:
        import shutil as _sh
        _sh.rmtree(path_ws, ignore_errors=True)

    # T45 视觉审核 SHA 与最终 PDF SHA 不一致 -> visual_review --check FAIL
    path_ws = Path(tempfile.mkdtemp())
    try:
        (path_ws / "paper").mkdir(parents=True)
        (path_ws / "reports").mkdir()
        (path_ws / "paper" / "main.pdf").write_bytes(b"%PDF-fake-1")
        (path_ws / "reports" / "visual_review.json").write_text(
            json.dumps({"reviewed_pdf_sha256": "deadbeef" * 8}), encoding="utf-8")
        results.append(report("T45", "审稿 SHA 与 PDF 不一致 FAIL", False,
                              run([SCRIPTS / "visual_review.py", "--workspace", path_ws, "--check"])))
    finally:
        import shutil as _sh
        _sh.rmtree(path_ws, ignore_errors=True)

    # ============ v4.2 false-pass regression（T46-T64，任务书 v4.2 第十节） ============
    import zipfile as _zip

    def make_support_zip(tws: Path, files: dict):
        """构造 提交/支撑材料.zip（files: relpath -> str 内容）。"""
        sub = tws / "提交"
        sub.mkdir(parents=True, exist_ok=True)
        zpath = sub / "支撑材料.zip"
        with _zip.ZipFile(zpath, "w") as z:
            for rel, content in files.items():
                if content is None:
                    continue
                z.writestr(rel, content if isinstance(content, str) else content.read_bytes())
        return zpath

    # T46 小写 u/l 区间似然反向表达（S(u)-S(l) / S(u_i^-)-S(l_i) / S(r)-S(l)）-> text_integrity FAIL
    for i, expr in enumerate([
        r"\log[S(u_i)-S(l_i)]",
        r"\log[S(u_i^-)-S(l_i)]",
        r"\log[S(r)-S(l)]",
        r"\log[S(U_i)-S(L_i)]",
    ]):
        with tempfile.TemporaryDirectory() as td:
            tws = Path(td)
            (tws / "paper").mkdir(parents=True)
            (tws / "paper" / "main.tex").write_text(f"区间删失贡献为 {expr}。\n", encoding="utf-8")
            results.append(report(f"T46.{i}", f"likelihood 角色化校验 FAIL（{expr[:24]}…）", False,
                                  run([SCRIPTS / "text_integrity.py", "--workspace", tws, "--strict"])))
    # 正确方向必须 PASS
    with tempfile.TemporaryDirectory() as td:
        tws = Path(td)
        (tws / "paper").mkdir(parents=True)
        (tws / "paper" / "main.tex").write_text(
            r"区间删失贡献为 \log[S(l_i)-S(u_i^-)] 与 \log[S(L_i)-S(U_i)]。\n", encoding="utf-8")
        results.append(report("T46.good", "likelihood 正确方向 PASS", True,
                              run([SCRIPTS / "text_integrity.py", "--workspace", tws, "--strict"])))

    # T47 列表项第 3 项与第 5 项重复（不相邻）-> text_integrity FAIL（section 级）
    with tempfile.TemporaryDirectory() as td:
        tws = Path(td)
        (tws / "paper" / "sections").mkdir(parents=True)
        (tws / "paper" / "sections" / "10_evaluation.tex").write_text(
            "\\section{模型评价与推广}\n\\subsection{模型缺点}\n\\begin{enumerate}\n"
            "\\item 观测为删失结构，达标时间在 12 周以前的识别能力较弱。\n"
            "\\item 高 BMI 组样本较少，推荐窗口较宽。\n"
            "\\item 风险权重 1/3/10 是对题面定性描述的定量化，不同权重下推荐时点存在小幅移动。\n"
            "\\item 女胎阳性样本较少，模型性能的置信区间较宽。\n"
            "\\item 风险权重 1/3/10 是对题面定性描述的定量化，不同权重下推荐时点存在小幅移动。\n"
            "\\end{enumerate}\n", encoding="utf-8")
        results.append(report("T47", "非相邻重复列表项 FAIL", False,
                              run([SCRIPTS / "text_integrity.py", "--workspace", tws, "--strict"])))

    # T48 跨问题总结节裸 G3/G4（无作用域）-> text_integrity FAIL
    with tempfile.TemporaryDirectory() as td:
        tws = Path(td)
        (tws / "paper" / "sections").mkdir(parents=True)
        (tws / "paper" / "sections" / "10_evaluation.tex").write_text(
            "\\section{模型评价与推广}\n\\subsection{模型缺点}\n"
            "高 BMI 组（G3/G4）样本较少（n=20 与 n=95 中的 20）。\n", encoding="utf-8")
        results.append(report("T48", "无作用域组引用 FAIL", False,
                              run([SCRIPTS / "text_integrity.py", "--workspace", tws, "--strict"])))

    # T49 caption 含 A/B/C 但 manifest panels=[] -> figure_story FAIL（panel_declaration）
    td, tws = method_copy()
    try:
        (tws / "figures").mkdir(exist_ok=True)
        json_write(tws / "figures" / "fig_q1.meta.json",
                   {"figure_id": "fig1", "generator": "g", "generator_sha256": "x",
                    "source_results": [], "annotations": [], "axes": [], "panels": {}})
        manifest = json.loads((tws / "figures" / "figure_manifest.json").read_text(encoding="utf-8"))
        manifest[0]["caption"] = "数据总览（A：样本结构；B：浓度趋势）"
        manifest[0]["panels"] = []
        json_write(tws / "figures" / "figure_manifest.json", manifest)
        results.append(report("T49", "multi-panel 空 panels FAIL", False,
                              run([SCRIPTS / "figure_story.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T50 story claim 与 result 值矛盾（crosses_zero expected=False 但实际跨 0）-> figure_story FAIL
    td, tws = method_copy()
    try:
        (tws / "results").mkdir(exist_ok=True)
        json_write(tws / "results" / "p1_desc.json",
                   {"two_stage": {"bmi_ci": {"low": -0.047, "high": 0.026}}})
        manifest = json.loads((tws / "figures" / "figure_manifest.json").read_text(encoding="utf-8"))
        manifest[0]["story"] = {"main_message": "BMI 系数稳健（Bootstrap CI 不跨零）",
                                "claims": [{"result_key": "p1_desc.two_stage.bmi_ci",
                                            "predicate": "crosses_zero", "expected": False}]}
        manifest[0]["source"] = {"source_results": [{"file": "results/p1_desc.json", "keys": []}]}
        json_write(tws / "figures" / "figure_manifest.json", manifest)
        results.append(report("T50", "story claim 与结果矛盾 FAIL", False,
                              run([SCRIPTS / "figure_story.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T51 story 说插值口径而 caption 是 Turnbull -> figure_story FAIL（stale_story_term）
    td, tws = method_copy()
    try:
        (tws / "paper" / "main.tex").write_text(
            "\\begin{figure}\\includegraphics{figures/fig_q1}"
            "\\caption{各 BMI 组达标比例曲线（Turnbull 区间删失估计，阶梯型）}"
            "\\label{fig:q1}\\end{figure}\n", encoding="utf-8")
        manifest = json.loads((tws / "figures" / "figure_manifest.json").read_text(encoding="utf-8"))
        manifest[0]["story"] = {"main_message": "高 BMI 组达标更晚（插值口径）"}
        manifest[0]["caption"] = "各 BMI 组达标比例曲线（Turnbull 区间删失估计，阶梯型）"
        json_write(tws / "figures" / "figure_manifest.json", manifest)
        results.append(report("T51", "story 旧口径词 FAIL", False,
                              run([SCRIPTS / "figure_story.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T52 support code 含本机绝对路径 -> submission_package_gate FAIL
    with tempfile.TemporaryDirectory() as td:
        tws = Path(td)
        make_support_zip(tws, {
            "code/utils.py": "XLSX = r\"D:\\CUMCM2025Problems\\C题\\附件.xlsx\"\n",
            "README.md": "# 运行说明\n", "requirements.txt": "pandas\n",
        })
        results.append(report("T52", "支撑包绝对路径 FAIL", False,
                              run([SCRIPTS / "submission_package_gate.py", "--workspace", tws, "--check"])))

    # T53 ZIP 解压后 python problem1.py 因绝对路径失败 -> smoke FAIL
    with tempfile.TemporaryDirectory() as td:
        tws = Path(td)
        make_support_zip(tws, {
            "code/problem1.py": "open(r\"C:\\Users\\Administrator\\no_such_file_xyz.xlsx\")\n",
            "README.md": "# 运行说明\n", "requirements.txt": "pandas\n",
        })
        data_ph = tws / "fake.xlsx"
        data_ph.write_bytes(b"fake")
        results.append(report("T53", "clean-room smoke 绝对路径失败 FAIL", False,
                              run([SCRIPTS / "submission_package_gate.py", "--workspace", tws,
                                   "--smoke", "--data", str(data_ph)],
                                  )))

    # T54 appendix 列表 8 个但 ZIP code 有 13 个 -> submission_package_gate FAIL
    with tempfile.TemporaryDirectory() as td:
        tws = Path(td)
        (tws / "paper" / "sections").mkdir(parents=True)
        files = {"README.md": "# 运行说明\n", "requirements.txt": "pandas\n"}
        listed = []
        for i in range(13):
            files[f"code/p{i}.py"] = "x\n"
            listed.append(f"\\lstinputlisting{{../code/p{i}.py}}\n")
        files["paper/sections/A_code.tex"] = "\\section*{附录}\n" + "".join(listed[:8])
        files["references/literature.md"] = "| ref1 | x |\n"
        make_support_zip(tws, files)
        results.append(report("T54", "附录清单与 ZIP 不一致 FAIL", False,
                              run([SCRIPTS / "submission_package_gate.py", "--workspace", tws, "--check"])))

    # T55 literature registry 6 篇 vs paper refs 8 篇 -> submission_package_gate FAIL
    with tempfile.TemporaryDirectory() as td:
        tws = Path(td)
        (tws / "paper").mkdir(parents=True)
        (tws / "reports").mkdir()
        (tws / "paper" / "references.tex").write_text(
            "\\begin{thebibliography}{9}\n" + "".join(
                f"\\bibitem{{ref{i}}} x\n" for i in range(1, 9)) + "\\end{thebibliography}\n",
            encoding="utf-8")
        (tws / "reports" / "method_citation_map.json").write_text(
            json.dumps({"Turnbull": ["ref_turnbull"], "AFT": ["ref6"]}), encoding="utf-8")
        lit = "| 编号 | 标题 |\n" + "".join(f"| ref{i} | x |\n" for i in range(1, 7))
        make_support_zip(tws, {"README.md": "# 运行说明\n", "requirements.txt": "pandas\n",
                               "code/a.py": "x\n",
                               "references/literature.md": lit})
        results.append(report("T55", "references registry 落后 FAIL", False,
                              run([SCRIPTS / "submission_package_gate.py", "--workspace", tws, "--check"])))

    # T56 A_code.tex 用 \input{appendix_source_list.tex} 且 fragment 齐全 -> appendix_source_list PASS
    path_ws = Path(tempfile.mkdtemp())
    try:
        (path_ws / "code").mkdir(parents=True)
        (path_ws / "paper" / "sections").mkdir(parents=True)
        (path_ws / "code" / "problem1.py").write_text('"""问题一：描述统计。"""\nx\n', encoding="utf-8")
        (path_ws / "paper" / "appendix_source_list.tex").write_text(
            "\\subsubsection*{problem1.py}\n\\lstinputlisting{../code/problem1.py}\n",
            encoding="utf-8")
        (path_ws / "paper" / "sections" / "A_code.tex").write_text(
            "\\section*{附录}\n\\input{../appendix_source_list}\n", encoding="utf-8")
        results.append(report("T56", "input 展开后清单一致 PASS", True,
                              run([SCRIPTS / "appendix_source_list.py", "--workspace", path_ws, "--check"])))
    finally:
        import shutil as _sh
        _sh.rmtree(path_ws, ignore_errors=True)

    # T57 contact sheet 请求 N 页必须渲染 N 页（请求 20 页 -> layout 5x4，禁止 15 页溢出）
    try:
        import fitz as _fitz
        path_ws = Path(tempfile.mkdtemp())
        try:
            (path_ws / "paper").mkdir(parents=True)
            (path_ws / "reports").mkdir()
            pdf = path_ws / "paper" / "main.pdf"
            with _fitz.open() as d:
                for _ in range(20):
                    d.new_page(width=595, height=842)
                d.save(str(pdf))
            proc = run([SCRIPTS / "visual_review.py", "--workspace", path_ws, "--pages", "20"])
            rec = json.loads((path_ws / "reports" / "visual_review.json").read_text(encoding="utf-8"))
            ok_layout = rec.get("contact_sheet_pages") == 20 and rec.get("contact_sheet_layout") == "5x4"
            results.append(report("T57", "contact sheet 20 页全渲染 PASS", True, proc)
                           if ok_layout else
                           report("T57", "contact sheet 20 页全渲染 PASS", False,
                                  SimpleNamespace(returncode=proc.returncode, stdout=proc.stdout,
                                                  stderr=proc.stderr),
                                  f"layout={rec.get('contact_sheet_layout')} pages={rec.get('contact_sheet_pages')}"))
        finally:
            import shutil as _sh
            _sh.rmtree(path_ws, ignore_errors=True)
    except ImportError:
        print("[SKIP] T57 缺少 PyMuPDF")
        skipped.append("T57 contact sheet（缺 PyMuPDF）")

    # T58 workflow input 写 generated_values mandatory 但 README 标 optional -> docs_sync FAIL
    repo_root = Path(__file__).resolve().parents[3]
    repo = Path(tempfile.mkdtemp())
    try:
        shutil.copy2(repo_root / "workflow_spec.yaml", repo / "workflow_spec.yaml")
        readme_src = repo_root / "README.md"
        readme_text = readme_src.read_text(encoding="utf-8")
        readme_text = readme_text.replace("可选的 `paper/generated_values.tex`", "`paper/generated_values.tex`")
        (repo / "README.md").write_text(readme_text, encoding="utf-8")
        results.append(report("T58", "generated_values 政策漂移 FAIL", False,
                              run([SCRIPTS / "docs_sync.py", "--check", "--root", repo])))
    finally:
        import shutil as _sh
        _sh.rmtree(repo, ignore_errors=True)

    # T59 methodology 输出旧 reports/figure_story_manifest.json -> docs_sync FAIL
    repo = Path(tempfile.mkdtemp())
    try:
        shutil.copy2(repo_root / "workflow_spec.yaml", repo / "workflow_spec.yaml")
        readme_src = repo_root / "README.md"
        (repo / "README.md").write_text(readme_src.read_text(encoding="utf-8"), encoding="utf-8")
        (repo / "skills" / "1start-mathmodel").mkdir(parents=True)
        (repo / "skills" / "1start-mathmodel" / "SKILL.md").write_text(
            "产出 `reports/figure_story_manifest.json`。\n", encoding="utf-8")
        results.append(report("T59", "旧 figure_story 路径残留 FAIL", False,
                              run([SCRIPTS / "docs_sync.py", "--check", "--root", repo])))
    finally:
        import shutil as _sh
        _sh.rmtree(repo, ignore_errors=True)

    # T60 chosen PPV <= all-positive baseline 且论文有强结论词 -> deployment_utility FAIL
    with tempfile.TemporaryDirectory() as td:
        tws = Path(td)
        (tws / "paper").mkdir(parents=True)
        (tws / "reports").mkdir()
        (tws / "paper" / "main.tex").write_text(
            "本模型显著提高阳性识别效率，为临床提供预警支持。\n", encoding="utf-8")
        (tws / "reports" / "audit.json").write_text(json.dumps({
            "prevalence": 0.299, "chosen": {"ppv": 0.2958},
            "all_positive": {"ppv": 0.299}}), encoding="utf-8")
        results.append(report("T60", "部署效用无增益强结论 FAIL", False,
                              run([SCRIPTS / "deployment_utility.py", "--workspace", tws, "--strict",
                                   "--audit-json", "reports/audit.json"])))

    # T61 simpler ablation AUPRC > primary 但无 parsimony review -> methodology FAIL
    td, tws = method_copy()
    try:
        (tws / "results").mkdir(exist_ok=True)
        json_write(tws / "results" / "p4_models.json",
                   {"primary": {"auprc": 0.4564}, "ablation_simpler": {"auprc": 0.4722}})
        results.append(report("T61", "无 parsimony review FAIL", False,
                              run([SCRIPTS / "methodology_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T62 算法家族选择用 outer_test 登记（宣称 nested 却用外层）-> leakage FAIL
    td, tws = method_copy()
    try:
        scope = json.loads((tws / "reports" / "methodology" / "ml_operation_scope.json")
                           .read_text(encoding="utf-8"))
        scope["operations"].append({"operation": "algorithm_family_selection",
                                    "allowed_data": "outer_test"})
        json_write(tws / "reports" / "methodology" / "ml_operation_scope.json", scope)
        results.append(report("T62", "家族选择 outer_test FAIL", False,
                              run([SCRIPTS / "leakage_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T63 support 引用不存在的内部 report -> submission_package_gate FAIL（dangling）
    with tempfile.TemporaryDirectory() as td:
        tws = Path(td)
        make_support_zip(tws, {
            "README.md": "# 运行说明\n", "requirements.txt": "pandas\n",
            "code/utils.py": "# 口径/方法细节见 reports/ANALYSIS_MODELING_REPORT.md\n",
        })
        results.append(report("T63", "dangling 内部路径引用 FAIL", False,
                              run([SCRIPTS / "submission_package_gate.py", "--workspace", tws, "--check"])))

    # T64 核心结果 .get(key, 0.0395) 硬编码 fallback -> leakage FAIL
    with tempfile.TemporaryDirectory() as td:
        tws = Path(td)
        (tws / "code").mkdir(parents=True)
        (tws / "code" / "woman_level.py").write_text(
            "thr = cfg.get(\"threshold\", 0.0395)\n", encoding="utf-8")
        results.append(report("T64", "硬编码 fallback FAIL", False,
                              run([SCRIPTS / "leakage_gate.py", "--workspace", tws, "--strict"])))

    # ============ v4.3 contract semantics regression（T70-T74，任务书 v4.3 §4/§14/§15） ============
    import hashlib as _hl

    def _v2_spec(tws, dist="weibull", fsid="Q1.feat.v1", fig_ids=("fig1",), rev="Q1"):
        spec = json.loads((tws / "reports" / "FINAL_MODEL_SPEC.json").read_text(encoding="utf-8"))
        spec["schema_version"] = 2
        spec["contract_rev"] = int(spec.get("contract_rev", 1) or 1) + 1
        p = dict(spec["problems"][0])
        p["problem_id"] = rev
        p["model"] = {"family": "aft", "distribution": dist,
                      "parameterization": "logT = gamma0 + gamma1*BMI + sigma*W"}
        p["features"] = {"feature_set_id": fsid, "included": [{"id": "bmi", "role": "covariate"}],
                         "excluded": []}
        p["figure_ids"] = list(fig_ids)
        p["result_keys"] = ["results/p0.json#a"]
        spec["problems"] = [p]
        json_write(tws / "reports" / "FINAL_MODEL_SPEC.json", spec)
        return spec

    def _vars(tws):
        json_write(tws / "reports" / "variables.json",
                   {"bmi": {"storage_unit": "kg_m2", "availability": "available"},
                    "age": {"storage_unit": "year"}})

    def _meta_ok(spec_hash, dist="weibull", fsid="Q1.feat.v1", pid="Q1"):
        return {"_meta": {"problem_id": pid, "role": "paper_authority",
                          "model_spec_sha256": spec_hash, "contract_rev": 2,
                          "model_family": "aft", "model_distribution": dist,
                          "feature_set_id": fsid}}

    # T70 部分绑定：15 个 paper-authority 结果仅 5 个带正确 hash -> FAIL
    td, tws = method_copy()
    try:
        _v2_spec(tws)
        _vars(tws)
        (tws / "results").mkdir(exist_ok=True)
        spec_hash = _hl.sha256((tws / "reports" / "FINAL_MODEL_SPEC.json").read_bytes()).hexdigest()
        arts = []
        for i in range(15):
            fn = f"p{i}.json"
            doc = {"a": i}
            if i < 5:
                doc.update(_meta_ok(spec_hash))
            json_write(tws / "results" / fn, doc)
            arts.append({"file": f"results/{fn}", "role": "paper_authority",
                         "problem_id": "Q1", "requires_model_spec_binding": True})
        json_write(tws / "results" / "RESULT_REGISTRY.json", {"schema_version": 1, "artifacts": arts})
        results.append(report("T70", "结果部分绑定契约 FAIL", False,
                              run([SCRIPTS / "methodology_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T70.good 全部绑定 + _meta 一致 -> PASS
    td, tws = method_copy()
    try:
        _v2_spec(tws)
        _vars(tws)
        (tws / "results").mkdir(exist_ok=True)
        spec_hash = _hl.sha256((tws / "reports" / "FINAL_MODEL_SPEC.json").read_bytes()).hexdigest()
        arts = []
        for i in range(3):
            fn = f"p{i}.json"
            json_write(tws / "results" / fn, {"a": i, **_meta_ok(spec_hash)})
            arts.append({"file": f"results/{fn}", "role": "paper_authority",
                         "problem_id": "Q1", "requires_model_spec_binding": True})
        json_write(tws / "results" / "RESULT_REGISTRY.json", {"schema_version": 1, "artifacts": arts})
        results.append(report("T70.good", "全量绑定+语义一致 PASS", True,
                              run([SCRIPTS / "methodology_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T71 spec distribution=weibull vs result _meta lognormal -> FAIL
    td, tws = method_copy()
    try:
        _v2_spec(tws, dist="weibull")
        _vars(tws)
        (tws / "results").mkdir(exist_ok=True)
        spec_hash = _hl.sha256((tws / "reports" / "FINAL_MODEL_SPEC.json").read_bytes()).hexdigest()
        json_write(tws / "results" / "p0.json", {"a": 1, **_meta_ok(spec_hash, dist="lognormal")})
        json_write(tws / "results" / "RESULT_REGISTRY.json",
                   {"artifacts": [{"file": "results/p0.json", "role": "paper_authority",
                                   "problem_id": "Q1", "requires_model_spec_binding": True}]})
        results.append(report("T71", "spec/result 分布元数据矛盾 FAIL", False,
                              run([SCRIPTS / "methodology_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T72 spec feature_set_id vs result _meta 不一致 -> FAIL
    td, tws = method_copy()
    try:
        _v2_spec(tws, fsid="Q1.feat.v1")
        _vars(tws)
        (tws / "results").mkdir(exist_ok=True)
        spec_hash = _hl.sha256((tws / "reports" / "FINAL_MODEL_SPEC.json").read_bytes()).hexdigest()
        json_write(tws / "results" / "p0.json", {"a": 1, **_meta_ok(spec_hash, fsid="Q1.feat.OLD")})
        json_write(tws / "results" / "RESULT_REGISTRY.json",
                   {"artifacts": [{"file": "results/p0.json", "role": "paper_authority",
                                   "problem_id": "Q1", "requires_model_spec_binding": True}]})
        results.append(report("T72", "spec/result feature_set 元数据矛盾 FAIL", False,
                              run([SCRIPTS / "methodology_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T73 spec included 引用 availability=unavailable 变量 -> FAIL
    td, tws = method_copy()
    try:
        _v2_spec(tws)
        json_write(tws / "reports" / "variables.json",
                   {"bmi": {"storage_unit": "kg_m2", "availability": "unavailable"}})
        results.append(report("T73", "spec 引用 unavailable 变量 FAIL", False,
                              run([SCRIPTS / "methodology_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T74 spec figure_ids 指向 deleted/不存在图 -> FAIL
    for name, fig_ids, extra_manifest in (
            ("T74", ("fig_del",), {"id": "fig_del", "status": "deleted"}),
            ("T74.b", ("ghost_fig",), None)):
        td, tws = method_copy()
        try:
            _v2_spec(tws, fig_ids=fig_ids)
            _vars(tws)
            if extra_manifest:
                man = json.loads((tws / "figures" / "figure_manifest.json").read_text(encoding="utf-8"))
                man.append(extra_manifest)
                json_write(tws / "figures" / "figure_manifest.json", man)
            results.append(report(name, "spec 引用失效图 FAIL", False,
                                  run([SCRIPTS / "methodology_gate.py", "--workspace", tws, "--strict"])))
        finally:
            td.cleanup()

    # ============ v4.3 decision / provenance / uncertainty regression（T75-T79） ============

    def _good_bind_ws(tws, dist="weibull", fsid="Q1.feat.v1"):
        _v2_spec(tws, dist=dist, fsid=fsid)
        _vars(tws)
        (tws / "results").mkdir(exist_ok=True)
        spec_hash = _hl.sha256((tws / "reports" / "FINAL_MODEL_SPEC.json").read_bytes()).hexdigest()
        json_write(tws / "results" / "p0.json", {"a": 1, **_meta_ok(spec_hash, dist=dist, fsid=fsid)})
        json_write(tws / "results" / "RESULT_REGISTRY.json",
                   {"schema_version": 1, "artifacts": [{"file": "results/p0.json",
                                                        "role": "paper_authority", "problem_id": "Q1",
                                                        "requires_model_spec_binding": True}]})
        return spec_hash

    def _decision(tws, d):
        (tws / "reports" / "decisions").mkdir(parents=True, exist_ok=True)
        json_write(tws / "reports" / "decisions" / "MODEL_SELECTION_DECISION.json",
                   {"schema_version": 1, "decisions": [d]})

    def _paper(tws, extra):
        body = ("\\section{方法}\n在控制孕妇个体随机效应后，条件残差近似独立。\n"
                "删失结构为区间删失，候选模型采用 Turnbull 与 interval-censored Weibull。\n"
                "组样本量充足。\n" + extra + "\n")
        (tws / "paper" / "main.tex").write_text(body, encoding="utf-8")

    # T75 论文声明"预指定"但 decision frozen_at 晚于结果生成 -> FAIL
    td, tws = method_copy()
    try:
        _good_bind_ws(tws)
        _paper(tws, "按预指定解释性优先级保留 22 维模型。")
        _decision(tws, {"decision_id": "Q1-D01", "decision_type": "feature_set",
                        "candidate_ids": ["A", "B"], "frozen_at": "2099-01-01T00:00:00+08:00",
                        "before_result_artifacts": ["results/p0.json"],
                        "selection_rule": "pre_specified_primary", "selected": "B",
                        "rejected": ["A"], "exceptions": []})
        results.append(report("T75", "预指定无时序证据 FAIL", False,
                              run([SCRIPTS / "methodology_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T75.good 决策冻结早于结果 -> PASS
    td, tws = method_copy()
    try:
        _good_bind_ws(tws)
        _paper(tws, "按预指定解释性优先级保留 22 维模型。")
        _decision(tws, {"decision_id": "Q1-D01", "decision_type": "feature_set",
                        "candidate_ids": ["A", "B"], "frozen_at": "2020-01-01T00:00:00+08:00",
                        "before_result_artifacts": ["results/p0.json"],
                        "selection_rule": "pre_specified_primary", "selected": "B",
                        "rejected": ["A"], "exceptions": []})
        results.append(report("T75.good", "预指定时序可证明 PASS", True,
                              run([SCRIPTS / "methodology_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T76 one_se_choose_simpler 但选择更复杂模型且无例外 -> FAIL
    td, tws = method_copy()
    try:
        _good_bind_ws(tws)
        _decision(tws, {"decision_id": "Q1-D02", "decision_type": "feature_set",
                        "frozen_at": "2020-01-01T00:00:00+08:00", "before_result_artifacts": ["results/p0.json"],
                        "selection_rule": "one_se_choose_simpler", "selected": "B", "rejected": ["A"],
                        "exceptions": [], "selected_complexity": 22,
                        "complexity_of_best_simple": 19})
        results.append(report("T76", "one-SE 选复杂模型无例外 FAIL", False,
                              run([SCRIPTS / "methodology_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T76.good one-SE 选复杂但有例外 -> PASS
    td, tws = method_copy()
    try:
        _good_bind_ws(tws)
        _decision(tws, {"decision_id": "Q1-D02", "decision_type": "feature_set",
                        "frozen_at": "2020-01-01T00:00:00+08:00", "before_result_artifacts": ["results/p0.json"],
                        "selection_rule": "one_se_choose_simpler", "selected": "B", "rejected": ["A"],
                        "exceptions": [{"id": "interpretability_priority", "note": "临床可解释性优先"}],
                        "selected_complexity": 22, "complexity_of_best_simple": 19})
        results.append(report("T76.good", "one-SE 例外声明充分 PASS", True,
                              run([SCRIPTS / "methodology_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T77 家族选择声明 inner_cv 但缺逐折 provenance -> leakage FAIL
    td, tws = method_copy()
    try:
        scope = json.loads((tws / "reports" / "methodology" / "ml_operation_scope.json")
                           .read_text(encoding="utf-8"))
        scope["operations"].append({"operation": "algorithm_family_selection",
                                    "allowed_data": "inner_cv"})
        json_write(tws / "reports" / "methodology" / "ml_operation_scope.json", scope)
        results.append(report("T77", "nested 家族选择无 provenance FAIL", False,
                              run([SCRIPTS / "leakage_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T77.good 完整逐折 provenance -> PASS
    td, tws = method_copy()
    try:
        scope = json.loads((tws / "reports" / "methodology" / "ml_operation_scope.json")
                           .read_text(encoding="utf-8"))
        scope["operations"].append({"operation": "algorithm_family_selection",
                                    "allowed_data": "inner_cv"})
        json_write(tws / "reports" / "methodology" / "ml_operation_scope.json", scope)
        prov = {"outer_folds": [{
            "outer_fold": f, "inner_candidates": ["lr", "rf", "gbdt"],
            "selected_family": "lr", "selection_data_hash": f"inner{f}",
            "outer_test_group_hash": f"outer{f}"} for f in (1, 2)]}
        json_write(tws / "reports" / "methodology" / "family_selection_provenance.json", prov)
        results.append(report("T77.good", "家族选择 provenance 齐全 PASS", True,
                              run([SCRIPTS / "leakage_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T78 provenance 缺 inner-only group 字段 -> FAIL
    td, tws = method_copy()
    try:
        scope = json.loads((tws / "reports" / "methodology" / "ml_operation_scope.json")
                           .read_text(encoding="utf-8"))
        scope["operations"].append({"operation": "algorithm_family_selection",
                                    "allowed_data": "inner_cv"})
        json_write(tws / "reports" / "methodology" / "ml_operation_scope.json", scope)
        prov = {"outer_folds": [{"outer_fold": 1, "inner_candidates": ["lr"], "selected_family": "lr"}]}
        json_write(tws / "reports" / "methodology" / "family_selection_provenance.json", prov)
        results.append(report("T78", "provenance 缺 hash 字段 FAIL", False,
                              run([SCRIPTS / "leakage_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T79 sampling CI 直接充当推荐窗口（无 construction_rule）-> methodology FAIL
    td, tws = method_copy()
    try:
        _good_bind_ws(tws)
        doc = json.loads((tws / "results" / "p0.json").read_text(encoding="utf-8"))
        doc["uncertainty"] = {"sampling_ci": {"level": 0.95, "low": 13.0, "high": 24.2},
                              "decision_window": {"low": None, "high": None, "construction_rule": None}}
        json_write(tws / "results" / "p0.json", doc)
        _paper(tws, "95\\% 置信区间为 13.0-24.2 周，推荐窗口为 13.0-24.2 周。")
        results.append(report("T79", "CI 充当推荐窗口 FAIL", False,
                              run([SCRIPTS / "methodology_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T79.good 显式 construction_rule -> PASS
    td, tws = method_copy()
    try:
        _good_bind_ws(tws)
        doc = json.loads((tws / "results" / "p0.json").read_text(encoding="utf-8"))
        doc["uncertainty"] = {"sampling_ci": {"level": 0.95, "low": 13.0, "high": 24.2},
                              "decision_window": {"low": None, "high": None,
                                                  "construction_rule": "按点估计与 95% CI 结合 q 约束、整数周与安全边界的规则构造"}}
        json_write(tws / "results" / "p0.json", doc)
        _paper(tws, "95\\% 置信区间为 13.0-24.2 周，推荐窗口为 13.0-24.2 周。")
        results.append(report("T79.good", "窗口构造规则显式 PASS", True,
                              run([SCRIPTS / "methodology_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # ============ v4.3 brainstorm contracts regression（T65-T69，任务书 v4.3 §12） ============

    def _idea_ws(fail_cond_ok=True, with_i10=False, spec_idea="Q1-I02", primary="Q1-I02",
                 no_evidence=False, claim_word=None, report_text=None):
        td = tempfile.TemporaryDirectory()
        tws = Path(td.name)
        (tws / "reports" / "contracts").mkdir(parents=True, exist_ok=True)
        json_write(tws / "reports" / "contracts" / "QUESTION_CONTRACT.json",
                   {"schema_version": 1, "questions": [{
                       "question_id": "Q1", "original_request": "...", "decision_target": "...",
                       "analysis_unit": "pregnant_woman", "observation_unit": "test_record",
                       "required_outputs": [], "allowed_information": [], "forbidden_information": [],
                       "special_data_structure": ["left_censoring", "interval_censoring", "right_censoring"],
                       "evaluation_target": []}]})
        cands = [
            {"idea_id": "Q1-I01", "question_id": "Q1", "method_family": "turnbull_interval",
             "tier": "minimal_sufficient_solution", "core_hypothesis": "非参数区间删失估计",
             "why_applicable": "数据为删失", "required_variables": [], "required_assumptions": ["观测机制一致"],
             "data_risks": [], "strengths": [], "weaknesses": [], "validation_plan": [],
             "failure_conditions": ["删失比例过高"], "complexity": "low", "interpretability": "high",
             "status": "candidate"},
            {"idea_id": "Q1-I02", "question_id": "Q1", "method_family": "interval_censored_aft",
             "tier": "recommended_solution", "core_hypothesis": "AFT 可解释时点",
             "why_applicable": "删失+协变量", "required_variables": ["BMI"],
             "required_assumptions": ["对数正态误差"], "data_risks": [], "strengths": [],
             "weaknesses": [], "validation_plan": [], "failure_conditions": ["组间异质"],
             "complexity": "medium", "interpretability": "high", "status": "candidate"},
            {"idea_id": "Q1-I03", "question_id": "Q1", "method_family": "joint_model",
             "tier": "advanced_alternative", "core_hypothesis": "联合建模",
             "why_applicable": "", "required_variables": [], "required_assumptions": ["a"],
             "data_risks": [], "strengths": [], "weaknesses": [], "validation_plan": [],
             "failure_conditions": ["收敛失败"], "complexity": "high", "interpretability": "low",
             "status": "candidate"},
        ]
        if with_i10:
            cands.append({"idea_id": "Q1-I10", "question_id": "Q1", "method_family": "exact_event_ols",
                          "tier": "recommended_solution", "core_hypothesis": "精确事件回归",
                          "why_applicable": "", "required_variables": [], "required_assumptions": ["a"],
                          "data_risks": [], "strengths": [], "weaknesses": [], "validation_plan": [],
                          "failure_conditions": ["f"], "complexity": "low", "interpretability": "high",
                          "status": "candidate"})
        if not fail_cond_ok:
            cands[0]["failure_conditions"] = []
        if no_evidence:
            cands[2].pop("evidence_against_minimal", None)
        else:
            cands[2]["evidence_against_minimal"] = ["minimal 无法解释协变量效应"]
        if claim_word:
            cands[1]["core_hypothesis"] = f"{claim_word}该方法有效解决量化问题"
        json_write(tws / "reports" / "contracts" / "IDEA_CANDIDATES.json",
                   {"schema_version": 1, "candidates": cands})
        json_write(tws / "reports" / "contracts" / "IDEA_DECISION.json",
                   {"schema_version": 1, "primary": {"Q1": primary}, "accepted": ["Q1-I01", "Q1-I02"],
                    "baseline": ["Q1-I01"], "backup": [], "exploratory": ["Q1-I03"],
                    "rejected": ["Q1-I99"], "unresolved_questions": []
                    if not with_i10 else []})
        (tws / "reports" / "BRAINSTORM_REPORT.md").write_text(
            "候选评估：Q1-I01 作为基线；Q1-I02 推荐。" if report_text is None else report_text,
            encoding="utf-8")
        json_write(tws / "reports" / "FINAL_MODEL_SPEC.json",
                   {"schema_version": 1, "project": "fixture", "contract_rev": 1,
                    "problems": [{"problem_id": "Q1", "idea_id": spec_idea,
                                  "primary_model": "interval_censored_aft"}]})
        return td, tws

    # T65 候选缺 failure_conditions -> idea_gate FAIL
    td, tws = _idea_ws(fail_cond_ok=False)
    try:
        results.append(report("T65", "候选缺失败条件 FAIL", False,
                              run([SCRIPTS / "idea_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T65.good 完整三件套（含 minimal/recommended/advanced + primary recommended）-> PASS
    td, tws = _idea_ws()
    try:
        results.append(report("T65.good", "Brainstorm 三件套合规 PASS", True,
                              run([SCRIPTS / "idea_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T66 rejected 候选进入 FINAL_MODEL_SPEC -> FAIL
    td, tws = _idea_ws(spec_idea="Q1-I99")
    try:
        results.append(report("T66", "rejected 候选进入正式模型 FAIL", False,
                              run([SCRIPTS / "idea_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T67 advanced primary 无 minimal 反证 -> FAIL
    td, tws = _idea_ws(primary="Q1-I03", no_evidence=True)
    try:
        results.append(report("T67", "复杂 primary 无 minimal 证据 FAIL", False,
                              run([SCRIPTS / "idea_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T68 Brainstorm 出现实验结论词 -> FAIL
    td, tws = _idea_ws(claim_word="结果表明")
    try:
        results.append(report("T68", "Brainstorm 结论词 FAIL", False,
                              run([SCRIPTS / "idea_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # T69 契约声明删失但 primary 用 exact-event OLS 无标记 -> FAIL
    td, tws = _idea_ws(with_i10=True, primary="Q1-I10", spec_idea="Q1-I10")
    try:
        results.append(report("T69", "删失数据精确事件模型 FAIL", False,
                              run([SCRIPTS / "idea_gate.py", "--workspace", tws, "--strict"])))
    finally:
        td.cleanup()

    # ============ v4.3 final page composition regression（T95-T99，任务书 v4.3 §29A） ============
    try:
        import fitz as _fitz

        def _pdf_ws(pages):
            """pages: list of str；构造 project.manifest(latex 无源) + paper/main.pdf。
            文本按行插入（每行 56 字符、行距 16pt），嵌入微软雅黑保证中文可提取。"""
            _td = tempfile.TemporaryDirectory()
            tws = Path(_td.name)
            (tws / "paper").mkdir(parents=True)
            (tws / "reports").mkdir()
            (tws / "project.manifest.json").write_text(
                json.dumps({"schema_version": 1, "engine": "latex", "entry": "paper/main.tex"}),
                encoding="utf-8")
            fontfile = r"C:\Windows\Fonts\msyh.ttc"
            import textwrap as _tw
            with _fitz.open() as d:
                for txt in pages:
                    pg = d.new_page(width=595, height=842)
                    y = 100
                    for line in _tw.wrap(txt, 38)[:40]:
                        pg.insert_text((72, y), line, fontsize=10, fontfile=fontfile,
                                       fontname="msyh", encoding="utf-8")
                        y += 16
                d.save(str(tws / "paper" / "main.pdf"))
            return _td, tws

        # T95 摘要+关键词跨页（关键词尾部 3 字溢出第 2 页）-> orphan_text_spill FAIL
        _td, tws = _pdf_ws(["摘要" + "模型描述" * 60 + "关键词：A B C D E F",
                            "体判定"])
        try:
            results.append(report("T95", "关键词尾部溢出 FAIL", False,
                                  run([SCRIPTS / "layout_gate.py", "--workspace", tws])))
        finally:
            _td.cleanup()

        # T95.good 摘要+关键词完整同页 -> PASS
        _td, tws = _pdf_ws(["摘要" + "模型描述" * 60 + "关键词：A B C D E F"])
        try:
            results.append(report("T95.good", "摘要关键词同页 PASS", True,
                                  run([SCRIPTS / "layout_gate.py", "--workspace", tws])))
        finally:
            _td.cleanup()

        # T96 近空延续页（第 2 页仅 2 字，第 3 页继续正文）-> FAIL
        _td, tws = _pdf_ws(["正文" * 200, "12", "正文延续" * 100])
        try:
            results.append(report("T96", "近空延续页 FAIL", False,
                                  run([SCRIPTS / "layout_gate.py", "--workspace", tws])))
        finally:
            _td.cleanup()

        # T97 低填充页 + 下一页顶部为图 caption -> recoverable_underfill FAIL（JSON 断言）
        _td, tws = _pdf_ws(["正文" * 300, "本页内容很少" * 5,
                            "图 9：多特征分类性能。 " + "正文" * 200])
        try:
            proc = run([SCRIPTS / "layout_gate.py", "--workspace", tws])
            rec = json.loads((tws / "reports" / "gates" / "layout_gate.json").read_text(encoding="utf-8"))
            triggered = any(c.get("id") == "recoverable_underfill" and c["status"] == "FAIL"
                            for c in rec["checks"])
            results.append(report("T97", "float 诱导欠填充 FAIL", not triggered, proc,
                                  "" if triggered else "underfill 未触发"))
        finally:
            _td.cleanup()

        # T99 首次引用"表 5"在第 1 页（低填充）、表 5 caption 在第 2 页 -> first_reference_gap FAIL
        _td, tws = _pdf_ws(["如表 5 所示。" + "正文" * 400, "表 5：分组阈值。" + "正文" * 200])
        try:
            proc = run([SCRIPTS / "layout_gate.py", "--workspace", tws])
            rec = json.loads((tws / "reports" / "gates" / "layout_gate.json").read_text(encoding="utf-8"))
            triggered = any(c.get("id") == "first_reference_gap" and c["status"] == "FAIL"
                            for c in rec["checks"])
            results.append(report("T99", "首次引用 float 断裂 FAIL", not triggered, proc,
                                  "" if triggered else "first_reference_gap 未触发"))
        finally:
            _td.cleanup()
    except ImportError:
        print("[SKIP] T95-T99 缺少 PyMuPDF")
    try:
        import fitz as _fitz

        def _visual_ws(pdf_pages=3, pr=None, vr=None):
            _td = tempfile.TemporaryDirectory()
            tws = Path(_td.name)
            (tws / "paper").mkdir(parents=True)
            (tws / "reports").mkdir()
            with _fitz.open() as _d:
                for _ in range(pdf_pages):
                    _d.new_page(width=595, height=842)
                _d.save(str(tws / "paper" / "main.pdf"))
            sha = _hl.sha256((tws / "paper" / "main.pdf").read_bytes()).hexdigest()
            json_write(tws / "reports" / "visual_review.json",
                       vr or {"reviewed_pdf_sha256": sha, "contact_sheet_pages": pdf_pages})
            if pr is not None:
                json_write(tws / "reports" / "page_visual_review.json", pr)
            return _td, tws, sha

        def _pr_ok(sha, npages, findings=None):
            return {"reviewed_pdf_sha256": sha, "reviewed_pages": list(range(1, npages + 1)),
                    "expected_pages": npages, "coverage_complete": True,
                    "page_findings": findings or [], "verdict": "PASS"}

        # T100 SHA 对齐但缺 page_visual_review.json -> FAIL
        _td, tws, _sha = _visual_ws(3)
        try:
            results.append(report("T100", "评审材料缺逐页裁决 FAIL", False,
                                  run([SCRIPTS / "visual_review_gate.py", "--workspace", tws, "--strict"])))
        finally:
            _td.cleanup()

        # T100.good 完整视觉执行闭环 -> PASS
        _td, tws, sha = _visual_ws(3)
        try:
            json_write(tws / "reports" / "page_visual_review.json", _pr_ok(sha, 3))
            results.append(report("T100.good", "视觉执行闭环 PASS", True,
                                  run([SCRIPTS / "visual_review_gate.py", "--workspace", tws, "--strict"])))
        finally:
            _td.cleanup()

        # T101 reviewed_pages 未覆盖 expected_pages -> FAIL
        _td, tws, sha = _visual_ws(5)
        try:
            pr = _pr_ok(sha, 5)
            pr["reviewed_pages"] = [1, 2, 3]
            json_write(tws / "reports" / "page_visual_review.json", pr)
            results.append(report("T101", "逐页覆盖缺页 FAIL", False,
                                  run([SCRIPTS / "visual_review_gate.py", "--workspace", tws, "--strict"])))
        finally:
            _td.cleanup()

        # T102 未关闭 BLOCKER（veto 不被总分平均）-> FAIL
        _td, tws, sha = _visual_ws(3)
        try:
            pr = _pr_ok(sha, 3, findings=[{"page": 2, "type": "orphan_text_spill",
                                           "severity": "BLOCKER", "evidence": "关键词尾部溢出"}])
            json_write(tws / "reports" / "page_visual_review.json", pr)
            results.append(report("T102", "未关闭视觉 BLOCKER 否决 FAIL", False,
                                  run([SCRIPTS / "visual_review_gate.py", "--workspace", tws, "--strict"])))
        finally:
            _td.cleanup()

        # T102.good BLOCKER 带 resolution -> PASS
        _td, tws, sha = _visual_ws(3)
        try:
            pr = _pr_ok(sha, 3, findings=[{"page": 2, "type": "orphan_text_spill",
                                           "severity": "BLOCKER", "evidence": "...",
                                           "resolution": "关键词压缩回第 1 页（sections/0_abstract.tex L42）",
                                           "post_fix_review": {"reviewed_pdf_sha256": sha}}])
            json_write(tws / "reports" / "page_visual_review.json", pr)
            results.append(report("T102.good", "BLOCKER 已关闭 PASS", True,
                                  run([SCRIPTS / "visual_review_gate.py", "--workspace", tws, "--strict"])))
        finally:
            _td.cleanup()

        # T103 6verity 执行席位用"创新席"且无视觉席 -> roster drift FAIL
        repo = Path(tempfile.mkdtemp())
        try:
            shutil.copy2(Path(__file__).resolve().parents[3] / "workflow_spec.yaml",
                         repo / "workflow_spec.yaml")
            (repo / "skills" / "6verity").mkdir(parents=True, exist_ok=True)
            (repo / "skills" / "6verity" / "SKILL.md").write_text(
                "# 6verity\n\n三席盲评：①通审席 ②正确性与可复现席 ③创新与决策效用席（seat3_innovation）。\n",
                encoding="utf-8")
            _td, tws, sha = _visual_ws(3)
            try:
                json_write(tws / "reports" / "visual_review.json", {"reviewed_pdf_sha256": sha})
                json_write(tws / "reports" / "page_visual_review.json", _pr_ok(sha, 3))
                results.append(report("T103", "roster 视觉席漂移 FAIL", False,
                                      run([SCRIPTS / "visual_review_gate.py", "--workspace", tws,
                                           "--root", str(repo), "--strict"])))
            finally:
                _td.cleanup()
        finally:
            import shutil as _sh
            _sh.rmtree(repo, ignore_errors=True)

        # T103.good 真实仓库 roster 一致 -> PASS
        _td, tws, sha = _visual_ws(3)
        try:
            json_write(tws / "reports" / "visual_review.json", {"reviewed_pdf_sha256": sha})
            json_write(tws / "reports" / "page_visual_review.json", _pr_ok(sha, 3))
            results.append(report("T103.good", "roster 与 workflow_spec 一致 PASS", True,
                                  run([SCRIPTS / "visual_review_gate.py", "--workspace", tws,
                                       "--root", str(Path(__file__).resolve().parents[3]),
                                       "--strict"])))
        finally:
            _td.cleanup()
    except ImportError:
        print("[SKIP] T100-T103 缺少 PyMuPDF")

    # ============ v4.3 scientific figure system regression（T90-T94，任务书 v4.3 §25-27） ============

    def _fig_spec_ws(manifest_pri="primary", spec=None, with_code=None):
        _td = tempfile.TemporaryDirectory()
        tws = Path(_td.name)
        (tws / "figures" / "specs").mkdir(parents=True)
        json_write(tws / "figures" / "figure_manifest.json",
                   [{"id": "fig_q1", "visual_priority": manifest_pri,
                     "files": ["figures/fig_q1.pdf"], "status": "approved"}])
        if spec is not None:
            json_write(tws / "figures" / "specs" / "fig_q1.figure.json", spec)
        if with_code is not None:
            (tws / "code").mkdir(exist_ok=True)
            (tws / "code" / "make_figures.py").write_text(with_code, encoding="utf-8")
        return _td, tws

    _SPEC_OK = {"figure_id": "fig_q1", "claim_id": "Q1.PRIMARY", "figure_role": "primary",
                "evidence_type": "longitudinal_effect", "renderer": "python_matplotlib",
                "layout": {"grid_columns": 12, "panels": [{"id": "A", "role": "primary", "colspan": 7}]},
                "visual_encoding": {"primary": "strong_color_dark_blue",
                                    "comparators": "gray", "baseline": "light_gray_dashed"},
                "label_budget": 8, "final_width_mm": 170}

    # T90 primary 图缺 FIGURE_SPEC -> FAIL
    _td, tws = _fig_spec_ws()
    try:
        results.append(report("T90", "primary 图缺 FIGURE_SPEC FAIL", False,
                              run([SCRIPTS / "figure_spec_gate.py", "--workspace", tws, "--strict"])))
    finally:
        _td.cleanup()

    # T90.good 完整 FIGURE_SPEC -> PASS
    _td, tws = _fig_spec_ws(spec=_SPEC_OK)
    try:
        results.append(report("T90.good", "FIGURE_SPEC 齐全 PASS", True,
                              run([SCRIPTS / "figure_spec_gate.py", "--workspace", tws, "--strict"])))
    finally:
        _td.cleanup()

    # T92 primary/comparators 等权重彩色 -> WARN（exit 0，report 断言）
    _td, tws = _fig_spec_ws()
    try:
        spec = dict(_SPEC_OK)
        spec["visual_encoding"] = {"primary": "blue", "comparators": ["orange", "green"],
                                   "baseline": "purple_dashed"}
        json_write(tws / "figures" / "specs" / "fig_q1.figure.json", spec)
        proc = run([SCRIPTS / "figure_spec_gate.py", "--workspace", tws, "--strict"])
        rec = json.loads((tws / "reports" / "gates" / "figure_spec_gate.json").read_text(encoding="utf-8"))
        triggered = any(c.get("level") == "WARN" and "语义层级" in c.get("message", "")
                        for c in rec["findings"])
        results.append(report("T92", "等权重彩色编码 WARN", triggered, proc,
                              "" if triggered else "语义层级 WARN 未触发"))
    finally:
        _td.cleanup()

    # T93 renderer=r_ggplot2 且缺 renv.lock -> FAIL
    _td, tws = _fig_spec_ws()
    try:
        spec = dict(_SPEC_OK)
        spec["renderer"] = "r_ggplot2"
        json_write(tws / "figures" / "specs" / "fig_q1.figure.json", spec)
        results.append(report("T93", "r_ggplot2 缺 renv.lock FAIL", False,
                              run([SCRIPTS / "figure_spec_gate.py", "--workspace", tws, "--strict"])))
    finally:
        _td.cleanup()

    # T93.good 有 renv.lock -> PASS
    _td, tws = _fig_spec_ws()
    try:
        spec = dict(_SPEC_OK)
        spec["renderer"] = "r_ggplot2"
        json_write(tws / "figures" / "specs" / "fig_q1.figure.json", spec)
        (tws / "renv.lock").write_text("{}", encoding="utf-8")
        results.append(report("T93.good", "renv.lock 可复现 PASS", True,
                              run([SCRIPTS / "figure_spec_gate.py", "--workspace", tws, "--strict"])))
    finally:
        _td.cleanup()

    # T94 脚本引用本机字体绝对路径 -> FAIL
    _td, tws = _fig_spec_ws(with_code='font_manager.addfont(r"C:\\Users\\Administrator\\AppData\\Fonts\\simsun.ttf")\n')
    try:
        results.append(report("T94", "本机字体绝对路径 FAIL", False,
                              run([SCRIPTS / "figure_spec_gate.py", "--workspace", tws, "--strict"])))
    finally:
        _td.cleanup()

    # ============ v4.3 support registry regression（T82-T89，任务书 v4.3 §10/P0-07） ============

    def _support_ws(zip_files, paper_tex="", workspace_files=None):
        _td = tempfile.TemporaryDirectory()
        tws = Path(_td.name)
        if workspace_files:
            for rel, content in workspace_files.items():
                p = tws / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")
        (tws / "paper").mkdir(exist_ok=True)
        (tws / "paper" / "main.tex").write_text(paper_tex or "支撑材料见附录 A。\n",
                                                encoding="utf-8")
        make_support_zip(tws, zip_files)
        return _td, tws

    # T82 data_sources.md 写旧 6 篇 / 文献数漂移 -> FAIL
    _td, tws = _support_ws({
        "README.md": "# 运行说明\n", "requirements.txt": "pandas\n",
        "references/literature.md": "\n".join(
            "| ref{} | x |".format(i) for i in range(1, 9)),
        "references/data_sources.md": "方法学文献见 literature.md（6 篇：Chiu2008/Zhou2015/Kinnings2015/Luo2026/Chawla2002/Wang2025）。\n",
    })
    try:
        results.append(report("T82", "data_sources 文献漂移 FAIL", False,
                              run([SCRIPTS / "submission_package_gate.py", "--workspace", tws, "--check"])))
    finally:
        _td.cleanup()

    # T82.good data_sources 指向唯一登记源 -> PASS
    _td, tws = _support_ws({
        "README.md": "# 运行说明\n", "requirements.txt": "pandas\n",
        "references/literature.md": "\n".join("| ref{} | x |".format(i) for i in range(1, 9)),
        "references/data_sources.md": "方法学文献见 references/literature.md（唯一文献登记源）。\n",
    })
    try:
        results.append(report("T82.good", "data_sources 唯一登记源 PASS", True,
                              run([SCRIPTS / "submission_package_gate.py", "--workspace", tws, "--check"])))
    finally:
        _td.cleanup()

    # T83 论文附录声明未覆盖包内实际类别 -> FAIL
    _td, tws = _support_ws({
        "README.md": "# 运行说明\n", "requirements.txt": "pandas\n", "run_all.py": "print(1)\n",
        "code/utils.py": "x\n", "results/r.json": "{}", "figures/f.pdf": "f",
        "styles/mpl_paper_style.py": "x\n", "repro/VERIFY_SUMMARY.json": "{}",
    }, paper_tex="支撑材料包含 code/*.py、results/*.json。\n")
    try:
        results.append(report("T83", "附录声明未覆盖包内类别 FAIL", False,
                              run([SCRIPTS / "submission_package_gate.py", "--workspace", tws, "--check"])))
    finally:
        _td.cleanup()

    # T84 README "以预置值为准" -> FAIL
    _td, tws = _support_ws({
        "README.md": "若重跑与预置值不一致，说明环境差异，以预置值为准比对差异。\n",
        "requirements.txt": "pandas\n",
    })
    try:
        results.append(report("T84", "README 预置值语义错误 FAIL", False,
                              run([SCRIPTS / "submission_package_gate.py", "--workspace", tws, "--check"])))
    finally:
        _td.cleanup()

    # T85 VERIFY_SUMMARY 有 WARN 但缺 warning_ledger -> FAIL
    _td, tws = _support_ws({
        "README.md": "# 运行说明\n", "requirements.txt": "pandas\n",
        "repro/VERIFY_SUMMARY.json": json.dumps({"warns": 3, "fails": 0, "paper_pages": 28}),
    })
    try:
        results.append(report("T85", "WARN 无 ledger FAIL", False,
                              run([SCRIPTS / "submission_package_gate.py", "--workspace", tws, "--check"])))
    finally:
        _td.cleanup()

    # T85.good ledger 存在且无 open P0/P1 -> PASS
    _td, tws = _support_ws({
        "README.md": "# 运行说明\n", "requirements.txt": "pandas\n",
        "repro/VERIFY_SUMMARY.json": json.dumps({"warns": 2, "fails": 0}),
        "repro/warning_ledger.json": json.dumps({"warnings": [
            {"id": "layout_w01", "gate": "layout", "message": "x", "status": "fixed", "reason": "修"}]}),
    })
    try:
        results.append(report("T85.good", "WARN ledger 已关 PASS", True,
                              run([SCRIPTS / "submission_package_gate.py", "--workspace", tws, "--check"])))
    finally:
        _td.cleanup()

    # T86 README 声称完整复现但 reproduction_level != full -> FAIL
    _td, tws = _support_ws({
        "README.md": "本包可完整复现论文全部数值与图。\n",
        "requirements.txt": "pandas\n",
        "repro/VERIFY_SUMMARY.json": json.dumps({"reproduction_level": "smoke_min"}),
    })
    try:
        results.append(report("T86", "smoke_min 声称 full FAIL", False,
                              run([SCRIPTS / "submission_package_gate.py", "--workspace", tws, "--check"])))
    finally:
        _td.cleanup()

    # T87 repro/FINAL_MODEL_SPEC 与 authority 不一致 -> FAIL
    _td, tws = _support_ws({
        "README.md": "# 运行说明\n", "requirements.txt": "pandas\n",
        "repro/FINAL_MODEL_SPEC.json": json.dumps({"schema_version": 2, "v": 1}),
        "reports/FINAL_MODEL_SPEC.json": json.dumps({"schema_version": 2, "v": 2}),
    })
    try:
        results.append(report("T87", "spec 双份漂移 FAIL", False,
                              run([SCRIPTS / "submission_package_gate.py", "--workspace", tws, "--check"])))
    finally:
        _td.cleanup()

    # T88 VERIFY_SUMMARY.paper_pages 空但含 PDF -> FAIL
    _td, tws = _support_ws({
        "README.md": "# 运行说明\n", "requirements.txt": "pandas\n",
        "paper/main.pdf": "x",
        "repro/VERIFY_SUMMARY.json": json.dumps({"paper_pages": None, "fails": 0}),
    })
    try:
        results.append(report("T88", "paper_pages 缺失 FAIL", False,
                              run([SCRIPTS / "submission_package_gate.py", "--workspace", tws, "--check"])))
    finally:
        _td.cleanup()

    # T89 AI 报告声称全绑定但 registry 有未绑定 authority -> FAIL
    try:
        import fitz as _fitz
        _td, tws = _support_ws({
            "README.md": "# 运行说明\n", "requirements.txt": "pandas\n",
            "results/RESULT_REGISTRY.json": json.dumps({"artifacts": [
                {"file": "results/p4_best.json", "role": "paper_authority",
                 "requires_model_spec_binding": True}]}),
            "results/p4_best.json": json.dumps({"auprc": 0.456}),
            "AI 工具使用详情.pdf": None,
        })
        try:
            (tws / "提交").mkdir(exist_ok=True)
            with _fitz.open() as d:
                pg = d.new_page()
                pg.insert_text((72, 100), "All results bound to model_spec_sha256.",
                               fontsize=10)
                d.save(str(tws / "提交" / "ai_tmp.pdf"))
            import zipfile as _zf
            with _zf.ZipFile(tws / "提交" / "支撑材料.zip", "a") as z:
                z.write(tws / "提交" / "ai_tmp.pdf", "AI 工具使用详情.pdf")
            results.append(report("T89", "AI 报告声称与事实矛盾 FAIL", False,
                                  run([SCRIPTS / "submission_package_gate.py", "--workspace", tws, "--check"])))
        finally:
            _td.cleanup()
    except ImportError:
        print("[SKIP] T89 缺少 PyMuPDF")


    n_fail = sum(1 for ok in results if not ok)
    suffix = f"（{len(skipped)} 项跳过：{'、'.join(skipped)}）" if skipped else ""
    print(f"\nRESULT: {len(results) - n_fail}/{len(results)} 通过{suffix}")
    return 1 if n_fail else 0

if __name__ == "__main__":
    sys.exit(main())
