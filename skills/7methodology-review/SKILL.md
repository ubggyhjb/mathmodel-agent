---
name: 7methodology-review
description: "数学建模竞赛方法学审查阶段（v3，独立强制阶段）。用于建模前/中审计数据生成机制与观测机制、统计假设一致性、删失结构、优化退化、模型必要性、ML 泄露、样本量与不确定性，并做结论强度校准，为建模与论文奠定方法学合法性。"
whenToUse: "数模工作流中完成建模设计（2analysis-modeling）后、进入代码实现与绘图（3coding-visual）前，进行方法学审计与假设一致性检查时使用（通常由 1start-mathmodel 调用）。"
allowed-tools: pwsh, read, write, edit, grep, glob, subagent, workflow, web_search, ask_user_question
---

# 方法学审查（v3 Methodology Review）

本 skill 是 `2analysis-modeling` 之后、`3coding-visual` 之前的独立强制阶段（时序：`2analysis-modeling → 7methodology-review → 3coding-visual → 4drawio → 5writing → 6verity`）。它不写代码、不画图、不排论文；它把"模型定义是否成立"这件事从流程里显式拎出来，防止把一条不成立的方法学假设一路带到代码、图表和论文里。

本 skill 的产出是 `reports/methodology/*.json` 一组方法学登记文件 + **`reports/FINAL_MODEL_SPEC.json`（v4 可执行模型契约）** + `reports/figure_story_manifest.json`，作为 `6verity` 阶段 v4 三门禁（methodology / leakage / figure_story）的**输入**，其中 FINAL_MODEL_SPEC 同时是 `3coding-visual`（只实现它）与 `5writing`（只描述它）的唯一模型接口。本阶段不满足，后续阶段必须停下修正。

## 数学建模规范参考

如需领域判断，读取 `../references/math_modeling_norms.md` 中的"赛题理解与子问题识别""假设与模型建立"小节。该文件只作规范知识库，不替代本阶段的方法学登记产物。

## 核心纪律（写在最前，每次建模前先自问）

> **不要为了"更高级"继续堆算法。** 每一个新增方法必须回答：
> **"它解决了哪个现有方法无法解决的问题？"** 如果不能回答，就不要加。
>
> 本阶段的目的不是让模型更多、更复杂，而是让 Agent **主动怀疑自己的建模假设、验证设计、优化结构和视觉表达**——把"模型定义是否成立"当作第一优先级，而不是把"能跑出结果"当作完成。

## 阶段边界

- 本阶段负责：登记数据生成机制、审计统计假设与删失、检验优化退化、判定模型必要性、登记 ML 操作数据范围、核查样本量与不确定性、校准结论强度。产出方法学登记 JSON。
- 本阶段不负责：写代码、跑实验、生成图表、排版论文（那分别是 `3coding-visual` / `4drawio` / `5writing` / `6verity`）。
- 任一审计 FAIL：先回 `2analysis-modeling` 或直接修 JSON/建模口径，**禁止带病进入 `3coding-visual`**。

## 产出入口（7 个方法学 JSON + 1 个模型契约 + 1 个 Figure Story manifest）

全部写入工作区 `reports/`：

| 文件 | 对应步骤 | 用途 |
| --- | --- | --- |
| `reports/methodology/data_generating_process.json` | Step 1 | 数据生成机制与观测机制审计 |
| `reports/methodology/statistical_assumptions.json` | Step 2 | 统计假设一致性 |
| `reports/methodology/censoring_report.json` | Step 3 | 删失结构审计 |
| `reports/methodology/optimization_degeneracy.json` | Step 4 | 优化退化三角对比 |
| `reports/methodology/model_necessity.json` | Step 5 | 模型必要性 / Ablation 分类 |
| `reports/methodology/ml_operation_scope.json` | Step 6 | ML 操作数据范围登记 |
| `reports/methodology/sample_sizes.json` | Step 7 | 样本量与不确定性 |
| `reports/FINAL_MODEL_SPEC.json` | 汇总（v4 强制） | **可执行模型契约**：逐问题声明 outcome/观测机制/likelihood/协变量/result_keys/figure_ids/paper_section（schema 见 `docs/FINAL_MODEL_SPEC.schema.md`）。`3coding-visual` 只实现它、`5writing` 只描述它、`6verity` 逐问核验它 |
| `reports/figure_story_manifest.json` | （`3coding-visual`/`6verity` 用） | 每张主图的 Figure Story 定义（v4 迁移到 `figures/figure_manifest.json` 唯一清单） |

