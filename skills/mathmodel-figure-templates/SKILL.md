---
name: mathmodel-figure-templates
description: Use this skill in the MathModel LaTeX sandbox when the user asks to reproduce built-in scientific visualization templates, especially prompts from the Improve tab mentioning $mathmodel-figure-templates, 科研绘图模板, SHAP蜂群柱状图, 配对云雨图, 交叉验证ROC, 泰勒图, 相关矩阵组合图, 预测真实值边缘分布图, TPE调参3D曲面, 下三角相关矩阵半边小提琴图, 分组环形热图, 城市公园降温组合图, or Nature和弦图. It provides ready-to-run Python scripts bundled inside the skill.
whenToUse: "数模论文需要炫酷科研绘图（云雨图、泰勒图、ROC、SHAP、和弦图等）时使用。"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# MathModel Figure Templates

## 本机论文级图表（Windows/DSH，优先用这节）

上游内容（下方 Fast Path 起）面向 Linux LaTeX 沙箱（/home/user 路径），本机不可直接用。本机出图走两条路：

### 流程图/技术路线图 → TikZ（首选，零安装）
- 模板在 `tikz/` 目录（本机 xelatex 实测可编译）：
  - `tikz_flow_vertical.tex` —— 纵向技术路线图（fig_roadmap，三阶段输入→建模→输出骨架）
  - `tikz_flow_layers.tex` —— 分层架构图（指标体系/模型结构/模块关系）
  - `tikz_flow_decision.tex` —— 带判断菱形的子问题求解流程（fig_flow_qN）
- 用法：论文导言区加入 `\usepackage{tikz}` + `\usetikzlibrary{arrows.meta, positioning, fit, backgrounds, shapes.geometric}`（一次即可），把模板中的 `\begin{tikzpicture}...\end{tikzpicture}` 整段复制进正文 `\begin{figure}[H]\centering ... \end{figure}`，改节点文字即可。
- 为什么选它：图内字体与正文完全一致（ctex 宋体/黑体）、矢量、公式可直接进节点、无需额外软件——这是真国一论文流程图的同款做法。
- 颜色纪律：黑/深灰 + 至多一种强调色；灰度打印可辨；节点文字短。

### 数据图 → matplotlib + 论文风格
- 绘图脚本开头：
  ```python
  import mpl_paper_style as mps   # 位于本 skill 的 scripts/
  mps.apply()
  fig, ax = mps.subplots(width_cm=12, aspect=0.75)
  ...
  mps.save(fig, "figures/xxx")    # PNG 300dpi + 矢量 PDF
  ```
- 要点：SimHei 中文字体、图内字号 8pt（对应正文 12pt）、去顶/右 spine、浅网格、`pdf.fonttype=42`（修复 matplotlib 默认 Type3 导致 xelatex 编译失败的历史问题，矢量 PDF 可直接 \includegraphics）。

## Fast Path

This skill is bundled into the LaTeX sandbox at `/home/user/.claude/skills/mathmodel-figure-templates`. It contains ready-to-run Python/matplotlib scripts for the figure templates exposed in the MathModel Improve tab.

## Fast Path

1. Match the requested chart in `references/figure-catalog.md`.
2. From `/home/user/workspace`, run the renderer with the template id:

```bash
python3 /home/user/.claude/skills/mathmodel-figure-templates/scripts/render_template.py paired-raincloud
```

3. The renderer copies the bundled template script into `绘图复刻/scripts/`, runs it there, and writes outputs to `绘图复刻/outputs/`.
4. Return the generated PNG/PDF/SVG paths and the copied script path to the user.

Use `--list` to show supported ids:

```bash
python3 /home/user/.claude/skills/mathmodel-figure-templates/scripts/render_template.py --list
```

## Output Contract

- Work under the current workspace unless the user gives another path.
- Default project folder: `绘图复刻`.
- Script path: `绘图复刻/scripts/make_<template>.py`.
- Outputs: `绘图复刻/outputs/<template>_replica.png`, `.pdf`, `.svg`.
- Use the bundled scripts as the first choice; edit the copied workspace script only when the user requests customization.
- The bundled scripts use deterministic simulated data. Do not claim simulated values reproduce a source study exactly.

## Template Ids

- `multiclass-shap-combo`
- `paired-raincloud`
- `cv-roc-ci`
- `taylor-diagram`
- `correlation-pairgrid`
- `prediction-marginal-grid`
- `rf-tpe-surface`
- `grouped-corr-split-violin`
- `grouped-circular-heatmap`
- `urban-park-cooling-combo`
- `nature-chord-diagram`

## When Customizing

If the user asks for changes, copy/run the nearest template first, then edit the copied file in `绘图复刻/scripts/`. Preserve:

- `MPLCONFIGDIR` before importing matplotlib.
- deterministic seeds for simulated data.
- PNG/PDF/SVG export.
- readable labels, legends, and high-DPI output.

Use `references/plot-recipes.md` for implementation patterns.
