#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_tests.py — v2 门禁回归测试。

覆盖历史事故与 v2 新增门（每个用例独立临时副本，跑完清理）：
  T01 trace  LaTeX 基线回归（真实项目 模型四\新稿，--strict 必须 PASS）
  T02 trace  Typst 引擎 fixture（tests/tmp_trace，--strict 必须 PASS）
  T03 trace  engine=word -> 明确 FAIL（退出 1）
  T04 layout_gate LaTeX 基线（新稿 --strict，允许 WARN，必须无 FAIL）
  T05 layout_gate engine=unknown + --strict -> FAIL
  T06 layout_gate 图源缺失 -> FAIL（改坏 A_code/章节副本）
  T07 style_audit 新稿基线 --strict -> PASS（允许 WARN）
  T08 style_audit 附录缺一源文件 -> FAIL（内容哈希门）
  T09 style_audit AI 声明改错定句 -> FAIL
  T10 check_decision_log freshness 过期 -> FAIL
  T11 verify_refs 编造文献 -> strict FAIL（离线时标 SKIP）
  T12 run_all_gates 新稿聚合（网络可用时跑，离线时 SKIP refs 门）
  T13 whitespace_qa 合成 PDF 大空带页 → strict FAIL（行带+空带口径，非纵向跨度）

用法：python run_tests.py [--workspace <真实项目>] [--skip-online]
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

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
    # T06 图源缺失（复制新稿 paper，删除某图的 pdf 与 png 两种源）
    if need_ws("T06", "layout_gate 图源缺失 FAIL"):
        with tempfile.TemporaryDirectory() as td:
            tws = Path(td)
            shutil.copytree(ws / "paper", tws / "paper")
            shutil.copytree(ws / "figures", tws / "figures")
            shutil.copy2(ws / "project.manifest.json", tws / "project.manifest.json")
            for name in ("fig_network_mine1.pdf", "fig_network_mine1.png"):
                target = tws / "figures" / name
                if target.is_file():
                    target.unlink()
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

    # T12 聚合门（离线时 skip refs；v3 新门 methodology/leakage/figure_story 由 T14-T19 单独覆盖，
    # 待 C 题项目完成 v3 methodology 补全后启用全量聚合基线）
    if need_ws("T12", "run_all_gates 聚合"):
        skip_extra = "refs,methodology,leakage,figure_story" if args.skip_online else "methodology,leakage,figure_story"
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

    n_fail = sum(1 for ok in results if not ok)
    suffix = f"（{len(skipped)} 项跳过：{'、'.join(skipped)}）" if skipped else ""
    print(f"\nRESULT: {len(results) - n_fail}/{len(results)} 通过{suffix}")
    return 1 if n_fail else 0

if __name__ == "__main__":
    sys.exit(main())