**FINAL_MODEL_SPEC 生成规则**：完成 Step 1-7 后，为每个子问题写一条 problems[]（与题面问题数量一致）；
同一 `outcome.id` 跨问题必须同一种删失机制（若不同，`mechanism_change_rationale` 必须非空并给证据）；
`contract_rev` 从 1 起，修改契约必须 +1（触发依赖段落失效）。

## 工作流程

### Step 1: 数据生成机制审计（对应 _mathmode.docx 一条）

建模前强制生成 `reports/methodology/data_generating_process.json`，登记"数据是怎么产生的、我们是怎么观测到的"。字段：

```json
{
  "analysis_unit": "分析单位（如 孕妇/样本/运动员）",
  "repeated_measurement": true,
  "group_id_field": "同组/同一对象的分组键（如 woman_id）",
  "within_group_dependence": true,
  "outcome_directly_observed": false,
  "censoring": {"left": true, "interval": true, "right": true, "truncation": false},
  "missingness": false,
  "measurement_error": false,
  "class_imbalance": false,
  "time_dependence": true,
  "notes": ""
}
```

- `censoring` 四个布尔位 `left/interval/right/truncation` 对应四种非精确观测：`T<=t1` 左删失；`tj<T<=tj+1` 区间删失；`T>tlast` 右删失；`truncation` 截断。
- 判定标准：只要目标**不是**每个样本都拿到精确观测时间，就必须标记至少一种删失/截断。
- **NIPT 示例**（必须能识别出这些结构）：
  - 同一孕妇多次检测 → `repeated_measurement=true`；
  - 首检已达 4% → 左删失（`censoring.left=true`）；
  - 两次检测间跨过 4% → 区间删失（`censoring.interval=true`）；
  - 末检仍未达 4% → 右删失（`censoring.right=true`）。
- 若数据存在上述结构，后续模型必须**显式处理**或**说明为何采用近似**，二者必居其一，禁止默认当作精确观测。

### Step 2: 统计假设一致性（对应 _mathmode.docx 二条）

生成 `reports/methodology/statistical_assumptions.json`：

```json
{
  "independence": "conditional_on_random_effects",
  "conditional_independence": "conditional on fixed effects",
  "homoscedasticity": "plausible",
  "distribution": "logistic",
  "censoring_assumption": "noninformative",
  "missingness_assumption": "none",
  "random_effect_structure": "random intercept per woman"
}
```

- 全文扫描"独立、正态、随机、无偏"等假设词，与模型结构逐项交叉验证。
- **repeated_measurement=true 时的硬规则**：正文禁止出现无修饰的"相互独立"。只允许"在控制个体随机效应后，条件残差近似独立"。`methodology_gate.py` 会在 strict 下自动 FAIL 无修饰的"相互独立"——但本 skill 的价值是**教建模者先写对**，而不是等门禁抓出来再改。
- `censoring_assumption` 区分 `noninformative`（非信息性删失，常用）与 `informative`；`missingness_assumption` 区分 `mcar/mar/mnar/none`。

### Step 3: Censoring Audit（对应 _mathmode.docx 三条）

任何目标不是精确观测时间，必须先分类删失结构。生成 `reports/methodology/censoring_report.json`：

```json
{
  "classification": "interval",
  "candidate_models": ["turnbull", "interval_weibull"],
  "interpolation_used": false,
  "interpolation_labeled_approximate": false,
  "interval_model_comparison_done": true,
  "decision_impact_reported": true
}
```

- 若出现区间删失，**默认候选模型**至少含：`turnbull` / `interval_weibull` / `interval_lognormal` / `interval_aft`（Turnbull 估计器、区间删失 Weibull、区间删失 log-normal、区间删失 AFT）。
- **若用插值恢复精确事件时间**，必须：
  1. `interpolation_labeled_approximate=true`——明确标为近似；
  2. `interval_model_comparison_done=true`——与区间删失模型做比较；
  3. `decision_impact_reported=true`——报告对最终决策的影响。
  缺一项，`methodology_gate.py` 在 strict 下即 FAIL。

### Step 4: Optimization Degeneracy（对应 _mathmode.docx 四条）

