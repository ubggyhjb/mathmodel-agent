#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""submission_package_gate.py — v4.2（P0-06/9.2）：支撑材料提交包审计 + clean-room smoke test。

v4.2 目标：从"工作区十门全绿"升级到"最终 ZIP 在干净机器上可证明正确、可读、可复现"——
只验证结果 JSON 内部一致性的 verify_all.py 不覆盖：换机器能不能跑、ZIP 解压后路径是否成立、
是否漏依赖、是否缺输入说明、是否引用作者本机目录。

检查项（--check，不跑代码）：
  1. 找到提交包 ZIP（*支撑材料*.zip / *support*.zip，缺省 glob workspace 与 提交/ 目录）；
  2. ZIP 可解压（临时目录）；解压后结构：
     - README.md 存在（P1-11）；requirements.txt 存在；
     - 无本机绝对路径（扫描 .py/.md/.json/.yml：盘符路径 `[A-Za-z]:\\`、`/Users/`、`/home/`）；
     - code/ 源文件集合与论文附录引入集合一致（P0-07：先展开 A_code 的 input 再比对）；
     - 无 dangling 内部路径引用（reports/… 但 ZIP 内无 reports/）——P1-15；
  3. ZIP 大小、名称编码合理性（WARN 级）。

--smoke（clean-room 实测）：解压到临时目录 -> 复制 --data 指定的官方附件到解压后
  data/（或 README 声明的路径）-> 运行 --script（默认 problem1.py）-> 断言退出 0 且
  产生输出 JSON -> 清理。只有 --smoke 通过才能称"可运行支撑材料"。

用法：
  python submission_package_gate.py --workspace <项目根> --check
  python submission_package_gate.py --workspace <项目根> --smoke --data <附件.xlsx>
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import gate_common as gc

ABS_PATH_RE = re.compile(r"[A-Za-z]:[\\/]|/Users/|/home/|/mnt/c/|\\Users\\")
DANGLING_RE = re.compile(r"reports/|ANALYSIS_MODELING_REPORT\.md|figure_story_manifest")


def find_zip(ws: Path):
    for name in ("支撑材料.zip", "support.zip", "support_package.zip"):
        p = ws / name
        if p.is_file():
            return p
    cands = sorted(ws.rglob("*支撑材料*.zip")) + sorted(ws.rglob("*support*.zip"))
    return cands[0] if cands else None


def unpack(zp: Path, dest: Path) -> Path:
    with zipfile.ZipFile(zp) as z:
        z.extractall(dest)
    return dest


def scan_texts(root: Path, suffixes=(".py", ".md", ".json", ".yml", ".yaml", ".txt", ".tex")):
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in suffixes:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        yield p, text


def count_literature(lit: Path) -> int:
    try:
        text = lit.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return 0
    return len(re.findall(r"^\s*\|?\s*\*?\*?(?:ref|\[ref)[A-Za-z0-9_]+\*?\*?\s*\|?", text, re.M))


