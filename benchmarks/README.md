# MathModel Agent Benchmark（v4.3，任务书 §31）

> 目的：test count 不是能力分数——用 **Golden Problems** 验证门禁能力覆盖与版本进步。
> 每道 golden = QUESTION_CONTRACT（题目契约）+ KNOWN_TRAPS（已知陷阱）+
> REFERENCE_MODEL_SPEC（参考模型契约）+ EXPECTED_FINDINGS（预期发现）+
> FORBIDDEN_ERRORS（禁止错误，对应门禁 FAIL）。

## 基准清单（4 道）

| # | Golden | 覆盖数据机制 | 参考主模型 | 主要门禁 |
|---|---|---|---|---|
| G1 | **NIPT（真实项目，20260820）** | 重复测量 + 左/区间/右删失 + 类别不平衡 | 区间删失 AFT（log-normal 误差）/ 多因素 AFT / 代价敏感 LR | 全量 15 门 |
| G2 | **类别不平衡分类**（合成 605 条/2 类） | 不平衡二分类 + 分组嵌套 CV | 逻辑回归（uncalibrated score）+ 嵌套阈值 | methodology/leakage/idea |
| G3 | **时间序列预测**（合成 120 期） | 平稳 + 趋势 + 季节性 | ARIMA（Box-Jenkins 流程） | methodology/figure_story |
| G4 | **区间删失 + 约束优化决策**（合成 267 人） | 左/区间/右删失；达标率约束主导 | Turnbull + interval-censored AFT | methodology/degeneracy |

生成器：`gen_golden.py`（在 benchmarks/ 下重建 ws_G2/G3/G4 三个最小项目，每个可独立跑
`methodology_gate.py / leakage_gate.py / idea_gate.py / figure_story.py --strict`）。
G1 为真实项目（`C:\UMCM2025Problems\C题_重生成_20260820`），以 `reports/v43_baseline.md` 为基线快照。

## KNOWN_TRAPS（每道纪录的已知陷阱 → 对应回归）

- G2：`algorithm_family_selection.allowed_data=outer_test`（T62/T77）；0.5 阈值指标与混淆矩阵不一致（B3 型，Trace+人工）；score 写"患病概率"（T80 词表）。
- G3：spec features 引用 `availability=unavailable` 变量（T73）；差分阶数经全样本确定（Leakage）；多步预测用滚动真实值而非预测值回溯（Leakage 型）。
- G4：exact-event OLS 忽略区间删失（T69）；"95% CI"直接充当"推荐窗口"无 construction_rule（T79）；G4 左删失主导的识别性不披露（Reviewer B 型）。
- G1：spec 与代码分布族不一致（T71，v4.2 真实发生过：Weibull vs log-normal）；pre-specified 无时序证据（T75，v4.2 真实发生过）；CI 与推荐窗口混用（T79）。

## EXPECTED_FINDINGS（参考解应得到的结论形态）

- G2：AUPRC 优于先验、灵敏度-特异度权衡随阈值单调、PPV 相对全阳性基线无显著提升时不得写"预警支持"。
- G3：残差白噪声、AIC/BIC 选择低阶模型、预测区间随步长展宽。
- G4：推荐时点主要由达标率约束边界决定（full≈constraint-only）；宽 CI 组按决策窗口口径报告。

## FORBIDDEN_ERRORS（出现即门禁 FAIL）

G2：outer-family 选择 / 概率解释词 / 阈值泄漏。G3：unavailable 变量入模 / 全样本差分。G4：精确事件模型 / CI 冒充窗口 / 强结论词（最佳时点）。G1：契约漂移 / 时序不能证明 / 内部文件词泄漏 / 摘要关键词跨页 / 近空页。

## 版本对比（v4.2 → v4.3）

| 能力 | v4.2 | v4.3 |
|---|---|---|
| 模型契约 | schema v1（自由文本） | schema v2（机器可比字段 + 语义对账 T71-74） |
| 结果绑定 | 目录启发式（部分绑定即过） | RESULT_REGISTRY 驱动（逐个校验 T70） |
| 决策时序 | 无（"预指定"仅存于论文） | 决策账本 + frozen_at 校验（T75/T76） |
| 家族选择 | 声明式 | 逐折运行时 provenance（T77/T78）+ 决策账本 |
| Brainstorm | 自由发散 Markdown | 契约三件套 + 淘汰状态机（T65-69） |
| 图规范 | 模板优先 | FIGURE_SPEC + 语义配色 + renderer 契约（T90-94） |
| 页面构图 | A4/bbox/字号 | 摘要关键词同页/孤儿/欠填充/首引断裂（T95-99） |
| 视觉评审 | 材料准备 + SHA 绑定 | 逐页结构化裁决 + veto + roster 唯一源（T100-103） |
| 支撑包 | 存在性检查 | 语义单一事实源/manifest/warning ledger/full repro（T82-89） |
| 回归计数 | T01-T64 | T01-T109（含 4 道 golden 基线 + 陷阱用例） |

运行：`python skills/6verity/tests/run_tests.py --workspace <G1 项目>`（T104-T109 为 golden 基线/陷阱用例）。
