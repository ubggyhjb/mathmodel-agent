#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""project_manifest.py — 项目工件清单（引擎无关单一事实源）初始化与校验。

三份清单（均不依赖 git）：
  project.manifest.json       声明的引擎(latex|typst|word)、入口、题目数、
                              route.requested/actual、hil_policy、工具路径/版本。
                              未知一律写 "unknown"，绝不编造。
  artifact_manifest.json      输入/输出工件 SHA256 快照
                              (results/ figures/ paper 源码 = 输入；paper/main.pdf 等 = 输出)。
  state/runtime_manifest.json 门禁运行记录（由 run_all_gates.py 更新；本脚本只校验结构）。

用法：
  python project_manifest.py --workspace <项目根> --init
      缺失则创建三份清单（已存在的字段不覆盖）；自动探测 engine/entry 并记录工具版本
  python project_manifest.py --workspace <项目根> --refresh
      重算工具版本与工件哈希，保留 --set 已声明的字段
  python project_manifest.py --workspace <项目根> --check
      校验结构 + 工件哈希与磁盘一致性（漂移 = FAIL）
  python project_manifest.py --workspace <项目根> --set engine=latex --set hil_policy=interactive
      写/改声明字段（校验取值；首次自动 --init）

退出码：0 PASS / 1 FAIL / 2 环境或参数错误。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import gate_common as gc

VALID_ENGINES = {"latex", "typst", "word"}
VALID_HIL = {"interactive", "auto", "disabled"}


def detect_engine_entry(ws: Path):
    paper = ws / "paper"
    for eng, names in (("latex", ("main.tex",)), ("typst", ("main.typ",)),
                       ("word", ("main.docx", "main.doc"))):
        for n in names:
            if (paper / n).is_file():
                return eng, f"paper/{n}"
    return "unknown", "unknown"


def blank_manifest(ws: Path) -> dict:
    engine, entry = detect_engine_entry(ws)
    return {
        "schema_version": gc.SCHEMA_VERSION,
        "workspace": str(ws),
        "problem": "unknown",
        "engine": engine,
        "entry": entry,
        "problem_count": "unknown",
        "route": {"requested": "unknown", "actual": "unknown"},
        "hil_policy": "interactive",
        "tools": gc.detect_all_tools(),
        "updated_at": gc.iso_now(),
    }


def compute_artifacts(ws: Path) -> dict:
    paper_pdf = None
    outputs = {}
    for cand in (ws / "paper" / "main.pdf", ws / "paper" / "main.typ.pdf"):
        if cand.is_file():
            paper_pdf = cand
            break
    if paper_pdf is None:
        # word 输出或自定义入口：尽力找
        for p in sorted((ws / "paper").glob("*.pdf")) if (ws / "paper").is_dir() else []:
            paper_pdf = p
            break
    if paper_pdf is not None:
        st = paper_pdf.stat()
        outputs[paper_pdf.relative_to(ws).as_posix()] = {
            "path": paper_pdf.relative_to(ws).as_posix(),
            "sha256": gc.sha256_file(paper_pdf),
            "size": st.st_size,
            "mtime": st.st_mtime,
        }
    return {
        "schema_version": gc.SCHEMA_VERSION,
        "workspace": str(ws),
        "generated_at": gc.iso_now(),
        "inputs": {
            "results": gc.dir_snapshot(ws / "results", {".json", ".csv", ".xlsx"}),
            "figures": gc.dir_snapshot(ws / "figures", {".pdf", ".png", ".jpg", ".svg", ".drawio"}),
            "paper_src": gc.dir_snapshot(ws / "paper", {".tex", ".typ", ".bib", ".md"}),
        },
        "outputs": outputs,
    }


def set_field(doc: dict, key: str, value: str) -> tuple[bool, str]:
    if key == "engine":
        v = value.strip().lower()
        if v not in VALID_ENGINES:
            return False, f"engine 取值非法: {value}（允许 {sorted(VALID_ENGINES)}）"
        doc["engine"] = v
        return True, ""
    if key == "entry":
        doc["entry"] = value.strip()
        return True, ""
    if key == "problem":
        doc["problem"] = value.strip()
        return True, ""
    if key == "problems":
        doc["problem_count"] = value.strip()
        return True, ""
    if key == "hil_policy":
        v = value.strip().lower()
        if v not in VALID_HIL:
            return False, f"hil_policy 取值非法: {value}（允许 {sorted(VALID_HIL)}）"
        doc["hil_policy"] = v
        return True, ""
    if key in ("route.requested", "route.actual"):
        doc.setdefault("route", {})[key.split(".")[1]] = value.strip()
        return True, ""
    return False, f"不支持的 key: {key}"


def check_manifest(ws: Path, verbose=True) -> list:
    problems = []
    doc = gc.load_manifest(ws)
    if not doc:
        return ["project.manifest.json 缺失或无法解析"]
    if doc.get("engine") not in VALID_ENGINES:
        problems.append(f"engine 未声明或非法: {doc.get('engine')}（先 --set engine=latex|typst|word）")
    if not doc.get("entry") or doc.get("entry") == "unknown":
        problems.append("entry 未声明")
    if doc.get("hil_policy") not in VALID_HIL:
        problems.append(f"hil_policy 非法: {doc.get('hil_policy')}")
    for k in ("schema_version", "workspace", "problem_count"):
        if k not in doc:
            problems.append(f"project.manifest.json 缺字段 {k}")
    return problems


