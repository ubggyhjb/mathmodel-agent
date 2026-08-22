#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_common as gc
import workflow_spec as wfs
"""check_decision_log.py — state/decision_log.json 结构校验与初始化。

用法:
  python check_decision_log.py --workspace <项目根> [--create]

阶段列表（v4）：从仓库根 workflow_spec.yaml 单一事实源加载（workflow_spec.py），
不再手写顺序。decision_log 的 stages 键 = spec 中每阶段的 skill 名（如
brainstorm-mathmodel / 7methodology-review ...），并保留 1start-mathmodel 入口键。

检查项（任一不满足 → FAIL，退出码 1）:
  1. 文件存在且为合法 JSON 对象；
  2. 必需键齐全：problem / current_stage / stages / decisions / open_issues / last_updated；
  3. stages 覆盖全部 v4 核心阶段（brainstorm 可按旧项目兼容缺席），status 取值合法，
     且完成状态必须构成前缀（不允许前面还有未完成阶段时后面阶段已完成）；
  4. 除 1start-mathmodel 外，每个 done/skipped 的阶段至少有一条 stage 匹配的 decision；
  5. open_issues 每条的 status 必须为 closed（盲评问题清单未闭环 = FAIL）；
  6. current_stage 必须合法（任一阶段或 "complete"）。
"""


def _load_stages():
    """从 workflow_spec.yaml 加载阶段 skill 名列表（含 1start 入口键）。"""
    try:
        spec = wfs.load_spec(wfs.repo_root(Path(__file__).resolve().parent))
        skills = [str(s.get("skill", "")) for s in spec.get("stages", []) if s.get("skill")]
        if skills:
            return ["1start-mathmodel"] + skills
    except Exception:
        pass
    # 回退（spec 缺失时显式报错而非静默用旧顺序）
    raise RuntimeError("workflow_spec.yaml 无法加载：请检查仓库根目录的 workflow_spec.yaml（v4 单一事实源）")


STAGES = _load_stages()
REQUIRED_DECISION_STAGES = [s for s in STAGES if s != "1start-mathmodel"]
CORE_STAGES = [s for s in STAGES if s != "brainstorm-mathmodel"]
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
        "current_stage": "brainstorm-mathmodel",
        "stages": {s: {"status": "done" if s == "1start-mathmodel" else "pending"}
                   for s in STAGES},
        "decisions": [],
        "open_issues": [],
        "last_updated": gc.iso_now(),
    }


def validate(doc):
    errors = []
    if not isinstance(doc, dict):
        return ["根节点必须是 JSON 对象"]

    for key in ("problem", "current_stage", "stages", "decisions", "open_issues", "last_updated"):
        if key not in doc:
            errors.append(f"缺少必需键: {key}")

    stages = doc.get("stages")
    if isinstance(stages, dict) and "brainstorming" in stages:
        if "brainstorm-mathmodel" not in stages:
            stages["brainstorm-mathmodel"] = stages.pop("brainstorming")
        else:
            stages.pop("brainstorming", None)
    if isinstance(stages, dict):
        for s in CORE_STAGES:
            if s not in stages:
                errors.append(f"stages 缺少核心阶段: {s}")
        for s, v in stages.items():
            if s not in STAGES:
                errors.append(f"stages 出现未知阶段: {s}")
                continue
            if not isinstance(v, dict) or v.get("status") not in VALID_STATUS:
                errors.append(f"阶段 {s} 的 status 非法（应为 pending/in_progress/done/skipped）")
        seen_unfinished = False
        ordered_stages = STAGES if "brainstorm-mathmodel" in stages else CORE_STAGES
        for s in ordered_stages:
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
    for d in decisions:
        if isinstance(d, dict) and d.get("stage") == "brainstorming":
            d["stage"] = "brainstorm-mathmodel"
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
            if s == "brainstorm-mathmodel" and s not in stages:
                continue
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



def _files(ws, name):
    root = Path(ws) / name
    return [p for p in root.rglob("*") if p.is_file()] if root.is_dir() else []