每个优化问题做 **objective-only / constraint-only / full** 三角对比。生成 `reports/methodology/optimization_degeneracy.json`：

```json
{
  "problems": [
    {
      "id": "Q2",
      "objective_only": 10.0,
      "constraint_only": 9.98,
      "full": 9.99,
      "eps": 0.05,
      "active_constraints": ["a1"],
      "constraint_dominance_ratio": 0.99,
      "objective_sensitivity": 0.01
    }
  ]
}
```

- 若 `|full - constraint_only|` 相对差 < `eps` 且多组一致 → 结论为"**当前最终解主要由约束边界决定，目标函数对最终决策贡献有限**"，**禁止把该目标函数包装为核心创新**（methodology_gate.py 会针对"风险最小化创新/核心创新…目标函数"式表述 FAIL）。
- `active_constraints`、`constraint_dominance_ratio`、`objective_sensitivity` 一并输出，用于解释"到底是谁在决定解"。

### Step 5: Model Necessity（对应 _mathmode.docx 五条）

对正文中每一个模型逐一问四个问题，生成 `reports/methodology/model_necessity.json`：

```json
{
  "models": [
    {"id": "LMM", "role": "Primary", "changes_conclusion": false,
     "improves_performance": true, "explains_mechanism": true, "used_in_decision": true},
    {"id": "OLS", "role": "Baseline"},
    {"id": "Bootstrap", "role": "Robustness"},
    {"id": "TwoStage", "role": "Rejected", "moved_to_appendix": true}
  ],
  "content_share": {"primary": 0.7, "baseline": 0.15, "robustness": 0.15},
  "moved_to_appendix": ["TwoStage"]
}
```

- 四种角色：`Primary`（主模型）/ `Baseline`（基线）/ `Robustness`（稳健性）/ `Rejected`（被拒）。
- 每问四个问题：①是否改变最终结论？②是否提升预测性能？③是否解释新机制？④是否参与最终决策？
- 四个问题全为否、且不改变结论不入决策 → `Rejected`，**移入附录**（`moved_to_appendix`），不得留在正文。`methodology_gate.py` 会把"Rejected 模型仍出现在正文"判 FAIL。
- 正文内容份额硬约束：`Primary ≥60%`、`Baseline ≤20%`、`Robustness ≤20%`；不达标 FAIL。
- 参考（NIPT 问题一收敛建议）：LMM 主模型、OLS 基线、cluster-robust/Bootstrap 稳健性、两阶段增长曲线若独立价值不足则移附录或缩写。

### Step 6: ML Leakage 登记（对应 _mathmode.docx 六、七条）

登记每个机器学习操作允许使用的数据范围，生成 `reports/methodology/ml_operation_scope.json`：

```json
{
  "operations": [
    {"operation": "standardization", "allowed_data": "training_fold"},
    {"operation": "imputation", "allowed_data": "training_fold"},
    {"operation": "feature_selection", "allowed_data": "training_fold"},
    {"operation": "oversampling", "allowed_data": "training_fold"},
    {"operation": "class_weight", "allowed_data": "training_fold"},
    {"operation": "hyperparameter_selection", "allowed_data": "inner_cv"},
    {"operation": "threshold_selection", "allowed_data": "inner_cv"},
    {"operation": "calibration", "allowed_data": "inner_cv"},
    {"operation": "pruning_rule", "allowed_data": "training_fold"},
    {"operation": "final_metrics", "allowed_data": "outer_test"}
  ],
  "outer_split": "stratified_group_kfold",
  "notes": ""
}
```

- 规范映射：`standardization / imputation / feature_selection / oversampling / class_weight → training_fold`；`hyperparameter_selection / threshold_selection / calibration → inner_cv`；`pruning_rule → training_fold 或 inner_cv`；`final_metrics → outer_test`。
- 只要某步用了 `outer_test` 且非 `final_metrics`，`leakage_gate.py --strict` 即 FAIL。
- **嵌套 Group CV**：同一对象多次测量数据，外层用 `GroupKFold / StratifiedGroupKFold` 做最终性能评价；内层同样按 group 划分，用于超参/阈值/特征筛选/过采样参数/calibration/pruning。
- 禁止"用所有 OOF 标签选阈值后，再用同一批数据报最终测试性能"（`leakage_gate.py` 对"所有样本选择阈值/全体样本确定阈值/所有 OOF 阈值"式表述 FAIL）。

