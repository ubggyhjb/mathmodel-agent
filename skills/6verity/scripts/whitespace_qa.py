#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""whitespace_qa.py — 页面留白 QA（行带占用率 + 最大连续空带）。

设计背景：页面留白不能只看“内容最高点到最低点”的纵向跨度——顶部有标题、底部有
页码时，中间空半页也会显示 98% 占满。本工具把人眼判断拆成两个可计算指标：
  1) 行带占用率：内容区切成 12pt 横向条带，与任何文本行/图片 bbox 相交即记为占用，
     占用条带数 / 总条带数；文本页 70-85%、图页 60-80% 为舒适带。
  2) 最大连续空带：最长的连续未占用条带高度（pt）；超过内容区高度 25% 判偏空。
判定偏空：占用率 < --min-ratio，或最大空带 > --max-gap-ratio × 内容区高度。
处置纪律：偏空页优先放大核心图 10-20%，禁止塞字、缩行距、缩图、并图。

用法：
  python whitespace_qa.py --pdf paper/main.pdf
  python whitespace_qa.py --pdf paper/main.pdf --pages 5,14,17,19
  python whitespace_qa.py --pdf paper/main.pdf --strict     # 有偏空/偏满页时退出码 1

依赖：PyMuPDF（fitz）。
"""
from __future__ import annotations

import argparse
import sys

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

try:
    import fitz
except ImportError:
    print("FAIL 需要 PyMuPDF：pip install pymupdf", file=sys.stderr)
    sys.exit(2)

A4_W, A4_H = 595.27, 841.89


def page_fill(page, top_margin=0.08, bottom_margin=0.10, band_pt=12.0):
    """返回 (占用率, 最大连续空带 pt, 内容区高度 pt)。"""
    h = float(page.rect.height)
    area = fitz.Rect(0, h * top_margin, float(page.rect.width), h * (1 - bottom_margin))
    if area.is_empty or area.get_area() <= 0:
        return 0.0, area.height, area.height
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
        return 0.0, area.height, area.height
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
    return len(occupied) / n, max_gap, area.height


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--pages", default="", help="逗号分隔页码，留空=全部页")
    ap.add_argument("--top-margin", type=float, default=0.08)
    ap.add_argument("--bottom-margin", type=float, default=0.10)
    ap.add_argument("--band", type=float, default=12.0)
    ap.add_argument("--min-ratio", type=float, default=0.55)
    ap.add_argument("--max-gap-ratio", type=float, default=0.25)
    ap.add_argument("--max-ratio", type=float, default=0.99)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    try:
        doc = fitz.open(args.pdf)
    except Exception as exc:
        print(f"FAIL PDF 打开失败: {args.pdf} ({exc})", file=sys.stderr)
        return 2

    if args.pages:
        wanted = {int(x) for x in args.pages.split(",") if x.strip()}
        indices = [i for i in range(doc.page_count) if i + 1 in wanted]
    else:
        indices = list(range(doc.page_count))

    low, high, rows = [], [], []
    for i in indices:
        ratio, gap, area_h = page_fill(doc[i], args.top_margin, args.bottom_margin, args.band)
        rows.append((i + 1, ratio, gap))
        if ratio < args.min_ratio or gap > args.max_gap_ratio * area_h:
            low.append((i + 1, round(ratio, 3), round(gap, 1)))
        elif ratio > args.max_ratio:
            high.append((i + 1, round(ratio, 3)))
    doc.close()

    for p, ratio, gap in rows:
        print(f"page {p:>4}: fill={ratio:6.1%}  max_gap={gap:6.1f}pt")
    print("-" * 60)
    if low:
        print(f"[WARN] 偏空页 {low}（占用率<{args.min_ratio:.0%} 或空带>{args.max_gap_ratio:.0%}内容高）"
              "——优先放大核心图 10-20%，禁止塞字/缩行距")
    if high:
        print(f"[WARN] 偏满页 {high}（占用率>{args.max_ratio:.0%}）——检查是否拥挤")
    if not low and not high:
        print(f"[PASS] 无偏空/偏满页（{len(rows)} 页）")
    if args.strict and (low or high):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
