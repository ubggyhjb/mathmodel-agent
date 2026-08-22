# AI_USE_PROVENANCE.json — v4.3 AI 使用溯源契约（schema）

> 位置：`repro/AI_USE_PROVENANCE.json`（交付包）＋ `reports/AI_USE_PROVENANCE.json`（工作区）。
> 目的（任务书 §11）：AI 工具使用详情不再是"人工措辞"，而是**事实化的角色分工记录**：
> AI proposed / AI executed / human selected / human verified 逐项落盘，
> 由"AI 工具使用详情.pdf"引用或以本文件为唯一事实源生成。

## 完整 schema

```json
{
  "schema_version": 1,
  "problem_id": "Q2",
  "stages": [
    {
      "stage": "brainstorm",
      "ai_role": "draft_and_check",
      "human_role": "approve_direction",
      "tools": ["mathmodel-agent brainstorm-mathmodel"],
      "artifacts": ["reports/contracts/IDEA_CANDIDATES.json"],
      "execution": "ai_candidate_generation + ai_critique；human 在 IDEA_DECISION 批准"
    },
    {
      "stage": "methodology_review",
      "ai_role": "draft_and_check",
      "human_role": "approve_model_choice",
      "tools": ["mathmodel-agent 7methodology-review"],
      "artifacts": ["reports/FINAL_MODEL_SPEC.json"]
    }
  ],
  "stage_coverage": {
    "modeling_ideas_ai_involved": true,
    "core_modeling_led_by": "human",
    "human_verification": ["每步门禁复跑记录 runs/"],
    "note": "AI 参与了建模思路与模型设计建议；核心建模决策由人确认，AI 仅执行与检查。"
  },
  "generated_at": "2026-08-24T00:00:00+08:00"
}
```

## 角色枚举

- `ai_role`：`not_used` / `execution_only` / `draft_and_check` / `proposed_with_human_selection` /
  `check_only`
- `human_role`：`approve_direction` / `approve_model_choice` / `verify_numbers` / `final_author`

## 强制规则

1. **事实一致性**：如果方法学阶段 AI 提出了建模思路（brainstorm/analysis 由 Agent 执行），
   详情报告不得写"建模思路与模型设计：否"；必须按上表事实化区分（§11.1）。
2. **声明与产物一致**（submission_package_gate T89）：报告声称"所有结果绑定 model_spec"时，
   RESULT_REGISTRY 中 requires 绑定的文件必须全部有 hash，否则 FAIL。
3. "AI 工具使用详情.pdf" 与 `AI_USE_PROVENANCE.json` 同版本；PDF 由本文件生成或
   逐条引用本文件字段（避免人工措辞漂移）。