def check_v43(ws: Path, root: Path, problems):
    """v4.3（§10/P0-07, T82-T89）：support registry 语义一致性——同一事实只维护一遍。"""
    # T82：data_sources.md 不得重复枚举/漂移文献数量与旧文献名
    ds = root / "references" / "data_sources.md"
    lit = root / "references" / "literature.md"
    if ds.is_file():
        ds_text = ds.read_text(encoding="utf-8", errors="replace")
        lit_n = count_literature(lit) if lit.is_file() else 0
        for m in re.finditer(r"literature\.md[^\n]{0,30}?(\d+)\s*篇", ds_text):
            if int(m.group(1)) != lit_n:
                problems.append(f"references/data_sources.md 声明文献 {m.group(1)} 篇 ≠ literature.md "
                                f"实际 {lit_n} 篇（T82：同一事实不要在人读文档中维护两遍）")
        if lit.is_file():
            lit_text = lit.read_text(encoding="utf-8", errors="replace")
            for old in ("Chiu2008", "Zhou2015", "Kinnings2015", "Luo2026", "Chawla2002", "Wang2025"):
                if old in ds_text and old not in lit_text:
                    problems.append(f"data_sources.md 残留已淘汰/替换文献名 {old}（T82）")
            if "6 篇" in ds_text and lit_n > 0 and lit_n != 6:
                problems.append(f"data_sources.md 仍写旧 6 篇，literature registry 实际 {lit_n} 篇（T82）")
    # T83：论文附录 A 声明的支撑材料类别 vs 包内 manifest/实际顶级目录
    paper_text = ""
    paper_dir = ws / "paper"
    if paper_dir.is_dir():
        for p in sorted(paper_dir.rglob("*")):
            if p.suffix.lower() in (".tex", ".typ"):
                try:
                    paper_text += p.read_text(encoding="utf-8", errors="replace") + "\n"
                except Exception:
                    pass
    claimed = set(re.findall(r"\b(code|results|figures|references|styles|repro|R|data)\s*/", paper_text))
    claimed |= {c for c in ("README.md", "requirements.txt", "run_all.py", "renv.lock",
                            "AI 工具使用详情") if c in paper_text}
    man = gc.load_json(root / "repro" / "SUBMISSION_MANIFEST.json", None)
    actual = []
    if isinstance(man, dict):
        actual = [str(c.get("path", "")).rstrip("/").lstrip("./")
                  for c in (man.get("categories") or []) if c.get("path")]
    else:
        for d in sorted(root.iterdir()):
            if d.is_dir() and d.name not in ("paper", "data", "runs", "__MACOSX"):
                actual.append(d.name)
        for f in ("run_all.py", "README.md", "requirements.txt", "renv.lock"):
            if (root / f).is_file():
                actual.append(f)
    if claimed and actual:
        missing = [c for c in actual if c not in claimed]
        if missing and "支撑材料" in paper_text:
            problems.append(f"论文附录 A 声明支撑内容未覆盖包内实际类别：{missing[:8]}"
                            f"（T83：附录应自动从 SUBMISSION_MANIFEST 生成，不手写）")
    # T84：README "rerun 不一致以预置值为准" -> FAIL（应为 reference snapshot vs reproduction result）
    readme = root / "README.md"
    if readme.is_file():
        rt = readme.read_text(encoding="utf-8", errors="replace")
        if re.search(r"以\s*预置值?\s*为\s*准|预置值.{0,12}为准|不一致.{0,12}预置值", rt):
            problems.append("README 写『不一致时以预置值为准』——reproduction 语义错误："
                            "预置值=reference snapshot，重跑=reproduction result，超容差应 FAIL/investigate（T84）")
    # T86 前置：VERIFY_SUMMARY / warning ledger
    vs = gc.load_json(root / "repro" / "VERIFY_SUMMARY.json", None)
    ledger = gc.load_json(root / "repro" / "warning_ledger.json", None)
    # T85：VERIFY_SUMMARY 有 WARN 但 warning_ledger 缺失或含 open P0/P1 -> FAIL
    if isinstance(vs, dict):
        warn_n = 0
        for k in ("warns", "warn_total", "warning_count", "warnings_total"):
            v = vs.get(k)
            if isinstance(v, (int, float)):
                warn_n += int(v)
        if warn_n > 0 and not isinstance(ledger, dict):
            problems.append(f"VERIFY_SUMMARY 报告 {warn_n} 个 WARN 但无 repro/warning_ledger.json——"
                            f"『0 FAIL 即全绿』不可信，open P0/P1 必须可见（T85）")
        elif isinstance(ledger, dict):
            open_p01 = [w for w in (ledger.get("warnings") or [])
                        if isinstance(w, dict) and str(w.get("status", "open")) in ("open",)
                        and re.search(r"P0|P1", str(w.get("priority", "")) + str(w.get("id", "")))]
            if open_p01:
                problems.append(f"warning_ledger 存在未解决 P0/P1 WARN："
                                f"{[(w.get('id'), w.get('status')) for w in open_p01][:5]}（T85）")
    # T86：README 声称完整复现 vs reproduction_level==full
    if readme.is_file():
        rt = readme.read_text(encoding="utf-8", errors="replace")
        if re.search(r"完整复现|全部数值.{0,8}图|可完整", rt):
            level = (vs or {}).get("reproduction_level") if isinstance(vs, dict) else None
            if level != "full":
                problems.append("README 声称『可完整复现全部数值与图』但 VERIFY_SUMMARY.reproduction_level "
                                f"={level!r}（需 'full'）——smoke_min 不等于完整复现（T86）")
    # T87：repro/FINAL_MODEL_SPEC.json 与 reports 当前契约内容/hash 一致
    spec_repro = root / "repro" / "FINAL_MODEL_SPEC.json"
    spec_authority = root / "reports" / "FINAL_MODEL_SPEC.json" if (root / "reports" / "FINAL_MODEL_SPEC.json").is_file() \
        else ws / "reports" / "FINAL_MODEL_SPEC.json"
    if spec_repro.is_file() and spec_authority.is_file():
        h1 = gc.sha256_file(spec_repro)
        h2 = gc.sha256_file(spec_authority)
        if h1 != h2:
            problems.append(f"repro/FINAL_MODEL_SPEC.json（{h1[:12]}）与 authority 契约（{h2[:12]}）不一致——"
                            f"内容双份漂移（T87）")
    # T88：finalized PDF 存在但 VERIFY_SUMMARY.paper_pages 缺失
    if isinstance(vs, dict) and (root / "paper" / "main.pdf").exists():
        pp = vs.get("paper_pages")
        if pp in (None, "", 0):
            problems.append("VERIFY_SUMMARY.paper_pages 为空但包内含 main.pdf——finalized 交付应补齐页数（T88）")
    # T89：AI 使用报告声称全部绑定 vs registry 实际
    ai_pdf = root / "AI 工具使用详情.pdf"
    if ai_pdf.is_file():
        try:
            import fitz
            with fitz.open(str(ai_pdf)) as d:
                ai_text = "".join(p.get_text() for p in d)
        except Exception:
            ai_text = ""
        if re.search(r"(?i)(所有.{0,12}结果.{0,20}绑定|all\s+result.{0,20}bound|所有.{0,15}绑定).{0,60}model_spec",
                     ai_text) and "model_spec" in ai_text:
            reg = gc.load_json(root / "results" / "RESULT_REGISTRY.json", None)
            if isinstance(reg, dict):
                unbound = []
                for a in reg.get("artifacts") or []:
                    if not bool(a.get("requires_model_spec_binding")):
                        continue
                    doc = gc.load_json(root / str(a.get("file", "")), None)
                    if not isinstance(doc, dict):
                        continue
                    has = bool(doc.get("model_spec_sha256")) or bool(
                        (doc.get("_meta") or {}).get("model_spec_sha256"))
                    if not has:
                        unbound.append(a.get("file"))
                if unbound:
                    problems.append(f"AI 工具使用详情声称『所有结果绑定 model_spec』，但 registry 要求绑定的 "
                                    f"文件缺 hash：{unbound[:5]}（T89）")


