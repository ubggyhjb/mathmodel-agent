# MathModel-Agent v4.4 变更说明（反 false-pass 收口）

> 发布日期：2026-08-23（与 NIPT golden 项目同一 release record）
> 定位：v4.3 的"契约/决策/Provenance/Figure/Visual Reviewer"已建立，v4.4 不再堆 Gate，
> 而是让**声明、执行、结果、论文、图、支撑包与最终验收成为同一条可证明链**——
> 任何机器契约都不能靠 AI 手填一个 JSON 就取得 PASS。

## 0. 修复的 P0（审计任务书逐条）

| 编号 | 问题 | 修复 |
|---|---|---|
| P0-01 | Q4 用外层测试折 mean AUPRC argmax 选家族（与实际预选 LR 矛盾） | `problem4.py` 改为 `PRIMARY_MODEL="lr_full"` 预选 + `selection_mode=pre_specified` + `runtime_selection_events=[]` + `family_benchmark`（RF/GBDT 仅基准）；`leakage_gate.check_selection_semantics`（T110）— 代码出现"候选+外测指标+argmax"即 FAIL |
| P0-02 | `run_all.py` R 步不可达（三元组 script 位=描述） | 结构化 STEPS 对象（id/kind/script/desc）、startup self-check（id 唯一/kind 合法/脚本存在/R 依赖/README marker）、README 步骤表由 `--update-readme` 渲染 |
| P0-03 | `add_meta` 在绘图后改写结果、figure meta 由一次性 `v43_meta.py` 生成 | 顺序改为 model→add_meta→verify→figures→figure meta→R→claim provenance；新增 `code/make_figure_meta.py`（真实可交付生成器，runtime 时间）与 `code/repro_claim_provenance.py`（无依赖） |
| P0-04 | `VERIFY_SUMMARY` layout fails=2 仍 `reproduction_level=full` | `repro/VERIFY_SUMMARY.json` v3：`overall/release_ready/gate_snapshot_sha256/required_gates/failed_gate_ids` 全部由门禁报告硬聚合（ANY required gate fails>0 → release_ready=false）；`submission_package_gate` 硬读 |
| P0-05 | warning ledger 15/26 且理由全部模板化 | ledger v2：issue 1:1（WARN+FAIL、message_sha256）、人工确认合并自 `reports/warning_ledger_review.json`、批量相同 reason → FAIL、FAIL 禁止 accepted_with_reason、`open_p01` 从明细重算 |
| P0-06 | SUBMISSION_MANIFEST size=0 / 98 vs 99 / 自引用 package_sha | 两层完整性：ZIP 内 payload manifest（每文件 size+sha256，canonical `payload_manifest_sha256`，manifest 自身不在 files 集合）+ ZIP 外 `支撑材料.zip.sha256`（sidecar） |
| P0-07 | 13 个未来时间戳 + 手填时间 | 时间三概念：`event_at`（历史声称）/`recorded_at`（系统时钟，禁止手填）/`evidence_type=prospective|reconstructed_posthoc`；`methodology_gate.check_temporal_integrity`（任何 provenance 时间 > now+5min → FAIL；prospective 无不可变证据 → FAIL） |

## 1. P1 修复

