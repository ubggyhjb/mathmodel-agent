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
        (tws / "reports" / "figure_story_manifest.json").unlink()
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
        manifest = json.loads((tws / "reports" / "figure_story_manifest.json").read_text(encoding="utf-8"))
        manifest[0]["panels"] = [{"id": "B", "expected_marks": ["line:x", "line:y"],
                                  "min_artist_count": 3}]
        json_write(tws / "reports" / "figure_story_manifest.json", manifest)
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
        manifest = json.loads((tws / "reports" / "figure_story_manifest.json").read_text(encoding="utf-8"))
        manifest[0]["caption"] = "panel 为 M1/M2 的描述"
        json_write(tws / "reports" / "figure_story_manifest.json", manifest)
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
        manifest = json.loads((tws / "reports" / "figure_story_manifest.json").read_text(encoding="utf-8"))
        manifest = [
            {"id": "fig_q1", "main_message": "PR 曲线", "visual_priority": "primary",
             "files": ["figures/fig_q1.pdf"], "redundant_with": ["fig_q2"], "unique_information": "x",
             "keep_both_reason": ""},
            {"id": "fig_q2", "main_message": "PR 曲线（重复）", "visual_priority": "primary",
             "files": ["figures/fig_q2.pdf"], "redundant_with": ["fig_q1"], "unique_information": "x",
             "keep_both_reason": ""},
        ]
        json_write(tws / "reports" / "figure_story_manifest.json", manifest)
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

    n_fail = sum(1 for ok in results if not ok)
    suffix = f"（{len(skipped)} 项跳过：{'、'.join(skipped)}）" if skipped else ""
    print(f"\nRESULT: {len(results) - n_fail}/{len(results)} 通过{suffix}")
    return 1 if n_fail else 0

if __name__ == "__main__":
    sys.exit(main())
