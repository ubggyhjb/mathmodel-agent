#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""layout_gate.py — v2 引擎无关排版门禁：共享 PDF 检查 + LaTeX/Typst 源适配器。

与 layout_audit.py（纯 PDF 越界/重叠审计）互补：
  * layout_audit  管"PDF 物理排版"（越界、重叠、行高）
  * layout_gate   管"门禁基建"：入口/引擎适配、include/image 引用、图源/论文
                  新鲜度、PDF 页面尺寸与底部空白/近空页、**被引图源有效字号**。

PDF 层（latex/typst/word 通用，需 PyMuPDF）：
  pdf_exists      入口声明的 PDF 存在且非空
  page_size       页面 A4（595.27x841.89pt，容差 2pt）
  blank_pages     整页无文字 -> FAIL
  near_empty      非首页文本 <60 字符 -> WARN
  bottom_blank    页有正文但底部 55% 区域文本覆盖 <5% -> WARN
  page_fill       行带占用率 + 最大连续空带（12pt 条带；占用率<55% 或空带>25% 内容高 WARN，
                  占用率>99% WARN）——禁止用纵向跨度判留白
  fig_text_size   被引矢量图有效字号 = 源最小字号 × 放置宽/源宽；<5pt FAIL，5-6pt WARN
源适配器层（engine=latex|typst）：
  include_refs    入口 include/input（#include）引用存在、无重复
  image_refs      includegraphics/image() 引用存在（相对含引用文件解析 + graphicspath）
  caption         figure 环境必须含 caption（#figure 含 caption:；缺失 WARN）
  freshness       main.pdf 晚于全部源文件与被引图源（容差 1s）；results JSON 晚于图源 -> WARN
word/unknown：无源适配器，executed=False；--strict 下 FAIL（禁止伪 PASS）。

用法：
  python layout_gate.py --workspace <项目根> [--engine latex|typst|word]
        [--entry paper/main.tex] [--pdf paper/main.pdf] [--figures-dir figures]
        [--strict] [--report reports/gates/layout_gate.json]
退出码：0 无 FAIL；1 存在 FAIL（含 strict 下未知引擎/未执行 adapter）；2 环境错误。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import fitz
except ImportError:
    print("FAIL 需要 PyMuPDF：pip install pymupdf")
    sys.exit(2)

import gate_common as gc

POLICY = gc.load_policy()
A4_W, A4_H = POLICY.get("pages", {}).get("a4", [595.27, 841.89])
SIZE_TOL = POLICY.get("pages", {}).get("size_tolerance_pt", 2.0)
NEAR_EMPTY = POLICY.get("pages", {}).get("near_empty_chars", 60)
BOTTOM_BLANK_RATIO = POLICY.get("pages", {}).get("bottom_blank_ratio_warn", 0.55)
PAGE_FILL_LOW_WARN = POLICY.get("pages", {}).get("page_fill_min_warn", 0.55)
PAGE_FILL_HIGH_WARN = POLICY.get("pages", {}).get("page_fill_max_warn", 0.99)
PAGE_FILL_GAP_WARN = POLICY.get("pages", {}).get("page_fill_gap_max_warn", 0.25)
FILL_TOP_MARGIN = POLICY.get("pages", {}).get("page_fill_top_margin", 0.08)
FILL_BOTTOM_MARGIN = POLICY.get("pages", {}).get("page_fill_bottom_margin", 0.10)
FIG_FAIL_PT = POLICY.get("figures", {}).get("min_effective_font_fail_pt", 5.0)
FIG_WARN_PT = POLICY.get("figures", {}).get("min_effective_font_warn_pt", 6.0)
SIDE_BY_SIDE_MAX = POLICY.get("figures", {}).get("side_by_side_max_texwidth", 0.5)

