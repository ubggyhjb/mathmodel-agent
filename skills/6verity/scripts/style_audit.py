
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
import sys, os, re, argparse, json
from pathlib import Path

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)
import gate_common as gc

import fitz


def load_style_policy():
    policy = gc.load_policy()
    if not policy:
        p = Path(_SCRIPT_DIR).parent / "style_policy.json"
        try:
            with p.open(encoding="utf-8") as fh:
                policy = json.load(fh)
        except Exception:
            policy = {}
    return policy


def autodetect_engine(ws):
    if any(Path(ws).rglob("*.typ")):
        return "typst"
    if any(Path(ws, "paper").rglob("*.tex")):
        return "latex"
    if any(Path(ws).rglob("*.docx")):
        return "word"
    return "unknown"


def abstract_bold_metrics(sp1, body_sz):
    keyword = False
    bold_chars = body_chars = 0
    bare = total = 0
    labels = {"关键词", "关键词：", "关键词:", "关键字", "关键字：", "关键字:"}
    for s in sp1:
        text = s.get("text", "")
        stripped = text.strip()
        sz = round(s.get("size", 0), 1)
        if not keyword and (stripped in labels or re.fullmatch(r"关键词\s*[:：]?", stripped)):
            keyword = True
            continue
        if keyword or sz >= 15 or (sz >= 13 and stripped == "摘要"):
            continue
        if 9 <= sz <= 13:
            n = len(text.strip())
            body_chars += n
            if isbold(s) and sz <= body_sz + 1.5 and n >= 1:
                bold_chars += n
                total += n
                if re.fullmatch(r"[0-9.%\-\u2013~\u2248+,\s]*", text):
                    bare += n
    return bold_chars, body_chars, bare / max(1, total)


