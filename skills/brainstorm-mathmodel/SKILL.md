---
name: brainstorm-mathmodel
description: "数学建模赛题头脑风暴（brainstorming）阶段：在读题后、详细建模前，把题意固化为 QUESTION_CONTRACT，再按 minimal/recommended/advanced 三档受约束生成候选方案、做候选评判与淘汰状态机，输出 IDEA_CANDIDATES/IDEA_DECISION 机器契约供 2analysis-modeling 收敛。"
whenToUse: "数学建模工作流中，1start-mathmodel 完成初始化和偏好确认后、2analysis-modeling 开始详细建模前使用；或在建模思路卡住、需要换路线时使用。"
allowed-tools: pwsh, read, write, edit, grep, glob, subagent, web_search, ask_user_question
---

# 数学建模头脑风暴（受约束候选生成 + 淘汰状态机）

本 skill 是数模工作流中新增的"先发散、后收敛"阶段。它不替代 2analysis-modeling 的详细建模报告，而是**先用题意契约锁住问题的边界，再系统性生成和筛选候选**，避免"第一反应就是最终方案"的众数解陷阱。

**本级不直接形成可执行模型定义**——那属于 7methodology-review（FINAL_MODEL_SPEC）。Brainstorm 的产出是"候选 + 淘汰理由 + 待验证问题"的机器契约，供后续阶段引用。

## 目标

- 每个子问题生成 **minimal sufficient / recommended / advanced** 三档候选，而不是"主流/进阶/交叉/反直觉"各凑一个。
- 每个候选必须**显式声明失败条件**——没有失败条件的方案本质上是"不可证伪的 AI 方案"。
- 每个候选必须通过 **DGP compatibility** 检查：数据生成机制（重复测量/删失/缺失/不平衡/时序）不允许的方案直接淘汰，不得以"区分度高"为由保留。
- 输出 `QUESTION_CONTRACT.json`（题意契约）＋ `IDEA_CANDIDATES.json`（候选清单）＋ `IDEA_DECISION.json`（淘汰状态机），由 `6verity/idea_gate.py` 机器校验（T65-T69）。

### 三档定义

| 档位 | 定义 | 何时升级 |
| --- | --- | --- |
| `minimal_sufficient_solution` | 能正确回答题目、统计上成立的最简单模型 | 永远保留作为对照基线 |
| `recommended_solution` | 综合正确性/可解释性/稳健性/竞赛表达/计算成本的最优平衡 | 默认主选 |
| `advanced_alternative` | 更复杂、更高风险的方法 | **仅当** minimal 被证明显著不足时才升级为主选，且必须给出 `evidence_against_minimal` |

原则：**先证明"简单方案不够"，再谈"复杂方案更好"**，这能显著抑制模型堆砌。

## 输入

- 赛题 PDF/文本/图片（已由用户提供）。
- 附件数据（若有）。
- `plan.md`、`todo.md`：已确认的竞赛类型、语言、排版引擎和子问题数量。
- `state/decision_log.json`：已记录的偏好和断点状态。

## 输出

- `reports/contracts/QUESTION_CONTRACT.json`：题意契约（机器可读）。
- `reports/contracts/IDEA_CANDIDATES.json`：候选清单（含失败条件，机器可读）。
- `reports/contracts/IDEA_DECISION.json`：收敛决策（accepted/rejected/primary/baseline/exploratory，机器可读）。
- `reports/BRAINSTORM_REPORT.md`：人读版头脑风暴报告（不含实验结论词）。
- 在 `state/decision_log.json` 中追加本阶段关键决策（stage=`brainstorm-mathmodel`）。

## 工作流程

### 1. 快速读题 → 题意契约

用 3–5 分钟把题面读成一张"问题卡片"，写入 `QUESTION_CONTRACT.json`（每问一条 `questions[]`）：

```json
{
  "question_id": "Q2",
  "original_request": "……题面原句……",
  "decision_target": "推荐各 BMI 组首次检测时间",
  "analysis_unit": "pregnant_woman",
  "observation_unit": "test_record",
  "required_outputs": ["分组的推荐检测时点", "不确定性说明"],
  "allowed_information": ["检测孕周", "Y 浓度", "孕周-浓度历史记录"],
  "forbidden_information": ["出生结局（若题面未给）"],
  "special_data_structure": ["repeated_measurement", "left_censoring", "interval_censoring", "right_censoring"],
  "evaluation_target": ["达标率保障", "风险代价", "模型稳定性"]
}
```

**任何候选方案不得违反题意契约**；契约中登记了删失/重复测量/缺失，后续候选与方法学 gate 都以此为准。

### 2. 受约束候选生成（三档）

针对每个子问题，生成 **minimal / recommended / advanced**。不要先判断好坏，先把想法写出来；每档至少一个。如果某档想不出合理方案，如实写"暂无可给出档位，不硬编"，不要为了凑数编造。

`IDEA_CANDIDATES.json` 每条必填：

