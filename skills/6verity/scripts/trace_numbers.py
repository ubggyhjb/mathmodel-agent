
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""trace_numbers.py — 论文数字 ↔ 结果 JSON 双向数值追溯（强制门禁）。

设计思想：吸收 AutoMCM-Pro 的 verify_*.py 强制自证 + EZ_math_model 的 manifest 对账——
论文正文出现的每一个数字，要么能在 results/ 的 JSON 里找到出处（TRACED），要么
写进 trace_allowlist.json 并说明合法来源（题面常数、文献值、显著性水平、样本量等）。
两者都不占 → UNTRACED → --strict 下退出码 1（FAIL）。程序强制，不靠模型自查。

2026-08 补丁（历史教训：图19 (f) 表内数字 10.80/9.17/16.13 与结果 JSON 完全不符，
但旧版只扫 .tex 不扫图内文字，"全追溯 PASS"照样放行）：
  - 图内追溯：对论文 includegraphics 引用的 figures/*.pdf，提取图内"高精度数值"
    （≥2 位小数）与节点编号（P/H 开头 4 位数字），必须命中 results/*.json 数值/字符串
    或 trace_figure_allowlist.json 白名单（带 note）；否则 FIG_UNTRACED → --strict FAIL。
  - 只扫 ≥2 位小数的浮点数：坐标轴刻度（1 位小数/整数）不误报；
    三位以上整数暂不扫（图内 3 位整数多为刻度/计数值，误报率高）。

用法：
  python trace_numbers.py --workspace <项目根>
      [--strict]              # 有 UNTRACED / FIG_UNTRACED 则退出码 1
      [--paper-dir <dir>]     # 默认 <workspace>/paper（递归找 *.tex）
      [--results-dir <dir>]   # 默认 <workspace>/results（递归找 *.json）
      [--figures-dir <dir>]   # 默认 <workspace>/figures
      [--no-figures]          # 跳过图内追溯（紧急豁免；提交前默认必须开）
      [--allowlist <file>]    # 默认 <workspace>/trace_allowlist.json
      [--fig-allowlist <file>]# 默认 <workspace>/trace_figure_allowlist.json
      [--tol-rel 0.0003]      # 相对容差，默认 3e-4（故意设紧，暴露四舍五入漂移）
      [--tol-abs 0.000001]    # 绝对容差，默认 1e-6
      [--ignore-int-max 5]    # 纯整数 0..N 不扫描（排版噪声），默认 5
      [--report <file>]       # 默认 <workspace>/trace_report.json

输出：stdout 摘要 + trace_report.json（summary / untraced / allowed / unused /
figure_untraced 明细）。
"""

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path


def force_utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


# 内置白名单：与任何结果无关的通用常数。数值匹配优先于白名单（结果里有的值不算白名单）。
BUILTIN_ALLOWLIST = {
    0.05: "显著性水平 0.05（内置）",
    0.01: "显著性水平 0.01（内置）",
    0.1: "显著性水平 0.10（内置）",
    9.8: "重力加速度 9.8（内置）",
    9.81: "重力加速度 9.81（内置）",
    3.14159: "圆周率（内置）",
    3.1416: "圆周率（内置）",
    2024: "年份（内置）",
    2025: "年份（内置）",
    2026: "年份（内置）",
    10: "常见百分比扰动 ±10%（内置）",
    20: "常见百分比扰动 ±20%（内置）",
    25: "MCM 页数限制 25 页（内置）",
    30: "摘要评分占比 30%（内置）",
    100: "百分数基准 100（内置）",
}

NUM_RE = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")
CODE_BLOCK_RE = re.compile(
    r"\\begin\{(?:lstlisting|verbatim|minted|lstcode|thebibliography)\}.*?"
    r"\\end\{(?:lstlisting|verbatim|minted|lstcode|thebibliography)\}",
    re.S,
)
PATH_ARG_RE = re.compile(r"\\(?:input|include|bibliography)\{[^}]*\}")
GRAPHICS_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{[^}]*\}")
# 内嵌 TikZ 流程图：样式参数（black!55、aspect=2.6、pos=0.35 等）不是论文数字，整块跳过；
# 节点文字里的阈值/判据常数须在正文有陈述（或进 allowlist），正文是追溯的唯一载体。
TIKZ_RE = re.compile(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", re.S)
SKIP_BRACE_MACROS = {
    "input", "include", "includegraphics", "linespread", "fontsize",
    "baselineskip", "parskip", "parindent", "setlength", "addtolength",
    "rule", "hspace", "vspace", "raisebox", "resizebox", "scalebox",
}
LENGTH_MACRO_RE = re.compile(
    r"\\(?:textwidth|linewidth|textheight|columnwidth|hsize|vsize|baselineskip|"
    r"parskip|parindent|topmargin|oddsidemargin|evensidemargin|headheight|headsep|"
    r"footskip|marginparwidth|marginparsep|paperwidth|paperheight)\b"
)
DATE_SUFFIX_RE = re.compile(r"[\/-]\d{1,2}[\/-]\d{1,2}\b")

# 图内追溯：只认"高精度数值"（≥2 位小数，坐标轴 1 位小数刻度不误报）与节点编号 P/Hxxxx
FIG_NUM_RE = re.compile(r"-?\d+\.\d{2,}")
FIG_ID_RE = re.compile(r"\b[PH]\d{4}\b")


def collect_truths(results_dir):
    """收集 results/*.json 的全部数值叶子与短字符串（键+值）作为真值。
    返回 (truths, strings)：truths=[(value, source), ...]，strings=set（图内 P/H 编号追溯用）。"""
    truths = []
    strings = set()
    root = Path(results_dir)
    if root.is_dir():
        for jf in sorted(root.rglob("*.json")):
            try:
                doc = json.loads(jf.read_text(encoding="utf-8", errors="replace"))
            except Exception as exc:
                print(f"WARN 无法解析结果 JSON: {jf} ({exc})", file=sys.stderr)
                continue
            _walk(doc, jf.name, truths, strings)
    return truths, strings


def _walk(node, path, out, strings):
    if isinstance(node, dict):
        for k, v in node.items():
            strings.add(str(k)[:40])
            _walk(v, f"{path} > {k}", out, strings)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _walk(v, f"{path}[{i}]", out, strings)
    elif isinstance(node, (int, float)) and not isinstance(node, bool):
        out.append((float(node), path))
    elif isinstance(node, str) and len(node) <= 40:
        strings.add(node)


def _enclosing_brace_macro(text, s):
    """token 紧跟在花括号组里时，返回该花括号组所属的命令名（如 linespread/fontsize）。"""
    if s == 0 or text[s - 1] != "{":
        return None
    tail = text[max(0, s - 80):s - 1]
    cmds = re.findall(r"\\([A-Za-z@]+)", tail)
    return cmds[-1] if cmds else None


def scan_tex_file(f, ignore_int_max):
    """抽取单个 .tex 的数值 token（跳过注释、代码块、长度参数、日期、上下标）。"""
    raw = Path(f).read_text(encoding="utf-8", errors="replace")
    text = raw.replace("\\%", "__PCT__")
    text = CODE_BLOCK_RE.sub("", text)
    text = PATH_ARG_RE.sub("", text)
    text = GRAPHICS_RE.sub("", text)
    text = TIKZ_RE.sub("", text)
    text = "\n".join(line.split("%", 1)[0] for line in text.splitlines())

    found = []
    for m in NUM_RE.finditer(text):
        token = m.group(0)
        s, e = m.start(), m.end()
        if s > 0:
            prev = text[s - 1]
            if prev.isascii() and (prev.isalnum() or prev in "._"):
                continue  # 是词/下标的一部分（abc123、x_1）
            if prev == "^" or (s > 1 and prev == "{" and text[s - 2] == "^"):
                continue  # 指数上标（10^{-3}）
        if e < len(text):
            nxt = text[e]
            if nxt.isascii() and nxt.isalnum():
                continue  # 后面直接跟字母数字（12pt、abc）
        if DATE_SUFFIX_RE.match(text, e):
            continue  # 2020/02/02、2021-11-15 之类日期
        if LENGTH_MACRO_RE.match(text, e):
            continue  # 0.85\textwidth 之类 LaTeX 长度
        if _enclosing_brace_macro(text, s) in SKIP_BRACE_MACROS:
            continue  # \linespread{1.43}、\fontsize{11}{13} 之类排版参数
        val = float(token)
        if token.lstrip("-").isdigit() and 0 <= int(token) <= ignore_int_max:
            continue  # 0..5 的纯整数是排版噪声（表号、[0,1] 区间等）
        line_no = text.count("\n", 0, s) + 1
        ctx_s = max(0, s - 24)
        ctx_e = min(len(text), e + 24)
        ctx = text[ctx_s:ctx_e].replace("\n", " ").replace("__PCT__", "%")
        found.append({
            "token": token,
            "value": val,
            "file": str(Path(f)),
            "line": line_no,
            "ctx": ctx,
        })
    return found


def match_truth(val, truths, tol_rel, tol_abs):
    for tv, tsrc in truths:
        if abs(val - tv) <= tol_abs + tol_rel * abs(tv):
            return tsrc
    return None


def load_allowlist(allow_file):
    """读取工作区白名单。返回 (allow_vals, allow_patterns)。"""
    allow_vals = {}
    allow_patterns = []
    path = Path(allow_file)
    if not path.is_file():
        print(f"INFO 未发现工作区白名单 {path}（PAPER_ONLY 数字需要在此登记来源）")
        return allow_vals, allow_patterns
    try:
        doc = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        for ent in doc.get("entries", []):
            note = str(ent.get("note", "")).strip()
            if not note:
                print("WARN 白名单条目缺少 note（必须说明来源），该条目无效: "
                      + json.dumps(ent, ensure_ascii=False), file=sys.stderr)
                continue
            if "value" in ent:
                allow_vals[float(ent["value"])] = note
            elif "pattern" in ent:
                try:
                    allow_patterns.append((re.compile(str(ent["pattern"])), note))
                except re.error as exc:
                    print(f"WARN 白名单 pattern 非法: {ent.get('pattern')} ({exc})", file=sys.stderr)
    except Exception as exc:
        print(f"WARN 白名单解析失败: {path} ({exc})", file=sys.stderr)
    return allow_vals, allow_patterns


def load_authority(ws):
    """读取工作区 trace_authority.json：论文关键数字必须命中其专属权威文件。
    条目 {value, glob, note}；glob 按结果文件名匹配（fnmatch，如 p4_mine*.json）。"""
    path = Path(ws) / "trace_authority.json"
    if not path.is_file():
        return []
    try:
        doc = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        print(f"WARN 权威源文件解析失败: {path} ({exc})", file=sys.stderr)
        return []
    entries = []
    for ent in doc.get("entries", []):
        glob = str(ent.get("glob", "")).strip()
        if not glob:
            print("WARN 权威源条目缺少 glob，该条目无效: "
                  + json.dumps(ent, ensure_ascii=False), file=sys.stderr)
            continue
        if "value" not in ent:
            print("WARN 权威源暂只支持 value 条目（pattern 待后续版本）: "
                  + json.dumps(ent, ensure_ascii=False), file=sys.stderr)
            continue
        entries.append({"value": float(ent["value"]), "glob": glob,
                        "note": str(ent.get("note", "")).strip() or "权威源校验"})
    return entries


def referenced_figure_stems(tex_files):
    """论文 includegraphics 引用的图 stem（去扩展名；只追溯被引图，备用图不查）。"""
    stems = set()
    for f in tex_files:
        raw = Path(f).read_text(encoding="utf-8", errors="replace")
        for m in GRAPHICS_RE.finditer(raw):
            arg = m.group(0).split("{", 1)[-1].rstrip("}")
            base = arg.split("/")[-1]
            for ext in (".pdf", ".png", ".jpg", ".jpeg", ".eps"):
                if base.lower().endswith(ext):
                    base = base[: -len(ext)]
                    break
            if base and not base.startswith("."):
                stems.add(base)
    return stems


def figure_text_tokens(fig_path):
    """提取矢量 PDF 图内的可追溯 token（≥2 位小数数值 + P/H 编号）。缺 PyMuPDF 返回 None。"""
    try:
        import fitz
    except Exception:
        return None
    try:
        doc = fitz.open(str(fig_path))
        text = "\n".join(pg.get_text() for pg in doc)
        doc.close()
    except Exception:
        return None
    toks = []
    for m in FIG_NUM_RE.finditer(text):
        toks.append({"kind": "num", "token": m.group(0), "value": float(m.group(0))})
    for m in FIG_ID_RE.finditer(text):
        toks.append({"kind": "id", "token": m.group(0), "value": None})
    return toks


def load_figure_allowlist(allow_file):
    """trace_figure_allowlist.json：图内数字/编号白名单（坐标轴刻度等衍生标注）。
    格式 {"entries": [{"figure": "fig_xxx", "tokens": [0.05], "ids": ["P0000"], "note": "..."}]}
    note 为空 = 未说明来源 = 该条目无效。"""
    path = Path(allow_file)
    if not path.is_file():
        return []
    try:
        doc = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        print(f"WARN 图白名单解析失败: {path} ({exc})", file=sys.stderr)
        return []
    entries = []
    for ent in doc.get("entries", []):
        fig = str(ent.get("figure", "")).strip()
        note = str(ent.get("note", "")).strip()
        if not fig or not note:
            print("WARN 图白名单条目缺少 figure/note，该条目无效", file=sys.stderr)
            continue
        entries.append({"figure": fig, "tokens": [float(x) for x in ent.get("tokens", [])],
                        "ids": [str(x) for x in ent.get("ids", [])], "note": note})
    return entries


def trace_figures(figures_dir, tex_files, truths, strings, fig_allow, tol_rel, tol_abs):
    """被引图的图内数字 ↔ results/*.json 追溯。
    返回 (traced, untraced, checked, raster_skipped)。
    raster_skipped = 被引图只有位图（PNG/JPG，无文字层）无法程序化追溯的张数——WARN 提醒人工核对。"""
    stems = referenced_figure_stems(tex_files)
    fig_dir = Path(figures_dir)
    if not stems or not fig_dir.is_dir():
        return [], [], 0, []
    traced, untraced, checked = [], [], 0
    raster_skipped = []
    for stem in sorted(stems):
        fp = fig_dir / f"{stem}.pdf"
        if not fp.is_file():
            png = fig_dir / f"{stem}.png"
            if png.is_file():
                raster_skipped.append(f"{stem}.png")
            continue  # 缺图由编译/style 门负责；位图无文字层，提示人工核对
        toks = figure_text_tokens(fp)
        if toks is None:
            raster_skipped.append(f"{stem}.pdf")
            continue
        checked += 1
        allow = next((e for e in fig_allow if e["figure"] == stem), None)
        for tk in toks:
            if tk["kind"] == "num":
                hit = any(round(tk["value"], 2) == round(tv, 2) for tv, _ in truths)
                if not hit and allow and \
                        any(round(tk["value"], 2) == round(a, 2) for a in allow["tokens"]):
                    hit = True
                if hit:
                    traced.append({**tk, "figure": stem})
                else:
                    untraced.append({**tk, "figure": stem})
            else:  # id：P/Hxxxx 必须出现在结果 JSON 的键/值字符串里
                if tk["token"] in strings or (allow and tk["token"] in allow["ids"]):
                    traced.append({**tk, "figure": stem})
                else:
                    untraced.append({**tk, "figure": stem})
    return traced, untraced, checked, raster_skipped


def main(argv=None):
    force_utf8()
    ap = argparse.ArgumentParser(description="论文数字 ↔ 结果 JSON 双向数值追溯")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--paper-dir", default=None)
    ap.add_argument("--results-dir", default=None)
    ap.add_argument("--figures-dir", default=None)
    ap.add_argument("--no-figures", action="store_true",
                    help="跳过图内数字追溯（紧急豁免；提交前默认必须开）")
    ap.add_argument("--allowlist", default=None)
    ap.add_argument("--fig-allowlist", default=None)
    ap.add_argument("--tol-rel", type=float, default=3e-4)
    ap.add_argument("--tol-abs", type=float, default=1e-6)
    ap.add_argument("--ignore-int-max", type=int, default=5)
    ap.add_argument("--report", default=None)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args(argv)

    ws = Path(args.workspace).resolve()
    paper_dir = Path(args.paper_dir).resolve() if args.paper_dir else ws / "paper"
    results_dir = Path(args.results_dir).resolve() if args.results_dir else ws / "results"
    figures_dir = Path(args.figures_dir).resolve() if args.figures_dir else ws / "figures"
    allow_file = Path(args.allowlist).resolve() if args.allowlist else ws / "trace_allowlist.json"
    fig_allow_file = (Path(args.fig_allowlist).resolve() if args.fig_allowlist
                      else ws / "trace_figure_allowlist.json")
    report_file = Path(args.report).resolve() if args.report else ws / "trace_report.json"

    if not paper_dir.is_dir():
        print(f"FAIL 论文目录不存在: {paper_dir}")
        return 2
    tex_files = sorted(paper_dir.rglob("*.tex"))
    if not tex_files:
        print(f"FAIL 论文目录下没有 .tex 文件: {paper_dir}")
        return 2
    if not results_dir.is_dir():
        print(f"WARN 结果目录不存在: {results_dir}，所有论文数字都将视为无出处", file=sys.stderr)

    truths, truth_strings = collect_truths(results_dir)
    allow_vals, allow_patterns = load_allowlist(allow_file)
    authority_entries = load_authority(ws)
    fig_allow = load_figure_allowlist(fig_allow_file)

    traced, allowed, untraced = [], [], []
    used_truths = set()

    for f in tex_files:
        for item in scan_tex_file(f, args.ignore_int_max):
            src = match_truth(item["value"], truths, args.tol_rel, args.tol_abs)
            if src is not None:
                item["status"] = "TRACED"
                item["source"] = src
                traced.append(item)
                used_truths.add(src)
                continue
            note = allow_vals.get(item["value"])
            if note is None:
                for pat, pnote in allow_patterns:
                    if pat.fullmatch(item["token"]):
                        note = pnote
                        break
            if note is None:
                note = BUILTIN_ALLOWLIST.get(item["value"])
            if note is not None:
                item["status"] = "ALLOWED"
                item["note"] = note
                allowed.append(item)
                continue
            item["status"] = "UNTRACED"
            untraced.append(item)

    unused = [{"value": tv, "source": ts} for tv, ts in truths if ts not in used_truths]
    unused.sort(key=lambda x: x["source"])

    # 图内数字追溯：被引图的"高精度数值 + P/H 编号"必须命中结果 JSON（或图白名单）
    fig_traced, fig_untraced, fig_checked, fig_raster = [], [], 0, []
    if not args.no_figures:
        fig_traced, fig_untraced, fig_checked, fig_raster = trace_figures(
            figures_dir, tex_files, truths, truth_strings, fig_allow,
            args.tol_rel, args.tol_abs)

    # 权威源校验：论文关键数字必须命中其专属权威文件（如 p4 数字必须存在于
    # p4_mine*.json）；只存在于 sensitivity.json 等同名值不算——拦"数字在错的文件里"。
    authority_miss = []
    for ent in authority_entries:
        hit = any(
            fnmatch.fnmatch(ts.split(" > ")[0], ent["glob"])
            and abs(tv - ent["value"]) <= args.tol_abs + args.tol_rel * abs(ent["value"])
            for tv, ts in truths
        )
        if not hit:
            authority_miss.append(ent)

    summary = {
        "paper_numbers": len(traced) + len(allowed) + len(untraced),
        "traced": len(traced),
        "allowed": len(allowed),
        "untraced": len(untraced),
        "unused": len(unused),
        "authority_checked": len(authority_entries),
        "authority_miss": len(authority_miss),
        "figure_checked": fig_checked,
        "figure_raster_skipped": len(fig_raster),
        "figure_traced": len(fig_traced),
        "figure_untraced": len(fig_untraced),
    }
    report = {
        "summary": summary,
        "untraced": untraced[:200],
        "allowed": allowed[:100],
        "unused": unused[:200],
        "authority_miss": authority_miss,
        "figure_untraced": fig_untraced[:200],
        "figure_raster_skipped": fig_raster[:50],
    }
    try:
        report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"WARN 写报告失败: {report_file} ({exc})", file=sys.stderr)

    print(f"论文目录: {paper_dir}（{len(tex_files)} 个 .tex）")
    print(f"结果目录: {results_dir}（真值 {len(truths)} 个）")
    print(f"论文数值 token: {summary['paper_numbers']} | TRACED {summary['traced']} | "
          f"ALLOWED {summary['allowed']} | UNTRACED {summary['untraced']} | UNUSED {summary['unused']}")
    if untraced:
        print("")
        print(f"UNTRACED（{len(untraced)} 个，最多显示 60 个）——必须回写结果 JSON 或登记白名单:")
        for item in untraced[:60]:
            print(f"  {item['value']:>10g}  {item['file']}:{item['line']}  ...{item['ctx']}...")
    if unused:
        print(f"INFO 结果 JSON 中未被论文引用的数值 {len(unused)} 个（前 10 个）:")
        for u in unused[:10]:
            print(f"  {u['value']:>10g}  <- {u['source']}")
    if authority_miss:
        print("")
        print(f"AUTHORITY MISS（{len(authority_miss)} 条）——关键数字未命中其专属权威文件:")
        for ent in authority_miss:
            print(f"  {ent['value']:>10g}  应存在于 {ent['glob']}  （{ent['note']}）")
    print("")
    if fig_checked or fig_raster:
        print(f"图内数字: 检查 {fig_checked} 张被引图 | TRACED {len(fig_traced)} | FIG_UNTRACED {len(fig_untraced)}")
    if fig_raster:
        print(f"WARN 位图跳过图内追溯 {len(fig_raster)} 张（无文字层，需人工核对图内数字或改矢量 PDF）: "
              + ", ".join(fig_raster[:8]))
    if fig_untraced:
        print("FIG_UNTRACED（图内数字/编号与结果 JSON 不符，必须重生成图或登记图白名单）:")
        for item in fig_untraced[:60]:
            print(f"  [{item['figure']}] {item['kind']}: {item['token']}")
    print("")
    if args.strict and (untraced or authority_miss or fig_untraced):
        print(f"FAIL 存在 {len(untraced)} 个 UNTRACED / {len(authority_miss)} 条权威源未命中"
              f" / {len(fig_untraced)} 个图内数字失配（--strict）。报告: {report_file}")
        return 1
    print(f"PASS 全部论文数字可追溯（权威源校验 {len(authority_entries)} 条通过，"
          f"图内追溯 {fig_checked} 张）。报告: {report_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

