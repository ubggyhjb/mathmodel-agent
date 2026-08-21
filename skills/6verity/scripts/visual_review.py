#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""visual_review.py — v4.1（R-09）：视觉审稿输入生成 + PDF SHA 绑定。

把 PDF 前 N 页渲染成 contact sheet PNG 并记录 reviewed_pdf_sha256 到
reports/visual_review.json。Reviewer C 只对登记了相同 SHA 的审稿负责：
PDF 重编译后 SHA 改变 -> 旧视觉审稿自动失效（再跑本脚本重新登记）。

用法：
  python visual_review.py --workspace <项目根> [--pages 30] [--figures-dir figures]
  python visual_review.py --check --workspace <项目根>   # 校验 visual_review.json 的 SHA == 当前 PDF
输出：reports/visual_review.json（contact_sheet 路径 / reviewed_pdf_sha256 / 单图渲染列表）
"""
from __future__ import annotations

import argparse
import hashlib
import json
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


def main(argv=None):
    gc.force_utf8()
    ap = argparse.ArgumentParser(description="v4.1 视觉审稿输入 + PDF SHA 绑定")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--pages", type=int, default=30)
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

    # contact sheet（1-N 页）
    n = min(args.pages, doc.page_count)
    cols, rows, thumb_w = 5, 3, 170
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

    # 单图渲染（本轮新增/修改图由调用方传入 --figures；此处渲染 figures 目录下元数据最新 8 张）
    singles = []
    figs = ws / "figures"
    if figs.is_dir():
        metas = sorted(figs.glob("*.meta.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:8]
        for mp in metas:
            stem = mp.stem.replace(".meta", "")
            for ext in ("pdf", "png"):
                src = figs / f"{stem}.{ext}"
                if src.is_file() and src.suffix == ".pdf":
                    try:
                        fd = fitz.open(str(src))
                        pix = fd[0].get_pixmap(matrix=fitz.Matrix(2.2, 2.2))
                        out = out_dir / f"{stem}.png"
                        pix.save(str(out))
                        singles.append(str(out.relative_to(ws)))
                        break
                    except Exception:
                        continue

    sha = sha256_file(pdf)
    record = {
        "reviewed_pdf_sha256": sha,
        "pdf": str(pdf.relative_to(ws)),
        "pdf_pages": doc.page_count,
        "contact_sheet": str(sheet_png.relative_to(ws)),
        "single_figure_previews": singles,
        "generated_at": gc.iso_now(),
        "note": "R-09：Reviewer C 结果必须对应本登记 SHA；PDF 重编译后 SHA 改变则审稿失效（--check 校验）",
    }
    (ws / "reports" / "visual_review.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"VISUAL_REVIEW: contact sheet -> {sheet_png.relative_to(ws)}")
    print(f"  reviewed_pdf_sha256 = {sha}")
    print(f"  单图预览 {len(singles)} 张；运行 --check 校验 SHA 绑定")
    return 0


if __name__ == "__main__":
    sys.exit(main())
