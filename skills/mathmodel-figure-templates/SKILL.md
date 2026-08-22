---
name: mathmodel-figure-templates
description: "数学建模论文的发表级科学图系统（Publication Scientific Figure System）：严格遵循 Evidence -> Visual Encoding -> Renderer 流程，提供统计图/示意图的可复现渲染模板（matplotlib 样式、TikZ 示意图、R/ggplot2 路由），用于论文 Figure 的最终设计与渲染。不是『炫酷模板库』：禁止先选模板再找数据塞进去。"
whenToUse: "在 3coding-visual/5writing 阶段需要生成或重制论文正式图（数据图、森林图、ROC/PR、生存曲线、校准、决策曲线、多面板组合、示意图/图形摘要）时使用；或用户要求优化已有论文图的视觉层级、配色语义、排版构图时使用。"
allowed-tools: pwsh, read, write, edit, grep, glob, subagent, workflow, web_search, ask_user_question
---

# MathModel Publication Scientific Figure System

定位（v4.3，任务书 §23）：

> **Evidence → Visual Encoding → Renderer**，绝不能 **Template → 找数据塞进去**。

本 skill 不做"炫酷模板图库"（SHAP 蜂群/raincloud/Taylor/3D TPE/circular heatmap 等）——
那些只有数据形状真正需要时（证据类型匹配）才用；任何图必须先有 `claim` 与 `visual_encoding`。

## 流程（每张正式图）

```
Result / Claim（figure_manifest story.claims）
   ↓
Figure Claim（one-line claim）
   ↓
Visual Encoding Spec（figure_manifest 唯一事实 + figures/specs/<id>.figure.json）
   ↓
Panel Outline（12 列网格；panel role/colspan/label_budget）
   ↓
Renderer Routing（R/ggplot2 首选 → Python/matplotlib fallback（显式记录）→ TikZ/SVG）
   ↓
Panel Render
   ↓
Figure Composition（final-size：final_width_mm）
   ↓
Visual Critic（数据保真/label 经济/bbox 碰撞/主次层级，≤3 轮）
   ↓
Publication Figure（PDF/SVG 矢量；PNG 仅 review preview）
```

正式主图必须在 `figures/specs/<id>.figure.json` 声明
（figure_id/claim_id/figure_role/evidence_type/renderer/layout/visual_encoding/
label_budget/final_width_mm；T90 门禁强制）。

## 语义配色（角色 = 颜色，非类别索引；跨图同实体同色）

| 角色 | 编码 |
| --- | --- |
| primary | 深蓝等强色 |
| comparators | 灰阶细线 |
| baseline/random | 浅灰虚线 |
| alert/risk | 橙红 |
| 次要强调 | 青绿 |

避免"有四条线就四种颜色"；legend 负担优先用 direct labeling 消解。

## 本机渲染路径

### 示意图/技术路线 → TikZ（零安装，图内字体与正文一致）
- 模板在 `tikz/`（xelatex 实测可编译）：`tikz_flow_vertical.tex`（纵向路线图）、
  `tikz_flow_layers.tex`（分层架构）、`tikz_flow_decision.tex`（带判断菱形流程）。
- 颜色纪律：黑/深灰 + 至多一种强调色；灰度打印可辨；节点文字短、字号 ≥7pt。

### 数据图 → matplotlib 论文风格（Python 后端）
```python
import mpl_paper_style as mps   # 本 skill scripts/（支撑包内联 styles/mpl_paper_style.py）
mps.apply()
fig, ax = mps.subplots(width_cm=12, aspect=0.75)
...
mps.save(fig, "figures/xxx")    # PNG 300dpi + 矢量 PDF
```
要点：中文字体经系统探测（禁止字体绝对路径，T94）、图内字号 8pt（对应正文 12pt）、
去顶/右 spine、浅网格、`pdf.fonttype=42`；最终宽度 170mm（正文通栏）/84mm（双栏）。

### R/ggplot2 首选（当本机有 R 时）
- 统计图（scatter+smooth+CI / forest / 分布 / ROC-PR / survival / calibration /
  decision curve / heatmap / multi-panel）首选 `r_ggplot2`，依赖
  ggplot2/patchwork/ggrepel/ggtext/scales/ggdist/cowplot/svglite/systemfonts。
- **可复现**：`renv.lock` 必须随项目；renders 前 `renv::restore()`。
- 无 R：自动 fallback Python **并在 FIGURE_SPEC 记录 `renderer_fallback: python_matplotlib`**，
  禁止静默切换。

## Visual Critic（投稿级检查，≤3 轮）

- data fidelity：曲线/点与结果 JSON 一致（figure_story source hash 已管）
- label economy：label_budget 内；direct labeling > legend
- 语义配色：primary/comparators/baseline 层阶（T92）
- final-size render QA：bbox collision、面板严重失衡、文字溢出、有效字号 ≥7pt
- 观感（层级/平衡/留白/阅读顺序）交给 Reviewer C/visual subagent 结构化裁决
  （page_visual_review.json），本 skill 只做确定性检查。

## 参考

- `references/figure-catalog.md`：证据类型 → 推荐 chart（按数据形状选型，禁止按模板选型）
- `references/plot-recipes.md`：配方级示例
- `docs/FIGURE_SPEC.schema.md`（仓库 docs/）：FIGURE_SPEC 字段定义