def appendix_hash_check(ws, texfiles, policy, entry_file=None):
    code_dir = Path(ws) / "code"
    exts = tuple(policy.get("appendix", {}).get("full_source_exts", []))
    if not code_dir.is_dir():
        return [], 0, "无 code/ 目录"
    code_files = sorted(p for p in code_dir.iterdir()
                        if p.is_file() and p.suffix in exts
                        and not p.name.startswith((".", "_")))
    included_hashes = set()
    unresolved = []
    cmd_re = re.compile(r"\\(?:lstinputlisting|verbatiminput)(?:\[[^\]]*\])?\{([^{}]+)\}")
    for tf_raw in texfiles:
        tf = Path(tf_raw)
        try:
            text = tf.read_text(encoding="utf-8")
        except Exception:
            continue
        for match in cmd_re.finditer(text):
            raw = match.group(1).strip()
            target = Path(raw)
            # LaTeX 相对路径按编译工作目录（main.tex 所在目录）解析，其次引用文件目录，再其次工作区根
            candidates = []
            if entry_file is not None:
                candidates.append(entry_file.parent / target)
            candidates += [tf.parent / target, Path(ws) / target]
            resolved = next((p for p in candidates if p.is_file()), None)
            if resolved is None:
                unresolved.append(raw)
            else:
                try:
                    included_hashes.add(gc.sha256_file(resolved))
                except OSError:
                    unresolved.append(raw)
    missing = [p.name for p in code_files if gc.sha256_file(p) not in included_hashes]
    missing.extend("unresolved:" + x for x in unresolved)
    return sorted(set(missing)), len(code_files), None


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
    gc.force_utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--report", default=None)
    args = ap.parse_args()
    ws = os.path.abspath(args.workspace)
    report_file = os.path.abspath(args.report or os.path.join(ws, "reports", "gates", "style_audit.json"))
    policy = load_style_policy()
    manifest_engine = gc.manifest_engine(ws)
    engine = manifest_engine if manifest_engine != "unknown" else autodetect_engine(ws)
    coverage = {"typ_files": len(list(Path(ws).rglob("*.typ"))), "skipped": []}
    pdf = os.path.join(ws, "paper", "main.pdf")
    if not os.path.exists(pdf):
        print("FAIL: paper/main.pdf 不存在（先编译论文再跑本门）")
        sys.exit(1)
    d = fitz.open(pdf)
    coverage["pdf_pages"] = d.page_count
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

    # 4 摘要内容性加粗与真实字符比例（第一页不是摘要页则整项 SKIP）
    abstract_ratio = None
    abstract_bare_ratio = None
    if not (len(p1.strip()) > 50 and "摘" in p1[:300] and re.search(r"关键词|关键字", p1)):
        coverage["skipped"].append("abstract_bold_ratio:not_abstract_page")
    else:
        bold_chars, body_chars, abstract_bare_ratio = abstract_bold_metrics(sp1, body_sz)
        abstract_ratio = bold_chars / max(1, body_chars)
        if abstract_ratio < policy.get("abstract", {}).get("bold_ratio_min", 0.05) or abstract_ratio > policy.get("abstract", {}).get("bold_ratio_max", 0.15):
            fails.append(f"摘要内容性加粗率 {abstract_ratio:.1%}（应在 5%-15%）")
        else:
            print(f"PASS: 摘要内容性加粗率 {abstract_ratio:.1%}（5%-15%）")
        if abstract_bare_ratio > policy.get("abstract", {}).get("bare_digit_ratio_max", 0.5):
            warns.append(f"摘要裸数字加粗占比 {abstract_bare_ratio:.0%}（应把关键数值包进结论短语整体加粗）")
        else:
            print(f"PASS: 摘要加粗以结论短语为主（裸数字占比 {abstract_bare_ratio:.0%}）")

    # 5 正文加粗密度带
    bb = bt = 0
    for i in range(1, min(8, d.page_count)):
        for s in spans(d, i):
            sz = round(s["size"], 1)
            if 9 <= sz <= 16:
                bt += len(s["text"])
                if isbold(s) and sz <= body_sz + 1.5 and len(s["text"].strip()) >= 2:
                    bb += len(s["text"])
    body_bold_ratio = bb / max(1, bt)
    body_min = policy.get("body", {}).get("bold_ratio_min", 0.005)
    body_max = policy.get("body", {}).get("bold_ratio_max", 0.08)
    if body_bold_ratio < body_min:
        warns.append(f"正文加粗密度 {body_bold_ratio:.1%} 低于 {body_min:.1%}")
    elif body_bold_ratio > body_max:
        warns.append(f"正文加粗密度 {body_bold_ratio:.1%} 超上限 {body_max:.1%}")
    else:
        print(f"PASS: 正文加粗密度 {body_bold_ratio:.1%}（官方带 {body_min:.1%}-{body_max:.0%}）")

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
                dpi_min = policy.get("figures", {}).get("dpi_min", 300)
                if dpi < dpi_min - 1:
                    fails.append(f"第{i+1}页嵌图有效 DPI {dpi:.0f} < {dpi_min}（位图必须达标，矢量图不检查）")
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
    max_pages = policy.get("body", {}).get("max_pages", 30)
    if body_pages > max_pages:
        fails.append(f"正文 {body_pages} 页 > {max_pages}（规范）")
    else:
        print(f"PASS: 正文 {body_pages} 页 ≤ {max_pages}")

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
        ai_text = re.sub(r"\s+", "", page_text(d, ai_page - 1))
        ai_policy = policy.get("ai_decl", {})
        not_used = re.sub(r"\s+", "", ai_policy.get("not_used", ""))
        used_prefix = re.sub(r"\s+", "", ai_policy.get("used_prefix", ""))
        used_suffix = re.sub(r"\s+", "", ai_policy.get("used_suffix", ""))
        valid_ai = (not_used and not_used in ai_text) or (used_prefix and used_prefix in ai_text and used_suffix and used_suffix in ai_text)
        if not valid_ai:
            fails.append("AI 工具使用声明内容不符合 policy 定句")
        elif ref_page and ai_page > ref_page:
            fails.append("AI 声明位于参考文献之后（必须在其前）")
        else:
            print(f"PASS: AI 工具使用声明在第 {ai_page} 页（内容及位置合规）")

    # 11 支撑材料文件列表
    full = "".join(page_text(d, i) for i in range(d.page_count))
    if "支撑材料文件列表" not in full:
        fails.append("附录缺支撑材料文件列表（2026 规范）")
    else:
        print("PASS: 附录含支撑材料文件列表")

    # ---- v3 粗体系统 v2 + 页面视觉密度：须在 d.close() 前计算 ----
    bold_v2 = bold_metrics_v2(d, body_sz)
    vis = page_visual_density(d)
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

    if engine == "typst":
        coverage["skipped"].extend(["latex:figure_caption", "latex:three_line_tables", "latex:appendix_full_source", "latex:abstract_formula", "latex:typeset_details"])
    elif not texfiles:
        coverage["skipped"].extend(["latex:figure_caption", "latex:three_line_tables", "latex:appendix_full_source", "latex:abstract_formula", "latex:typeset_details"])

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

    # 12 附录源码全文：按引用文件内容 hash 校验
    if engine == "typst" or not texfiles:
        print("INFO 跳过 LaTeX 附录源码全文检查（由 layout_gate 或其他门禁承担）")
    else:
        missing_code, code_count, no_code = appendix_hash_check(
            ws, texfiles, policy,
            entry_file=(Path(ws) / "paper" / "main.tex") if (Path(ws) / "paper" / "main.tex").is_file() else None)
        if no_code:
            print("INFO 无 code/ 目录，跳过附录源码全文检查")
        elif missing_code:
            fails.append("附录未包含全部源程序全文: " + ", ".join(missing_code)
                         + "（要求引入内容 sha256 完全相同）")
        else:
            print(f"PASS: 附录含全部源程序全文（{code_count} 个，内容 hash 命中）")

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
        # 只把"成对的 $...$ 片段内含 ="判为公式本体；跨段吞并的误匹配（旧 regex 缺陷）不再发生
        abs_eqs = [seg for seg in re.findall(r"\$[^$]*\$", abs_m.group(1)) if "=" in seg]
        if abs_eqs:
            fails.append(f"摘要出现公式本体 {len(abs_eqs)} 处（{abs_eqs[0][:20]}...）"
                         "——官方优秀语料零公式，模型公式应文字点名，参数符号与数值可作行内记号保留")
        else:
            print("PASS: 摘要无公式本体（公式文字点名）")
    else:
        print("INFO 未找到 \\abstractcn 块，跳过摘要公式检查")

    # 15b 摘要 CJK 字数硬带（600-900，style_policy）与"针对问题X"锚点（规范 4 个）
    if abs_m:
        abs_text = abs_m.group(1)
        cjk_len = len(re.findall(r"[\u4e00-\u9fff]", abs_text))
        anchors = re.findall(r"(?:针对)?问题[一二三四五六七八九十\d]", abs_text)
        coverage["abstract_cjk_len"] = cjk_len
        coverage["abstract_anchors"] = len(anchors)
        lo = int(policy.get("abstract", {}).get("min_chars", 600))
        hi = int(policy.get("abstract", {}).get("max_chars", 900))
        if cjk_len < lo or cjk_len > hi:
            fails.append(f"摘要 CJK 字数 {cjk_len} 不在 {lo}-{hi}（5writing 硬带）")
        else:
            print(f"PASS: 摘要 CJK 字数 {cjk_len}（{lo}-{hi}）")
        if len(anchors) != 4:
            warns.append(f"摘要'针对问题X'锚点 {len(anchors)} 个（规范 4 个；总起段应并入问题一段）")
        else:
            print("PASS: 摘要逐问锚点 4 个")

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

    result_pass = not fails
    # ---- v3 粗体系统 v2 / 视觉密度：warns 汇入（计算见 d.close() 前） ----
    for msg in bold_v2["warns"]:
        warns.append(msg)
    for msg in bold_v2["fails"]:
        fails.append(msg)
    for msg in vis["warns"][:3]:
        warns.append(msg)
    report = {
        "gate": "style_audit",
        "engine": engine,
        "coverage": {**coverage, "abstract_bold_ratio": abstract_ratio,
                     "content_bold_ratio": abstract_ratio,
                     "abstract_bare_digit_ratio": abstract_bare_ratio,
                     "body_bold_ratio": body_bold_ratio,
                     "bold_v2": bold_v2["summary"],
                     "page_density": vis["pages"]},
        "content_bold_ratio": abstract_ratio,
        "body_bold_ratio": body_bold_ratio,
        "abstract_bare_digit_ratio": abstract_bare_ratio,
        "fails": fails,
        "warns": warns,
        "summary": {"pass": result_pass, "strict": bool(args.strict)},
        "ran_at": gc.iso_now(),
        "report": report_file,
    }
    try:
        gc.save_json(report_file, report)
    except Exception as exc:
        warns.append(f"报告写入失败: {exc}")
    print()
    for w in warns:
        print("WARN:", w)
    for f in fails:
        print("FAIL:", f)
    mode = "--strict" if args.strict else "默认"
    print(f"RESULT: {'FAIL' if fails else 'PASS'}（{mode}模式，WARN {len(warns)}，FAIL {len(fails)}）")
    sys.exit(1 if fails else 0)


