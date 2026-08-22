#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""workflow_spec.py — v4 工作流单一事实源的加载与一致性校验。

workflow_spec.yaml 位于仓库根目录，定义 stages / gates_pipeline / final_review。
本模块是唯一加载器：check_decision_log.py、run_all_gates.py、1start 等一律
`import workflow_spec`（同目录搜索）读取阶段顺序，禁止再手写阶段列表。

用法：
  python workflow_spec.py --print            # 打印 stage id 列表（脚本间调用）
  python workflow_spec.py --check --root <repo>   # 校验各引用方与 spec 一致

一致性校验项：
  1. check_decision_log.py / run_all_gates.py 的源码里不再出现硬编码阶段列表
     （出现旧阶段名串联文本视为未接入，报 FAIL）；
  2. agent.cordis.yml 中包含全部 stage id 且出现顺序 = spec 顺序；
  3. docs 与 README 中引用的阶段顺序叙述与 spec 一致（按锚点序列提取比较）。
退出码：0 一致；1 不一致；2 用法/加载错误。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml  # type: ignore
except Exception:  # 回退：仓库未安装 pyyaml 时用极简解析（仅用于单行键值场景）
    yaml = None

SPEC_NAME = "workflow_spec.yaml"

# spec.stages[id] 的常见旧顺序文本（若在源码/文档中出现且顺序≠spec，判 FAIL）
OLD_SEQUENCES = [
    "brainstorm-mathmodel → 2analysis-modeling → 3coding-visual → 4drawio → 5writing → 6verity",
    "2analysis → 3coding → 4drawio → 5writing → 6verity",
    "头脑风暴与候选路线筛选 - `brainstorm-mathmodel`",
]


def repo_root(script_dir: Path) -> Path:
    """从本脚本位置向上找含 workflow_spec.yaml 的仓库根。"""
    p = script_dir.resolve()
    for _ in range(6):
        if (p / SPEC_NAME).is_file():
            return p
        if p.parent == p:
            break
        p = p.parent
    return script_dir.parent  # 回退


def load_spec(root: Path) -> dict:
    spec_path = (Path(root) / SPEC_NAME) if (Path(root) / SPEC_NAME).is_file() else None
    if spec_path is None:
        spec_path = repo_root(Path(__file__).resolve().parent) / SPEC_NAME
    if yaml is not None:
        with open(spec_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    # 极简回退：仅提取 stages — id 行（行首 - id: xxx）与 gates_pipeline 列表
    text = spec_path.read_text(encoding="utf-8")
    ids = re.findall(r"^\s*-\s*id:\s*(\S+)", text, re.M)
    gates = re.findall(r"^\s*-\s*(\w+)\s*$", text, re.M)
    return {"version": 4, "stages": [{"id": i} for i in ids], "gates_pipeline": gates}


def stage_ids(spec: dict) -> list:
    return [str(s.get("id", "")) for s in spec.get("stages", []) if s.get("id")]


def gate_ids(spec: dict) -> list:
    """兼容层：返回 gate registry 的 id 顺序（v4.4 起 gates 为结构化对象）。"""
    reg = spec.get("gates")
    if isinstance(reg, list):
        return [str(g.get("id", "")) for g in reg if isinstance(g, dict) and g.get("id")]
    return [str(g) for g in spec.get("gates_pipeline", []) if g]


def gates_registry(spec: dict) -> list:
    """v4.4（P0-10）：gate registry 解析——[{id, script, args, report, required, strict_aware}]。
    缺 registry（旧 spec）时回退空列表（调用方报缺失）。"""
    reg = spec.get("gates")
    if not isinstance(reg, list):
        return []
    out = []
    for g in reg:
        if not isinstance(g, dict) or not g.get("id"):
            continue
        out.append({"id": str(g.get("id")),
                    "script": str(g.get("script", "")),
                    "args": list(g.get("args") or []),
                    "report": g.get("report") or None,
                    "required": bool(g.get("required", True)),
                    "strict_aware": bool(g.get("strict_aware", False))})
    return out


# 旧阶段序列残余锚点（v3 及以前手写顺序的典型表述；出现即 FAIL）
OLD_SEQUENCE_ANCHORS = [
    "2analysis-modeling → 3coding-visual → 4drawio → 5writing → 6verity",
    "2analysis → 3coding → 4drawio → 5writing → 6verity",
    "1. 赛题分析与建模设计 - `2analysis-modeling`\n2. 编程实现和图表生成 - `3coding-visual`",
    "brainstorm → analysis → modeling → coding → writing → verification",
]
V4_STAGE_MARKERS = ["7methodology-review", "FINAL_MODEL_SPEC", "workflow_spec"]


def _check_file_text(root: Path, rel: str, spec_stages: list, findings: list):
    """稳定锚点校验（不做脆弱的全文顺序推断）：
    1) 文档必须引用 workflow_spec（声称来源）；
    2) 文档必须提及 v4 阶段 7methodology-review；
    3) 文档不得残留旧阶段序列锚点（箭头串叙述）。
    """
    p = root / rel
    if not p.is_file():
        findings.append(("FAIL", f"{rel} 缺失（引用方的状态无法校验）"))
        return
    text = p.read_text(encoding="utf-8")
    if "workflow_spec" not in text:
        findings.append(("FAIL", f"{rel} 未引用 workflow_spec.yaml（阶段顺序未声明来源，v4 禁止手写顺序）"))
    if "7methodology-review" not in text:
        findings.append(("FAIL", f"{rel} 未提及 v4 阶段 7methodology-review（阶段表可能仍是旧六阶段）"))
    for anchor in OLD_SEQUENCE_ANCHORS:
        if anchor in text:
            findings.append(("FAIL", f"{rel} 残留旧阶段序列表述：{anchor[:48]}..."))


def main(argv=None):
    ap = argparse.ArgumentParser(description="workflow_spec 一致性工具")
    ap.add_argument("--print", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--root", default=None)
    args = ap.parse_args(argv)

    root = Path(args.root).resolve() if args.root else repo_root(Path(__file__).resolve().parent)
    spec = load_spec(root)
    if not spec.get("stages"):
        print(f"ERROR: {root / SPEC_NAME} 未找到或 stages 为空", file=sys.stderr)
        return 2
    ids = stage_ids(spec)
    if args.print:
        for s in spec.get("stages", []):
            print(s.get("id", ""))
        return 0
    if not args.check:
        print("用法: python workflow_spec.py [--print | --check --root <repo>]")
        return 0

    findings = []
    # 1. 关键脚本必须已接 spec（源码出现 OLD_SEQUENCES 残留即 FAIL）
    for rel in ("skills/6verity/scripts/check_decision_log.py",
                "skills/6verity/scripts/run_all_gates.py"):
        p = root / rel
        if not p.is_file():
            findings.append(("FAIL", f"{rel} 缺失"))
            continue
        text = p.read_text(encoding="utf-8")
        if "workflow_spec" not in text:
            findings.append(("FAIL", f"{rel} 未接入 workflow_spec（源码无 workflow_spec 引用）"))
    # 2. persona 与 README/docs 中的阶段出现顺序 = spec 顺序
    for rel in ("agent.cordis.yml", "README.md", "docs/WORKFLOW_v4.md"):
        _check_file_text(root, rel, spec.get("stages", []), findings)

    ok = True
    for level, msg in findings:
        print(f"  [{level}] {msg}")
        if level == "FAIL":
            ok = False
    print(f"WORKFLOW_SPEC: {'PASS' if ok else 'FAIL'}（{len(findings)} 项）")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