### Step 7: 样本量与不确定性（对应 _mathmode.docx 八条）

对所有分组决策自动检查样本量、事件数、删失数、置信区间宽度，生成 `reports/methodology/sample_sizes.json`：

```json
{
  "groups": [
    {"id": "B1", "n": 120, "effective_n": 120, "events": 90,
     "censored": 30, "ci_width_weeks": 2.0, "exploratory": false}
  ],
  "minimum_group_n": 20,
  "ci_width_limit_weeks": 4.0
}
```

- 默认阈值：`minimum_group_n = max(20, 5%N)`、`ci_width_limit_weeks = 4`。
- 若 `effective_n < minimum_group_n` 或 `ci_width_weeks > ci_width_limit_weeks` → 标记 `exploratory=true`，并**合并**或**降级为探索性表述**。
- 弱证据（小样本/宽 CI/exploratory）下禁止"最佳时点"式强结论，应写"推荐窗口"。`methodology_gate.py` 对弱证据组仍用"最佳时点/精确决定/稳定表明"判 FAIL。
- 推荐时点 CI 很宽（>4 周）时，输出优先写"推荐窗口"而非单一点估计。

### Step 8: 结论强度校准（对应 _mathmode.docx 九条）

按证据强度控制用词，不靠"结果看起来显著"就上强词。证据 → 用词映射表：

| 证据强度 | 允许用词 |
| --- | --- |
| 强证据 | 建议、稳定表明 |
| 中等证据 | 结果显示、数据支持 |
| 小样本 / CI 宽 | 数据提示、可作为参考、建议窗口约为 |
| 探索性结果 | 初步结果提示 |

- 禁止：小样本 + 宽 CI 仍写"最佳时点为 XX 周"。弱证据下强结论词（最佳时点/精确决定/稳定表明/确定为）由 `methodology_gate.py` 判 FAIL。
- 本步无独立 JSON；结果落到上面 Step 7 的 `exploratory` 标记 + 各步骤的汇总结论。

### Step 9: 收口（门槛门禁 + 攻击式问题生成）

本阶段收口必须跑通以下 4 个脚本（`<项目根>` 为当前工作区），一门 FAIL 即停下修复，**全部通过才允许进入 `3coding-visual`**：

```bash
# ① 方法学门（DGP/假设/删失/退化/必要性/样本量/结论强度）
python skills/6verity/scripts/methodology_gate.py --workspace . --strict
# ② ML 泄露门（操作范围登记 + 论文/代码启发式）
python skills/6verity/scripts/leakage_gate.py --workspace . --strict
# ③ Figure Story 门（主图必填 main_message + 覆盖 + 去重）
python skills/6verity/scripts/figure_story.py --workspace . --strict
# ④ 攻击式评委问题生成器（生成 ≥10 个最难问题 → reports/methodology/attack_questions.md）
python skills/6verity/scripts/attack_questions.py --workspace .
```

- `methodology_gate.py` / `leakage_gate.py` / `figure_story.py` 在 `--strict` 下：任何 FAIL → 修复对应 JSON 或建模口径后再重跑，禁止改判放行。
- `attack_questions.py` 是生成器（退出码恒为 0，不判 PASS/FAIL）：它产出 `reports/methodology/attack_questions.md` + `.json`，**每个问题必须能在正文或附录回答**；任何问题不可回答，记 open issue 并不得宣布 final PASS（此事在 `6verity` 的 Step 10 强制销号）。

## 与 6verity 的分工

- 本阶段负责**方法学审计的登记与自检**，是建模者自己的"出声思考"。
- `6verity` 的 methodology / leakage / figure_story 三门禁**复用**本阶段产物做程序化复检，并补齐论文侧的交叉验证（如"相互独立"修饰词、Rejected 模型残留正文、弱证据强结论词）。
- 一切门禁**阈值**以 `<6verity skill>/style_policy.json` 为单一事实源；本阶段只登记事实与结论，不复制阈值数字。

## 硬性返回触发

- Step 1–8 任何一项审计不通过（删失未分类、假设矛盾、退化未检测、必要性未分类、泄露未登记、样本量未核查）→ 回 `2analysis-modeling` 修正建模口径后再重跑本 skill。
- Step 9 的 v3 三门禁任一 FAIL → 修正后重跑，禁止带病进入 `3coding-visual`。