TEX_INCLUDE_RE = re.compile(r"\\(?:input|include)\s*\{([^}]+)\}")
TEX_GRAPHICS_RE = re.compile(r"\\includegraphics(?:\[([^\]]*)\])?\{([^}]+)\}")
TEX_GRAPHICSPATH_RE = re.compile(r"\\graphicspath\s*\{((?:\s*\{[^{}]*\})+)\}", re.S)
TEX_FIGURE_RE = re.compile(r"\\begin\{figure\}(.*?)\\end\{figure\}", re.S)
TEX_CAPTION_RE = re.compile(r"\\caption")
TEX_GEOMETRY_RE = re.compile(r"\\usepackage(?:\[[^\]]*\])?\{geometry\}")
TEX_GEOM_KV_RE = re.compile(r"(top|bottom|left|right)\s*=\s*([\d.]+)\s*(cm|mm|in|pt)")
TYP_INCLUDE_RE = re.compile(r'#include\s*\(\s*"([^"]+\.typ)"\s*\)')
TYP_IMAGE_RE = re.compile(r'image\s*\(\s*"([^"]+)"\s*(?:,\s*width\s*:\s*([\d.]+)%\s*)?\)')
TYP_FIGURE_RE = re.compile(r"#figure\s*\(", re.S)

IMG_EXTS = (".pdf", ".png", ".jpg", ".jpeg", ".eps")


def unit_to_pt(value: float, unit: str) -> float:
    return {"cm": value * 28.3465, "mm": value * 2.83465, "in": value * 72.0,
            "pt": value}.get(unit, value * 28.3465)


def parse_geometry(text: str):
    """解析 main.tex/typ 边距 -> textwidth(pt)。失败返回 None。"""
    if "geometry" in text:
        m = re.search(r"(?:\[[^\]]*\])?\s*\{geometry\}", text)
        if m:
            head = text[:m.start()]
            kv = re.search(r"\[([^\]]*)\]", head[::-1])
            if kv:
                kv_s = kv.group(1)[::-1]
                vals = {k: unit_to_pt(float(v), u) for k, v, u in TEX_GEOM_KV_RE.findall(kv_s)}
                if "left" in vals and "right" in vals:
                    return A4_W - vals["left"] - vals["right"]
    if "page(" in text and "margin:" in text:
        m = re.search(r"margin:\s*\([^,]*,\s*([\d.]+)(cm|mm|in|pt)\)", text)
        if m:
            side = unit_to_pt(float(m.group(1)), m.group(2))
            return A4_W - 2 * side
    return None


def width_to_pt(spec: str, textwidth: float) -> float:
    spec = spec.strip()
    if not spec:
        return textwidth
    if spec.endswith("\\textwidth") or spec.endswith("\\linewidth"):
        frac = re.match(r"([\d.]+)\\textwidth|([\d.]+)\\linewidth", spec)
        if frac:
            return textwidth * float(frac.group(1) or frac.group(2))
        return textwidth
    m = re.match(r"([\d.]+)\s*(cm|mm|in|pt)", spec)
    if m:
        return unit_to_pt(float(m.group(1)), m.group(2))
    return textwidth


def text_boxes(page):
    out = []
    for b in page.get_text("dict").get("blocks", []):
        if b.get("type") != 0:
            continue
        for l in b.get("lines", []):
            txt = "".join(s["text"] for s in l["spans"]).strip()
            if txt:
                out.append((fitz.Rect(l["bbox"]), txt))
    return out


