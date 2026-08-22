#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""schema_validator.py — v4.4（P1-19/T 新）：机器 JSON Schema 校验门。

docs/schemas/*.schema.json（draft-07）与 Markdown 文档分离：Markdown 只解释，Schema 约束。
映射（workspace 相对路径 -> schema 文件名）：
  reports/FINAL_MODEL_SPEC.json              -> final_model_spec.v2.schema.json
  reports/contracts/QUESTION_CONTRACT.json   -> question_contract.v1.schema.json
  reports/contracts/IDEA_CANDIDATES.json     -> idea_candidates.v1.schema.json
  reports/contracts/IDEA_DECISION.json       -> idea_decision.v1.schema.json
  results/RESULT_REGISTRY.json               -> result_registry.v1.schema.json
  figures/specs/*.figure.json                -> figure_spec.v1.schema.json（每个文件）
  reports/page_visual_review.json            -> page_visual_review.v1.schema.json

校验失败 -> FAIL（契约机器可验，禁止手放）。

用法：python schema_validator.py --workspace <项目根> [--strict] [--report ...]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import gate_common as gc

try:
    import jsonschema
except Exception:
    jsonschema = None

DOC_MAP = [
    ("reports/FINAL_MODEL_SPEC.json", "final_model_spec.v2.schema.json", "file"),
    ("reports/contracts/QUESTION_CONTRACT.json", "question_contract.v1.schema.json", "file"),
    ("reports/contracts/IDEA_CANDIDATES.json", "idea_candidates.v1.schema.json", "file"),
    ("reports/contracts/IDEA_DECISION.json", "idea_decision.v1.schema.json", "file"),
    ("results/RESULT_REGISTRY.json", "result_registry.v1.schema.json", "file"),
    ("figures/specs/*.figure.json", "figure_spec.v1.schema.json", "glob"),
    ("reports/page_visual_review.json", "page_visual_review.v1.schema.json", "file"),
]


def _violation(findings, check, msg, strict):
    findings.append({"level": "FAIL" if strict else "WARN", "check": check, "message": msg})


def main(argv=None):
    gc.force_utf8()
    ap = argparse.ArgumentParser(description="v4.4 机器 JSON Schema 门禁")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--report", default=None)
    args = ap.parse_args(argv)

    ws = Path(args.workspace).resolve()
    findings = []
    if jsonschema is None:
        _violation(findings, "schema",
                   "jsonschema 库未安装——机器 Schema 校验不可用（pip install jsonschema）", args.strict)
    else:
        schemas_dir = Path(__file__).resolve().parents[3] / "docs" / "schemas"
        checked = 0
        for doc_rel, schema_name, kind in DOC_MAP:
            schema_path = schemas_dir / schema_name
            if not schema_path.is_file():
                _violation(findings, "schema",
                           f"schema 文件缺失：docs/schemas/{schema_name}（P1-19）", args.strict)
                continue
            try:
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
            except Exception as exc:
                _violation(findings, "schema", f"schema {schema_name} 解析失败：{exc}", args.strict)
                continue
            if kind == "glob":
                targets = sorted((ws / "figures" / "specs").glob("*.figure.json")) \
                    if (ws / "figures" / "specs").is_dir() else []
            else:
                targets = [ws / doc_rel]
            for t in targets:
                if not t.is_file():
                    continue
                try:
                    doc = json.loads(t.read_text(encoding="utf-8"))
                except Exception as exc:
                    _violation(findings, "schema",
                               f"{t.relative_to(ws)} 非法 JSON：{exc}（契约必须机器可验）", args.strict)
                    continue
                errs = sorted(jsonschema.Draft7Validator(schema).iter_errors(doc),
                              key=lambda e: list(e.path))
                if errs:
                    e0 = errs[0]
                    path = ".".join(str(p) for p in e0.path) or "(root)"
                    _violation(findings, "schema",
                               f"{t.relative_to(ws)} 违反 {schema_name}：{path} {e0.message}"
                               f"（+{len(errs) - 1} 处）——契约机器校验失败（P1-19）", args.strict)
                else:
                    checked += 1
        findings.append({"level": "OK", "check": "schema",
                         "message": f"JSON Schema 校验通过：{checked} 个契约文档"})

    fails = [f for f in findings if f["level"] == "FAIL"]
    warns = [f for f in findings if f["level"] == "WARN"]
    report = {
        "gate": "schema_validation", "schema_version": 1, "workspace": str(ws),
        "strict": args.strict, "engine": gc.manifest_engine(ws),
        "findings": findings,
        "summary": {"fails": len(fails), "warns": len(warns), "checks": len(findings)},
        "note": "docs/schemas/*.schema.json（draft-07）为机器约束；Markdown schema 文档只作解释（P1-19）。",
    }
    out = Path(args.report).resolve() if args.report else ws / "reports" / "gates" / "schema_validation.json"
    gc.save_json(out, report)
    for f in findings:
        print(f"  [{f['level']}] {f['check']}: {f['message']}")
    print(f"SCHEMA_VALIDATION: {'PASS' if not fails else 'FAIL'}（{len(fails)} FAIL / {len(warns)} WARN） -> {out}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