def freshness_errors(ws, doc):
    try: stamp=dt.datetime.fromisoformat(str(doc.get("last_updated","")).replace("Z","+00:00")).timestamp()
    except Exception: return [], ["last_updated 无法解析，已跳过 freshness"]
    fs=[]
    for n in ("results","figures","paper"): fs += _files(ws,n)
    # 门禁报告（reports/gates/*.json）不参与 freshness：它们是决策日志更新后由
    # run_all_gates 写入的运行记录，与"阶段产物是否比决策新"无关（避免循环依赖）。
    if not fs:return [],["freshness: 未发现被检查目录文件"]
    p=max(fs,key=lambda x:x.stat().st_mtime); m=p.stat().st_mtime
    msg=f"freshness: 最新文件 {p.relative_to(ws)} @ {dt.datetime.fromtimestamp(m).astimezone().isoformat()}"
    return ([f"{msg}，last_updated 早于最新文件超过120秒"],[]) if stamp<m-120 else ([],[msg+"，PASS"])


def artifact_errors(ws, doc):
    errors=[];st=doc.get("stages",{})
    req={"1start-mathmodel":[ws/"plan.md",ws/"todo.md"],"brainstorm-mathmodel":[ws/"reports/BRAINSTORM_REPORT.md"],"2analysis-modeling":[ws/"reports/ANALYSIS_MODELING_REPORT.md"],"5writing":[ws/"paper/main.tex",ws/"paper/main.typ",ws/"paper/main.docx"],"6verity":[ws/"reports/VERIFY_REPORT.md"]}
    for s,ps in req.items():
        if st.get(s,{}).get("status")=="done" and not any(p.is_file() for p in ps): errors.append(f"阶段 {s} 缺少产物")
    if st.get("3coding-visual",{}).get("status")=="done":
        if not any(p.suffix.lower() in (".py",".m") for p in _files(ws,"code")):errors.append("阶段 3coding-visual 缺少 code/ 下 .py/.m")
        if not any(p.suffix.lower() in (".json",".csv",".xlsx") for p in _files(ws,"results")):errors.append("阶段 3coding-visual 缺少 results/ 下结果文件")
        if not (ws/"reports/RESULTS_REPORT.md").is_file():errors.append("阶段 3coding-visual 缺少 reports/RESULTS_REPORT.md")
    if st.get("4drawio",{}).get("status")=="done" and not (ws/"reports/DRAWIO_REPORT.md").is_file() and not any(p.suffix.lower() in (".drawio",".pdf") for p in _files(ws,"figures")):errors.append("阶段 4drawio 缺少产物")
    return errors


def artifact_errors(ws, doc):
    errors = []
    manifest = gc.load_json(gc.artifact_path(ws), None)
    if not isinstance(manifest, dict):
        return ["artifact_manifest.json 缺失或无法解析"]
    specs = {"results": ("results", {".json", ".csv", ".xlsx"}),
             "figures": ("figures", {".pdf", ".png", ".jpg", ".svg", ".drawio"}),
             "paper_src": ("paper", {".tex", ".typ", ".bib", ".md"})}
    for group, (directory, exts) in specs.items():
        expected = manifest.get("inputs", {}).get(group, {}).get("sha256")
        actual = gc.dir_snapshot(Path(ws) / directory, exts).get("sha256")
        if expected != actual:
            errors.append(f"工件漂移: {directory}/ 与 artifact_manifest.json 快照不一致")
    if doc.get("stages", {}).get("brainstorm-mathmodel", {}).get("status") == "done" and not (ws / "reports" / "BRAINSTORM_REPORT.md").is_file():
        errors.append("阶段 brainstorm-mathmodel 缺少 reports/BRAINSTORM_REPORT.md")
    # A completed stage must have tangible evidence.  Alternatives keep this
    # useful for projects that put analysis outputs in reports or results.
    stage_dirs = {"1start-mathmodel": ("state",), "brainstorm-mathmodel": ("reports",),
                  "2analysis-modeling": ("reports", "results"),
                  "3coding-visual": ("code", "results"), "4drawio": ("figures", "paper"),
                  "5writing": ("paper",), "6verity": ("reports",)}
    for stage, dirs in stage_dirs.items():
        if isinstance(doc.get("stages", {}).get(stage), dict) and doc["stages"][stage].get("status") == "done":
            if not any(_files(ws, d) for d in dirs):
                errors.append(f"阶段 {stage} 已 done，但没有可核验的阶段产物")
    return errors


