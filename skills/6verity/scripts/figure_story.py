#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""figure_story.py — v4 Figure Story 门（唯一清单 + 图完整性）。

唯一事实源：figures/figure_manifest.json（schema 见 docs/figure_manifest.schema.md）。
发现 v3 旧路径 reports/figure_story_manifest.json 时回退读取并 WARN（迁移提示）。

检查项（strict FAIL 级）：
  1. manifest 存在且为数组；每条 story.main_message 非空；
  2. 正文引用（includegraphics/image）必须登记；
  3. supersedes 生效：A.supersedes=[B,...] 时 B 仍在正文 → FAIL；
  4. redundant_with 双方都在正文且无 keep_both_reason（非空独有信息说明）→ FAIL；
  5. panel integrity：panels[].min_artist_count > 0 时，
     figures/<id>.meta.json 的 panels[id] artist 计数必须 >= 下限 → 否则 FAIL；
     meta.json 缺失 → WARN（v4 起新图必带）；
  6. annotation-key trace：meta.annotations[].value_key 必须在 source_results 的 JSON 中存在；
  7. caption 一致性：论文 figure 块的 caption 必须与 manifest.caption 一致（归一化后互为子串；
     manifest 缺 caption 跳过）；
  8. unit audit：meta.axes[].variable/display 与 reports/variables.json 声明不一致 → FAIL；
  9. primary 数量 > max_primary（默认 6）→ WARN；
  10. figures/ 下未采用未登记文件 → WARN。

用法：python figure_story.py --workspace <项目根> [--strict]
输出：reports/gates/figure_story.json；退出码 0 PASS / 1 FAIL / 2 ERROR。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import gate_common as gc

MANIFEST_REL = "figures/figure_manifest.json"
LEGACY_REL = "reports/figure_story_manifest.json"
VARIABLES_REL = "reports/variables.json"
VALID_PRIORITY = {"primary", "secondary", "appendix"}


def collect_paper_figures(ws: Path) -> list:
    """论文源（tex/typ）中引用的图像文件名（stem 列表 + 原文件名）。"""
    used = []
    paper = ws / "paper"
    if paper.is_dir():
        for p in sorted(paper.rglob("*")):
            if p.suffix.lower() not in (".tex", ".typ"):
                continue
            try:
                t = p.read_text(encoding="utf-8")
            except Exception:
                continue
            for m in re.finditer(r"(?:includegraphics|image)\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}", t):
                stem = Path(m.group(1).strip()).name
                used.append(stem)
            for m in re.finditer(r"image\(\s*\"([^\"]+)\"", t):
                stem = Path(m.group(1).strip()).name
                used.append(stem)
    return used


def collect_figure_dir(ws: Path) -> list:
    figs = ws / "figures"
    out = []
    if figs.is_dir():
        for p in sorted(figs.iterdir()):
            if p.suffix.lower() in (".pdf", ".png"):
                out.append(p.name)
    return out


def load_manifest(ws: Path):
    """v4 唯一清单；回退 v3 旧清单并提示迁移。返回 (manifest, used_legacy)。"""
    doc = gc.load_json(ws / MANIFEST_REL, None)
    if isinstance(doc, list):
        return doc, False
    doc = gc.load_json(ws / LEGACY_REL, None)
    if isinstance(doc, list):
        return doc, True
    return None, False


# ---------- 论文 caption 提取 ----------