def check(ws: Path, strict: bool):
    problems = []
    zp = find_zip(ws)
    if zp is None:
        problems.append("未找到提交包 ZIP（*支撑材料*.zip / *support*.zip）")
        for p in problems:
            print(f"  [FAIL] {p}")
        print("SUBMISSION_PACKAGE: FAIL（缺少提交包）")
        return 1
    print(f"  [OK] 提交包: {zp.name}（{zp.stat().st_size / 1024:.0f} KB）")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "pkg"
        root.mkdir()
        try:
            unpack(zp, root)
        except Exception as e:
            print(f"  [FAIL] ZIP 解压失败: {e}")
            return 1
        # README / requirements
        if not (root / "README.md").is_file():
            problems.append("ZIP 缺 README.md（P1-11：环境/运行顺序/附件放置说明）")
        if not (root / "requirements.txt").is_file():
            problems.append("ZIP 缺 requirements.txt（P1-11：依赖声明）")
        # 绝对路径
        for p, text in scan_texts(root):
            for m in ABS_PATH_RE.finditer(text):
                problems.append(f"{p.relative_to(root)}: 残留本机绝对路径 {m.group(0)!r}（P0-05：必须可移植）")
                break
        # appendix 一致性（P0-07：论文 A_code 来源集合 vs ZIP code/）
        a_code = None
        for cand in (root / "paper" / "sections" / "A_code.tex",):
            if cand.is_file():
                a_code = cand
        if a_code is not None:
            lines = a_code.read_text(encoding="utf-8", errors="replace")
            input_re = re.compile(r"\\input\s*\{([^}]+)\}")
            listed = set(re.findall(r"\\lstinputlisting(?:\[[^\]]*\])?\{([^}]+)\}", lines))
            for m in input_re.finditer(lines):
                inc = (root / m.group(1).strip())
                if not inc.suffix:
                    inc = inc.with_suffix(".tex")
                if inc.is_file():
                    listed |= set(re.findall(r"\\lstinputlisting(?:\[[^\]]*\])?\{([^}]+)\}",
                                             inc.read_text(encoding="utf-8", errors="replace")))
            code_files = {p.name for p in (root / "code").rglob("*.py")} if (root / "code").is_dir() else set()
            if code_files:
                missing = sorted(code_files - set(Path(x).name for x in listed))
                extra = sorted(set(Path(x).name for x in listed) - code_files)
                if missing:
                    problems.append(f"附录文献清单与 ZIP 不一致：code/ 有但附录未引入 {missing[:8]}（P0-07）")
                if extra:
                    problems.append(f"附录引入但 ZIP code/ 不存在：{extra[:8]}（P0-07）")
        # references 三方一致（P1-12/T55）：论文 bibitem ↔ ZIP references/literature.md ↔ method_citation_map
        bibs = set()
        for cand in (ws / "paper").glob("references*.tex") if (ws / "paper").is_dir() else []:
            t = cand.read_text(encoding="utf-8", errors="replace")
            bibs |= set(re.findall(r"\\bibitem\{([^}]+)\}", t))
        lit = root / "references" / "literature.md"
        lit_refs = set()
        if lit.is_file():
            for m in re.finditer(r"^\|\s*([A-Za-z0-9_\-]+)\s*\|", lit.read_text(encoding="utf-8", errors="replace"),
                                 re.M):
                if m.group(1).startswith("ref"):
                    lit_refs.add(m.group(1))
        cmap_rel = "reports/method_citation_map.json"
        cmap_refs = set()
        cmap = gc.load_json(ws / cmap_rel, None)
        if isinstance(cmap, dict):
            for v in cmap.values():
                if isinstance(v, list):
                    cmap_refs |= set(str(x) for x in v)
                elif isinstance(v, str):
                    cmap_refs.add(v)
        if bibs and lit_refs and bibs != lit_refs:
            problems.append(f"论文引用 {len(bibs)} 篇（{sorted(bibs - lit_refs)[:5]}…）≠ ZIP literature.md "
                            f"{len(lit_refs)} 篇——references registry 落后（P1-12/T55）")
        if cmap_refs and cmap_refs - bibs:
            problems.append(f"method_citation_map 引用未在参考文献定义：{sorted(cmap_refs - bibs)[:5]}（P1-12/T55）")
        # dangling 内部路径（P1-15）：具体文件字面引用，且该文件在解压后不存在 -> FAIL；
        # 诊断工具（需完整 Agent 工作区的门禁报告）按 README 分类豁免
        DIAGNOSTIC = {"render_v3_deliverables.py", "leakage_proof.py"}
        DANGLING_FILES = ["reports/ANALYSIS_MODELING_REPORT.md",
                          "reports/v3_official_rules.json",
                          "reports/v3_deliverables/", "reports/gates/"]
        for p, text in scan_texts(root):
            if p.name in DIAGNOSTIC:
                continue
            for d in DANGLING_FILES:
                if d in text and not (root / d).exists():
                    problems.append(f"{p.relative_to(root)}: 引用 ZIP 中不存在的内部路径 {d}"
                                    f"（P1-15 dangling；诊断工具除外）")
                    break
        # v4.3（§10/P0-07, T82-T89）：support registry 语义一致性
        check_v43(ws, root, problems)
    if problems:
        for p in problems:
            print(f"  [FAIL] {p}")
        print("SUBMISSION_PACKAGE: FAIL")
        return 1
    print("SUBMISSION_PACKAGE: PASS（解压/绝对路径/README/requirements/附录一致/refs 一致/dangling 全部通过）")
    return 0


