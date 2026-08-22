# v4.3 变更说明（Decision, Provenance & Scientific Figure Architecture）

> 任务书：`优化/v4.3.md`。定位：把 v4.2 的"存在性与一致性检查"推进为
> **语义、时序、决策与视觉证据的可证明一致性**。原则：每条新规则 = bad fixture 稳定 FAIL + fixed fixture 稳定 PASS。

## Phase 1 — 契约层（模型语义契约）

- `FINAL_MODEL_SPEC` schema v2（`docs/FINAL_MODEL_SPEC.schema.md`）：新增机器可比字段
  `model{family,distribution,error_distribution,parameterization,role}`、
  `features{feature_set_id,included[{id,role}],excluded[{id,reason}]}`、
  `selection`、`uncertainty`、`prediction_output`；自由文本只作 note。
- `results/RESULT_REGISTRY.json`：结果文件角色唯一登记源
  （paper_authority/model_output/figure_source/external_registry/diagnostic/support +
  `requires_model_spec_binding`）。
- **methodology_gate**：绑定检查由 registry 驱动（T70：逐个 requires 文件校验，
  废除"目录中一部分带 hash 即通过"启发式；无 registry 回退启发式 + WARN）。
- spec v2 语义对账（`check_spec_v2_semantics`）：
  - T71 结果 `_meta.model_distribution` vs 契约；
  - T72 `_meta.feature_set_id` vs 契约；
  - T73 spec features 变量 ID 必须登记于 `reports/variables.json`，
    `availability=unavailable` 引用 FAIL；
  - T74 spec.figure_ids 必须指向 figure_manifest 中 active 图（status 非 deleted/superseded）。
- 结果 `_meta` 统一结构（§15）：problem_id/role/model_spec_sha256/contract_rev/
  code_sha256/data_sha256/model_family/model_distribution/feature_set_id/generated_at；
  兼容顶层旧 hash（双口径）。

## Phase 2 — 决策与预注册

- `reports/decisions/MODEL_SELECTION_DECISION.json`（schema 见
  `docs/MODEL_SELECTION_DECISION.schema.md`）：科学决策账本。
  - T75 预指定时序：frozen_at 必须早于 `before_result_artifacts` 的生成时间，
    否则"预指定"不可证 → FAIL；
  - T76 one-SE 方向：`one_se_choose_simpler` 选择更复杂模型且无 exceptions → FAIL。
- `leakage_gate.check_family_provenance`（T77/T78）：家族选择声明 nested（inner_cv）
  必须提供逐折运行时 provenance（inner_candidates/selected_family/
  selection_data_hash/outer_test_group_hash，且 selection_data_hash ≠ outer_test_group_hash）；
  方案 A（pre_specified）要求决策账本存在。
- `methodology_gate.check_typed_uncertainty`（T79）：结果声明 sampling_ci 但
  decision_window.construction_rule 为空，而论文把"置信区间"与"推荐/决策窗口"混用 → FAIL。
- failure-driven rollback（§16/§18）：`reports/methodology/failure_events.json`
  中 severity∈{blocker,critical} 且未 resolved → methodology FAIL；
  `workflow_spec.yaml` 新增 `control_plane` 段（verdict 枚举 + 回滚规则）。

## Phase 3 — Brainstorm 契约化

- `skills/brainstorm-mathmodel/SKILL.md` 重写：三档候选
  （minimal_sufficient_solution / recommended_solution / advanced_alternative）、
  淘汰状态机、禁止实验结论词、失败条件必填、rejected 隔离。
- 新增 `idea_gate.py`（T65-T69）：QUESTION_CONTRACT / IDEA_CANDIDATES / IDEA_DECISION
  三件套校验——缺假设/失败条件（T65）、rejected 进入正式模型（T66）、
  复杂 primary 无 minimal 反证（T67）、结论词（T68）、删失数据用精确事件模型（T69）。
- `workflow_spec.yaml`：brainstorm 输出扩展为三件套；methodology 输入引用 IDEA artifacts；
  gates_pipeline 增加 idea_contracts。

## Phase 4 — 科学图系统 + 页面构图

- `docs/FIGURE_SPEC.schema.md` + `figure_spec_gate.py`（T90-T94）：
  primary 图必须 `figures/specs/<id>.figure.json`（figure_id/claim_id/figure_role/
  evidence_type/renderer/layout/visual_encoding/label_budget/final_width_mm）；
  语义配色层级（T92 WARN）；`r_ggplot2` 必须 renv.lock（T93）；
  禁止本机字体绝对路径（T94）。
- `mathmodel-figure-templates/SKILL.md` 重定位为
  "Publication Scientific Figure System"（Evidence→Visual Encoding→Renderer，
  删除"炫酷模板库"定位）；3coding-visual 增加五步流程（Narrative/Encoding/Routing/
  Composition/Critic）。