- **P1-01 RF 超参协议**：论文"300 棵默认深度"与代码 GridSearchCV 矛盾 → 统一为"baseline 自身超参在 outer-train 内 inner CV 调优，不参与家族选择"；`family_benchmark.baseline_hyperparameter_protocol` 登记 + `methodology_gate.check_baseline_protocol`（T111）。
- **P1-02 score 语义**：`\hat p`→`s(x)`、`概率阈值`→`score 阈值 τ`；`text_integrity.scan_score_semantics`（T112）覆盖论文/结果 JSON/源码注释/图 caption/README（否定语境与 `predict_proba` API 豁免）。
- **P1-03 主模型 vs 最优**：全文"最优模型"→"主模型"；methodology 检查 role=primary 且非 performance_optimal 时禁"最优"。
- **P1-04 Z 基线身份拆分**：固定 |Z|>3 operating point（灵敏度 6.0%/特异度 92.4%）与连续 Z score 基线（AUROC 0.479/AUPRC 0.110）分别登记。
- **P1-05/P1-06 规则口径收敛**：`rule_scope=evaluation_only`、`deployable=false`、`threshold_origin=outer-train inner-CV fold-specific`、`single_global_threshold_valid=false`；"临床落地/初筛/预警/排阴参考"→"研究性规则表达/高召回实验性筛查/不得替代临床判断/尚未证明部署效用"。
- **P1-07 Q2 主公式**：`w_g^*(q)=min{w:F_g(w)≥q}`（约束式为主），风险函数 E_g(w) 移辅助框架。
- **P1-08/P1-09 layout**：block-aware next-page（section heading+紧跟表 = keep-together candidate，T114）；T99 扩展为**每个** figure/table 的 first-ref placement（`reference_placement[]`）。
- **P1-10 stale Figure 4**：caption 用 `\ref{fig:v3_f4}` 映射当前编号；`figure_story.check_hardcoded_fig_refs`（T113）。
- **P1-11 Figure 2 → TikZ**：`figures/tikz_framework.tex`（xelatex standalone；节点标题+≤1 行说明、左→右形状编码、三删失形状、阈值/推荐 mini-glyph；`renderer=tikz`；`make_figures_v3.fig2` 改为 xelatex 编译/无 xelatex 显式 fallback）。
- **P1-12/13 图 5/9/10**：图 5 页面利用率联动；图 9 R 版（ggrepel/direct labels）；图 10 语言中文化（Precision/Recall→召回率/精确率）、红蓝→主蓝+灰阶、内部审查语气删除。
- **P1-14/15/16 Claim 链**：claim_id 统一消费 FIGURE_SPEC（11 张图全部补 spec）、CLAIM_PROVENANCE v2（claim→result artifact→spec→code→data 全链非空，code_sha 从 `_meta` 消费）、生成器改为 `code/repro_claim_provenance.py`（真实存在）。
- **P1-17/18 RENDER_PROVENANCE + R clean-room**：`repro/RENDER_PROVENANCE.json`（declared vs actual/fallback_reason/script+lock+output sha）；`tests/r_cleanroom.py`（无 R → NOT VERIFIED 不为 PASS）。
- **P1-19 JSON Schema**：`docs/schemas/{final_model_spec.v2,question_contract.v1,idea_candidates.v1,idea_decision.v1,result_registry.v1,figure_spec.v1,page_visual_review.v1}.schema.json` + `schema_validator.py`（jsonschema draft-07；注册为 gate）。
- **P1-20 idea 引用完整性**：`idea_gate.check_referential_integrity`（T120，全量 resolve、状态互斥、minimal+recommended 必需）。
- **§4 视觉四修**：reviewed_pages 精确集合 1..N；coverage 由 gate 从 `page_records` 计算（不再读 self-declared boolean）；结构化 resolution（fixed_and_rereviewed+fixed_pdf_sha256==current / waived_by+rule_ref）；MAJOR 政策（必须 fixed 或显式 waiver，否则 FAIL）。
- **§7 gate registry SSOT**：`workflow_spec.yaml gates:` 完整 registry（16 门，required/strict_aware/args/report）；`run_all_gates.py` 纯解析（T117 静态检查）。
- **§8 AI provenance 两栏制**：`observed_by_system / declared_by_user / unknown_or_unconfirmed`，`attestation_required=true`；未确认项写"待参赛队确认"（禁止自动断言"仅使用…/未使用其他 AI"）。

## 2. 测试与 golden

- T110–T123（14 条，全部来自真实 false-pass）：bad fixture 稳定 FAIL / fixed PASS。
- benchmarks G1–G6 语义并入 T110–T123 场景与现有 golden G2/G3/G4（G3/G4 补全被拒候选 `gold-I99` 引用完整性）。
- `r_cleanroom.py`：R 模板 golden 森林/ROC 渲染（非空矢量 + 重跑确定性）。
- 全量：**138/138 PASS**（无 workspace 基线 7 项正常跳过）；带 NIPT 基线（145 项，除 3 项项目侧待全链完成的基线）→ 全链完成后 15/15 门禁 PASS。

## 3. NIPT golden 项目返修（§15 25 项对照）

1–8 语义/预选/超参/score/主模型/Z 基线/公式 ✓；9 第 5-6 页空白修复（fill 0.47→0.85 级，T114 PASS）；10 Figure 2 TikZ；11 图 5 版面联动；12 图 9 labels；13 图 10 语言/配色；14–18 meta 顺序/真实生成器/claim 链/时间戳（0 未来时间）/重建决策不伪装 prospective；19 clean-room 全链（见 release 记录）；20 R 真实路径 + fallback 记录；21 VERIFY_SUMMARY 硬聚合 0 FAIL；22 ledger 100% 覆盖；23 manifest per-file size/hash；24 sidecar 外部 SHA；25 同一 release record 绑定。

## 4. 文档漂移修正

- `docs/V43_CHANGES.md`：`save_figure.R` 说明订正（v4.4 起 `save_figure()` 定义于 `R/theme_mathmodel.R`）。
- `workflow_spec.yaml`：gates registry（16 门）为唯一事实源；README/计数不再手写第二份。
- SKILL 同步：`6verity/SKILL.md`（新检查/表单/门禁清单引用 registry）、`5writing/SKILL.md`（cross-figure 引用稳定 id + `\ref` 映射；score 语义）、`3coding-visual/SKILL.md`（save_result 原子写 meta；renderer 执行证据）、`7methodology-review/SKILL.md`（pre_specified 纪律/时间三概念）。