# ---------- v3：粗体系统 v2 指标（_mathmode.docx 十一条） ----------

_SYMBOL_BOLD_RE = re.compile(
    r"^(?:p\s*[<>=]?\s*0?\.?\d+|r\s*[<>=]?\s*-?0?\.?\d+"
    r"|R\s*2|R²|CI|SE|SD|adj\s*R\s*2|n\s*[=<>]?\s*\d+|"
    r"-?\d+(?:\.\d+)?\s*%?)$")


def bold_metrics_v2(d, body_sz):
    """粗体系统 v2：span 计数/平均长度/孤立数值与符号粗体/每块密度。
    全部 WARN/Fail 级：孤立 p 值/r/R²/CI/SE 加粗、短数字粗体、一段多短语。"""
    warns, fails = [], []
    n_spans = total_chars = 0
    isolated = []
    short_num_spans = 0
    per_block_bold = []
    for i in range(1, d.page_count):
        for b in d[i].get_text("dict")["blocks"]:
            if b.get("type") != 0:
                continue
            nb = 0
            for l in b.get("lines", []):
                for s in l["spans"]:
                    if not isbold(s) or not 9 <= round(s["size"], 1) <= body_sz + 1.5:
                        continue
                    t = s["text"].strip()
                    if not t:
                        continue
                    n_spans += 1
                    total_chars += len(t)
                    nb += 1
                    if _SYMBOL_BOLD_RE.match(t):
                        isolated.append(t)
                        if i + 1 <= 2 or len(t) <= 6:
                            short_num_spans += 1
            if nb >= 1:
                per_block_bold.append((i + 1, nb))
    avg_len = total_chars / max(1, n_spans)
    if isolated:
        warns.append(
            f"粗体系统 v2：孤立符号/数值加粗 {len(isolated)} 处（p 值、r、R²、CI、SE 或裸数字不得单独加粗，"
            f"示例：{sorted(set(isolated))[:6]}）——规范禁止，建议包进结论短语或取消加粗")
    if short_num_spans:
        warns.append(f"粗体系统 v2：长度 <6 且主要为数字/符号的加粗 span {short_num_spans} 处（内容性粗体应为结论短语）")
    dense_blocks = [(pg, nb) for pg, nb in per_block_bold if nb >= 3]
    if len(dense_blocks) > max(2, 0.02 * len(per_block_bold)):
        warns.append(
            f"粗体系统 v2：一个文本块内 ≥3 处加粗的密集块 {len(dense_blocks)} 处（"
            f"前 3：{dense_blocks[:3]}）——规范建议一段最多 1 处内容性粗体")
    return {
        "warns": warns, "fails": fails,
        "summary": {"n_bold_spans": n_spans, "avg_span_len": round(avg_len, 2),
                    "isolated_numeric_bold": isolated, "dense_blocks": len(dense_blocks)},
    }


