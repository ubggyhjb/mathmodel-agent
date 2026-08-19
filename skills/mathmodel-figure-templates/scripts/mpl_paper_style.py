# -*- coding: utf-8 -*-
"""mpl_paper_style.py — 数模论文级 matplotlib 风格（2026 官方展示论文实证版）。

用法（绘图脚本开头）：
    import mpl_paper_style as mps
    mps.apply()
    fig, ax = mps.subplots(width_cm=12, aspect=0.75)   # 或 plt.subplots()
    ...
    mps.save(fig, "figures/xxx")   # 同时输出 xxx.png(300dpi) + xxx.pdf(矢量)

实证依据（2025 官方展示论文全页 + 2010-2024 优秀论文全库抽样）：
- 官方主流 = 矢量图、白底、蓝 + 橙双强调色 + 灰辅助（禁彩虹色）、图注在图下方居中。
- 图内字号 = 正文 0.75-0.8 倍：正文 12pt → 图内 9pt（历史 8pt 偏小，评审放大才能看清）。
- 中文字体 SimHei（本机已装）+ unicode_minus，中文图例/标签不乱码、负号正常。
- pdf.fonttype=42 / ps.fonttype=42：xelatex 可直接嵌入矢量 PDF。
  历史教训：matplotlib 默认 Type3 字体曾导致 MiKTeX 编译失败，被迫退回 PNG 300dpi；
  设了 42 之后矢量 PDF 直接可用，图质上一个台阶。
- 学术化：去顶/右 spine、浅网格、单一强调色系，灰度打印可辨。
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # 无显示环境安全，必须先于 pyplot 导入
import matplotlib.pyplot as plt

ACCENT = "#1f77b4"
# 官方蓝橙双强调色板：第 1 色蓝（主线）、第 2 色橙（对比线）、其后为低饱和区分色
PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
           "#9467bd", "#7f7f7f", "#17becf", "#8c564b"]


def apply():
    plt.rcParams.update({
        "font.sans-serif": ["SimHei", "Microsoft YaHei", "SimSun"],
        "axes.unicode_minus": False,
        "font.size": 9,
        "axes.labelsize": 9,
        "axes.titlesize": 9.5,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 8.5,
        "figure.dpi": 110,
        "savefig.dpi": 300,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "axes.linewidth": 0.8,
        "lines.linewidth": 1.5,
        "lines.markersize": 4.5,
        "grid.linewidth": 0.5,
        "grid.alpha": 0.25,
        "legend.frameon": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "axes.prop_cycle": plt.cycler(color=PALETTE),
    })


def apply_science():
    """可选：SciencePlots 学术样式预设（pip install SciencePlots 后可用）。
    以 science+no-latex 为基础（学术配色/线型/刻度风格），随后重新覆盖
    中文字体与本模式蓝橙双强调色板，保证中文不乱码、色板不漂移。"""
    try:
        import scienceplots  # noqa: F401
        plt.style.use(["science", "no-latex", "bright"])
    except Exception:
        raise ImportError("SciencePlots 未安装：pip install SciencePlots")
    apply()


def subplots(width_cm=12, aspect=0.75, nrows=1, ncols=1, **kw):
    """论文宽度版 subplots：width_cm 为图内可用宽度（正文约 15cm，图宽 80-90% → 12-13.5cm）。"""
    w = width_cm / 2.54
    fig, ax = plt.subplots(nrows, ncols, figsize=(w, w * aspect), **kw)
    return fig, ax


def save(fig, stem, png=True, pdf=True):
    """保存 PNG(300dpi) + 矢量 PDF；stem 不带扩展名。"""
    stem = Path(stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    if png:
        fig.savefig(str(stem) + ".png", bbox_inches="tight", pad_inches=0.02)
    if pdf:
        fig.savefig(str(stem) + ".pdf", bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
