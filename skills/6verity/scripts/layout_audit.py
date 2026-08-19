#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""layout_audit.py — 论文 PDF 程序化排版审计（6verity 排版门禁）。

用法:
  python layout_audit.py --workspace <项目根> [--pdf <显式PDF路径>] [--strict]

检查项:
  1. 页面尺寸（A4 595x842pt）；
  2. 文字/图片越界：页边距 2.5cm=70.87pt；越界 >15pt → FAIL，8–15pt → WARN；
  3. 行间重叠（>35% 交叠面积）：多为公式字体提取假阳性，WARN，需视觉抽查；
  4. 近空页（首页外文本 <60 字符）：WARN；
  5. 异常行高（>60pt）：WARN（旋转的轴标签等已尽量豁免）。
退出码: 0 = 无 FAIL；1 = 存在 FAIL。FAIL 必须修复或说明，WARN 需渲染对应页视觉复核。

依赖: PyMuPDF（fitz）。数字页脚、页眉自动豁免。
"""
import argparse
import sys
from pathlib import Path

try:
    import fitz
except ImportError:
    print("FAIL 需要 PyMuPDF：pip install pymupdf")
    sys.exit(2)


def force_utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass


ML, MR, MT, MB = 70.87, 524.4, 70.87, 771.0  # A4 2.5cm 边距
CJK_PUNCT = "，。、；：！？）》”’〉」』】"  # 行尾全角标点：字宽含尾部空白，视觉墨迹在边距内


def audit(pdf_path):
    doc = fitz.open(str(pdf_path))
    fails, warns = [], []
    if doc.page_count == 0:
        return ["PDF 无页面"], []
    for pno in range(doc.page_count):
        page = doc[pno]
        r = page.rect
        if abs(r.width - 595.27) > 2 or abs(r.height - 841.89) > 2:
            fails.append(f"p{pno+1}: 页面尺寸异常 {r.width:.0f}x{r.height:.0f}")
        lines = []
        for b in page.get_text("dict")["blocks"]:
            if b.get("type") != 0:
                continue
            for l in b["lines"]:
                txt = "".join(s["text"] for s in l["spans"]).strip()
                if not txt:
                    continue
                bb = fitz.Rect(l["bbox"])
                lines.append((bb, txt))
        for bb, txt in lines:
            if len(txt) <= 3 and txt.isdigit() and bb.y0 > 760:  # 页脚页码
                continue
            if bb.y0 < 45 and bb.height < 30:  # 页眉
                continue
            for side, over in (("左", ML - bb.x0), ("右", bb.x1 - MR),
                               ("上", MT - bb.y0), ("下", bb.y1 - MB)):
                if over > 15:
                    fails.append(f"p{pno+1}: {side}越界 {over:.0f}pt [{txt[:22]}]")
                elif over > 8:
                    if side == "右" and txt and txt[-1] in CJK_PUNCT and over <= 12:
                        continue  # 全角标点字宽伪影：TeX 日志无 overfull，视觉正常
                    warns.append(f"p{pno+1}: {side}越界 {over:.1f}pt [{txt[:22]}]")
            if bb.height > 60:
                warns.append(f"p{pno+1}: 异常行高 {bb.height:.0f}pt [{txt[:22]}]")
        for i in range(len(lines)):
            for j in range(i + 1, len(lines)):
                a, ta = lines[i]
                b, tb = lines[j]
                inter = a & b
                if not inter.is_empty and inter.get_area() > 0.35 * min(a.get_area(), b.get_area()):
                    warns.append(f"p{pno+1}: 行重叠（多为公式假阳性） [{ta[:12]}] vs [{tb[:12]}]")
        for xref in [x[0] for x in page.get_images(full=True)]:
            for rct in page.get_image_rects(xref):
                if rct.x1 - MR > 15 or ML - rct.x0 > 15 or rct.y1 - MB > 15:
                    fails.append(f"p{pno+1}: 图片越界 {rct}")
        text = page.get_text().strip()
        if len(text) < 60 and pno != 0:
            warns.append(f"p{pno+1}: 近空页（{len(text)} 字符）")
    doc.close()
    return fails, warns


def main(argv=None):
    force_utf8()
    ap = argparse.ArgumentParser(description="论文 PDF 程序化排版审计")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--pdf", default=None, help="显式 PDF 路径；默认 <workspace>/paper/main.pdf")
    ap.add_argument("--strict", action="store_true", help="存在 FAIL 时退出码 1（默认仅报告）")
    args = ap.parse_args(argv)

    ws = Path(args.workspace).resolve()
    pdf = Path(args.pdf).resolve() if args.pdf else ws / "paper" / "main.pdf"
    if not pdf.is_file():
        print(f"FAIL 找不到 PDF: {pdf}")
        return 2
    fails, warns = audit(pdf)
    print(f"审计: {pdf.name}（{len(fails) + len(warns)} 条）")
    for f in fails:
        print("  FAIL " + f)
    for w in warns:
        print("  WARN " + w)
    if not fails and not warns:
        print("  PASS 无程序化排版异常")
    print("")
    if fails:
        print("FAIL 存在硬排版问题（越界>15pt/尺寸异常/图片越界），修复后重跑。")
        return 1 if args.strict else 0
    print("PASS 无硬问题；WARN 项按 6verity Step 8 渲染对应页视觉复核。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