```json
{
  "idea_id": "Q2-I01",
  "question_id": "Q2",
  "method_family": "interval_censored_survival",
  "tier": "minimal_sufficient_solution",
  "core_hypothesis": "达标时间服从区间删失，可用非参数/参数生存模型描述",
  "why_applicable": "数据为此机制，题面要求保障达标率",
  "required_variables": ["Y浓度", "检测孕周"],
  "required_assumptions": ["观测机制与题面一致", "组内异质性可建模"],
  "data_risks": ["左删失占比高", "首检晚导致区间宽"],
  "strengths": [], "weaknesses": [],
  "validation_plan": ["与插值口径对比", "Bootstrap 置信区间"],
  "failure_conditions": ["删失占比 > X 无法识别", "组内分布严重异质"],
  "complexity": "low | medium | high",
  "interpretability": "high | medium | low",
  "status": "candidate"
}
```

### 3. 候选评判（candidate critic）

对每条候选做**四问**，任一不通过则标记给下一级：

1. **DGP 兼容**：数据生成机制是否允许？机制不允许（如区间删失数据用精确事件回归且无近似标记）→ 淘汰。
2. **可证伪**：`failure_conditions` 是否明确？（机器强制，T65）
3. **数据可得**：所需变量是否有数据/权威来源？
4. **验证计划**：能否用对照/灵敏度/交叉验证证明？

### 4. 收敛决策（淘汰状态机）

写入 `IDEA_DECISION.json`：

```json
{
  "primary": {"Q2": "Q2-I01"},
  "accepted": ["Q2-I01", "Q2-I02", "Q2-I04"],
  "baseline": ["Q2-I01"],
  "backup": ["Q2-I04"],
  "exploratory": ["Q2-I03"],
  "rejected": ["Q2-I05"],
  "unresolved_questions": ["首检晚的窗口该按 q=0.95 还是 0.90"],
  "rejection_reasons": {"Q2-I05": "DGP 不兼容：精确事件回归忽略区间删失"}
}
```

规则：

- `primary` 是每个问题的主选（minimal 或 recommended 或经 `evidence_against_minimal` 证明后的 advanced）。
- **rejected 隔离**：被淘汰候选后续阶段（Code/Figure/Writing）一律禁用，只可进历史附录。
- 主选不一定是创新解；如果简单解更稳，就明确选 minimal/recommended，这不可耻。
- 淘汰路线必须写一句原因（机器可见），防止后面重新捡起。

### 5. 落盘与交接

- 三件套 JSON + `reports/BRAINSTORM_REPORT.md`（人读版，结构与"报告模板"一致）。
- 在 `state/decision_log.json` 增加一条或多条 `stage: "brainstorm-mathmodel"` 的决策记录。
- 将 `IDEA_CANDIDATES/IDEA_DECISION` 作为 `2analysis-modeling` 与 `7methodology-review` 的输入。

## 纪律

- **禁止实验结论词**：本阶段不得出现"结果表明 / 显著提升 / 最终证明 / 该方法有效解决 / 最佳模型为"（机器 FAIL，T68）。只允许"值得测试 / 若假设成立可考虑 / 作为 baseline / 需要通过…验证"。
- **不编造**：没有文献或数据支撑的路线必须标记"待验证"。
- **不硬凹创新**：如果全题都是常规解，如实说明并接受创新附加分可能偏低。
- **不越界**：本阶段只做思路筛选，不写最终模型公式、不写论文、不生成正式图表。
- **rejected 不可复活**：除非重新走候选评判并给出新的机器化决策记录。
- **时间盒**：一般 1–2 个回合内完成；如果某个子问题特别复杂，可以先完成其他子问题，再回来补。
- **可选并行**：条件允许时可用 `subagent` 派 2–3 个互不共享上下文的"头脑风暴手"，各自生成候选，再由主代理评判合并。
- **HIL 兼容**：当前审批策略为 auto/disabled 时，不需要向用户确认，按"正确性 > 可解释性 > 稳健性 > 表达成本"自行收敛；不要把"没问用户"当成"用户已同意"。

## 报告模板

`reports/BRAINSTORM_REPORT.md` 推荐结构：

```markdown
# 头脑风暴报告

## 1. 问题卡片（摘要版，机器版见 QUESTION_CONTRACT.json）
## 2. 候选路线总览（minimal/recommended/advanced）
## 3. 候选评判（DGP 兼容 / 可证伪 / 数据可得 / 验证计划）
## 4. 收敛决策（primary / accepted / rejected / unresolved）
## 5. 淘汰路线及理由
## 6. 后续交接
```

## 验证

本阶段产出由 `python <6verity>/scripts/idea_gate.py --workspace . --strict` 校验：
T65 候选缺假设/失败条件、T66 rejected 进入正式模型、T67 复杂方案无 minimal 反证、
T68 结论词、T69 删失数据用精确事件模型 → 均 FAIL。
