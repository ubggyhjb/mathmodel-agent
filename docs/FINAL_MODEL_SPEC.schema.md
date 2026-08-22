# FINAL_MODEL_SPEC.json — v4.3 语义模型契约（schema v2）

> 唯一允许被 `3coding-visual` 实现、被 `5writing` 描述、被 `6verity/methodology_gate`
> 逐问题审查的**模型定义**。由 `7methodology-review` 阶段产出。
>
> **唯一 authority**：`reports/FINAL_MODEL_SPEC.json`。
> `repro/FINAL_MODEL_SPEC.json` 仅为交付包副本，内容/SHA256 必须与 authority 一致
> （submission_package gate 校验，T87）。
> 任何阶段不得再把 `ANALYSIS_MODELING_REPORT.md` 当最终模型接口，也不得在别处
> 维护第二份"模型定义"。

## 版本

- `schema_version`：**2**（v4.3：从 prose contract 进化为 semantic contract）。
- v1 仍在场时 methodology gate 只做旧规则检查；**v2 激活语义对账**
  （distribution / feature_set_id / variable ID / active figure），见"强制规则"。
- 每次修改契约 = 模型定义变更：更新 `generated_at`、`contract_rev`（递增），
  并重跑 `7methodology-review`（触发全部依赖该契约的正文段落失效）。

## 完整 schema（v2）

```json
{
  "schema_version": 2,
  "project": "2025 CUMCM C（NIPT）",
  "generated_at": "2026-08-22T00:00:00+08:00",
  "generated_by": "7methodology-review",
  "contract_rev": 4,
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
      "model": {
        "family": "aft",
        "distribution": "lognormal",
        "error_distribution": "normal",
        "parameterization": "logT = gamma0 + gamma1*BMI + sigma*W",
        "role": "primary_decision",
        "note": "机器可比字段；自由文本只作 note，不用于控制流程"
      },
      "features": {
        "feature_set_id": "Q2.primary.v1",
        "included": [{"id": "BMI", "role": "body_size_primary"}],
        "excluded": [{"id": "height", "reason": "structural_collinearity"}]
      },
      "selection": {
        "model_family": "pre_specified",
        "feature_selection": "none",
        "hyperparameter_selection": "none"
      },
      "uncertainty": {
        "sampling": "cluster_bootstrap",
        "model_form": true,
        "decision_window": true
      },
      "prediction_output": {
        "type": "uncalibrated_score",
        "source": "logistic_regression_raw_output",
        "probability_interpretation_allowed": false,
        "calibration": "none"
      },
      "likelihood": "interval",
      "likelihood_evidence": ["区间删失", "Turnbull", "interval-censored"],
      "likelihood_contribution": {
        "form": "S(L_i)-S(U_i)",
        "left": "log F(U_i)",
        "interval": "log [S(L_i) - S(U_i)]",
        "right": "log S(L_i)",
        "note": "v4.1（R-08）：程序侧检测 S(U)-S(L) 型反向表达（text_integrity likelihood_inverted，FAIL）"
      },
      "result_keys": ["results/p2_ic.json#G2.recommended.low"],
      "figure_ids": ["fig_v3_f2_framework", "fig_q2_km"],
      "no_figure_required": false,
      "paper_section": "sections/6_problem2.tex",
      "mechanism_change_rationale": ""
    }
  ]
}
```

## 字段说明（v2 新增/变化）

| 字段 | 必填 | 说明 |
|---|---|---|
| `schema_version` | 是 | 固定 2 |
| `problems[].model` | 建议（无分布参数模型可省略 distribution） | **机器可比**：`family` / `distribution` /
  `error_distribution` / `parameterization` / `role`。与结果 `_meta` 逐项对账（T71）。 |
| `problems[].features` | 建议 | `feature_set_id`（结果 `_meta` 回写同一 ID，T72）+ `included[]`/`excluded[]`，
  每条 `id` **必须是 `reports/variables.json` 已登记 variable ID**；primary feature set
  引用 `availability="unavailable"` 变量 → FAIL（T73）。 |
| `problems[].selection` | 建议 | model_family / feature_selection / hyperparameter_selection 的预指定协议与范围。 |
| `problems[].uncertainty` | 建议 | 三类不确定性分型开关：sampling / model_form / decision_window（§7）。 |
| `problems[].prediction_output` | 建议（分类/打分问题启用） | `type=uncalibrated_score` 时禁止
  论文写"发生概率/患病概率/校准概率/风险概率"（T80；text_integrity 词表）。 |
| `problems[].figure_ids` | 建议 | 必须是 `figures/figure_manifest.json` 中存在的 active 图
  （status 非 deleted/superseded）（T74）。 |
| `problems[].no_figure_required` | 条件 | 有 result_keys 但确实无图时显式声明，否则 WARN。 |

## 结果 `_meta`（v4.3 §15）

所有 paper-authority / model_output / figure_source 结果 JSON（由 `RESULT_REGISTRY` 登记）统一：

```json
{
  "_meta": {
    "problem_id": "Q4",
    "role": "paper_authority",
    "model_spec_sha256": "<reports/FINAL_MODEL_SPEC.json 的 SHA256>",
    "contract_rev": 4,
    "code_sha256": "<生成脚本 SHA256>",
    "data_sha256": "<输入数据 SHA256>",
    "model_family": "logistic_regression",
    "model_distribution": "lognormal",
    "feature_set_id": "Q4.full22"
  }
}
```

`model_spec_sha256` 兼容顶层旧口径（v4 已有文件不改也可，新写统一放 `_meta`）。
`model_family / model_distribution / feature_set_id` 必须与契约对应问题逐项一致。

## RESULT_REGISTRY.json（v4.3 §4）

`results/RESULT_REGISTRY.json` 是结果文件角色的唯一登记源：

```json
{
  "schema_version": 1,
  "artifacts": [
    {"file": "results/p4_best.json", "role": "paper_authority",
     "problem_id": "Q4", "requires_model_spec_binding": true},
    {"file": "results/external_data.json", "role": "external_registry",
     "requires_model_spec_binding": false}
  ]
}
```

- 角色：`paper_authority` / `model_output` / `figure_source` / `external_registry` /
  `diagnostic` / `support`。
- `requires_model_spec_binding=true` 的文件必须写当前契约 hash——**逐个**检查，
  不存在"目录中一部分带 hash 即通过"的启发式（T70）。

## 强制规则（由门禁执行）

1. **契约唯一**：`3coding-visual` 只实现本文件声明的模型；结果绑定由
   `RESULT_REGISTRY` 驱动（methodology 门，T70）。
2. **语义一致**：v2 契约下，绑定结果的 `_meta.model_family / model_distribution /
   feature_set_id` 必须与契约对应问题一致（T71/T72）。
3. **变量登记**：spec 只能引用 `reports/variables.json` 已登记 variable ID；
   `availability=unavailable` → FAIL（T73）。
4. **active figure**：spec.figure_ids 必须指向 figure_manifest 中 active 图（T74）。
5. **机制一致性**：同一 `outcome.id` 跨问题 `observation_mechanism` 不一致且无
   `mechanism_change_rationale` → FAIL。
6. **依赖失效**：`contract_rev` 变化后所有依赖该模型的段落标 stale。
7. 契约缺失 = 未做模型审计 → methodology 门 strict FAIL。

## 生成器

`7methodology-review` 阶段的产物之一；可运行
`python <6verity>/scripts/methodology_gate.py --workspace . --strict --require-spec`
验证项目是否已消费契约。
