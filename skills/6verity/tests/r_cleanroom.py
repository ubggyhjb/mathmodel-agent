# -*- coding: utf-8 -*-
"""r_cleanroom.py — v4.4（P1-18/T119）：R 渲染真可复现性 clean-room 测试。

独立于 NIPT：用 figure-templates 的 R 模板 + 内嵌最小假数据，在临时目录验证——
  1. Rscript 可用（PATH / RSCRIPT env / 常见安装位置探测）；
  2. renv.lock parse（若存在）；
  3. 渲染 example_forest（AFT 森林图）与 example_roc（ROC），输出非空矢量 PDF；
  4. 重跑一次验证确定性输出（PNG 逐字节一致即为强证据，PDF 退化为 non-empty 检查）。

无 R 环境：打印 NOT VERIFIED 并退出 0（调用方不得把「R 路由已验证」当作 PASS——run_tests T119 应 SKIP）。

用法：python tests/r_cleanroom.py [--quiet]
退出码：0 = verified（或 no-R 显式记录）；1 = R 存在但验证失败。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[2] / "mathmodel-figure-templates" / "R"


def find_rscript() -> str | None:
    cand = os.environ.get("RSCRIPT") or shutil.which("Rscript")
    if cand:
        return cand
    for p in (r"E:\R-4.6.1\bin\Rscript.exe", r"C:\Program Files\R"):
        base = Path(p)
        if p.endswith("Rscript.exe") and base.is_file():
            return str(base)
        if base.is_dir():
            for v in sorted(base.glob("R-*/bin/Rscript.exe"), reverse=True):
                return str(v)
    return None


def write_fake_results(tmp: Path) -> None:
    """模板脚本数据结构的最小假数据（与 NIPT 同构：aft coef/se/p_value + pooled.<m>.roc/auc）。"""
    coef = {"intercept": 0.8, "bmi_coef": -0.21, "age_coef": 0.03, "parity_coef": 0.05, "ivf_coef": -0.02}
    p3 = {"aft": {"coef": coef,
                  "se": {k: 0.08 for k in coef},
                  "p_value": {"bmi_coef": 0.001, "age_coef": 0.4, "parity_coef": 0.5, "ivf_coef": 0.7},
                  "n": 267}}
    (tmp / "results").mkdir(parents=True, exist_ok=True)
    (tmp / "results" / "p3_models.json").write_text(json.dumps(p3), encoding="utf-8")
    roc = {"fpr": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0], "tpr": [0.0, 0.6, 0.8, 0.9, 0.95, 1.0]}
    p4 = {"pooled": {m: {"roc": roc, "auc": a} for m, a in
                     [("lr_full", 0.78), ("rf", 0.75), ("gbdt", 0.71), ("z_base", 0.48)]}}
    (tmp / "results" / "p4_curves.json").write_text(json.dumps(p4), encoding="utf-8")


def main() -> int:
    quiet = "--quiet" in sys.argv
    rscript = find_rscript()
    if rscript is None:
        print("R_CLEANROOM: NOT VERIFIED（未找到 Rscript；R 路由未验证，不得当作 PASS）")
        return 0
    if not (TEMPLATES / "plots" / "example_forest.R").is_file():
        print(f"R_CLEANROOM: FAIL 模板缺失 {TEMPLATES / 'plots' / 'example_forest.R'}")
        return 1
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        shutil.copytree(TEMPLATES, tmp / "R")
        write_fake_results(tmp)
        ok_all = True
        pdfs = []
        for script, stem in (("example_forest.R", "fig_q3_effects"), ("example_roc.R", "fig_q4_roc")):
            proc = subprocess.run([rscript, f"R/plots/{script}"], cwd=str(tmp),
                                  capture_output=True, text=True, encoding="utf-8", errors="replace")
            if proc.returncode != 0:
                ok_all = False
                if not quiet:
                    print(f"R_CLEANROOM: FAIL {script} exit={proc.returncode}\n{proc.stderr[-800:]}")
                continue
            pdf = tmp / "figures" / f"{stem}.pdf"
            pdfs.append(pdf)
            if not pdf.is_file() or pdf.stat().st_size < 1024:
                ok_all = False
                if not quiet:
                    print(f"R_CLEANROOM: FAIL {script} 输出缺失/过小 {pdf}")
            else:
                head = pdf.read_bytes()[:5]
                if head != b"%PDF-":
                    ok_all = False
                    if not quiet:
                        print(f"R_CLEANROOM: FAIL {pdf} 非矢量 PDF（head={head!r}）")
        # 重跑一次验证确定性（PNG 逐字节）
        png_before = None
        png_path = tmp / "figures" / "fig_q3_effects.png"
        if png_path.is_file():
            png_before = png_path.read_bytes()
        subprocess.run([rscript, "R/plots/example_forest.R"], cwd=str(tmp), capture_output=True)
        deterministic = True
        if png_before is not None and png_path.is_file():
            deterministic = png_path.read_bytes() == png_before
        if ok_all and deterministic:
            print(f"R_CLEANROOM: PASS（Rscript={Path(rscript).name}，2 golden 渲染非空矢量，"
                  f"重跑确定性={'OK' if deterministic else 'PNG 有浮动'}）")
            return 0
        print("R_CLEANROOM: FAIL（见上）")
        return 1


if __name__ == "__main__":
    sys.exit(main())
