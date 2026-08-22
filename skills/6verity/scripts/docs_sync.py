#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""docs_sync.py — v4.2（R-04）：README/docs 与 workflow_spec 单一事实源同步校验。

- 阶段表区块：README 中以
      <!-- docs_sync:stages -->
      ...
      <!-- /docs_sync:stages -->
  标记的区块由 workflow_spec.yaml 渲染生成（id | skill | gate | 产出 | 目的），
  禁止手写第二份阶段顺序。
- --check（CI）：
    1) README 阶段表区块 == 渲染结果；
    2) 仓库全部 .md/.yaml/.yml 不得再出现已废除路径 reports/figure_story_manifest.json
       （R-01：唯一清单只能有 figures/figure_manifest.json 一条路径）；
    3) README 提及 generated_values 的句子必须含"可选/optional/recommended"之一
       （R-02：generated_values 是 recommended 而非 mandatory）。

用法：
  python docs_sync.py --root <仓库根>          # 渲染并写回 README 区块
  python docs_sync.py --check --root <仓库根>  # 一致性校验（漂移即 FAIL）
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import workflow_spec as wfs

BLOCK_OPEN = "<!-- docs_sync:stages -->"
BLOCK_CLOSE = "<!-- /docs_sync:stages -->"
LEGACY_PATH = "reports/figure_story_manifest.json"
README_REL = "README.md"


def render_stages_block(spec: dict) -> str:
    lines = [BLOCK_OPEN, "| 阶段 | skill | 门禁 | 主要产出 | 目的 |", "|---|---|---|---|---|"]
    for st in spec.get("stages", []):
        sid = st.get("id", "?")
        skill = st.get("skill", "")
        gate = st.get("gate", "") or "—"
        outs = st.get("outputs", []) or []
        if isinstance(outs, list):
            outs = ", ".join(str(o) for o in outs[:4])
        purpose = str(st.get("purpose", "") or "")
        if len(purpose) > 80:
            purpose = purpose[:80] + "…"
        lines.append(f"| {sid} | {skill} | {gate} | {outs} | {purpose} |")
    lines.append(BLOCK_CLOSE)
    return "\n".join(lines)


def check(root: Path, findings: list):
    readme = root / README_REL
    if not readme.is_file():
        findings.append(("FAIL", f"{README_REL} 缺失"))
        return 1
    spec = wfs.load_spec(root)
    rendered = render_stages_block(spec)
    text = readme.read_text(encoding="utf-8")
    m = re.search(re.escape(BLOCK_OPEN) + "(.*?)" + re.escape(BLOCK_CLOSE), text, re.S)
    if m is None:
        findings.append(("FAIL", f"{README_REL} 缺少 docs_sync 阶段表区块（{BLOCK_OPEN}…{BLOCK_CLOSE}）——"
                                 "阶段顺序必须由 workflow_spec.yaml 渲染，禁止手写"))
        return 1
    if not text_fragment_matches(m, rendered):
        findings.append(("FAIL", "README 阶段表区块与 workflow_spec.yaml 渲染结果不一致（漂移："
                                 "请运行 python docs_sync.py --root <仓库根> 重新同步）"))
        return 1
    return 0


def text_fragment_matches(m: re.Match, rendered: str) -> bool:
    # 允许区块内换行/额外空行的容差比较：逐行比较非空行
    cur = [l.strip() for l in m.group(1).splitlines() if l.strip()]
    new = [l.strip() for l in rendered.split(BLOCK_CLOSE)[0].split(BLOCK_OPEN)[1].splitlines() if l.strip()]
    return cur == new


def main(argv=None):
    gc = None  # docs_sync 只依赖标准库 + workflow_spec
    ap = argparse.ArgumentParser(description="v4.2 README/docs 与 workflow_spec 同步")
    ap.add_argument("--root", default=".")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    spec = wfs.load_spec(root)
    rendered = render_stages_block(spec)
    readme = root / README_REL
    if args.check:
        findings = []
        rc = check(root, findings)
        # 2) 行为/声明文档旧路径残留扫描（docs/ 允许历史性"已废除"说明）
        behavior_docs = {"README.md", "agent.cordis.yml", "workflow_spec.yaml"}
        for p in sorted(root.rglob("SKILL.md")):
            behavior_docs.add(str(p.relative_to(root)))
        for p in sorted(root.rglob("*")):
            if p.is_dir() or p.suffix.lower() not in (".md", ".yaml", ".yml"):
                continue
            rel = str(p.relative_to(root))
            if rel not in behavior_docs:
                continue
            t = p.read_text(encoding="utf-8", errors="replace")
            if LEGACY_PATH in t:
                findings.append(("FAIL", f"{rel}: 残留已废除路径 {LEGACY_PATH}（R-01 唯一清单）"))
                rc = 1
        # 3) README generated_values 政策措辞
        t = readme.read_text(encoding="utf-8", errors="replace") if readme.is_file() else ""
        for m in re.finditer(r"[^\n]*generated_values[^\n]*", t):
            if not re.search(r"可选|optional|recommended|二选一", m.group(0)):
                findings.append(("FAIL", "README 提及 generated_values 但未标注 optional/recommended"
                                         "（R-02：generated_values 是 recommended 而非 mandatory）"))
                rc = 1
        for lvl, msg in findings:
            print(f"  [{lvl}] {msg}")
        print(f"DOCS_SYNC: {'PASS' if rc == 0 else 'FAIL'}")
        return rc
    # 渲染写回（幂等）
    if not readme.is_file():
        print(f"FAIL {README_REL} 缺失")
        return 1
    text = readme.read_text(encoding="utf-8")
    m = re.search(re.escape(BLOCK_OPEN) + "(.*?)" + re.escape(BLOCK_CLOSE), text, re.S)
    if m is None:
        text = text + "\n\n" + rendered + "\n"
    else:
        text = text[:m.start()] + rendered + text[m.end():]
    readme.write_text(text, encoding="utf-8")
    print(f"DOCS_SYNC: README 阶段表区块已同步（{len(spec.get('stages', []))} 阶段）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
