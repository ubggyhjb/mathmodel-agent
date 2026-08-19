
# -*- coding: utf-8 -*-
"""style_audit.py — 图表/排版/强调规范程序门（官方展示论文实证版）。

用法: python style_audit.py --workspace . [--strict]

检查项（证据口径见 references/visual-calibration.md）:
  1 摘要页完整：标题+摘要+关键词同页，摘要 ≤1 页
  2 摘要页页码 "1" 页脚居中（2026 规范）
  3 无目录页（2026 规范禁止）
  4 摘要含内容性加粗（引导语/模型名/关键数值/结论句；--strict 下 0 处 = FAIL，默认 WARN）
  5 正文加粗密度带 0.5-8%（官方中位 0.5-2%，0% 或 >8% = WARN）
  6 嵌图位图有效 DPI ≥ 300（矢量图不检查）
  7 图注在图下方（tex 静态检查）
  8 表格全部三线表（tex: tabular 必须含 toprule，禁止 hline 网格）
  9 正文页数 ≤ 30（摘要页之后至参考文献之前）
 10 AI 工具使用声明存在且位于参考文献前
 11 附录含"支撑材料文件列表"节
 12 附录含全部完整源程序（code/*.py 等必须逐一被 lstinputlisting/verbatiminput 引入；
   2026 规范：建模所用全部完整可运行源码，缺程序可能取消评奖资格）
 13 交付物新鲜度：main.pdf 必须晚于全部 .tex 与 figures/*.pdf（编译后仍改文件 =
   门禁结果不代表最终版 → FAIL）；results/*.json 晚于图 → WARN（结果改动后未重生成图）
 14 正文裸数字加粗（官方口径：关键数值须包进结论短语；正文表里逐个加粗数字是历史
   硬伤，--strict 下占比过高 = FAIL）

  15 摘要公式清零（93 篇官方优秀摘要语料零公式实证：摘要不出现含"="的公式本体，
    模型公式文字点名；参数符号与行内数值记号保留）
  16 LaTeX 排版细节（吸收 PaperFit/paper-typeset 实证规则）：16a ref/cite 前必须
    用不可断空格 ~；16b label 必须在 caption 之后（否则 ref 指向章节号）；
    16c 禁用断行符断段；16d 中文论文禁英文直引号

exit code: 有 FAIL = 1，全 PASS（允许 WARN）= 0。
"""
import sys, os, re, argparse

import fitz


def spans(d, i):
    out = []
    for b in d[i].get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                out.append(s)
    return out


def isbold(s):
    return bool(s["flags"] & 16) or bool(re.search(r"(Bold|Black|Hei|Heiti|黑体)", s["font"]))