# ---------- v3：页面视觉密度/视觉熵（_mathmode.docx 二十条） ----------

def page_visual_density(d):
    """每页统计 图数/表数/字号层级/粗体数/公式密度，页级 density=high 时 WARN。
    公式数按 '(',')' 数学文本块近似：统计含较多符号的文本块。"""
    pages = []
    warns = []
    n_high = 0
    for i in range(d.page_count):
        pg = d[i]
        text = page_text(d, i)
        n_images = len(pg.get_images(full=True))
        n_fonts = len({round(s["size"], 1) for s in spans(d, i) if 8 <= round(s["size"], 1) <= 24})
        n_bold = sum(1 for s in spans(d, i) if isbold(s) and len(s["text"].strip()) >= 2)
        n_tables = len(re.findall(r"表\s*\d+", text))
        n_figs = len(re.findall(r"图\s*\d+", text))
        n_math = text.count("(") + text.count(")") + text.count("=")
        score = (1 if n_images >= 2 else 0) + (1 if n_tables >= 2 else 0) + \
                (1 if n_fonts >= 5 else 0) + (1 if n_bold >= 8 else 0) + \
                (1 if n_math >= 60 else 0)
        density = "high" if score >= 4 else ("medium" if score >= 2 else "low")
        if density == "high":
            n_high += 1
            warns.append(
                f"视觉密度 high（第{i+1}页）：图 {n_images} / 表 {n_tables} / 字号层级 {n_fonts} / "
                f"粗体 {n_bold}——建议拆页或降级次要元素（视觉熵控，参照正文最舒服页面）")
        pages.append({"page": i + 1, "images": n_images, "tables": n_tables,
                      "font_levels": n_fonts, "bold_spans": n_bold,
                      "math_sym": n_math, "density": density})
    return {"pages": pages, "warns": warns, "n_high": n_high}


if __name__ == "__main__":
    main()

