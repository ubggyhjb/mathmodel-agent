#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_decision_log.py — state/decision_log.json 结构校验与初始化。

用法:
  python check_decision_log.py --workspace <项目根> [--create]

检查项（任一不满足 → FAIL，退出码 1）:
  1. 文件存在且为合法 JSON 对象；
  2. 必需键齐全：problem / current_stage / stages / decisions / open_issues / last_updated；
  3. stages 恰好覆盖 6 个阶段，status 取值合法，且完成状态必须构成前缀
     （不允许前面还有未完成阶段时后面阶段已完成）；
  4. 除 1start-mathmodel 外，每个 done/skipped 的阶段至少有一条 stage 匹配的 decision；
  5. open_issues 每条的 status 必须为 closed（盲评问题清单未闭环 = FAIL）；
  6. current_stage 必须合法（6 个阶段之一或 "complete"）。
"""

import argparse
import json
import sys
from pathlib import Path

STAGES = ["1start-mathmodel", "2analysis-modeling", "3coding-visual",
          "4drawio", "5writing", "6verity"]
REQUIRED_DECISION_STAGES = [s for s in STAGES if s != "1start-mathmodel"]
VALID_STATUS = {"pending", "in_progress", "done", "skipped"}


def force_utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def template():
    from datetime import datetime
    return {
        "problem": "",
        "current_stage": "2analysis-modeling",
        "stages": {s: {"status": "done" if s == "1start-mathmodel" else "pending"}
                   for s in STAGES},
        "decisions": [],
        "open_issues": [],
        "last_updated": datetime.now().isoformat(timespec="seconds"),
    }


def validate(doc):
    errors = []
    if not isinstance(doc, dict):
        return ["根节点必须是 JSON 对象"]

    for key in ("problem", "current_stage", "stages", "decisions", "open_issues", "last_updated"):
        if key not in doc:
            errors.append(f"缺少必需键: {key}")

    stages = doc.get("stages")
    if isinstance(stages, dict):
        for s in STAGES:
            if s not in stages:
                errors.append(f"stages 缺少阶段: {s}")
        for s, v in stages.items():
            if s not in STAGES:
                errors.append(f"stages 出现未知阶段: {s}")
                continue
            if not isinstance(v, dict) or v.get("status") not in VALID_STATUS:
                errors.append(f"阶段 {s} 的 status 非法（应为 pending/in_progress/done/skipped）")
        seen_unfinished = False
        for s in STAGES:
            v = stages.get(s)
            status = v.get("status") if isinstance(v, dict) else None
            if status in ("pending", "in_progress"):
                seen_unfinished = True
            elif status in ("done", "skipped") and seen_unfinished:
                errors.append(f"阶段顺序异常: {s} 已完成，但前面的阶段还有未完成的")

    decisions = doc.get("decisions")
    if not isinstance(decisions, list):
        errors.append("decisions 必须是数组")
        decisions = []
    per_stage = {}
    for d in decisions:
        if not isinstance(d, dict):
            errors.append("decisions 存在非对象条目")
            continue
        if not d.get("id"):
            errors.append("decision 条目缺少 id")
        for f in ("stage", "decision", "reason"):
            if not d.get(f):
                errors.append(f"decision {d.get('id', '?')} 缺少 {f}")
        if d.get("stage") not in STAGES:
            errors.append(f"decision {d.get('id', '?')} 的 stage 非法: {d.get('stage')}")
        per_stage[d.get("stage")] = per_stage.get(d.get("stage"), 0) + 1
    if isinstance(stages, dict):
        for s in REQUIRED_DECISION_STAGES:
            v = stages.get(s)
            status = v.get("status") if isinstance(v, dict) else None
            if status in ("done", "skipped") and per_stage.get(s, 0) == 0:
                errors.append(f"阶段 {s} 状态为 {status}，但 decisions 中没有该阶段的决策记录")

    issues = doc.get("open_issues")
    if not isinstance(issues, list):
        errors.append("open_issues 必须是数组")
        issues = []
    for i in issues:
        if not isinstance(i, dict):
            errors.append("open_issues 存在非对象条目")
            continue
        for f in ("id", "source", "description", "status"):
            if not i.get(f):
                errors.append(f"open_issue {i.get('id', '?')} 缺少 {f}")
        if i.get("status") != "closed":
            errors.append(f"open_issue {i.get('id', '?')} 未闭环（status={i.get('status')}）："
                          "必须修复并置为 closed 才能 PASS")

    if doc.get("current_stage") not in STAGES + ["complete"]:
        errors.append(f"current_stage 非法: {doc.get('current_stage')}")
    return errors


def main(argv=None):
    force_utf8()
    ap = argparse.ArgumentParser(description="state/decision_log.json 校验与初始化")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--create", action="store_true", help="不存在时创建初始模板")
    args = ap.parse_args(argv)

    ws = Path(args.workspace).resolve()
    path = ws / "state" / "decision_log.json"

    if not path.is_file():
        if args.create:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(template(), ensure_ascii=False, indent=2),
                            encoding="utf-8")
            print(f"PASS（已初始化）创建模板: {path}")
            print("提示: 填入 problem 后，每完成一个阶段都要更新 stages/current_stage/decisions。")
            return 0
        print(f"FAIL 决策日志不存在: {path}（用 --create 初始化）")
        return 1

    try:
        doc = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        print(f"FAIL 决策日志不是合法 JSON: {path} ({exc})")
        return 1

    errors = validate(doc)
    if errors:
        print(f"FAIL {path}（{len(errors)} 个问题）:")
        for e in errors:
            print("  - " + e)
        return 1

    done = sum(1 for s in STAGES if doc["stages"][s].get("status") == "done")
    print(f"PASS 决策日志结构完整、问题清单已闭环。阶段完成: {done}/6，"
          f"当前阶段: {doc.get('current_stage')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
