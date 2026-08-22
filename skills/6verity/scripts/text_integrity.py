#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""text_integrity.py — v4 文本完整性门（任务书 十二、十三条）。

提交级硬 FAIL 扫描：
  1. 论文源（paper/**/*.tex|*.typ）中的占位/残留标记：
       图 ?? / 表 ?? / 式 ?? / 裸 ?? / TODO / TBD / PLACEHOLDER / 待补 / 待续 / XXX / FIXME
  2. 关键词行程序化检查：3-8 个；必含分隔符（；|;|，）；
     整行除空格无任何分隔符 / 词数越界 → FAIL（v4 建议分隔符 ；）。
  3. 编译产物扫描（paper/*.log / 或 --log 指定）：
       undefined reference           -> FAIL（可配置 --allow-undefined-refs 用于未编译完的草稿）
       undefined citation            -> FAIL
       multiply-defined labels       -> FAIL
       overfull hbox > severe_pt(默认 15pt) -> FAIL；<= severe_pt -> WARN
  4. 正文中残留的 \ref{??} / \cite{??} 悬空标签（源级即 FAIL）。

用法：
  python text_integrity.py --workspace <项目根> [--strict] [--log paper/main.log]
输出：reports/gates/text_integrity.json；退出码 0 PASS / 1 FAIL / 2 ERROR。
"""
from __future__ import annotations

import argparse
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

import gate_common as gc

PLACEHOLDER_PATTERNS = [
    (r"图\s*\?\?", "fig_placeholder"),
    (r"表\s*\?\?", "tab_placeholder"),
    (r"式\s*\?\?", "eq_placeholder"),
    (r"(?<!图)(?<!表)(?<!式)\?\?", "bare_placeholder"),
    (r"TODO", "todo"),
    (r"TBD", "tbd"),
    (r"PLACEHOLDER", "placeholder"),
    (r"待补", "pending"),
    (r"待续", "to_be_continued"),
    (r"XXX", "xxx"),
    (r"FIXME", "fixme"),
    (r"\\ref\{[^}]*\?\?[^}]*\}", "dangling_ref"),
    (r"\\cite\{[^}]*\?\?[^}]*\}", "dangling_cite"),
]
KEYWORD_SEPARATORS = ["；", ";", "，", ","]
# 关键词一行里出现 3 个以上词但无分隔符 → 未分隔（乱炖）；2 个词无分隔符是常见合法简写？——
# 不，CUMCM 惯例关键词以 ；分隔；此处规则 = 整行（去前缀后）无任何分隔符且词数 >= 3 才 FAIL，
# 2 词且无分隔符记 WARN（允许"关键词：NIPT 风险"这类极短形式）。
KEYWORDS_MIN = 3
KEYWORDS_MAX = 8


def scan_placeholders(ws: Path, strict: bool):
    findings = []
    paper = ws / "paper"
    if not paper.is_dir():
        findings.append({"level": "FAIL" if strict else "WARN", "check": "paper_missing",
                         "message": "paper/ 目录不存在，无法做文本完整性扫描"})
        return findings
    for p in sorted(paper.rglob("*")):
        if p.suffix.lower() not in (".tex", ".typ"):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        for pat, name in PLACEHOLDER_PATTERNS:
            for m in re.finditer(pat, text):
                findings.append({"level": "FAIL" if strict else "WARN", "check": name,
                                 "message": f"{p.relative_to(ws)}: 命中 {pat!r} -> {m.group(0)[:40]!r}"})
    return findings


def _strip_comments(text: str) -> str:
    """剥离 LaTeX 注释行与行内注释（% 至行尾），不破坏内容。"""
    return re.sub(r"(?m)%.*$", "", text)


def _clean_kw_line(line: str) -> str:
    """清除 latex 命令/花括号/宏参数标记，得到纯文本。"""
    line = re.sub(r"\\[a-zA-Z]+", " ", line)
    line = re.sub(r"#\d", " ", line)
    line = re.sub(r"[{}\[\]]+", " ", line)
    line = re.sub(r"\s+", " ", line)
    return line.strip()


# 内部流程术语（R-04/P0-03）：正文节（排除附录 A_code 与 references）不得出现；
# 支持 LaTeX 转义下划线变体（FINAL\_MODEL\_SPEC / result\_s 等）
INTERNAL_TERM_PATTERNS = [
    (r"FINAL\\?_MODEL\\?_SPEC", "模型契约文件名泄漏到正文"),
    (r"model\\?_spec\\?_sha(256)?", "契约哈希字段泄漏到正文"),
    (r"methodology[_ ]review", "内部流程名泄漏到正文"),
    (r"7methodology", "内部阶段名泄漏到正文"),
    (r"workflow\\?_spec", "内部配置文件泄漏到正文"),
    (r"\breports/", "内部目录路径泄漏到正文"),
    (r"\bresults/\w", "内部结果路径泄漏到正文"),
    (r"\bcode/\w+\.py", "内部源码路径泄漏到正文"),
    (r"(?<![A-Za-z_:])v[0-9]{1,2}(?![0-9A-Za-z_.])", "版本号（v3/v4）泄漏到正文（fig:v3_* 标签名除外）"),
]
# Markdown 残留（P0-07）：正文不得出现 **粗体** / `行内代码` 标记
MARKDOWN_RE = re.compile(r"\*\*[^*\n]{1,120}\*\*|`[^`\n]{1,120}`")
# 区间删失似然方向（T38/P0-06；v4.2 G-01 强化为角色化校验，大小写/空格/下标/^- 变体全覆盖）：
#   S(上界变量)-S(下界变量) 数学上为负（S 递减）→ 必须 FAIL；正确 = S(下界)-S(上界)。
#   角色判定：变量名以 u/U/r/R 开头 = 上界（u_i / U_i / r_i / R_i）；l/L 开头 = 下界。
S_UPPER_RE = re.compile(r"^[uUrR]")
S_LOWER_RE = re.compile(r"^[lL]")
# S(x)-S(y)：捕获组取下标根名（u_i^、U_ij、l、r 等）；允许 LaTeX 分行/空格/^- 后缀
LIKELIHOOD_SIGN_RE = re.compile(
    r"S\s*\(\s*([A-Za-z][A-Za-z0-9_^{}]*)[^)]{0,20}\)\s*[-−]\s*"
    r"S\s*\(\s*([A-Za-z][A-Za-z0-9_^{}]*)[^)]{0,20}\)",
    re.IGNORECASE,
)
# 方括号省略写法（[S(U_i) … S(L_i)]，无减号分隔）
LIKELIHOOD_SIGN_RE2 = re.compile(
    r"\[\s*S\s*\(\s*([A-Za-z][A-Za-z0-9_^{}]*)[^)]{0,20}\)[^\]]{0,25}?"
    r"S\s*\(\s*([A-Za-z][A-Za-z0-9_^{}]*)[^)]{0,20}\)\s*\]",
    re.IGNORECASE,
)


def scan_likelihood_direction(stripped: str, rel: str):
    """角色化区间似然方向校验：上界变量在减号前（S(u)-S(l)）即 FAIL。"""
    findings = []
    matches = list(LIKELIHOOD_SIGN_RE.finditer(stripped))
    for m2 in LIKELIHOOD_SIGN_RE2.finditer(stripped):
        if any(m2.start() <= m.start() and m2.end() >= m.end() for m in matches):
            continue  # 已被含减号的正则捕获，避免双报
        matches.append(m2)
    for m in matches:
        a, b = m.group(1), m.group(2)
        a_upper = bool(S_UPPER_RE.match(a)) and not bool(S_LOWER_RE.match(a))
        b_upper = bool(S_UPPER_RE.match(b)) and not bool(S_LOWER_RE.match(b))
        a_lower = bool(S_LOWER_RE.match(a)) and not bool(S_UPPER_RE.match(a))
        b_lower = bool(S_LOWER_RE.match(b)) and not bool(S_UPPER_RE.match(b))
        # 角色未知（如 S(10)-S(5) 或同名 S(a)-S(a)）不判向；方向错误 = 上界减下界
        if a_upper and b_lower:
            findings.append({"level": "FAIL", "check": "likelihood_inverted",
                             "message": f"{rel}: 区间删失似然反向表达 {m.group(0)[:50]!r}——"
                                        f"应为 S(L)-S(U)（=F(U)-F(L)），S(U)-S(L) 数学上为负，"
                                        f"不能取对数（T38/P0-06，v4.2 角色化校验）"})
    return findings


def _norm_dup_text(s: str) -> str:
    """重复检测用归一化：去注释/命令/数学标记/空白，保留文字内容。"""
    s = re.sub(r"(?m)(?<!\\)%.*$", "", s)
    s = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^{}]*\})?", " ", s)
    s = re.sub(r"[${}\[\]&\\_^~]", " ", s)
    s = re.sub(r"\s+", "", s)
    return s.strip()


def _dup_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def scan_section_duplicates(rel: str, text: str, strict: bool):
    r"""v4.2 G-02/T47：section/subsection 级重复审计（非相邻重复项——相邻检测可被隔项绕过）。

    对每个 \\section/\\subsection 块：
      - 列表项（\item 之间）两两比较，归一化相似度 > 0.92 即 FAIL（T47：第 3 项与第 5 项重复）；
      - 长句（归一化后 >= 30 字）两两比较，相似度 > 0.95 即 FAIL（同节措辞重复）。
    跳过表格行/公式环境/无文字行（结构重复属正常排版）。
    """
    findings = []
    # 按 section 标题切块（含 subsection 层级：块内再按 subsection 细分）
    head_re = re.compile(r"\\(?:sub)*section\s*(\[[^\]]*\])?\{[^{}]*\}|\\(?:sub)*section\*\{[^{}]*\}")
    cuts = [(m.start(), m.group(0)) for m in head_re.finditer(text)]
    if not cuts:
        cuts = [(0, "(whole file)")]
    bounds = cuts + [(len(text), "")]
    for bi in range(len(cuts)):
        seg = text[bounds[bi][0]:bounds[bi + 1][0]]
        head = cuts[bi][1] if cuts[bi][1] else ""

        # —— 列表项级（非相邻重复 T47）——
        items = []
        if "\\item" in seg:
            parts = re.split(r"\\item(?:\s*\[[^\]]*\])?\s*", seg)
            items = parts[1:]  # 首个 \item 之前的文本不算项
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a = _norm_dup_text(items[i])
                b = _norm_dup_text(items[j])
                if len(a) < 20 or len(b) < 20:
                    continue
                if "&" in items[i] and "&" in items[j]:
                    continue  # 表格行
                r = _dup_ratio(a, b)
                if r > 0.92:
                    findings.append({"level": "FAIL" if strict else "WARN", "check": "duplicate_section",
                                     "message": f"{rel}（{head[:40]}）: 列表项 {i + 1} 与 {j + 1} 重复"
                                                f"（相似度 {r:.0%}，非相邻）：{a[:50]}..."})

        # —— 长句级（块内两两比较）——
        story = re.sub(r"\$[^$]{0,300}?\$", " ", seg)  # 剔除行内公式
        story = re.sub(r"\\(begin|end)\{[a-z]+\*?\}", " ", story)
        seen_sents = []
        for sent in re.split(r"[。；;]+", story):
            s = _norm_dup_text(sent)
            if len(s) < 30:
                continue
            for t in seen_sents:
                r = _dup_ratio(s, t)
                if r > 0.95:
                    findings.append({"level": "FAIL" if strict else "WARN", "check": "duplicate_section",
                                     "message": f"{rel}（{head[:40]}）: 长句重复（相似度 {r:.0%}）：{s[:50]}..."})
                    break
            seen_sents.append(s)
    return findings

# 相邻重复句（R-04）
def _norm_line(s: str) -> str:
    s = re.sub(r"(?m)(?<!\\)%.*$", "", s)
    s = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^{}]*\})?", " ", s)
    return re.sub(r"\s+", "", s)


def scan_unscoped_group_ids(rel: str, text: str, strict: bool):
    """v4.2 P0-03/T48：跨问题总结章节（模型评价/推广/结论）内出现无作用域组引用
    裸 G3/G4（问题二组）或 g3（问题三组）→ FAIL（串台风险）。

    要求：跨问题总结必须用"问题二 G4 组 / Q2.G4 / 问题三 g3"式限定；禁止裸 G/g。
    """
    if not re.search(r"\\section\{[^{}]*(评价|推广|优点|缺点|结论|总结)", text):
        return []
    findings = []
    for m in re.finditer(r"(?<![A-Za-z0-9.])[Gg][1-4]\b", text):
        ctx = text[max(0, m.start() - 14):m.start()]
        if re.search(r"问题[一二三四]|Q\d\.|第[一二三四]问", ctx):
            continue  # 已限定作用域
        findings.append({"level": "FAIL" if strict else "WARN", "check": "unscoped_group_id",
                         "message": f"{rel}: 跨问题总结出现无作用域组引用 {m.group(0)!r}"
                                    f"（应写 '问题二 G4 组' / 'Q2.G4' 式限定；P0-03/T48 串台风险）"})
    return findings


def scan_internal_and_markdown(ws: Path, strict: bool):
    """R-04/P0-03/P0-07：正文节内部术语 + Markdown 残留 + 相邻重复句。"""
    findings = []
    paper = ws / "paper"
    if not paper.is_dir():
        return findings
    for p in sorted(paper.rglob("*")):
        if p.suffix.lower() not in (".tex", ".typ"):
            continue
        rel = p.relative_to(ws).as_posix()
        # 附录源码引用与参考文献区豁免（路径/文件名属合法内容）；
        # appendix_source_list.tex 为附录生成片段（源码清单/路径/版本号属合法内容）
        if "A_code" in rel or "references" in rel or "appendix_source_list" in rel:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        # 剔除注释行/行内注释（LaTeX % 与 Typst //）后检查——注释中的 v4/模板说明不算正文；
        # `\%` 等转义百分号不是注释（负向后视）
        stripped = re.sub(r"(?m)(?<!\\)%.*$", "", text)
        if p.suffix.lower() == ".typ":
            stripped = re.sub(r"(?m)//.*$", "", stripped)
        for pat, why in INTERNAL_TERM_PATTERNS:
            for m in re.finditer(pat, stripped):
                findings.append({"level": "FAIL" if strict else "WARN", "check": "internal_term",
                                 "message": f"{rel}: 内部流程术语 {m.group(0)[:40]!r}（{why}）——生产系统措辞不得进入正文"})
        for m in MARKDOWN_RE.finditer(stripped):
            findings.append({"level": "FAIL" if strict else "WARN", "check": "markdown_leak",
                             "message": f"{rel}: Markdown 残留 {m.group(0)[:40]!r}——LaTeX 正文不得出现 **/**/` 标记"})
        findings.extend(scan_likelihood_direction(stripped, rel))
        # 相邻重复句（跳过表格行/宏定义/环境行/无文字行——结构重复属正常排版）
        lines = [l for l in (_norm_line(x) for x in stripped.splitlines()) if l]
        for a, b in zip(lines, lines[1:]):
            if not a or not b:
                continue
            if not re.search(r"[\u4e00-\u9fff]", a) and not re.search(r"\b[A-Za-z]{3,}\b", a):
                continue  # 纯符号/模板行（{0pt}、[H]、长度残片等）
            if "&" in a or "&" in b or a.startswith(("\\begin", "\\end", "\\newcommand", "\\def")):
                continue
            if a == b:
                findings.append({"level": "FAIL" if strict else "WARN", "check": "duplicate_adjacent",
                                 "message": f"{rel}: 相邻行重复句：{a[:50]}..."})
            elif len(a) > 20 and len(b) > 20:
                sim = len(set(a) & set(b)) / max(1, len(set(a) | set(b)))
                if sim > 0.9:
                    findings.append({"level": "WARN", "check": "duplicate_adjacent",
                                     "message": f"{rel}: 相邻行高度相似（{sim:.0%}）：{a[:40]}..."})
        # v4.2 G-02：section 级重复审计（非相邻列表项/长句）
        findings.extend(scan_section_duplicates(rel, stripped, strict))
        # v4.2 P0-03/T48：跨问题总结节的无作用域组引用
        findings.extend(scan_unscoped_group_ids(rel, stripped, strict))
    return findings


def scan_keywords(ws: Path, strict: bool):
    """关键词程序化检查。支持两种位置：
      A) `关键词：<词…>`（前缀行）；
      B) `\abstractcn{…}{<关键词>}` 等宏的第二参数（CUMCM 模板写法）。
    规则：3-8 个词；无分隔符（；|;|，）且 >=3 词 -> FAIL；2 词无分隔符 -> WARN。
    """
    findings = []
    paper = ws / "paper"
    if not paper.is_dir():
        return findings
    kw_re = re.compile(r"关键词\s*[:：]\s*([^\n]*)")
    macro_re = re.compile(r"\\abstractcn\s*\{.*?\}\s*\{([\s\S]*?)\}", re.S)
    for p in sorted(paper.rglob("*")):
        if p.suffix.lower() not in (".tex", ".typ"):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        if "关键词" not in text and "abstractcn" not in text:
            continue
        text = _strip_comments(text)
        raw_lines = []
        for m in kw_re.finditer(text):
            raw_lines.append(m.group(1))
        for m in macro_re.finditer(text):
            raw_lines.append(m.group(1))
        seen = set()
        for raw in raw_lines:
            line = _clean_kw_line(raw)
            if not re.search(r"[\u4e00-\u9fffA-Za-z]", line):
                continue  # 宏定义/模板说明等无实际词的内容
            if line in seen:
                continue
            seen.add(line)
            seps = [s for s in KEYWORD_SEPARATORS if s in line]
            if seps:
                words = [w for w in re.split(r"[；;，,]+", line) if w.strip()]
            else:
                words = [w for w in line.split() if w.strip()]
            n = len(words)
            if n < KEYWORDS_MIN or n > KEYWORDS_MAX:
                findings.append({"level": "FAIL" if strict else "WARN", "check": "keyword_count",
                                 "message": f"{p.relative_to(ws)}: 关键词 {n} 个，超出 "
                                            f"{KEYWORDS_MIN}-{KEYWORDS_MAX} 范围：{line[:60]}"})
            if not seps and n >= 3:
                findings.append({"level": "FAIL" if strict else "WARN", "check": "keyword_separator",
                                 "message": f"{p.relative_to(ws)}: 关键词未用分隔符（；/;，）分隔: "
                                            f"{line[:60]}（官方模板默认 ； 分隔）"})
            elif not seps and n == 2:
                findings.append({"level": "WARN", "check": "keyword_separator",
                                 "message": f"{p.relative_to(ws)}: 关键词 2 个且无分隔符，建议改用 ； 分隔: "
                                            f"{line[:60]}"})
    return findings


def scan_compile_log(ws: Path, log_rel: str, strict: bool, severe_pt: float):
    """扫描 LaTeX 编译日志 .log：undefined ref/citation、multiply-defined、overfull。"""
    findings = []
    log_path = Path(log_rel) if log_rel else (ws / "paper" / "main.log")
    if not log_path.is_file():
        return findings
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return findings
    undef_ref = list(dict.fromkeys(re.findall(r"LaTeX Warning: Reference `[^']*' on page \d+ undefined", text)))
    undef_cite = list(dict.fromkeys(re.findall(r"LaTeX Warning: Citation `[^']*' on page \d+ undefined", text)))
    multi = list(dict.fromkeys(re.findall(r"LaTeX Warning: There were multiply-defined labels", text)))
    overfull = re.findall(r"Overfull \\hbox \((\d+(?:\.\d+)?)pt too wide\)", text)
    for m in undef_ref:
        findings.append({"level": "FAIL" if strict else "WARN", "check": "undefined_ref",
                         "message": f"编译日志出现 undefined reference: {m}"})
    for m in undef_cite:
        findings.append({"level": "FAIL" if strict else "WARN", "check": "undefined_citation",
                         "message": f"编译日志出现 undefined citation: {m}"})
    for m in multi:
        findings.append({"level": "FAIL" if strict else "WARN", "check": "multiply_defined_labels",
                         "message": "编译日志出现 multiply-defined labels（标签冲突）"})
    for m in overfull:
        pt = float(m)
        lvl = "FAIL" if pt > severe_pt else "WARN"
        msg = (f"overfull hbox {pt}pt（severe 阈值 >{severe_pt}pt，本次判定 {lvl}"
               f"{'，需视觉检查裁切' if lvl == 'WARN' else ''}）")
        findings.append({"level": lvl, "check": "overfull_hbox", "message": msg})
    return findings


def main(argv=None):
    gc.force_utf8()
    ap = argparse.ArgumentParser(description="v4 文本完整性门")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--log", default=None, help="指定 .log 路径（默认 paper/main.log）")
    ap.add_argument("--overfull-severe-pt", type=float, default=15.0)
    ap.add_argument("--report", default=None)
    args = ap.parse_args(argv)

    ws = Path(args.workspace).resolve()
    findings = []
    findings.extend(scan_placeholders(ws, args.strict))
    findings.extend(scan_keywords(ws, args.strict))
    findings.extend(scan_internal_and_markdown(ws, args.strict))
    findings.extend(scan_compile_log(ws, args.log, args.strict, args.overfull_severe_pt))

    fails = [f for f in findings if f["level"] == "FAIL"]
    warns = [f for f in findings if f["level"] == "WARN"]
    report = {
        "gate": "text_integrity", "schema_version": 1, "workspace": str(ws),
        "strict": args.strict, "engine": gc.manifest_engine(ws),
        "findings": findings,
        "summary": {"fails": len(fails), "warns": len(warns), "checks": len(findings)},
        "note": "占位符/悬空引用/关键词分隔为提交级硬项；overfull ≤severe_pt 为 WARN 需视觉检查。",
    }
    out = Path(args.report).resolve() if args.report else ws / "reports" / "gates" / "text_integrity.json"
    gc.save_json(out, report)
    for f in findings:
        print(f"  [{f['level']}] {f['check']}: {f['message']}")
    print(f"TEXT_INTEGRITY: {'PASS' if not fails else 'FAIL'}（{len(fails)} FAIL / {len(warns)} WARN） -> {out}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