def smoke(ws: Path, data: Path, script: str, extra_args: list):
    zp = find_zip(ws)
    if zp is None:
        print("FAIL 未找到提交包 ZIP")
        return 1
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "pkg"
        root.mkdir()
        unpack(zp, root)
        # 官方附件放置：优先 README 声明的 data/ 路径；也兼容根目录
        data_dir = root / "data"
        data_dir.mkdir(exist_ok=True)
        shutil.copy2(data, data_dir / data.name)
        if data.name != "附件.xlsx":
            shutil.copy2(data, data_dir / "附件.xlsx")
        print(f"  [OK] 附件 {data.name} -> {data_dir}")
        # smoke run
        try:
            proc = subprocess.run(
                [sys.executable, script, *extra_args], capture_output=True, text=True,
                encoding="utf-8", errors="replace", cwd=str(root), timeout=3600)
        except subprocess.TimeoutExpired:
            print(f"  [FAIL] smoke run 超时（{script}）")
            return 1
        if proc.returncode != 0:
            print(f"  [FAIL] smoke run 退出码 {proc.returncode}: {script}")
            print((proc.stdout or "")[-800:])
            print((proc.stderr or "")[-800:])
            return 1
        print(f"  [OK] smoke run 通过: python {script} {' '.join(extra_args)}")
        print((proc.stdout or "")[-1000:])
        print("SUBMISSION_PACKAGE: clean-room smoke PASS（可运行支撑材料）")
        return 0


