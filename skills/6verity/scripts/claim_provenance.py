#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""claim_provenance.py — v4.3（§13.2）：从 figure_manifest 的 story.claims + spec 构建
CLAIM_PROVENANCE.json（Paper Claim → result key → artifact → spec sha → code sha → data sha）。

用法：python claim_provenance.py --workspace <项目根> [--out repro/CLAIM_PROVENANCE.json]
输出/校验：--check 校验已存在文件与当前 sha 一致（漂移即 FAIL）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import gate_common as gc

MANIFEST_REL = "figures/figure_manifest.json"
SPEC_REL = "reports/FINAL_MODEL_SPEC.json"
REGISTRY_REL = "results/RESULT_REGISTRY.json"


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build(ws: Path) -> dict:
    manifest = gc.load_json(ws / MANIFEST_REL, None) or []
    spec = gc.load_json(ws / SPEC_REL, None) or {}
    registry = gc.load_json(ws / REGISTRY_REL, None) or {}
    spec_sha = sha(ws / SPEC_REL) if (ws / SPEC_REL).is_file() else None
    data = next((p for p in [(ws / "data" / "附件.xlsx"), (ws / "data" / "data.xlsx")] if p.is_file()), None)
    data_sha = sha(data) if data else None
    gen_map = {}
    for a in registry.get("artifacts") or []:
        if isinstance(a, dict):
            gen_map[str(a.get("file", ""))] = str(a.get("generator", ""))
    claims = []
    for fig in manifest:
        if not isinstance(fig, dict):
            continue
        for c in (fig.get("story") or {}).get("claims") or []:
            rk = str(c.get("result_key", ""))
            file = None
            for src in fig.get("source", {}).get("source_results") or []:
                if rk.split(".")[0] == Path(str(src.get("file", ""))).stem:
                    file = str(src.get("file"))
                    break
            claims.append({
                "claim_id": f"{fig.get('id')}.CLAIM",
                "paper_location": "figures/figure_manifest.json (story.claims)",
                "claim_type": "figure_story_claim",
                "result": {"file": file, "key": rk},
                "predicate": c.get("predicate"),
                "expected": c.get("expected"),
                "model_spec_sha256": spec_sha,
                "code_sha256": sha(ws / gen_map[file]) if file and gen_map.get(file) and (ws / gen_map[file]).is_file() else None,
                "data_sha256": data_sha,
            })
    return {
        "schema_version": 1,
        "note": "v4.3（§13.2）：Paper Claim → result key → artifact → model spec sha → code sha → data sha 的简化 provenance 图；"
                "由 claim_provenance.py 从 figure_manifest story.claims 与 RESULT_REGISTRY 自动构建。",
        "model_spec_sha256": spec_sha,
        "data_sha256": data_sha,
        "claims": claims,
        "n_claims": len(claims),
    }


def main(argv=None):
    gc.force_utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--out", default="repro/CLAIM_PROVENANCE.json")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    ws = Path(args.workspace).resolve()
    doc = build(ws)
    out = ws / args.out
    if args.check:
        cur = gc.load_json(out, None)
        if cur is None:
            print(f"CLAIM_PROVENANCE: FAIL {args.out} 缺失")
            return 1
        if cur.get("model_spec_sha256") != doc["model_spec_sha256"] or \
           any(doc.get("claims")[i].get("model_spec_sha256") != (cur.get("claims") or [])[i].get("model_spec_sha256")
               for i in range(min(len(doc.get("claims") or []), len(cur.get("claims") or [])))) or \
           (cur.get("model_spec_sha256") and cur.get("model_spec_sha256") != doc["model_spec_sha256"]):
            print("CLAIM_PROVENANCE: FAIL 内容漂移（spec/结果已变未重新生成）")
            return 1
        print(f"CLAIM_PROVENANCE: PASS（{cur.get('n_claims')} 条 claim 与当前契约一致）")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"CLAIM_PROVENANCE: {doc['n_claims']} 条 claim -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
