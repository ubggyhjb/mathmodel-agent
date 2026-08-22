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
    """v4.1（R-01）：唯一清单 figures/figure_manifest.json——不再回退旧路径
    reports/figure_story_manifest.json（旧文件存在时提示删除，不影响判定）。"""
    doc = gc.load_json(ws / MANIFEST_REL, None)
    if isinstance(doc, list):
        return doc, False
    if gc.load_json(ws / LEGACY_REL, None) is not None:
        print(f"WARN 发现旧清单 {LEGACY_REL}：v4.1 已废除该路径，请删除（仅保留 {MANIFEST_REL}）",
              file=sys.stderr)
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


# ---------- v4.2：panel 强制声明 / structured claims / stale story ----------


def _multi_panel_signals(mcap: str, meta: dict) -> list:
    """G-03/T49：检测 multi-panel 图信号（caption 面板标记 / meta 多面板计数）。"""
    sigs = []
    if mcap and re.search(r"(?<![A-Za-z0-9])([A-D])\s*[：:]", mcap):
        sigs.append("caption 含面板标记（A：/B：/C：）")
    if isinstance(meta, dict):
        mp = meta.get("panels")
        if isinstance(mp, dict) and len(mp) > 1:
            sigs.append(f"meta.panels 记录 {len(mp)} 个面板")
        axes = meta.get("axes")
        if isinstance(axes, list) and len(axes) > 1:
            sigs.append(f"meta.axes 登记 {len(axes)} 个坐标轴")
    return sigs


CLAIM_PREDICATES = {"crosses_zero", "equal_to", "gt", "lt", "within", "contains", "not_contains"}


def check_structured_claims(ws: Path, item: dict, strict: bool):
    """v4.2 G-04/T50：story.claims 结构化绑定 result key + predicate；
    story 自由文本只做呈现，claim 才是真值源——claim 与结果矛盾或 key 失效即 FAIL。"""
    findings = []
    claims = (item.get("story") or {}).get("claims") or []
    if not claims:
        return findings
    src_map = {}
    for src in item.get("source", {}).get("source_results") or []:
        rel = str(src.get("file", "")).strip().lstrip("/\\")
        doc = gc.load_json(ws / rel, None) if rel else None
        if doc is not None:
            src_map.setdefault(Path(rel).stem, doc)
    for c in claims:
        rk = str(c.get("result_key", "") or "")
        pred = str(c.get("predicate", "") or "")
        if "." not in rk or pred not in CLAIM_PREDICATES:
            findings.append({"level": "FAIL" if strict else "WARN", "check": "claim_schema",
                             "message": f"Figure {item.get('id')}: claim 缺少合法 result_key/predicate"
                                        f"（{rk!r}/{pred!r}）——G-04 要求结构化绑定"})
            continue
        stem, path = rk.split(".", 1)
        doc = src_map.get(stem)
        if doc is None:
            findings.append({"level": "FAIL" if strict else "WARN", "check": "claim_key",
                             "message": f"Figure {item.get('id')}: claim 的 result_key={rk} "
                                        f"在 source_results 中无对应文件"})
            continue
        val = _find_json_value(doc, path)
        if val is None:
            findings.append({"level": "FAIL" if strict else "WARN", "check": "claim_key",
                             "message": f"Figure {item.get('id')}: claim 的 result_key={rk} 在 "
                                        f"{stem} 中不存在"})
            continue
        exp = c.get("expected")
        ok = None
        if pred == "crosses_zero":
            lo = hi = None
            if isinstance(val, dict):
                lo = val.get("low", val.get("ci_low", val.get("lower")))
                hi = val.get("high", val.get("ci_high", val.get("upper")))
            elif isinstance(val, (list, tuple)) and len(val) == 2:
                lo, hi = val[0], val[1]
            ok = (lo is not None and hi is not None and lo < 0 < hi) == bool(exp)
        elif pred == "equal_to":
            ok = str(val) == str(exp)
        elif pred == "gt":
            ok = float(val) > float(exp)
        elif pred == "lt":
            ok = float(val) < float(exp)
        elif pred == "within":
            ok = isinstance(exp, (list, tuple)) and len(exp) == 2 and exp[0] <= float(val) <= exp[1]
        elif pred == "contains":
            ok = str(exp) in str(val)
        elif pred == "not_contains":
            ok = str(exp) not in str(val)
        if ok is None:
            continue  # 无法判定（类型不符）——不误报
        if not ok:
            findings.append({"level": "FAIL" if strict else "WARN", "check": "claim_false",
                             "message": f"Figure {item.get('id')}: claim {rk} {pred}={exp} 与结果值 "
                                        f"{str(val)[:40]} 矛盾（T50：story 与 result 不一致）"})
    return findings


