#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""visual_review.py — v4.2（R-09 强化）：视觉审稿输入生成 + PDF SHA 绑定。

把 PDF 前 N 页渲染成 contact sheet PNG 并记录 reviewed_pdf_sha256 到
reports/visual_review.json。Reviewer C 只对登记了相同 SHA 的审稿负责：
PDF 重编译后 SHA 改变 -> 旧视觉审稿自动失效（再跑本脚本重新登记）。

v4.2（G-05/G-06）：
  - contact sheet 行数按请求页数动态计算（rows = ceil(n/cols)），并断言
    实际渲染页数 == 请求页数——旧版 5x3 只装 15 页，16-N 页落画布外（第 25 页重复错误曾在盲区）；
  - 单图预览不再取 mtime 最新 8 张：默认全审 figure_manifest 的 primary 图，
    另可用 --figures 传入本次变更集合（changed figures 全审），避免靠 mtime 猜。

用法：
  python visual_review.py --workspace <项目根> [--pages 30] [--figures q1,q2]
  python visual_review.py --check --workspace <项目根>   # 校验 visual_review.json 的 SHA == 当前 PDF
输出：reports/visual_review.json（contact_sheet 路径 / reviewed_pdf_sha256 / 单图渲染列表）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import gate_common as gc


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check(ws: Path, strict: bool):
    doc = gc.load_json(ws / "reports" / "visual_review.json", None)
    pdf = ws / "paper" / "main.pdf"
    if not isinstance(doc, dict) or not doc.get("reviewed_pdf_sha256"):
        msg = "reports/visual_review.json 缺失：视觉审稿尚未登记（R-09 强制绑定 PDF SHA）"
        print(f"  [{'FAIL' if strict else 'WARN'}] pdf_sha: {msg}")
        return 1 if strict else 0
    if not pdf.is_file():
        print("  [FAIL] pdf_sha: paper/main.pdf 缺失")
        return 1
    cur = sha256_file(pdf)
    if cur != doc["reviewed_pdf_sha256"]:
        print(f"  [FAIL] pdf_sha: 当前 PDF SHA {cur[:16]}… 与审稿登记 SHA "
              f"{doc['reviewed_pdf_sha256'][:16]}… 不一致——PDF 已重编译，旧视觉审稿自动失效")
        return 1
    print(f"  [PASS] pdf_sha: 审稿 SHA 与当前 PDF 一致（{cur[:16]}…）")
    return 0


def primary_figures(ws: Path) -> list:
    """figure_manifest 中 visual_priority=primary 的全部图 stem（G-06：primary 全审）。"""
    manifest = ws / "figures" / "figure_manifest.json"
    if not manifest.is_file():
        return []
    try:
        items = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [it.get("id", "") for it in items if it.get("visual_priority") == "primary"]


def main(argv=None):
    gc.force_utf8()
    ap = argparse.ArgumentParser(description="v4.2 视觉审稿输入 + PDF SHA 绑定")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--pages", type=int, default=30)
    ap.add_argument("--figures", default="",
                    help="逗号分隔的本次变更图 stem（changed figures 全审）；缺省 = primary 图全审")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    ws = Path(args.workspace).resolve()
    if args.check:
        return check(ws, True)

    try:
        import fitz
    except Exception:
        print("FAIL 需要 PyMuPDF：pip install pymupdf")
        return 2
    pdf = ws / "paper" / "main.pdf"
    if not pdf.is_file():
        print(f"FAIL 找不到 PDF: {pdf}")
        return 2
    doc = fitz.open(str(pdf))
    out_dir = ws / "reports" / "visual"
    out_dir.mkdir(parents=True, exist_ok=True)

    # contact sheet（1-N 页；行数按请求页数动态计算，禁止画布溢出）
    n = min(args.pages, doc.page_count)
    cols, thumb_w = 5, 170
    rows = max(1, math.ceil(n / cols))
    th = int(thumb_w * 841.89 / 595.27)
    sheet = fitz.open()
    page = sheet.new_page(width=cols * thumb_w, height=rows * th)
    for i in range(n):
        p = doc[i]
        r = p.rect
        s = thumb_w / r.width
        pix = p.get_pixmap(matrix=fitz.Matrix(s, s))
        x = (i % cols) * thumb_w
        y = (i // cols) * th
        page.insert_image(fitz.Rect(x, y, x + pix.width, y + pix.height), pixmap=pix)
    sheet_png = out_dir / "contact_sheet.png"
    page.get_pixmap().save(str(sheet_png))
    if n < args.pages and doc.page_count >= args.pages:
        print(f"WARN 请求 {args.pages} 页但 PDF 仅 {doc.page_count} 页，渲染 {n} 页")
    if n != min(args.pages, doc.page_count):
        print("FAIL contact sheet 渲染页数 != 请求页数")
        return 2

    # 单图渲染：primary 全审 ∪ --figures 变更集合（G-06：不再用 mtime 最新 8 张）
    requested = []
    for it in primary_figures(ws):
        if it and it not in requested:
            requested.append(it)
    for stem in [s.strip() for s in args.figures.split(",") if s.strip()]:
        if stem not in requested:
            requested.append(stem)
    singles = []
    missing_src = []
    figs = ws / "figures"
    for stem in requested:
        src = None
        for ext in ("pdf", "png"):
            cand = figs / f"{stem}.{ext}"
            if cand.is_file():
                src = cand
                break
        if src is None:
            missing_src.append(stem)
            continue
        if src.suffix == ".pdf":
            try:
                fd = fitz.open(str(src))
                pix = fd[0].get_pixmap(matrix=fitz.Matrix(2.2, 2.2))
                out = out_dir / f"{stem}.png"
                pix.save(str(out))
                singles.append(str(out.relative_to(ws)))
                continue
            except Exception:
                pass
        # png 源：直接复制为预览（无矢量重渲染）
        out = out_dir / f"{stem}.png"
        out.write_bytes(src.read_bytes())
        singles.append(str(out.relative_to(ws)))
    if missing_src:
        print(f"FAIL 以下被审图在 figures/ 无 pdf/png 源：{missing_src}")
        return 2
    # 渲染完整性断言（G-05）：请求的每个 stem 都应有预览
    if len(singles) != len(requested):
        print(f"FAIL 单图预览 {len(singles)}/{len(requested)} 张，请求集合未全审")
        return 2

    sha = sha256_file(pdf)
    record = {
        "reviewed_pdf_sha256": sha,
        "pdf": str(pdf.relative_to(ws)),
        "pdf_pages": doc.page_count,
        "contact_sheet": str(sheet_png.relative_to(ws)),
        "contact_sheet_pages": n,
        "contact_sheet_layout": f"{cols}x{rows}",
        "single_figure_previews": singles,
        "single_figure_requested": requested,
        "generated_at": gc.iso_now(),
        "note": "R-09：Reviewer C 结果必须对应本登记 SHA；PDF 重编译后 SHA 改变则审稿失效（--check 校验）",
    }
    (ws / "reports" / "visual_review.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"VISUAL_REVIEW: contact sheet -> {sheet_png.relative_to(ws)}（{cols}x{rows} 布局，{n} 页）")
    print(f"  reviewed_pdf_sha256 = {sha}")
    print(f"  单图预览 {len(singles)}/{len(requested)} 张；运行 --check 校验 SHA 绑定")
    return 0


if __name__ == "__main__":
    sys.exit(main())