def page_fill_ratio(page, top_margin=0.08, bottom_margin=0.10, band_pt=12.0):
    """页有效内容填充率（行带占用口径）：把内容区切成 12pt 横向条带，统计“含任何文本行/图片”的条带占比，
    并返回最大连续空白条带高度。该口径比“内容纵向跨度”更接近人眼判断——能抓出
    “顶部和底部都有内容、但中间或页底有大块空白”的页面。
    文本页 70-85%、图页 60-80% 为经验舒适带；占用率 <55% 或最大空带 >25% 内容高判偏空。
    """
    h = float(page.rect.height)
    area = fitz.Rect(0, h * top_margin, float(page.rect.width), h * (1 - bottom_margin))
    if area.is_empty or area.get_area() <= 0:
        return 0.0, 0.0
    rects = []
    for b in page.get_text("dict").get("blocks", []):
        if b.get("type") != 0:
            continue
        txt = "".join(s["text"] for l in b.get("lines", []) for s in l.get("spans", [])).strip()
        if txt:
            for l in b.get("lines", []):
                rects.append(fitz.Rect(l["bbox"]))
    for im in page.get_image_info():
        rects.append(fitz.Rect(im["bbox"]))
    rects = [r & area for r in rects]
    rects = [r for r in rects if not r.is_empty]
    if not rects:
        return 0.0, area.height
    n = max(1, int(area.height // band_pt))
    occupied = set()
    for i in range(n):
        band = fitz.Rect(area.x0, area.y0 + i * band_pt,
                         area.x1, min(area.y1, area.y0 + (i + 1) * band_pt))
        if any((r & band).get_area() > 0 for r in rects):
            occupied.add(i)
    max_gap = 0.0
    start = None
    for i in range(n):
        if i in occupied:
            if start is not None:
                max_gap = max(max_gap, (i - start) * band_pt)
                start = None
        elif start is None:
            start = i
    if start is not None:
        max_gap = max(max_gap, (n - start) * band_pt)
    return len(occupied) / n, max_gap


def min_font_pt(fig_pdf: Path):
    try:
        doc = fitz.open(str(fig_pdf))
    except Exception:
        return None
    best = None
    for page in doc:
        for b in page.get_text("dict").get("blocks", []):
            if b.get("type") != 0:
                continue
            for l in b.get("lines", []):
                for s in l["spans"]:
                    if len(s["text"].strip()) >= 1 and s["size"] > 0.5:
                        best = s["size"] if best is None else min(best, s["size"])
    doc.close()
    return best


class Gate:
    def __init__(self, ws: Path, engine: str, entry: str, pdf: Path,
                 figures_dir: Path, strict: bool):
        self.ws = ws
        self.engine = engine
        self.entry = entry
        self.pdf = pdf
        self.figures_dir = figures_dir
        self.strict = strict
        self.checks = []
        self.fails = []
        self.warns = []
        self.coverage = {"pdf": False, "source_refs": False, "freshness": False,
                         "fig_text_size": False, "page_fill": False}

    def add(self, cid, status, message):
        self.checks.append({"id": cid, "status": status, "message": message})
        if status == "FAIL":
            self.fails.append(f"{cid}: {message}")
        elif status == "WARN":
            self.warns.append(f"{cid}: {message}")

    # ---- PDF 层 ----
    def pdf_checks(self):
        if not self.pdf.is_file() or self.pdf.stat().st_size == 0:
            self.add("pdf_exists", "FAIL", f"PDF 不存在或为空: {self.pdf}")
            return
        self.coverage["pdf"] = True
        self.add("pdf_exists", "PASS", f"PDF 存在且非空（{self.pdf.stat().st_size} bytes）")
        try:
            doc = fitz.open(str(self.pdf))
        except Exception as exc:
            self.add("pdf_open", "FAIL", f"PDF 打开失败: {exc}")
            return
        self.add("page_count", "PASS", f"{doc.page_count} 页")
        bad, blank, near, bottom, low_fill, high_fill = [], [], [], [], [], []
        fills = []
        for i, page in enumerate(doc):
            if abs(page.rect.width - A4_W) > SIZE_TOL or abs(page.rect.height - A4_H) > SIZE_TOL:
                bad.append(i + 1)
            boxes = text_boxes(page)
            text = "".join(t for _, t in boxes)
            if not text:
                blank.append(i + 1)
            elif i > 0 and len(text) < NEAR_EMPTY:
                near.append((i + 1, len(text)))
            if text:
                region = fitz.Rect(0, A4_H * (1 - BOTTOM_BLANK_RATIO), A4_W, A4_H)
                clipped = [r for r, _ in boxes]
                area = 0.0
                for r in clipped:
                    inter = r & region
                    if not inter.is_empty:
                        area += inter.get_area()
                if area / region.get_area() < 0.05:
                    bottom.append(i + 1)
            ratio, max_gap = page_fill_ratio(page, FILL_TOP_MARGIN, FILL_BOTTOM_MARGIN)
            fills.append(ratio)
            area_h = A4_H * (1 - FILL_TOP_MARGIN - FILL_BOTTOM_MARGIN)
            if ratio < PAGE_FILL_LOW_WARN or max_gap > PAGE_FILL_GAP_WARN * area_h:
                low_fill.append((i + 1, round(ratio, 3), round(max_gap, 1)))
            elif ratio > PAGE_FILL_HIGH_WARN:
                high_fill.append((i + 1, round(ratio, 3)))
        doc.close()
        self.add("page_size", "FAIL" if bad else "PASS",
                 f"异常页面 {bad}" if bad else f"全部页面 A4（{A4_W}x{A4_H}pt）")
        self.add("blank_pages", "FAIL" if blank else "PASS",
                 f"整页空白 {blank}" if blank else "无整页空白")
        self.add("near_empty", "WARN" if near else "PASS",
                 f"近空页 {near}（<{NEAR_EMPTY} 字符）" if near else "无近空页")
        self.add("bottom_blank", "WARN" if bottom else "PASS",
                 f"底部大面积空白页 {bottom}（>{(1 - BOTTOM_BLANK_RATIO) * 100:.0f}%）" if bottom else
                 "无异常底部空白")
        self.coverage["page_fill"] = True
        avg_fill = (sum(fills) / len(fills)) if fills else 0.0
        fill_msg = (f"低填充页 {low_fill}（占用率<{PAGE_FILL_LOW_WARN:.0%} 或最大空带>"
                    f"{PAGE_FILL_GAP_WARN:.0%}内容高）| 高填充页 {high_fill}（>{PAGE_FILL_HIGH_WARN:.0%}）"
                    f"| 页均 {avg_fill:.1%}；处置纪律：低填充优先放大核心图（10-20%），禁止塞字/缩行距")
        if low_fill or high_fill:
            self.add("page_fill", "WARN", fill_msg)
        else:
            self.add("page_fill", "PASS", fill_msg)

    # ---- LaTeX 源适配器 ----
    def latex_sources(self):
        entry = Path(self.entry)
        if not entry.is_absolute():
            entry = self.ws / entry
        if not entry.is_file():
            self.add("entry_exists", "FAIL", f"入口不存在: {entry}")
            return [], [], None, None
        self.add("entry_exists", "PASS", f"入口存在: {entry}")
        seen, stack = set(), [entry]
        found, missing = [], []
        while stack:
            f = stack.pop()
            key = str(f.resolve())
            if key in seen:
                continue
            seen.add(key)
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for raw in TEX_INCLUDE_RE.findall(text):
                target = f.parent / raw.strip()
                if not target.suffix:
                    target = target.with_suffix(".tex")
                if not target.is_file():
                    missing.append(f"{raw.strip()}（自 {f.name}）")
                else:
                    found.append(target)
                    stack.append(target)
        # 收集全部 tex 文本用于引用/图/geometry
        all_text = ""
        for f in [entry, *found]:
            try:
                all_text += f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
        # graphicspath 目录（相对声明它的文件目录解析）
        gpaths = []
        for f in [entry, *found]:
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in TEX_GRAPHICSPATH_RE.finditer(text):
                for raw in re.findall(r"\{([^{}]+)\}", m.group(1)):
                    gp = Path(raw.strip())
                    if not gp.is_absolute():
                        gp = f.parent / gp
                    gpaths.append(gp)
        # includegraphics 引用（含 width 与所在文件）
        refs = []
        for f in [entry, *found]:
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in TEX_GRAPHICS_RE.finditer(text):
                refs.append((f, m.group(2).strip(), m.group(1) or ""))
        self.add("include_refs", "FAIL" if missing else "PASS",
                 f"include/input 缺失: {missing}" if missing else
                 f"include/input 引用全部存在（{len(found)} 个）")
        dupes = sorted({p.name for p in found if sum(1 for q in found if q.name == p.name) > 1})
        if dupes:
            self.add("include_dupes", "WARN", f"重复引入同名文件: {dupes}")
        return refs, gpaths, entry, all_text

    def resolve_figure(self, rel: str, src_file: Path, gpaths, cwd_dir=None):
        cand = [src_file.parent / rel]
        if cwd_dir is not None:
            cand.append(cwd_dir / rel)   # LaTeX 相对路径按编译工作目录（main.tex 所在目录）
        cand += [Path(d) / rel for d in gpaths]
        cand.append(self.ws / rel)
        for c in cand:
            if c.is_file():
                return c
            for ext in IMG_EXTS:
                q = c.with_suffix(ext)
                if q.is_file():
                    return q
        return None

    def figure_checks(self, refs, gpaths, textwidth, entry=None):
        if not refs:
            self.add("image_refs", "SKIP", "论文未引用任何图片")
            self.add("fig_text_size", "SKIP", "无被引图")
            return []
        missing, placed = [], []
        for src_file, rel, opts in refs:
            p = self.resolve_figure(rel, src_file, gpaths,
                                    cwd_dir=entry.parent if entry else None)
            if p is None:
                missing.append(f"{rel}（自 {src_file.name}）")
                continue
            wspec = ""
            m = re.search(r"width\s*=\s*([^,\]]+)", opts)
            if m:
                wspec = m.group(1).strip()
            wpt = width_to_pt(wspec, textwidth)
            placed.append((p, wpt, src_file.name))
        self.add("image_refs", "FAIL" if missing else "PASS",
                 f"图源缺失: {missing}" if missing else f"图源全部存在（{len(placed)} 张被引）")
        self.coverage["source_refs"] = True

        # caption 检查
        no_caption = []
        for f in {src for src, _, _ in refs} | {self.ws / self.entry}:
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in TEX_FIGURE_RE.finditer(text):
                if not TEX_CAPTION_RE.search(m.group(1)):
                    no_caption.append(f"{f.name}: 第 {text[:m.start()].count(chr(10)) + 1} 行 figure 无 caption")
        self.add("caption", "FAIL" if no_caption else "PASS",
                 f"figure 缺 caption: {no_caption}" if no_caption else "figure 均有 caption")

        # 有效字号
        bad, warn, skip = [], [], []
        effs = []
        for p, wpt, src_name in placed:
            if p.suffix.lower() != ".pdf":
                skip.append(f"{p.name}（位图，跳过字号检查）")
                continue
            try:
                doc = fitz.open(str(p))
                src_w = doc[0].rect.width
                doc.close()
            except Exception:
                skip.append(f"{p.name}（无法读取）")
                continue
            mf = min_font_pt(p)
            if mf is None or src_w <= 0:
                skip.append(f"{p.name}（无文字层）")
                continue
            eff = mf * wpt / src_w
            effs.append(eff)
            tag = f"{p.name}: 源字号 {mf:.1f}pt × 放置 {wpt:.0f}pt / 源宽 {src_w:.0f}pt = 有效 {eff:.1f}pt"
            if eff < FIG_FAIL_PT:
                bad.append(tag)
            elif eff < FIG_WARN_PT:
                warn.append(tag)
        self.coverage["fig_text_size"] = True
        if bad or warn:
            self.add("fig_text_size", "FAIL" if bad else "WARN", "; ".join(bad + warn))
        elif effs:
            self.add("fig_text_size", "PASS",
                     f"被引图源有效字号达标（最小 {min(effs):.1f}pt，{len(effs)} 张）")
        else:
            self.add("fig_text_size", "SKIP", "无含文字层的被引矢量图")

        # 并排检测（同一 figure 环境内两张图且各自 <0.5\textwidth）
        side = []
        for f in {src for src, _, _ in refs}:
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in TEX_FIGURE_RE.finditer(text):
                body = m.group(1)
                widths = re.findall(r"\\includegraphics\[[^\]]*width\s*=\s*([\d.]+)\\textwidth", body)
                if len(widths) >= 2 and all(float(w) < SIDE_BY_SIDE_MAX for w in widths):
                    side.append(f"{f.name}（{widths}）")
        self.add("side_by_side", "WARN" if side else "PASS",
                 f"并排小图建议改单列: {side}" if side else "无并排小图")
        if skip:
            self.add("fig_skipped", "PASS", f"跳过字号检查: {skip}")
        return placed

    def freshness(self, placed):
        if not self.pdf.is_file():
            self.add("freshness", "SKIP", "无 PDF")
            return
        pdf_mt = self.pdf.stat().st_mtime
        stale = []
        for f in self.ws.rglob("*.tex"):
            if f.stat().st_mtime > pdf_mt + 1:
                stale.append(str(f.relative_to(self.ws)))
        for p, _, _ in placed:
            if p.stat().st_mtime > pdf_mt + 1:
                stale.append(str(p.relative_to(self.ws)))
        self.coverage["freshness"] = True
        self.add("freshness", "FAIL" if stale else "PASS",
                 f"main.pdf 早于源/图（改后未重编译）: {stale}" if stale else
                 "main.pdf 晚于全部源文件与被引图源")
        # results 晚于图源 → WARN
        res_stale = []
        res_mt = max((p.stat().st_mtime for p in (self.ws / "results").rglob("*")
                      if p.is_file() and p.suffix.lower() in (".json", ".csv", ".xlsx")), default=0)
        for p, _, _ in placed:
            if p.suffix.lower() == ".pdf" and p.stat().st_mtime + 1 < res_mt:
                res_stale.append(p.name)
        if res_stale:
            self.add("results_fig_freshness", "WARN",
                     f"results 晚于被引图（图未随结果重生成）: {res_stale}")

    # ---- Typst 源适配器 ----
    def typst_sources(self):
        entry = Path(self.entry)
        if not entry.is_absolute():
            entry = self.ws / entry
        if not entry.is_file():
            self.add("entry_exists", "FAIL", f"入口不存在: {entry}")
            return [], None, None
        self.add("entry_exists", "PASS", f"入口存在: {entry}")
        seen, stack = set(), [entry]
        found = []
        while stack:
            f = stack.pop()
            key = str(f.resolve())
            if key in seen:
                continue
            seen.add(key)
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for raw in TYP_INCLUDE_RE.findall(text):
                target = f.parent / raw
                if not target.is_file():
                    self.add("include_refs", "FAIL", f"#include 缺失: {raw}（自 {f.name}）")
                else:
                    found.append(target)
                    stack.append(target)
        self.add("include_refs", "PASS", f"#include 引用全部存在（{len(found)} 个）") \
            if not any(c["id"] == "include_refs" and c["status"] == "FAIL" for c in self.checks) else None
        refs = []
        for f in [entry, *found]:
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in TYP_IMAGE_RE.finditer(text):
                rel = m.group(1).strip()
                refs.append((f, rel, m.group(2) or "100%"))
        self.coverage["source_refs"] = True
        return refs, entry, None

    def typst_figure_checks(self, refs, entry):
        if not refs:
            self.add("image_refs", "SKIP", "论文未引用任何图片")
            return []
        missing, placed = [], []
        for src_file, rel, wspec in refs:
            p = self.resolve_figure(rel, src_file, [])
            if p is None:
                missing.append(f"{rel}（自 {src_file.name}）")
            else:
                textwidth = A4_W - 2 * 85.039  # 3cm 边距
                wpt = textwidth * float(wspec) / 100.0
                placed.append((p, wpt, src_file.name))
        self.add("image_refs", "FAIL" if missing else "PASS",
                 f"图源缺失: {missing}" if missing else f"图源全部存在（{len(placed)} 张被引）")
        for f in [entry]:
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in TYP_FIGURE_RE.finditer(text):
                if "caption" not in m.group(0)[:400]:
                    self.add("caption", "WARN", f"{f.name} 存在 #figure 无 caption")
        self.figure_size_eval(placed)
        return placed

    def figure_size_eval(self, placed):
        bad, warn, skip = [], [], []
        for p, wpt, src_name in placed:
            if p.suffix.lower() != ".pdf":
                skip.append(f"{p.name}（位图）")
                continue
            try:
                doc = fitz.open(str(p))
                src_w = doc[0].rect.width
                doc.close()
            except Exception:
                skip.append(f"{p.name}（无法读取）")
                continue
            mf = min_font_pt(p)
            if mf is None or src_w <= 0:
                skip.append(f"{p.name}（无文字层）")
                continue
            eff = mf * wpt / src_w
            tag = f"{p.name}: 源 {mf:.1f}pt × {wpt:.0f}/{src_w:.0f} = 有效 {eff:.1f}pt"
            if eff < FIG_FAIL_PT:
                bad.append(tag)
            elif eff < FIG_WARN_PT:
                warn.append(tag)
        self.coverage["fig_text_size"] = True
        self.add("fig_text_size", "FAIL" if bad else ("WARN" if warn else "PASS"),
                 "; ".join(bad + warn) if (bad or warn) else "被引图源有效字号全部达标")
        if skip:
            self.add("fig_skipped", "PASS", f"跳过: {skip}")


def main(argv=None):
    gc.force_utf8()
    ap = argparse.ArgumentParser(description="v2 排版门禁（PDF 层 + 源适配器 + 有效字号）")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--engine", default=None)
    ap.add_argument("--entry", default=None)
    ap.add_argument("--pdf", default=None)
    ap.add_argument("--figures-dir", default=None)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--report", default=None)
    args = ap.parse_args(argv)

    ws = Path(args.workspace).resolve()
    engine = (args.engine or gc.manifest_engine(ws)).lower()
    entry = args.entry or gc.manifest_entry(ws)
    if not entry or entry == "unknown":
        for z, e in (("paper/main.tex", "latex"), ("paper/main.typ", "typst"),
                     ("paper/main.docx", "word")):
            if (ws / z).is_file():
                entry, engine = z, e
                break
    pdf = Path(args.pdf).resolve() if args.pdf else ws / "paper" / "main.pdf"
    figures_dir = Path(args.figures_dir).resolve() if args.figures_dir else ws / "figures"

    g = Gate(ws, engine, entry, pdf, figures_dir, args.strict)
    g.pdf_checks()

    supported = engine in ("latex", "typst")
    executed = False
    if supported and entry and (ws / entry).is_file():
        executed = True
        if engine == "latex":
            refs, gpaths, entry_f, all_text = g.latex_sources()
            textwidth = parse_geometry(all_text) or (A4_W - 2 * 85.039)
            placed = g.figure_checks(refs, gpaths, textwidth, entry=entry_f)
            g.freshness(placed)
        else:
            refs, entry_f, _ = g.typst_sources()
            placed = g.typst_figure_checks(refs, entry_f)
            g.freshness(placed)
    else:
        g.add("adapter_run", "FAIL" if args.strict else "WARN",
              f"engine={engine}：无源适配器（entry={entry}），strict 下 FAIL")
        if not supported:
            g.add("adapter_supported", "FAIL" if args.strict else "WARN",
                  f"engine={engine} 不支持（仅 latex/typst）")

    if args.strict and not executed:
        g.fails.append("adapter: executed=False 且 --strict")

    out = Path(args.report).resolve() if args.report else ws / "reports" / "gates" / "layout_gate.json"
    summary = {"fails": len(g.fails), "warns": len(g.warns), "pass": not g.fails,
               "executed": executed, "supported": supported}
    rep = {"gate": "layout_gate", "engine": engine, "adapter": engine if executed else "none",
           "entry": entry, "supported": supported, "executed": executed,
           "coverage": g.coverage, "checks": g.checks, "summary": summary,
           "strict": args.strict, "ran_at": gc.iso_now()}
    gc.save_json(out, rep)
    print(f"layout_gate: engine={engine} adapter={engine if executed else 'none'} "
          f"supported={supported} executed={executed} strict={args.strict}")
    for c in g.checks:
        print(f"  [{c['status']}] {c['id']}: {c['message']}")
    print(f"RESULT: {'FAIL' if g.fails else 'PASS'} (fails={len(g.fails)}, warns={len(g.warns)}, "
          f"coverage={g.coverage})")
    print(f"报告: {out}")
    return 1 if g.fails else 0


if __name__ == "__main__":
    sys.exit(main())