def check_artifacts(ws: Path, verbose=True) -> list:
    problems = []
    doc = gc.load_json(gc.artifact_path(ws), {})
    if not doc:
        return ["artifact_manifest.json 缺失或无法解析（先 --init/--refresh）"]
    for group in ("results", "figures", "paper_src"):
        want = doc.get("inputs", {}).get(group, {})
        directory = "paper" if group == "paper_src" else group
        exts = {".json", ".csv", ".xlsx"} if group == "results" else (
            {".pdf", ".png", ".jpg", ".svg", ".drawio"} if group == "figures" else
            {".tex", ".typ", ".bib", ".md"})
        cur = gc.dir_snapshot(ws / directory, exts)
        if want.get("sha256") != cur.get("sha256"):
            problems.append(
                f"工件漂移: {directory}/ 与 artifact_manifest.json 快照不一致（文件被改未 --refresh）")
    for rel, meta in (doc.get("outputs") or {}).items():
        p = ws / (meta.get("path") or rel)
        if not p.is_file():
            problems.append(f"输出缺失: {meta.get('path') or rel}")
        elif gc.sha256_file(p) != meta.get("sha256"):
            problems.append(f"输出漂移: {meta.get('path') or rel} 内容与清单哈希不一致（改后未重编译/未刷新）")
    return problems


def check_runtime(ws: Path) -> list:
    problems = []
    doc = gc.load_json(gc.runtime_path(ws), {})
    if not doc:
        return ["state/runtime_manifest.json 缺失（先 run_all_gates.py 或 --init）"]
    if doc.get("schema_version") != gc.SCHEMA_VERSION:
        problems.append("runtime_manifest schema_version 不匹配")
    if doc.get("workspace") != str(ws):
        problems.append("runtime_manifest workspace 与当前工作区不一致")
    return problems


def main(argv=None):
    gc.force_utf8()
    ap = argparse.ArgumentParser(description="项目工件清单初始化与校验")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--set", action="append", default=[], metavar="K=V")
    args = ap.parse_args(argv)

    ws = Path(args.workspace).resolve()
    if not ws.is_dir():
        print(f"FAIL 工作区不存在: {ws}")
        return 2

    mp, apath, rp = gc.manifest_path(ws), gc.artifact_path(ws), gc.runtime_path(ws)
    if args.init:
        if not mp.is_file():
            gc.save_json(mp, blank_manifest(ws))
        else:
            doc = gc.load_json(mp, {})
            if not doc:
                return 1
            doc.setdefault("tools", gc.detect_all_tools())
            doc.setdefault("route", {"requested": "unknown", "actual": "unknown"})
            doc.setdefault("hil_policy", "interactive")
            doc["updated_at"] = gc.iso_now()
            gc.save_json(mp, doc)
        if not apath.is_file():
            gc.save_json(apath, compute_artifacts(ws))
        if not rp.is_file():
            gc.save_json(rp, {"schema_version": gc.SCHEMA_VERSION, "workspace": str(ws),
                              "engine": gc.manifest_engine(ws), "gates": {}, "last_run": None,
                              "snapshot": {}})
        print(f"PASS manifest 初始化完成: {mp}")
        print(f"     artifact: {apath}")
        print(f"     runtime : {rp}")
        return 0

    if args.refresh:
        doc = gc.load_json(mp, {}) if mp.is_file() else blank_manifest(ws)
        doc["tools"] = gc.detect_all_tools()
        doc["workspace"] = str(ws)
        if doc.get("engine") == "unknown":
            doc["engine"], doc["entry"] = detect_engine_entry(ws)
        doc["updated_at"] = gc.iso_now()
        gc.save_json(mp, doc)
        gc.save_json(apath, compute_artifacts(ws))
        print("PASS manifest 已刷新（工具版本 + 工件哈希）")
        return 0

    if args.set:
        doc = gc.load_json(mp, {}) if mp.is_file() else blank_manifest(ws)
        for kv in args.set:
            if "=" not in kv:
                print(f"FAIL --set 需要 K=V: {kv}")
                return 2
            k, v = kv.split("=", 1)
            ok, err = set_field(doc, k, v)
            if not ok:
                print(f"FAIL {err}")
                return 1
        doc["updated_at"] = gc.iso_now()
        gc.save_json(mp, doc)
        print(f"PASS manifest 已更新: {', '.join(args.set)}")
        return 0

    if args.check:
        problems = check_manifest(ws) + check_artifacts(ws) + check_runtime(ws)
        if problems:
            print("FAIL 清单校验未通过:")
            for p in problems:
                print("  -", p)
            return 1
        print("RESULT: PASS（项目清单结构 + 工件哈希一致）")
        return 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
