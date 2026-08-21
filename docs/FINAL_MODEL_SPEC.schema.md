# FINAL_MODEL_SPEC.json — v4 可执行模型契约（schema 文档）

> 唯一允许被 `3coding-visual` 实现、被 `5writing` 描述、被 `6verity/methodology_gate`
> 逐问题审查的**模型定义**。由 `7methodology-review` 阶段产出，位于 `reports/FINAL_MODEL_SPEC.json`。
> 任何阶段不得再把 `ANALYSIS_MODELING_REPORT.md` 当最终模型接口。

## 文件位置与版本

- 路径：`reports/FINAL_MODEL_SPEC.json`
- `schema_version`：当前 1。
- 每次修改契约 = 模型定义变更：需更新 `generated_at`、`contract_rev`（递增），
  并重跑 `7methodology-review`（触发全部依赖该契约的正文段落失效，见 dependency invalidation）。

## 完整 schema

```json
{
  "schema_version": 1,
  "project": "2025 CUMCM C",
  "generated_at": "2026-08-21T12:00:00+08:00",
  "generated_by": "7methodology-review",
  "contract_rev": 3,
  "problems": [
    {
      "problem_id": "Q2",
      "analysis_unit": "pregnant_woman",
      "outcome": {
        "id": "T_threshold",
        "type": "time_to_event",
        "unit": "week",
        "definition": "围产期首次达到高风险阈值的时间（周）"
      },
      "observation_mechanism": {
        "left_censoring": true,
        "interval_censoring": true,
        "right_censoring": true,
        "note": "..."
      },
      "primary_model": "interval_censored_weibull_aft",
      "likelihood": "interval",
      "likelihood_evidence": ["区间删失", "Turnbull", "interval-censored"],
      "likelihood_contribution": {
        "form": "F(U_i)-F(L_i) = S(L_i)-S(U_i)",
        "left": "log F(U_i)",
        "interval": "log [S(L_i) - S(U_i)]",
        "right": "log S(L_i)",
        "note": "v4.1（R-08）：结构化公式贡献——Writing Agent 只按本字段渲染公式，禁止自由重写；
                程序侧检测 S(U)-S(L) 型反向表达（text_integrity likelihood_inverted，FAIL）"
      },
      "covariates": ["BMI", "age", "parity", "IVF"],
      "excluded_covariates": {
        "height": "collinearity",
        "weight": "collinearity"
      },
      "validation": "nested CV: outer 5-fold × inner threshold selection",
      "result_keys": [
        "results/p2_ic.json#G2.recommended.low",
        "results/p2_ic.json#G3.recommended.high"
      ],
      "figure_ids": ["fig_v3_f2_interval"],
      "paper_section": "sections/6_problem2.tex",
      "mechanism_change_rationale": ""
    }
  ]
}
```

## 字段说明

| 字段 | 必填 | 说明 |
|---|---|---|
| `schema_version` | 是 | 固定 1 |
| `project` | 是 | 项目标识 |
| `generated_at` / `generated_by` / `contract_rev` | 是 | 溯源；rev 变 = 契约变 |
| `problems[]` | 是 | 每问一条，**问题数量与题面一致** |
| `problems[].problem_id` | 是 | 与论文章节/结果 JSON 对齐（Q1/Q2/Q3...） |
| `problems[].analysis_unit` | 是 | 分析单位（如 pregnant_woman） |
| `problems[].outcome` | 是 | 目标变量 id/type/unit/definition |
| `problems[].observation_mechanism` | 是 | 左/区间/右删失与截断；**同一 outcome.id 跨问题必须一致**（除非 `mechanism_change_rationale` 非空并说明证据） |
| `problems[].primary_model` | 是 | 唯一主模型名 |
| `problems[].likelihood` | 是 | `interval` / `exact` / `none` / `mixture` ... |
| `problems[].likelihood_evidence` | 建议 | 论文该问题章节**必须出现**的证据词（空数组 = 无法核验，methodology 门 WARN） |
| `problems[].covariates` | 是 | 入模协变量 |
| `problems[].excluded_covariates` | 建议 | 排除变量 + 理由（collinearity 等） |
| `problems[].validation` | 建议 | 验证协议一句话描述 |
| `problems[].result_keys` | 建议 | `results/<file>#<jsonpath>` 形式的结果键（trace/provenance 用） |
| `problems[].figure_ids` | 建议 | 与 figure_story_manifest 的 id 对应 |
| `problems[].paper_section` | 建议 | 论文中该问题章节相对 `paper/` 的路径（methodology 门逐节审查用） |
| `problems[].mechanism_change_rationale` | 条件 | 仅当同 outcome 跨问题机制不同时**必须**非空 |

## 强制规则（由门禁执行）

1. **契约唯一**：`3coding-visual` 只实现本文件声明的模型；结果 JSON 必须写
   `"model_spec_sha256": "<spec 文件 SHA256>"`（methodology 门校验）。
2. **逐问题绑定**：methodology 门按 `paper_section` 逐节检查
   `likelihood_evidence` 关键词，不做全文关键词匹配。
3. **机制一致性**：同一 `outcome.id` 在不同问题中的 `observation_mechanism`
   若不一致且无 `mechanism_change_rationale` → FAIL（抓"Q2 用区间删失、Q3 又用
   精确事件+右删失"这类 false-pass）。
4. **依赖失效**：`contract_rev` 变化后，摘要/方法/结果/小结/优缺点/灵敏度/结论中
   依赖该模型的段落标 stale，必须重生成或人工确认（paper 各节可声明 `depends_on`）。
5. 契约缺失 = 未做模型审计 → methodology 门 strict FAIL。

## 生成器

`7methodology-review` 阶段的产物之一；可运行
`python <6verity>/scripts/methodology_gate.py --workspace . --strict --require-spec`
验证项目是否已消费契约。