def page_text(d, i):
    return d[i].get_text()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()
    ws = args.workspace
    pdf = os.path.join(ws, "paper", "main.pdf")
    if not os.path.exists(pdf):
        print("FAIL: paper/main.pdf 不存在（先编译论文再跑本门）")
        sys.exit(1)
    d = fitz.open(pdf)
    fails, warns = [], []

    # 正文字号众数（用于区分标题/正文/标签）
    sizes = []
    for i in range(min(6, d.page_count)):
        for s in spans(d, i):
            sz = round(s["size"], 1)
            if 9 <= sz <= 13:
                sizes.append(sz)
    body_sz = max(set(sizes), key=sizes.count) if sizes else 12

    # 1 摘要页完整
    p1 = page_text(d, 0)
    if not (len(p1.strip()) > 50 and "摘" in p1[:300] and re.search(r"关键词|关键字", p1)):
        fails.append("摘要页不完整（标题+摘要+关键词必须同页）")
    else:
        print("PASS: 摘要页结构完整（标题+摘要+关键词同页）")
    p2_top = page_text(d, 1)[:120] if d.page_count > 1 else ""
    if re.search(r"^\s*摘\s*要", p2_top):
        fails.append("摘要超过 1 页（2026 规范）")

    # 2 摘要页页码 1 页脚
    sp1 = spans(d, 0)
    foot = [s for s in sp1 if s["bbox"][1] > d[0].rect.height - 60]
    if not any(s["text"].strip() == "1" for s in foot):
        fails.append("摘要页页脚无页码 1（2026 规范：页码从摘要页起 1，页脚中部）")
    else:
        print("PASS: 摘要页页码 1 页脚居中")

    # 3 无目录页
    for i in range(min(3, d.page_count)):
        for s in spans(d, i):
            if s["text"].strip() in ("目录", "目 录", "目  录") and round(s["size"], 1) >= 14:
                fails.append(f"第{i+1}页存在目录页（2026 规范禁止目录）")
    if not any("目录页" in f for f in fails):
        print("PASS: 无目录页")

    # 4 摘要内容性加粗
    labels = {"摘要", "关键词", "关键词：", "关键字", "关键字：", "关键字:", "关键词:"}
    cb = [s for s in sp1 if isbold(s) and round(s["size"], 1) <= body_sz + 1.5
          and s["text"].strip() not in labels and len(s["text"].strip()) >= 2
          and round(s["size"], 1) < body_sz + 5]
    if not cb:
        (fails if args.strict else warns).append(
            "摘要无内容性加粗（官方通行做法：结论句/引导语/模型名/关键数值加粗，5-15%；E030 达 20%+）")
    else:
        print(f"PASS: 摘要内容性加粗 {len(cb)} 处")
        # 裸数字加粗检查：官方加粗以结论句为主；一串纯数字加粗 = 等于没加粗（本模式犯过的真实错误）
        pure = [s for s in cb if re.fullmatch(r"[0-9.%\-\u2013~\u2248+,\s]*", s["text"])]
        ratio = len(pure) / max(1, len(cb))
        if ratio > 0.5:
            (fails if args.strict else warns).append(
                f"摘要裸数字加粗占比 {ratio:.0%}（应把关键数值包进结论短语整体加粗，如'仅到达 27 个端点'，而非逐个加粗数字）")
        else:
            print(f"PASS: 摘要加粗以结论短语为主（裸数字占比 {ratio:.0%}）")

    # 5 正文加粗密度带
    bb = bt = 0
    for i in range(1, min(8, d.page_count)):
        for s in spans(d, i):
            sz = round(s["size"], 1)
            if 9 <= sz <= 16:
                bt += len(s["text"])
                if isbold(s) and sz <= body_sz + 1.5 and len(s["text"].strip()) >= 2:
                    bb += len(s["text"])
    ratio = 100 * bb / max(1, bt)
    if ratio <= 0.05:
        warns.append("正文加粗密度 ≈0%（官方中位 0.5-2%，关键结论句应加粗）")
    elif ratio > 8:
        warns.append(f"正文加粗密度 {ratio:.1f}% 超官方上限带 8%")
    else:
        print(f"PASS: 正文加粗密度 {ratio:.1f}%（官方带 0.5-8%）")

    # 14 正文裸数字加粗：官方口径是"关键数值包进结论短语"，表里逐个加粗数字等于没加粗。
    # 只认结果型数字（≥3 位整数 或 ≥2 位小数），排除 6.1.1 / 1.1 这类标题编号。
    # 行级判定：短语加粗（如"仅到达 27 个端点"）里数字用 Times Bold、汉字用黑体，
    # PDF 提取会拆成多个 span——只要同一行内存在非数字的加粗 span，就视为短语加粗；
    # 整行加粗内容全是裸数字（表格逐格加粗）才判违规。图内文字随嵌图缩放 <9pt 被过滤。
    bare_bold, phrase_bold_lines = [], 0
    pure_num_re = re.compile(r"-?(?:\d{3,}|\d+\.\d{2,})")
    for i in range(1, d.page_count):
        for b in d[i].get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                bold_spans = [s for s in l["spans"] if isbold(s)
                              and 9 <= round(s["size"], 1) <= body_sz + 1.5
                              and len(s["text"].strip()) >= 1]
                if not bold_spans:
                    continue
                nums = [s["text"].strip() for s in bold_spans
                        if pure_num_re.fullmatch(s["text"].strip())]
                if nums and len(nums) == len(bold_spans):
                    bare_bold.extend(nums)  # 该行加粗内容全是裸数字
                elif nums:
                    phrase_bold_lines += 1  # 短语加粗，数字包在结论里，合规
    nbold = len(bare_bold)
    ntotal = sum(1 for i in range(1, d.page_count)
                 for s in spans(d, i)
                 if isbold(s) and 9 <= round(s["size"], 1) <= body_sz + 1.5
                 and len(s["text"].strip()) >= 2)
    if nbold:
        uniq = "、".join(sorted(set(bare_bold))[:8])
        ratio2 = nbold / max(1, ntotal)
        msg = (f"正文裸数字加粗 {nbold}/{ntotal}（{ratio2:.0%}）：{uniq}——"
               f"应把关键数值包进结论短语整体加粗（如“仅到达 27 个端点”）")
        if args.strict and ratio2 > 0.5:
            fails.append(msg)
        else:
            warns.append(msg)
    else:
        print(f"PASS: 正文无裸数字加粗（内容性加粗 {ntotal} 处，短语含数字 {phrase_bold_lines} 行）")

    # 6 嵌图有效 DPI（豁免极端长宽比条带：matplotlib 矢量 PDF 中 colorbar 的 20px 渐变条，打印不可见）
    for i in range(d.page_count):
        pg = d[i]
        for im in pg.get_images(full=True):
            xref = im[0]
            try:
                info = d.extract_image(xref)
                rects = pg.get_image_rects(xref)
                if not rects or not info.get("width"):
                    continue
                w_in = rects[0].width / 72
                dpi = info["width"] / max(w_in, 1e-6)
                w, h = info["width"], info.get("height") or 1
                aspect = max(w, h) / max(min(w, h), 1)
                if aspect >= 5 and min(w, h) <= 60:
                    continue  # colorbar 渐变条带，非内容位图
                if dpi < 299:
                    fails.append(f"第{i+1}页嵌图有效 DPI {dpi:.0f} < 300（位图必须 300dpi 级，矢量图不检查）")
            except Exception:
                pass
    if not any("DPI" in f for f in fails):
        print("PASS: 嵌图分辨率达标")

    # 9 正文页数 ≤30
    ref_page = None
    for i in range(d.page_count):
        for s in spans(d, i):
            # ≥14pt 才是节标题本体；目录条目约 12pt，必须排除（否则目录页骗过检测）
            if s["text"].strip() in ("参考文献", "参 考 文 献") and round(s["size"], 1) >= 14:
                ref_page = i + 1
                break
        if ref_page:
            break
    body_pages = (ref_page or d.page_count + 1) - 2
    if body_pages > 30:
        fails.append(f"正文 {body_pages} 页 > 30（2026 规范）")
    else:
        print(f"PASS: 正文 {body_pages} 页 ≤ 30")

    # 10 AI 声明
    ai_page = None
    for i in range(d.page_count):
        if "AI 工具使用声明" in page_text(d, i):
            ai_page = i + 1
            break
    if ai_page is None:
        fails.append("缺 AI 工具使用声明（2026 试行规定：参考文献前）")
    elif ref_page and ai_page > ref_page:
        fails.append("AI 声明位于参考文献之后（必须在其前）")
    else:
        print(f"PASS: AI 工具使用声明在第 {ai_page} 页（参考文献前）")

    # 11 支撑材料文件列表
    full = "".join(page_text(d, i) for i in range(d.page_count))
    if "支撑材料文件列表" not in full:
        fails.append("附录缺支撑材料文件列表（2026 规范）")
    else:
        print("PASS: 附录含支撑材料文件列表")

    d.close()

    # --- tex 静态检查 ---
    texfiles = []
    for root, dirs, files in os.walk(os.path.join(ws, "paper")):
        for f in files:
            if f.endswith(".tex"):
                texfiles.append(os.path.join(root, f))
    alltex = ""
    for tf in texfiles:
        with open(tf, encoding="utf-8") as fh:
            alltex += f"\n%%FILE%%{tf}\n" + fh.read()

    # 7 图注位置
    fig_bad = []
    for m in re.finditer(r"\\begin\{figure\}(.*?)\\end\{figure\}", alltex, re.S):
        body = m.group(1)
        imgs = re.findall(r"\\includegraphics", body)
        caps = re.findall(r"\\caption", body)
        if imgs and not caps:
            fig_bad.append("figure 缺 caption")
        elif imgs and caps and body.rfind("\\caption") < body.rfind("\\includegraphics"):
            fig_bad.append("caption 在图上方（官方规范：图注下方居中）")
    for x in sorted(set(fig_bad)):
        fails.append(x)
    if not fig_bad:
        print("PASS: 图注位置（图下居中）")

    # 8 表格三线表
    grid_bad = 0
    for m in re.finditer(r"\\begin\{tabular\}(.*?)\\end\{tabular\}", alltex, re.S):
        body = m.group(1)
        if "\\toprule" not in body or "\\hline" in body:
            grid_bad += 1
    if grid_bad:
        fails.append(f"{grid_bad} 个表格非三线表（必须 booktabs toprule/midrule/bottomrule，禁 hline 网格）")
    else:
        print("PASS: 表格全部三线表")

    # 12 附录源码全文（2026 规范：建模所用全部完整可运行源码，缺程序可能取消评奖资格）
    # 历史教训：附录只放 4 段"核心摘录"被认定违规——code/ 下每个源码文件都必须被
    # lstinputlisting / verbatiminput 完整引入（引入即全文，摘录不算）。
    code_dir = os.path.join(ws, "code")
    code_exts = (".py", ".m", ".R", ".jl", ".cpp", ".c", ".java", ".go", ".rs")
    if os.path.isdir(code_dir):
        code_files = [f for f in os.listdir(code_dir)
                      if f.endswith(code_exts) and not f.startswith((".", "_"))]
        missing_code = []
        for cf in sorted(code_files):
            base = os.path.splitext(cf)[0]
            pat = (r"\\(?:lstinputlisting|verbatiminput)(?:\[[^\]]*\])?\{[^}]*"
                   + re.escape(base) + r"(?=[.}/]|$|[^A-Za-z0-9_])")
            if not re.search(pat, alltex):
                missing_code.append(cf)
        if missing_code:
            (fails if args.strict else warns).append(
                "附录未包含全部源程序全文: " + ", ".join(missing_code)
                + "（2026 规范：建模所用全部完整可运行源码须入附录）")
        else:
            print(f"PASS: 附录含全部源程序全文（{len(code_files)} 个）")
    else:
        print("INFO 无 code/ 目录，跳过附录源码全文检查")

    # 13 交付物新鲜度：门禁结果必须对应"最终版"。
    # 历史教训：改完 tex/图/结果后没重新编译+没重跑门，交付物与"全 PASS"报告对不上。
    # a) main.pdf 必须晚于全部 .tex 与 figures/*.pdf —— 否则编译不是最终版（FAIL）；
    # b) results/*.json 晚于图 —— 结果改动后未重生成图，图内数字可能过期（WARN）。
    pdf_mt = os.path.getmtime(pdf)
    stale_src = [os.path.relpath(tf, ws) for tf in texfiles if os.path.getmtime(tf) > pdf_mt + 1]
    fig_dir = os.path.join(ws, "figures")
    if os.path.isdir(fig_dir):
        fig_files = [os.path.join(fig_dir, f) for f in os.listdir(fig_dir)
                     if f.lower().endswith(".pdf")]
        stale_src += [os.path.relpath(f, ws) for f in fig_files if os.path.getmtime(f) > pdf_mt + 1]
    else:
        fig_files = []
    if stale_src:
        fails.append("交付物不是最终版：编译后仍有源文件被修改（"
                     + "; ".join(stale_src[:5])
                     + "）——修改后必须重新编译并重跑全部程序门禁")
    else:
        print("PASS: main.pdf 为最新编译（tex/图无后续修改）")
    res_dir = os.path.join(ws, "results")
    if os.path.isdir(res_dir) and fig_files:
        rjs = [os.path.join(res_dir, f) for f in os.listdir(res_dir)
               if f.lower().endswith(".json")]
        if rjs:
            newest_res = max(os.path.getmtime(f) for f in rjs)
            stale_figs = [os.path.relpath(f, ws) for f in fig_files
                          if os.path.getmtime(f) < newest_res - 1]
            if stale_figs:
                warns.append(f"{len(stale_figs)} 张图早于最新结果 JSON"
                             "（结果改动后未重生成图，图内数字可能过期）: "
                             + "; ".join(stale_figs[:5]))

    # 15 摘要公式清零（93 篇官方优秀摘要语料零公式实证）：摘要不出现含 "=" 的公式本体，
    # 模型公式一律文字点名（如"推进速度由流量守恒确定"）；参数符号与行内数值记号保留。
    abs_m = re.search(r"\\abstractcn\{%(.*?)\}\{%", alltex, re.S)
    if abs_m:
        abs_eqs = re.findall(r"\$[^$]*=[^$]*\$", abs_m.group(1))
        if abs_eqs:
            fails.append(f"摘要出现公式本体 {len(abs_eqs)} 处（{abs_eqs[0][:20]}...）"
                         "——官方优秀语料零公式，模型公式应文字点名，参数符号与数值可作行内记号保留")
        else:
            print("PASS: 摘要无公式本体（公式文字点名）")
    else:
        print("INFO 未找到 \\abstractcn 块，跳过摘要公式检查")

    # 16 LaTeX 排版细节（吸收 PaperFit/paper-typeset 的实证规则，只取中文论文适用项）：
    # 16a \ref/\cite 前必须用不可断空格 ~（"图 7"断行 = 最常见排版缺陷）
    bad_ref = re.findall(r"[^\s~\[%(\\] +\\ref\{", alltex)
    bad_cite = re.findall(r"[^\s~\[%(\\] +\\cite\{", alltex)
    if bad_ref or bad_cite:
        fails.append(f"\\ref/\\cite 前缺不可断空格 ~：{len(bad_ref) + len(bad_cite)} 处"
                     "（'图 7' 被断行是常见排版缺陷，应写'图~\\ref'）")
    else:
        print("PASS: \\ref/\\cite 前均为不可断空格")
    # 16b \label 必须在 \caption 之后（error 级：放前面时 \ref 会解析成章节号）
    # 双子图（同一 float 内两个 caption）判据：label 前必须已出现过至少一个 \caption
    lab_bad = []
    for m in re.finditer(r"\\begin\{(figure|table)\}(.*?)\\end\{\1\}", alltex, re.S):
        body = m.group(2)
        for lm in re.finditer(r"\\label\{[^}]*\}", body):
            if not re.search(r"\\caption", body[:lm.start()]):
                lab_bad.append(lm.group(0))
    if lab_bad:
        fails.append(f"\\label 位于 \\caption 之前 {len(lab_bad)} 处（{lab_bad[0]}..."
                     "——\\ref 将指向章节号而非图表号）")
    else:
        print("PASS: \\label 均在 \\caption 之后")
    # 16c 用反斜杠断行符结束段落（会破坏段落缩进并产生 underfull）
    bad_para = re.findall(r"[。；]\\\\", alltex)
    if bad_para:
        warns.append(f"用断行符结束段落 {len(bad_para)} 处（应空行分段，断行符只用于表格/对齐环境）")
    else:
        print("PASS: 无断行符断段")
    # 16d 正文出现英文直引号（中文论文应使用中文引号；代码块与 % 注释内除外）
    tex_nocode = re.sub(r"\\begin\{(?:lstlisting|verbatim|minted)\}.*?"
                        r"\\end\{(?:lstlisting|verbatim|minted)\}", "", alltex, flags=re.S)
    tex_nocode = "\n".join(line.split("%", 1)[0] for line in tex_nocode.splitlines())
    straight_q = len(re.findall(r"[^\s]\"[A-Za-z\u4e00-\u9fff]", tex_nocode)) + \
                 len(re.findall(r"[A-Za-z\u4e00-\u9fff]\"[^\s]", tex_nocode))
    if straight_q:
        warns.append(f"正文疑似使用英文直引号 {straight_q} 处（中文论文应使用中文引号）")
    else:
        print("PASS: 无英文直引号")

    print()
    for w in warns:
        print("WARN:", w)
    for f in fails:
        print("FAIL:", f)
    mode = "--strict" if args.strict else "默认"
    print(f"RESULT: {'FAIL' if fails else 'PASS'}（{mode}模式，WARN {len(warns)}，FAIL {len(fails)}）")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