- **layout_gate `composition_checks`**（T95-T99）：
  摘要+关键词同页/孤儿溢出（T95）、近空延续页与孤立标题（T96）、
  可回收欠填充 + 下一页顶部 float 对象（T97/T98）、首次引用与对象断裂（T99）。
- **视觉执行闭环**：`visual_review_gate.py`（T100-T103）——page_visual_review.json
  SHA 对齐 / 逐页覆盖 / 未关闭 BLOCKER veto（不被盲评总分平均掉）/
  roster drift（workflow_spec 唯一事实源，6verity 不得用创新席替代视觉席）；
  6verity SKILL.md 三席对齐 workflow_spec final_review（A 数学建模 / B 统计ML /
  C 科学编辑与视觉 + 独立视觉否决权）；check_decision_log 席位名兼容。

## Phase 5 — 提交与溯源

- `submission_package_gate.check_v43`（T82-T89）：
  data_sources 唯一登记源（T82）、论文附录 A 类别覆盖实际包（T83）、
  README reproduction 容差语义（T84）、warning_ledger（T85）、
  完整复现分级（T86）、repro spec 双份一致（T87）、paper_pages（T88）、
  AI 报告与 registry 事实一致（T89）。
- `--build-manifest`：从最终 ZIP 自动构建 `repro/SUBMISSION_MANIFEST.json`（P1-08）。
- `docs/AI_USE_PROVENANCE.schema.md`：AI proposed/executed / human selected/verified 角色分工契约。

## 回归

- run_tests：T65-T103（39 条新）+ 既有 T01-T64 + 关键词策略新用例（T25.quad/T25.semi）。
- 当前基线：114+ 用例全 PASS（无真实 workspace 时若干基线 SKIP）；
  带 NIPT workspace 时含 T01/T04/T06-T09/T12 真实项目基线。

## NIPT golden（同步返修，20260820 项目）

- FINAL_MODEL_SPEC v2（Q2 log-normal AFT 修正、Q3 多因素集、Q4 22 维 variable IDs、
  prediction_output=uncalibrated_score、selection/uncertainty 机器化）。
- results 全部 `_meta` 绑定（add_meta.py，run_all 步骤 10）；
  RESULT_REGISTRY 登记；Q2/Q3 结果注入 typed uncertainty + 决策窗口构造规则。
- 决策账本（Q2-D01 log-normal AFT 识别性决策、Q4-D01 LR 主模型设计决策、
  Q4-D02 22 维 one-SE 例外）；论文删除"预指定"措辞，改为可验证例外叙事。
- 论文：摘要压缩为真摘要（526 字、一页完整）、关键词 `\quad` 固定间距、
  共线性 Q3 typed uncertainty 分型、假设外部不可验证化、附录 A 自动对应 manifest、
  第 6/21 页型构图修复（float 策略 + 表 6/图 7 尺寸）、AI 详情事实化
  （"建模思路与模型设计：部分（AI 辅助）——参赛队主导选型"）。
- 图：fig_q1_coef 去 intercept + 标准化效应；fig_q4_roc 语义层级配色
  （primary 深蓝粗线/benchmarks 灰阶/direct labeling）；11 张图 FIGURE_SPEC 登记。
- 支撑包：SUBMISSION_MANIFEST / warning_ledger / AI_USE_PROVENANCE /
  data_sources 唯一登记源 / README reproduction_tolerance / full 复现级别。

## v4.3 补遗：R/ggplot2 落地（§21/§22）

- **R 4.6.1 已接入**（用户侧安装，E:\R-4.6.1；Rscript 经 PATH/环境变量 RSCRIPT 探测，禁止本机绝对路径）：
  R/ 目录（theme_mathmodel.R 8pt 主题 + palette_mathmodel.R 语义配色 + save_figure() 定义于 theme_mathmodel.R 尾部；矢量/PNG 输出 +
  plots/fig_q3_effects.R·fig_q4_roc.R）+ 
env.lock（R 版本 + 13 包版本，等价恢复）。
- NIPT 图 7（AFT 森林图）/图 9（ROC）正式渲染器 = **r_ggplot2**（同源 results/*.json 数据、语义层级配色、
  ggrepel direct labeling）；FIGURE_SPEC renderer=r_ggplot2 + renderer_fallback；无 R 环境 run_all 自动记录
  fallback（不静默切换）。
- figure_spec_gate：renderer 契约对**全部**声明图（T90 仍只强制 primary 有 spec；T93/T92 全量）。
- mathmodel-figure-templates 增 R/ 模板（theme/palette + example_forest/example_roc）。
- Reviewer C trip3/trip4 复评 PASS（82），15/15 门禁保持。