STALE_TERMS = ("插值", "interpolation", "Kaplan-Meier", "Kaplan", "Greenwood", "KM ")
LATEST_TERMS = ("Turnbull", "区间删失", "interval-censored", "interval censored")


def check_stale_story(item: dict, mcap: str, strict: bool):
    """v4.2 T51：story 仍用旧口径词（插值/KM）而 caption 已是当前口径（Turnbull/区间删失）→ FAIL。"""
    findings = []
    story = str((item.get("story") or {}).get("main_message") or "")
    if not story or not mcap:
        return findings
    stale = [t for t in STALE_TERMS if t.lower() in story.lower()]
    latest = [t for t in LATEST_TERMS if t.lower() in mcap.lower()]
    if stale and latest:
        findings.append({"level": "FAIL" if strict else "WARN", "check": "stale_story_term",
                         "message": f"Figure {item.get('id')}: story.main_message 含旧口径词 {stale}，"
                                    f"但 caption 已是 {latest}——story 未随口径迁移（T51）"})
    return findings


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
    if not isinstance(manifest, list):
        findings.append({"level": "FAIL" if args.strict else "WARN", "check": "manifest",
                         "message": f"{MANIFEST_REL} 缺失或非数组：主图未做 Figure Story 定义（v4.1 唯一清单，无旧路径回退）"})
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
        mcap = str(item.get("caption", "") or "").strip()
        meta = load_meta(ws, files[0]) if files else None
        if files and idx not in used_stems and Path(files[0]).stem not in used_stems:
            continue  # 未上正文的图不做完整性检查
        if meta is None:
            # R-05：正式 Figure（primary/secondary）缺 meta 直接 FAIL；appendix 降为 WARN
            prio = item.get("visual_priority", "primary")
            findings.append({"level": "FAIL" if (args.strict and prio != "appendix") else "WARN",
                             "check": "meta_missing",
                             "message": f"Figure {idx} 缺 figures/<id>.meta.json（R-05：正式图必须带 "
                                        f"provenance + artist 计数；缺 meta 不得进入终稿）"})
        else:
            # v4.2 G-03/T49：multi-panel 信号但 manifest.panels 为空 -> FAIL
            #（空 panels 使 panel integrity 形同虚设：caption 有 A:B:C 或 meta 多面板都必须声明）
            if not (item.get("panels") or []):
                sigs = _multi_panel_signals(mcap, meta)
                if sigs:
                    findings.append({"level": "FAIL" if args.strict else "WARN", "check": "panel_declaration",
                                     "message": f"Figure {idx} 检测到 multi-panel 信号但 manifest.panels "
                                                f"为空（{sigs}）——panels: [] 绕过 panel integrity（G-03/T49）"})
            # panel integrity（R-05：panel 默认至少 1 个 data artist，除非 intentionally_empty=true）
            for panel in item.get("panels", []) or []:
                if not isinstance(panel, dict):
                    continue  # v3 旧 schema：字符串列表
                if panel.get("intentionally_empty") is True:
                    continue
                pid = str(panel.get("id", "A"))
                min_count = panel.get("min_artist_count", 1)
                counts = (meta.get("panels") or {}).get(pid) or {}
                total = sum(int(counts.get(k, 0) or 0) for k in
                            ("line_count", "scatter_count", "patch_count", "collection_count"))
                if total < int(min_count):
                    findings.append({"level": "FAIL" if args.strict else "WARN", "check": "panel_integrity",
                                     "message": f"Figure {idx} Panel {pid}: artist 计数 {total} "
                                                f"< min_artist_count {min_count}（空白/空 panel；"
                                                f"若确有意留空须声明 intentionally_empty=true）"})
            # annotation-key trace + semantic role（R-06）
            VALID_ROLES = {"current_recommendation", "baseline_interpolation",
                           "reference_threshold", "reference_line", "mechanism", "other"}
            key_roles = {}
            for ann in meta.get("annotations", []) or []:
                vk = ann.get("value_key")
                if not vk:
                    continue
                role = str(ann.get("role", "") or "").strip()
                if role not in VALID_ROLES:
                    findings.append({"level": "FAIL" if args.strict else "WARN", "check": "annotation_role",
                                     "message": f"Figure {idx} 标注 {ann.get('label')} 缺合法 role"
                                                f"（{role!r}；应为 {sorted(VALID_ROLES)}）——无法区分当前结论与旧基线"})
                ok_any = False
                for src in meta.get("source_results", []) or []:
                    if check_source_key(ws, src, vk):
                        ok_any = True
                        break
                if not ok_any:
                    findings.append({"level": "FAIL" if args.strict else "WARN", "check": "annotation_key",
                                     "message": f"Figure {idx} 标注 {ann.get('label')} 的 value_key={vk} "
                                                f"在 source_results 中不存在（数字可能来自旧口径）"})
                # 同一 value_key 不得同时被"当前推荐"与"旧基线"引用（T36 反例）
                if role.startswith("baseline"):
                    key_roles.setdefault(vk, set()).add("baseline")
                elif role == "current_recommendation":
                    key_roles.setdefault(vk, set()).add("current")
            for vk, roles in key_roles.items():
                if "baseline" in roles and "current" in roles:
                    findings.append({"level": "FAIL" if args.strict else "WARN", "check": "annotation_role",
                                     "message": f"Figure {idx} value_key={vk} 同时被标为当前推荐与旧基线"
                                                f"——旧值可能被当成当前结论（T36）"})
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
                    # T35/P0-02：caption 提及的模型编号与 panels[].model_id 集合必须一致
                    panel_models = {str(p.get("model_id")) for p in item.get("panels", []) or []
                                    if isinstance(p, dict) and p.get("model_id")}
                    cap_models = set(re.findall(r"\bM\d+\b", mcap) + re.findall(r"\bM\d+\b", pcap))
                    if panel_models and cap_models and panel_models != cap_models:
                        findings.append({"level": "FAIL" if args.strict else "WARN", "check": "caption_panel_model",
                                         "message": f"Figure {idx}: caption 提及模型 {sorted(cap_models)} "
                                                    f"与 panels.model_id {sorted(panel_models)} 不一致（P0-02/T35）"})
        # v4.2 G-04/T50 + T51：structured claims 真值校验 + story 旧口径词
        findings.extend(check_structured_claims(ws, item, args.strict))
        findings.extend(check_stale_story(item, mcap, args.strict))
        # T37/P0-05：spec 为 interval 主口径时，正式图 caption 不得用 KM/Greenwood 表述
        spec = gc.load_json(ws / "reports" / "FINAL_MODEL_SPEC.json", None)
        interval_main = bool(spec) and any(
            str(p.get("likelihood", "")) == "interval"
            for p in (spec.get("problems") or []))
        if interval_main and re.search(r"Kaplan|Greenwood|\bKM\b", mcap) \
                and item.get("visual_priority", "primary") != "appendix":
            findings.append({"level": "FAIL" if args.strict else "WARN", "check": "interval_vs_km",
                             "message": f"Figure {idx}: 主口径为区间删失（契约 likelihood=interval）但 caption"
                                        f" 使用 KM/Greenwood 表述——图与主方法不一致（P0-05/T37），"
                                        f"须重画为 Turnbull/区间删失曲线"})
        # T42/P0-09：称 forest 但无真实 CI 声明（或显式伪区间）→ FAIL
        if meta is not None and mcap:
            if re.search(r"森林|forest", mcap, re.I):
                axes_note = " ".join(str(a.get("note", "")) for a in meta.get("axes", []) or [])
                if "pseudo_interval" in axes_note or meta.get("ci_declared") is not True:
                    findings.append({"level": "FAIL" if args.strict else "WARN", "check": "fake_forest_ci",
                                     "message": f"Figure {idx}: caption 称 {mcap[:30]}… 但（伪区间标记 "
                                                f"或 meta 未声明 ci_declared=true）——无真实 95% CI 不得称 forest"
                                                f"（P0-09/T42），改标准化系数幅度图"})

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
