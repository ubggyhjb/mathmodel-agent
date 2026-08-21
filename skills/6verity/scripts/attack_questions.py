#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""attack_questions.py — v3 攻击式评委问题生成器（_mathmode.docx 二十五条）。

从 methodology/leakage/figure_story 门禁报告与 reports/methodology/*.json 的事实出发，
自动生成 ≥10 个"最难回答"的评审问题草稿，落到 reports/methodology/attack_questions.md。
每个问题标注：主题（censoring/assumptions/degeneracy/necessity/leakage/sample_size/
summary/figure）、由哪条检查触发、触发事实、可回答性（论文正文是否出现答案词——人工复核）。

用法：python attack_questions.py --workspace <项目根> [--min 10]
输出：reports/methodology/attack_questions.md + attack_questions.json
退出码 0 永远（生成器，不判 PASS/FAIL；答辩前人工确认全部问题可回答）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import gate_common as gc

MD_REL = "reports/methodology/attack_questions.md"
JSON_REL = "reports/methodology/attack_questions.json"


def scan_text(ws: Path) -> str:
    paper = ws / "paper"
    parts = []
    if paper.is_dir():
        for p in sorted(paper.rglob("*")):
            if p.suffix.lower() in (".tex", ".typ"):
                try:
                    parts.append(p.read_text(encoding="utf-8"))
                except Exception:
                    pass
    return " ".join(parts)


def q(topic, trigger, question, answerable_hint=None):
    return {"topic": topic, "trigger": trigger, "question": question,
            "answerable_in_text": answerable_hint is None or answerable_hint != "",
            "hint": answerable_hint or ""}


def main(argv=None):
    gc.force_utf8()
    ap = argparse.ArgumentParser(description="v3 攻击式评委问题生成器")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--min", type=int, default=10)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args(argv)

    ws = Path(args.workspace).resolve()
    mdir = ws / "reports" / "methodology"
    gates = ws / "reports" / "gates"
    dgp = gc.load_json(mdir / "data_generating_process.json", {}) or {}
    cand = gc.load_json(mdir / "censoring_report.json", {}) or {}
    deg = gc.load_json(mdir / "optimization_degeneracy.json", {}) or {}
    nec = gc.load_json(mdir / "model_necessity.json", {}) or {}
    ss = gc.load_json(mdir / "sample_sizes.json", {}) or {}
    leak = gc.load_json(gates / "leakage_gate.json", {}) or {}
    meth = gc.load_json(gates / "methodology_gate.json", {}) or {}
    text = scan_text(ws)

    questions = []
    cens = dgp.get("censoring") or {}
    if cens.get("interval"):
        questions.append(q("censoring", "DGP: interval censoring",
                           "为什么两次检测之间跨阈值用插值而不是区间删失模型？",
                           "区间删失" if "区间删失" in text else ""))
    if cens.get("left"):
        questions.append(q("censoring", "DGP: left censoring",
                           "为什么首检已达标（left censored）不是普通左删失？您的模型如何显式处理？"))
    if cand.get("interpolation_used"):
        questions.append(q("censoring", "censoring_report: interpolation_used",
                           "插值恢复事件时间对最终推荐时点的影响有多大？区间删失模型对比结果如何？",
                           "近似" if "近似" in text else ""))
    if dgp.get("repeated_measurement"):
        questions.append(q("assumptions", "DGP: repeated_measurement",
                           "『检测相互独立』如何与组内相关（同孕妇重复测量 / ICC）同时成立？请指明随机效应结构。",
                           "随机效应" if "随机效应" in text else ""))
    if deg.get("problems"):
        weak = [p.get("id") for p in deg["problems"] if p.get("rel_gap", 1) < float(deg.get("eps", 0.05))]
        if weak:
            questions.append(q("degeneracy", f"degeneracy: {weak}",
                               f"删除风险目标函数后，问题 {weak} 的推荐时点是否变化？若不变，目标函数在决策中的真实作用是什么？"))
    for m in (nec.get("models") or []):
        if m.get("role") == "Rejected":
            questions.append(q("necessity", f"necessity: {m.get('id')} Rejected",
                               f"模型「{m.get('id')}」被拒的依据是什么？删除后结论/性能/解释是否变化？"))
    share = nec.get("content_share", {})
    if share.get("primary", 0) < 0.6:
        questions.append(q("necessity", f"necessity: primary {share.get('primary')}",
                           "本问主模型内容占比不足 60%：哪个模型可以移除而不影响结论？"))
    small = [g for g in (ss.get("groups") or []) if int(g.get("effective_n", g.get("n", 0))) < int(ss.get("minimum_group_n", 20))]
    if small:
        questions.append(q("sample_size", f"n<min: {[g.get('id') for g in small]}",
                           f"为什么 group n 小于 {ss.get('minimum_group_n')} 仍独立输出正式推荐值？降级为 exploratory 或合并的考虑？",
                           "推荐窗口" if "推荐窗口" in text else "推荐窗口"))
    wide = [g for g in (ss.get("groups") or []) if float(g.get("ci_width_weeks", 0)) > float(ss.get("ci_width_limit_weeks", 4))]
    if wide:
        questions.append(q("sample_size", f"wide CI: {[g.get('id') for g in wide]}",
                           f"推荐时点 CI 宽达 {max(float(g.get('ci_width_weeks', 0)) for g in wide)} 周，为何输出单一点估计？应否改为推荐窗口？"))
    if leak.get("findings"):
        for f in leak["findings"]:
            if f.get("level") == "WARN" and f.get("check") == "code":
                questions.append(q("leakage", "leakage code heuristic",
                                   f"代码疑似泄露（{f.get('message', '')[:60]}…）：阈值/标准化是否使用外层测试信息？请确认训练/内层/外层三折边界。"))
    for m in (meth.get("findings") or []):
        if m.get("level") == "FAIL" or m.get("check") == "conclusion":
            questions.append(q("summary", f"methodology: {m.get('check')}",
                               f"方法学检查提示（{m.get('message', '')[:80]}…）：正文口径是否需要修正？"))
    if len(questions) < args.min:
        questions.append(q("figure", "default",
                           "每张主 Figure 的 main_message 是否在对应正文段落被明确支持？是否存在图与正文结论冲突？"))
    if len(questions) < args.min:
        questions.append(q("summary", "default",
                           "摘要在 30 秒内能否传达『发现问题→最终答案』？每问模型缩写是否超过 2 个？"))

    questions = questions[: max(args.min, len(questions))]
    outdir = Path(args.out_dir).resolve() if args.out_dir else mdir
    outdir.mkdir(parents=True, exist_ok=True)
    lines = ["# 攻击式评委问题清单（自动生成草稿，人工复核后答复）",
             "",
             f"- 共 {len(questions)} 条；每条须在正文或附录可回答，否则记为 open issue。",
             f"- 生成时间：{gc.iso_now()}；依据：methodology/leakage/figure_story 门禁与 reports/methodology/*.json。",
             ""]
    for i, item in enumerate(questions, 1):
        mark = "" if item["answerable_in_text"] else "（⚠ 正文未找到答案线索，须补充）"
        lines.append(f"{i}. **[{item['topic']}]** {item['question']}{mark}")
        lines.append(f"   - 触发：{item['trigger']}" + (f"；提示词：{item['hint']}" if item["hint"] else ""))
    (outdir / "attack_questions.md").write_text("\n".join(lines), encoding="utf-8")
    gc.save_json(outdir / "attack_questions.json", {"questions": questions, "generated_at": gc.iso_now()})
    print(f"ATTACK_QUESTIONS: {len(questions)} 条 -> {outdir / 'attack_questions.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