def paper_captions(ws: Path) -> dict:
    """{figure_stem: caption_text}：解析论文 figure 块（includegraphics/image + caption）。"""
    out = {}
    paper = ws / "paper"
    if not paper.is_dir():
        return out
    fig_block_re = re.compile(r"\\begin\{figure\}(.*?)\\end\{figure\}", re.S)
    img_re = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}")
    cap_re = re.compile(r"\\caption\s*\{(.*?)\}", re.S)
    typ_block_re = re.compile(r"#figure\s*\((.*?)\)\s*(?:,|$)", re.S)
    typ_img_re = re.compile(r'image\s*\(\s*"([^"]+)"')
    typ_cap_re = re.compile(r'caption:\s*\[(.*?)\]', re.S)
    for p in sorted(paper.rglob("*")):
        if p.suffix.lower() not in (".tex", ".typ"):
            continue
        try:
            t = p.read_text(encoding="utf-8")
        except Exception:
            continue
        if p.suffix.lower() == ".tex":
            for block in fig_block_re.findall(t):
                stems = [Path(m.group(1).strip()).name for m in img_re.finditer(block)]
                cap = cap_re.findall(block)
                if stems and cap:
                    for s in stems:
                        out.setdefault(s, cap[0])
        else:
            for block in typ_block_re.findall(t):
                stems = [Path(m.group(1).strip()).name for m in typ_img_re.finditer(block)]
                cap = typ_cap_re.findall(block)
                if stems and cap:
                    for s in stems:
                        out.setdefault(s, cap[0])
    return out


def normalize_caption(s: str) -> str:
    return re.sub(r"\s+", "", str(s)).replace("图", "").replace("表", "")


# ---------- meta / panels / annotations ----------

def load_meta(ws: Path, fig_file: str) -> dict:
    """figures/<stem>.meta.json（figure_id 或文件名匹配）。"""
    stem = Path(fig_file).stem
    for cand in (ws / "figures" / f"{stem}.meta.json",):
        doc = gc.load_json(cand, None)
        if isinstance(doc, dict):
            return doc
    return None


def _find_json_value(doc, key: str):
    """按点分路径在 JSON 中取值（G2.recommended.low -> doc['G2']['recommended']['low']）。"""
    cur = doc
    for part in key.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit():
            cur = cur[int(part)]
        else:
            return None
    return cur


def check_source_key(ws: Path, src: dict, key: str) -> bool:
    """校验 annotations value_key 在 source_results 文件 JSON 中存在。"""
    rel = str(src.get("file", "")).strip().lstrip("/\\")
    doc = gc.load_json(ws / rel, None) if rel else None
    if doc is None:
        return False
    return _find_json_value(doc, key) is not None


def audit_variables(ws: Path, meta: dict):
    """meta.axes 的 variable/display 声明必须与 reports/variables.json 一致；
    且 annotations 的 raw/value 不得同值（但 registry 声明了非 1 的显示变换）——
    单位未换算（如 Y_fraction 存 0.04、显示应为 4%）直接 FAIL（任务书 十五条）。"""
    reg = gc.load_json(ws / VARIABLES_REL, None)
    if not isinstance(reg, dict):
        return None  # 无 registry -> 跳过（有 registry 才校验）
    problems = []
    for ax in meta.get("axes", []) or []:
        var = ax.get("variable")
        disp = ax.get("display")
        if not var or not disp:
            continue
        entry = reg.get(var)
        if entry is None:
            problems.append(f"axis 声明 variable={var} 但 variables.json 未注册")
            continue
        displays = entry.get("display") or {}
        if isinstance(displays, dict) and disp not in displays:
            problems.append(f"axis display={disp} 与 registry[{var}] 的 display 集合不符")
            continue
        d_entry = displays.get(disp) if isinstance(displays, dict) else None
        if d_entry and str(d_entry.get("transform", "1")) not in ("1", "*1", "x1"):
            for ann in meta.get("annotations", []) or []:
                raw, val = ann.get("raw"), ann.get("value")
                if raw is None or val is None:
                    continue
                try:
                    if abs(float(raw) - float(val)) < 1e-12:
                        problems.append(f"annotation '{ann.get('label')}' raw==value，但变量 {var} "
                                        f"显示变换为 {d_entry['transform']}（如存 0.04 应显示 4.0）——单位未换算")
                except (TypeError, ValueError):
                    continue
    return problems


