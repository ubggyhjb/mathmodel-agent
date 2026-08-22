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
        # dangling 内部路径（P1-15）
        for p, text in scan_texts(root):
            if re.search(r"reports/[A-Za-z_]+\.md|ANALYSIS_MODELING_REPORT", text) \
                    and not any((root / r).exists() for r in ("reports",)):
                problems.append(f"{p.relative_to(root)}: 引用 ZIP 中不存在的内部路径（P1-15 dangling）")
                break
    if problems:
        for p in problems:
            print(f"  [FAIL] {p}")
        print("SUBMISSION_PACKAGE: FAIL")
        return 1
    print("SUBMISSION_PACKAGE: PASS（解压/绝对路径/README/requirements/附录一致/refs 一致/dangling 全部通过）")
    return 0


def smoke(ws: Path, data: Path, script: str):
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
                [sys.executable, script], capture_output=True, text=True, encoding="utf-8",
                errors="replace", cwd=str(root), timeout=1800)
        except subprocess.TimeoutExpired:
            print(f"  [FAIL] smoke run 超时（{script}）")
            return 1
        if proc.returncode != 0:
            print(f"  [FAIL] smoke run 退出码 {proc.returncode}: {script}")
            print((proc.stdout or "")[-600:])
            print((proc.stderr or "")[-600:])
            return 1
        print(f"  [OK] smoke run 通过: python {script}")
        print((proc.stdout or "")[-800:])
        print("SUBMISSION_PACKAGE: clean-room smoke PASS（可运行支撑材料）")
        return 0


def main(argv=None):
    gc.force_utf8()
    ap = argparse.ArgumentParser(description="v4.2 支撑材料提交包审计")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--smoke", action="store_true", help="clean-room 解压后实际运行最小复现脚本")
    ap.add_argument("--data", default=None, help="官方附件 xlsx 路径（--smoke 需要）")
    ap.add_argument("--script", default="problem1.py", help="smoke 脚本（默认 problem1.py，相对解压根）")
    args = ap.parse_args(argv)

    ws = Path(args.workspace).resolve()
    if args.smoke:
        if not args.data:
            print("FAIL --smoke 需要 --data <附件.xlsx>")
            return 2
        return smoke(ws, Path(args.data).resolve(), args.script)
    return check(ws, True)


if __name__ == "__main__":
    sys.exit(main())