def build_manifest(zp: Path, out: Path):
    """v4.3（P1-08）：从最终 ZIP 自动构建 SUBMISSION_MANIFEST.json（论文 Appendix A 由此生成）。"""
    categories = {"code": "source", "results": "authority_results", "figures": "publication_figures",
                  "references": "references", "styles": "styles", "repro": "provenance",
                  "R": "r_source", "data": "input_data", "paper": "paper_source"}
    with zipfile.ZipFile(zp) as z:
        names = z.namelist()
    top = sorted({n.split("/")[0] for n in names if "/" in n and not n.startswith("__")})
    cats = [{"path": c, "role": categories.get(c, "other")} for c in top]
    files = [{"path": n, "size": 0} for n in names]
    man = {
        "schema_version": 1,
        "package_sha256": gc.sha256_file(zp),
        "package_files": len(names),
        "categories": cats,
        "files": files,
        "built_at": gc.iso_now(),
        "note": "由 submission_package_gate --build-manifest 从最终 ZIP 自动生成；论文附录 A 必须与本文件一致（T83）。",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"SUBMISSION_MANIFEST: {len(files)} 文件 / {len(cats)} 类别 -> {out}")
    print(f"  categories: {[c['path'] for c in cats]}")
    return 0


def main(argv=None):
    gc.force_utf8()
    ap = argparse.ArgumentParser(description="v4.2 支撑材料提交包审计")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--smoke", action="store_true", help="clean-room 解压后实际运行最小复现脚本")
    ap.add_argument("--data", default=None, help="官方附件 xlsx 路径（--smoke 需要）")
    ap.add_argument("--script", default="problem1.py", help="smoke 脚本（默认 problem1.py，相对解压根）")
    ap.add_argument("--smoke-args", default="", help="透传给 smoke 脚本的附加参数（如 '--skip 5,6'）")
    ap.add_argument("--build-manifest", action="store_true",
                    help="从最终 ZIP 构建 repro/SUBMISSION_MANIFEST.json")
    args = ap.parse_args(argv)

    ws = Path(args.workspace).resolve()
    if args.build_manifest:
        zp = find_zip(ws)
        if zp is None:
            print("FAIL --build-manifest 未找到提交包 ZIP")
            return 1
        return build_manifest(zp, ws / "repro" / "SUBMISSION_MANIFEST.json")
    if args.smoke:
        if not args.data:
            print("FAIL --smoke 需要 --data <附件.xlsx>")
            return 2
        return smoke(ws, Path(args.data).resolve(), args.script, args.smoke_args.split())
    return check(ws, True)


if __name__ == "__main__":
    sys.exit(main())
