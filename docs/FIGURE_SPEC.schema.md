# FIGURE_SPEC.json — v4.3 科学图设计规范（schema）

> 位置：`figures/specs/<figure_id>.figure.json`。
> 与 `figure_manifest.json` 的关系：**manifest 是论文事实与 provenance；FIGURE_SPEC 是视觉设计规范**。
> 两者可关联（figure_id/claim_id），不要混为一个无限膨胀 JSON。

## 完整 schema

```json
{
  "figure_id": "fig_q4_primary",
  "claim_id": "Q4.PRIMARY_PERFORMANCE",
  "figure_role": "primary | secondary | schematic | appendix",
  "evidence_type": "classification_performance | longitudinal_effect | hazard_curve | forest | ...",
  "renderer": "r_ggplot2 | python_matplotlib | tikz | svg_inkscape | auto",
  "layout": {
    "grid_columns": 12,
    "panels": [
      {"id": "A", "role": "primary", "colspan": 7},
      {"id": "B", "role": "support", "colspan": 5}
    ]
  },
  "visual_encoding": {
    "primary": "strong_color_dark_blue",
    "comparators": "gray",
    "baseline": "light_gray_dashed",
    "alert": "orange_red"
  },
  "label_budget": 8,
  "final_width_mm": 170,
  "direct_labeling": true,
  "caption_policy": "voice_from_claim"
}
```

## 语义层级（§26：颜色表示"角色/语义"，不是类别索引）

| 角色 | 视觉编码 |
| --- | --- |
| primary | 深蓝等强色（跨图同实体同色） |
| comparators | 灰阶（细线） |
| baseline / random | 浅灰虚线 |
| alert / risk | 橙红 |
| 次要强调 | 青绿 |

`comparators`/`baseline` 非灰阶 → figure_spec_gate WARN（T92）。

## Renderer Routing（§21/22）

- statistical figure（scatter+smooth+CI / forest / 分布 / ROC-PR / survival / calibration /
  decision curve / heatmap / multi-panel）：首选 `r_ggplot2`；无 R 环境时
  `python_matplotlib` —— **必须在 FIGURE_SPEC.renderer 显式声明，禁止静默切换**；
  `auto` 时运行期探测并写 `renderer_fallback: python_matplotlib` 记录。
- schematic / graphical abstract：`tikz` / SVG。
- `r_ggplot2` 必须配 `renv.lock`（可复现；缺 → T93 FAIL）。

## 强制规则（figure_spec_gate）

1. manifest 中 `visual_priority=primary` 的图必须有完整 FIGURE_SPEC（T90 FAIL）。
2. `renderer=r_ggplot2` 且无 `renv.lock` → FAIL（T93）。
3. 脚本/图引用用户本机字体绝对路径 → FAIL（T94；字体走系统探测，不绑定本机路径）。
4. T92 语义配色偏离 → WARN（人工确认后销号）。
