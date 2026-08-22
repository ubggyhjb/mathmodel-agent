# MODEL_SELECTION_DECISION.json — v4.3 科学决策账本（schema）

> 位置：`reports/decisions/MODEL_SELECTION_DECISION.json`（唯一 authority）。
> 目的（任务书 §13.1 / P0-05）：把"为什么选它"从 Writing Agent 的合理化故事
> 变成**机器可验证的决策记录**——尤其证明"预指定"真的发生在结果出现之前。

## 完整 schema

```json
{
  "schema_version": 1,
  "decisions": [
    {
      "decision_id": "Q4-FEATURESET-01",
      "decision_type": "feature_set | model_family | hyperparameter | uncertainty_protocol",
      "candidate_ids": ["LR-22d", "LR-19d"],
      "frozen_at": "2026-08-20T09:00:00+08:00",
      "before_result_artifacts": ["results/p4_models.json"],
      "objective_priority": ["leakage_free_generalization", "parsimony", "interpretability"],
      "selection_rule": "one_se_choose_simpler | pre_specified_primary | nested_inner_cv",
      "selected": "LR-22d",
      "rejected": ["LR-19d"],
      "exceptions": [{"id": "interpretability_priority", "note": "..."}],
      "reason_codes": ["small_sample", "interpretability_priority"],
      "simplicity_order": [{"id": "LR-19d", "complexity": 19}, {"id": "LR-22d", "complexity": 22}],
      "selected_complexity": 22,
      "best_simple_within_one_se": "LR-19d",
      "complexity_of_best_simple": 19,
      "evidence": [],
      "generated_at": "2026-08-23T10:00:00+08:00",
      "approved_at": "2026-08-23T12:00:00+08:00"
    }
  ]
}
```

## 字段说明

| 字段 | 必填 | 说明 |
|---|---|---|
| `decision_id` | 是 | 与论文/契约引用的决策 ID 对应 |
| `decision_type` | 是 | feature_set / model_family / hyperparameter / uncertainty_protocol |
| `candidate_ids` | 是 | 参与比较的候选 |
| `frozen_at` | 是 | **决策冻结时间**；必须早于 `before_result_artifacts` 中任何结果的生成时间，否则"预指定"不成立（T75）。 |
| `before_result_artifacts` | 是 | 冻结时刻已经存在的（或决定其前序的）结果文件；gate 用其 `_meta.generated_at` / mtime 比对。 |
| `selection_rule` | 是 | one_se_choose_simpler / pre_specified_primary / nested_inner_cv。 |
| `exceptions` | 条件 | one_se_choose_simpler 选择更复杂模型时必须给出例外（T76）。 |
| `selected_complexity` / `complexity_of_best_simple` | 条件 | 有复杂度可比时填写，供 one-SE 方向校验。 |

## 强制规则（methodology gate）

1. 论文/契约用"预指定"措辞但无本账本或 `frozen_at` 晚于结果 → FAIL（T75）。
2. `selection_rule=one_se_choose_simpler` 且选择更复杂模型且无例外 → FAIL（T76）。
3. `model_family` 决策若为 `pre_specified`（方案 A）：leakage gate 要求本账本存在
   （family_selection_provenance 检查）。
4. Writing Agent 只允许引用本账本（+FINAL_MODEL_SPEC +RESULT_REGISTRY +CLAIM_PROVENANCE
   +figure_manifest）描述选型理由，不得自行杜撰。