def blind_closure_errors(ws, doc):
    """三席盲评销号链校验（reports/blind_scores.json 存在时才执行）。
    规则：三席终评必须齐全且各席 ≥70；每席终评 issues 列表中的每条问题必须
    在 decision_log.open_issues 登记且 status=closed、resolution 非空。"""
    path = Path(ws) / "reports" / "blind_scores.json"
    if not path.is_file():
        return [], ["blind_scores.json 不存在（三席盲评未执行或未落盘）"]
    try:
        b = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        return [f"blind_scores.json 无法解析: {exc}"], []
    scores = b.get("scores", []) if isinstance(b, dict) else []
    if not scores:
        return ["blind_scores.json 无席位记录"], []

    # 终评 = 每个 seat 的 trip 最大的条目
    seats_final = {}
    for s in scores:
        if not isinstance(s, dict):
            continue
        seat, trip = s.get("seat"), s.get("trip")
        if not seat or trip is None:
            continue
        cur = seats_final.get(seat)
        if cur is None or int(trip) >= int(cur.get("trip") or 0):
            seats_final[seat] = s

    errors, warnings = [], []
    # v4.3（§29B.1/T103）：席位名单以 workflow_spec.yaml final_review 为唯一事实源——
    # 新命名 seatA_modeling/seatB_statml/seatC_visual；旧命名兼容（历史项目不破坏）。
    SEATS_NEW = ("seatA_modeling", "seatB_statml", "seatC_visual")
    SEATS_OLD = ("seat1_overall", "seat2_correctness", "seat3_innovation")
    if all(x in seats_final for x in SEATS_NEW):
        missing = [x for x in SEATS_NEW if x not in seats_final]
        warnings.append("三席命名已迁移为 seatA/B/C（与 workflow_spec final_review 对齐）")
    elif all(x in seats_final for x in SEATS_OLD):
        missing = []
        warnings.append("blind_scores 仍用旧席位名（seat1/2/3_innovation）：建议迁移为 "
                        "seatA_modeling/seatB_statml/seatC_visual 并与 workflow_spec 一致——"
                        "旧名缺少独立视觉席（§29B.1）")
    else:
        missing = [x for x in SEATS_NEW if x not in seats_final] + \
                  [x for x in SEATS_OLD if x not in seats_final]
    if missing:
        errors.append(f"三席盲评缺席位（新名+旧名均不齐全）: {missing}")
    open_map = {}
    for i in doc.get("open_issues", []):
        open_map[str(i.get("id"))] = i
    for seat, s in seats_final.items():
        total = s.get("total")
        if not isinstance(total, (int, float)) or total < 70:
            errors.append(f"{seat} 终评总分 {total} < 70（不放行）")
        gate_text = str(s.get("gate") or "").strip()
        if total is not None and total >= 70 and gate_text and not gate_text.upper().startswith("PASS") \
                and not s.get("post_fix_gate"):
            warnings.append(f"{seat} 终评总分 {total}≥70 但 gate 非 PASS 且无 post_fix_gate 字段："
                            "修复完成后必须追加 post_fix_gate 说明最终判定（原 gate 字符串不得改写）")
        dims = s.get("dims") or {}
        if len(dims) != 8:
            warnings.append(f"{seat} 终评维度数 {len(dims)} != 8（完整 8 维才可对比）")
        for iss in (s.get("issues") or []):
            oi = open_map.get(str(iss))
            if oi is None:
                errors.append(f"{seat} 终评问题 {iss} 未在 decision_log.open_issues 登记")
            elif oi.get("status") != "closed":
                errors.append(f"{seat} 终评问题 {iss} 未 closed")
            elif not str(oi.get("resolution", "")).strip():
                warnings.append(f"{seat} 终评问题 {iss} 缺 resolution 销号证据")
    return errors, warnings


def main(argv=None):
    force_utf8()
    ap = argparse.ArgumentParser(description="state/decision_log.json 校验与初始化")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--create", action="store_true", help="不存在时创建初始模板")
    ap.add_argument("--no-freshness", action="store_true")
    ap.add_argument("--no-artifacts", action="store_true")
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
    warnings = []
    if not args.no_freshness:
        e, w = freshness_errors(ws, doc); errors.extend(e); warnings.extend(w)
    if not args.no_artifacts:
        errors.extend(artifact_errors(ws, doc))
    # 三席盲评销号链（有 blind_scores.json 才硬校验；无则 WARN 提示未执行）
    be, bw = blind_closure_errors(ws, doc)
    errors.extend(be); warnings.extend(bw)
    for w in warnings: print("WARN " + w)
    if errors:
        print(f"FAIL {path}（{len(errors)} 个问题）:")
        for e in errors:
            print("  - " + e)
        return 1

    present_stages = [s for s in STAGES if s in doc.get("stages", {})]
    done = sum(1 for s in present_stages if doc["stages"][s].get("status") == "done")
    print(f"PASS 决策日志结构完整、问题清单已闭环。阶段完成: {done}/{len(present_stages)}，"
          f"当前阶段: {doc.get('current_stage')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
