# -*- coding: utf-8 -*-
"""mpl_paper_style.py — v3 数模论文级 matplotlib 风格（biomedical paper 版）。

用法（绘图脚本开头）：
    import mpl_paper_style as mps
    mps.apply()
    fig, ax = mps.subplots(width_cm=12, aspect=0.75)   # 或 plt.subplots()
    ...
    mps.save(fig, "figures/xxx")   # 同时输出 xxx.png(300dpi) + xxx.pdf(矢量)

v3 视觉体系（_mathmode.docx 十三条，参考 Nature Medicine / Lancet DH / JAMA /
Statistics in Medicine 而非 NeurIPS 装饰风）：
- 颜色用于强调不用于平均分组：主模型深蓝 / 风险异常橙红 / 普通对照中灰 /
  背景数据浅灰 / 第三必要强调青绿。整篇统一，禁止每组一个鲜艳色。
- 次要信息后退：原始散点浅灰高透明；主趋势线 2-2.5pt；次要曲线 1.2-1.5pt；
  CI 同色低透明；阈值浅灰细虚线。
- 减少 legend：能 direct labeling 直接在线尾写字（mps.direct_label）。
- 减少边框与网格：默认去 top/right spine，垂直网格关闭，水平网格极淡，白底。
- 图标题写结论（调用方负责），图注说明方法。
- 系数/效应统一 forest plot（mps.forest_eval：point + 95% CI + 零线）。

兼容：apply()/subplots()/save() 签名不变；色板更新为 v3 五色。
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # 无显示环境安全，必须先于 pyplot 导入
import matplotlib.pyplot as plt

# v3 五色系统（_mathmode.docx 十三条）
PRI = "#2166ac"      # 主模型：深蓝
RISK = "#e64b35"     # 风险/异常：橙红
NEUTRAL = "#7f7f7f"  # 普通对照：中灰
BG = "#c8c8c8"       # 背景数据：浅灰
ACCENT3 = "#2a9d8f"  # 第三必要强调：青绿
PALETTE = [PRI, RISK, NEUTRAL, ACCENT3, "#8c6bb1", BG]
# 线宽档（次要信息后退）
L_MAIN = 2.2    # 主趋势线 2-2.5pt
L_SUB = 1.35    # 次要曲线 1.2-1.5pt
L_THRESH = 1.0  # 阈值虚线
ALPHA_SCATTER = 0.25  # 原始散点透明度（浅灰 + 高透明）
ALPHA_CI = 0.28       # CI 带透明度


def palette():
    return {"primary": PRI, "risk": RISK, "neutral": NEUTRAL, "background": BG,
            "accent3": ACCENT3}


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
        "lines.linewidth": L_SUB,
        "lines.markersize": 4.5,
        "grid.linewidth": 0.5,
        "grid.alpha": 0.15,
        "legend.frameon": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "axes.axisbelow": True,
        "axes.prop_cycle": plt.cycler(color=PALETTE),
    })


def apply_science():
    """可选：SciencePlots 学术样式预设（pip install SciencePlots 后可用）。
    以 science+no-latex 为基础（学术配色/线型/刻度风格），随后重新覆盖
    中文字体与 v3 五色板，保证中文不乱码、色板不漂移。"""
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


# ---------- v3 辅助函数 ----------

def despine(ax, keep_left=True, keep_bottom=True):
    """去 top/right spine + 关垂直网格 + 水平网格极淡（v3 默认观感）。"""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(keep_left)
    ax.spines["bottom"].set_visible(keep_bottom)
    ax.xaxis.grid(False)
    ax.yaxis.grid(True, alpha=0.15, linewidth=0.5)
    ax.set_facecolor("white")
    return ax


def primary_line(ax, x, y, *, color=PRI, lw=L_MAIN, **kw):
    """主趋势线（2-2.5pt）——全篇只有主模型/主结论用。"""
    kw.setdefault("label", "主模型")
    return ax.plot(x, y, color=color, lw=lw, solid_capstyle="round", **kw)


def secondary_line(ax, x, y, *, color=NEUTRAL, lw=L_SUB, alpha=0.85, **kw):
    """次要曲线（1.2-1.5pt）——对照组/次要模型。"""
    return ax.plot(x, y, color=color, lw=lw, alpha=alpha, **kw)


def scatter_bg(ax, x, y, *, color=BG, alpha=ALPHA_SCATTER, s=6, **kw):
    """背景原始散点：浅灰 + 高透明（次要信息后退）。"""
    return ax.scatter(x, y, s=s, color=color, alpha=alpha, edgecolors="none", **kw)


def ci_band(ax, x, lo, hi, *, color=PRI, alpha=ALPHA_CI, **kw):
    """置信带：同色低透明度。"""
    kw.setdefault("lw", 0)
    return ax.fill_between(x, lo, hi, color=color, alpha=alpha, **kw)


def threshold_line(ax, y=None, x=None, *, color=BG, lw=L_THRESH, ls="--", **kw):
    """阈值参考线：浅灰细虚线。"""
    if x is not None:
        return ax.axvline(x, color=color, lw=lw, ls=ls, **kw)
    return ax.axhline(y, color=color, lw=lw, ls=ls, **kw)


def direct_label(ax, x, y, s, *, color="black", fontsize=8, ha="left", va="center", **kw):
    """线尾直标（替代 legend）：收小字号、无框。"""
    return ax.text(x, y, s, fontsize=fontsize, color=color, ha=ha, va=va, **kw)


def panel_label(ax, s, *, x=0.0, y=1.0, fontsize=10, weight="bold"):
    """Panel 标签（A/B/C）：左上角 10pt。"""
    return ax.text(x, y, s, transform=ax.transAxes, fontsize=fontsize,
                   weight=weight, ha="left", va="bottom",
                   bbox=dict(boxstyle="square,pad=0.15", fc="white", ec="none"))


def forest_eval(ax, estimates, ci_low, ci_high, labels, *, zero_ref=0.0,
                color=PRI, xlabel="Effect (95% CI)", show_zero=True, **kw):
    """横向森林图：point estimate + 95% CI + 垂直零线（v3 系数统一语言）。
    estimates/ci_low/ci_high 为等长序列；labels 为行标签。"""
    import numpy as np
    y_pos = np.arange(len(estimates), 0, -1)
    if show_zero:
        ax.axvline(zero_ref, color=NEUTRAL, lw=1.0, ls="--", zorder=1)
    ax.errorbar(estimates, y_pos,
                xerr=[np.subtract(estimates, ci_low), np.subtract(ci_high, estimates)],
                fmt="o", color=color, ecolor=color, elinewidth=1.2,
                capsize=3, markersize=5, zorder=3, **kw)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=8.5)
    ax.set_xlabel(xlabel)
    ax.set_ylim(0.4, len(estimates) + 0.6)
    ax.set_xlim(min(ci_low) - 0.1 * max(1, abs(min(ci_low))),
                max(ci_high) + 0.1 * max(1, abs(max(ci_high))))
    despine(ax, keep_left=False)
    return ax