def main(argv=None):
    gc.force_utf8()
    ap = argparse.ArgumentParser(description="v4 Figure Story 门")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--max-primary", type=int, default=6)
    ap.add_argument("--report", default=None)
    args = ap.parse_args(argv)

    ws = Path(args.workspace).resolve()
    findings = []
    manifest, used_legacy = load_manifest(ws)
    if used_legacy:
        findings.append({"level": "WARN", "check": "manifest_merged",
                         "message": f"正在回退读取 v3 旧清单 {LEGACY_REL}——v4 唯一清单应为 "
                                    f"{MANIFEST_REL}（迁移/合并后删除旧文件）"})
    if not isinstance(manifest, list):
        findings.append({"level": "FAIL" if args.strict else "WARN", "check": "manifest",
                         "message": f"{MANIFEST_REL} 缺失或非数组：主图未做 Figure Story 定义"})
        manifest = []

    by_files = {}
    for item in manifest:
        item.setdefault("story", {})
        idx = item.get("id", "?")
        msg = item.get("story", {}).get("main_message") or item.get("main_message")
        if not str(msg or "").strip():
            findings.append({"level": "FAIL" if args.strict else "WARN", "check": "purpose",
                             "message": f"Figure {idx} 缺 story.main_message（先定『这张图证明什么』再画）"})
        if item.get("visual_priority") not in VALID_PRIORITY:
            findings.append({"level": "WARN", "check": "priority",
                             "message": f"Figure {idx} visual_priority={item.get('visual_priority')!r} 非法"})
        unique = item.get("story", {}).get("unique_information") or item.get("unique_information")
        if not str(unique or "").strip():
            findings.append({"level": "WARN", "check": "redundancy",
                             "message": f"Figure {idx} 未声明 unique_information——若删除后无独有信息应删除"})
        for f in item.get("files", []):
            by_files[Path(f).stem] = idx

    used = collect_paper_figures(ws)
    used_stems = {Path(u).stem for u in used}
    unregistered = sorted(used_stems - set(by_files))
    if unregistered:
        findings.append({"level": "FAIL" if args.strict else "WARN", "check": "coverage",
                         "message": f"正文引用但未登记 Figure Story 的图：{unregistered[:10]}"})
    dir_files = {Path(x).stem for x in collect_figure_dir(ws)}
    unused = sorted(dir_files - used_stems - set(by_files))
    if unused:
        findings.append({"level": "WARN", "check": "cleanup",
                         "message": f"figures/ 下未被正文采用也未登记的图（建议删除）：{unused[:10]}"})

    primaries = [it for it in manifest if it.get("visual_priority") == "primary"]
    if len(primaries) > args.max_primary:
        findings.append({"level": "WARN", "check": "focus",
                         "message": f"primary 图 {len(primaries)} 张 > {args.max_primary}"})

    id2item = {it.get("id"): it for it in manifest}
    # supersedes 硬 fail
    for a in manifest:
        for old in a.get("supersedes", []) or []:
            if old in id2item and Path(old).stem in used_stems:
                findings.append({"level": "FAIL" if args.strict else "WARN", "check": "supersedes",
                                 "message": f"Figure {a.get('id')} 已声明 supersedes=[{old}]，但旧图仍在正文（新图加了旧图没删）"})
    # redundant_with 硬 fail（无 keep_both_reason）
    for a in manifest:
        for b in a.get("redundant_with", []) or []:
            if b in id2item and Path(b).stem in used_stems and Path(a.get("id", "")).stem in used_stems:
                if not str(a.get("keep_both_reason", "") or "").strip():
                    findings.append({"level": "FAIL" if args.strict else "WARN", "check": "redundancy",
                                     "message": f"Figure {a.get('id')} 与 {b} 互为冗余且同处正文，"
                                                f"且无 keep_both_reason——必须合并/删除或说明各自独有信息"})

    # panel integrity + annotation-key + unit + caption
    caps = paper_captions(ws)
    for item in manifest:
        idx = item.get("id", "?")
        files = item.get("files", [])
        meta = load_meta(ws, files[0]) if files else None
        if files and idx not in used_stems and Path(files[0]).stem not in used_stems:
            continue  # 未上正文的图不做完整性检查
        if meta is None:
            findings.append({"level": "WARN", "check": "meta_missing",
                             "message": f"Figure {idx} 缺 figures/<id>.meta.json（v4 强制：provenance + artist 计数）"})
        else:
            # panel integrity
            for panel in item.get("panels", []) or []:
                if not isinstance(panel, dict):
                    continue  # v3 旧 schema：panels 为字符串列表（"A","B"），无完整性声明
                pid = str(panel.get("id", "A"))
                min_count = panel.get("min_artist_count")
                if min_count is None:
                    continue
                counts = (meta.get("panels") or {}).get(pid) or {}
                total = sum(int(counts.get(k, 0) or 0) for k in
                            ("line_count", "scatter_count", "patch_count", "collection_count"))
                if total < int(min_count):
                    findings.append({"level": "FAIL" if args.strict else "WARN", "check": "panel_integrity",
                                     "message": f"Figure {idx} Panel {pid}: artist 计数 {total} "
                                                f"< min_artist_count {min_count}（空白/空 panel）"})
            # annotation-key trace
            for ann in meta.get("annotations", []) or []:
                vk = ann.get("value_key")
                if not vk:
                    continue
                ok_any = False
                for src in meta.get("source_results", []) or []:
                    if check_source_key(ws, src, vk):
                        ok_any = True
                        break
                if not ok_any:
                    findings.append({"level": "FAIL" if args.strict else "WARN", "check": "annotation_key",
                                     "message": f"Figure {idx} 标注 {ann.get('label')} 的 value_key={vk} "
                                                f"在 source_results 中不存在（数字可能来自旧口径）"})
            # unit audit
            uproblems = audit_variables(ws, meta)
            if uproblems:
                for up in uproblems:
                    findings.append({"level": "FAIL" if args.strict else "WARN", "check": "unit_registry",
                                     "message": f"Figure {idx}: {up}"})
            # source freshness（任务书 9 条）：meta 记录的源结果 sha256 与当前文件不符
            # -> 图由旧结果生成（重画了但用的旧数据/旧口径），FAIL
            for src in meta.get("source_results", []) or []:
                rel = str(src.get("file", "")).strip().lstrip("/\\")
                rec = str(src.get("sha256", "") or "")
                if not rel or not rec:
                    continue
                cur = gc.sha256_file(ws / rel) if (ws / rel).is_file() else ""
                if cur and cur != rec:
                    findings.append({"level": "FAIL" if args.strict else "WARN", "check": "source_freshness",
                                     "message": f"Figure {idx} 声明的源结果 {rel} 哈希与当前文件不一致——"
                                                f"图可能由旧结果/旧口径生成（报告重新生成图）"})
        # caption 一致性（不依赖 meta.json）
        mcap = str(item.get("caption", "") or "").strip()
        if mcap:
            for f in files:
                stem = Path(f).stem
                pcap = caps.get(stem) or caps.get(f"{stem}.pdf") or caps.get(f"{stem}.png")
                if pcap:
                    if normalize_caption(mcap) not in normalize_caption(pcap) \
                            and normalize_caption(pcap) not in normalize_caption(mcap):
                        findings.append({"level": "FAIL" if args.strict else "WARN", "check": "caption_consistency",
                                         "message": f"Figure {idx} caption 与论文不一致：manifest='{mcap[:40]}' "
                                                    f"vs paper='{pcap[:40]}'"})

    fails = [f for f in findings if f["level"] == "FAIL"]
    warns = [f for f in findings if f["level"] == "WARN"]
    report = {
        "gate": "figure_story", "schema_version": 2, "workspace": str(ws),
        "strict": args.strict, "engine": gc.manifest_engine(ws),
        "manifest": MANIFEST_REL, "legacy_used": used_legacy,
        "n_manifest": len(manifest), "n_primary": len(primaries), "n_used": len(used_stems),
        "findings": findings, "summary": {"fails": len(fails), "warns": len(warns)},
        "note": "v4：多余/被取代/空 panel/annotation 无来源/caption 不一致均硬 FAIL；meta.json 缺失 WARN（新图强制）",
    }
    out = Path(args.report).resolve() if args.report else ws / "reports" / "gates" / "figure_story.json"
    gc.save_json(out, report)
    for f in findings:
        print(f"  [{f['level']}] {f['check']}: {f['message']}")
    print(f"FIGURE_STORY: {'PASS' if not fails else 'FAIL'}（{len(fails)} FAIL / {len(warns)} WARN） -> {out}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
