# MathModel Agent v4.2 变更说明

依据《优化/v4.2.md：最新论文 + 支撑材料 + Agent 仓库全链路复核整改任务书》实施。
原则：不加新门、不加新模型，把 v4.1 的验收能力做深，使"程序门全绿但论文/支撑材料仍有真实错误"
的一类 false-pass 无法再通过；并重新生成 NIPT golden fixture 做端到端回归。

## 一、false-pass 修补（新增回归 T46-T64 全部稳定 FAIL）

| 缺陷 | 修补 | 回归 |
|---|---|---|
| 似然公式写反但大小写/变量名可绕过 | text_integrity 角色化校验：S(上界)-S(下界) 一律 FAIL（u/U/r/R=上界，l/L=下界；兼容 `u_i^-`、空格/分行、方括号省略式） | T46（4 种注入 + 正确方向 PASS） |
| 重复列表项隔一条可绕过相邻检测 | section 级重复审计：按 \section 切块，列表项/长句两两归一化比对（>0.92/0.95 → FAIL） | T47 |
| 跨问题总结裸 G3/G4/g3 串台 | text_integrity 扫描"评价/推广/优缺点/结论"章节中无作用域组引用（要求"问题二 G4 组"/Q2.G4 式限定） | T48 |
| multi-panel 图 panels:[] 绕过 panel integrity | figure_story：caption 有 A:/B:/C: 或 meta 多面板信号但 panels 为空 → FAIL | T49 |
| Figure Story 自然语言漂移 | story.claims 结构化绑定 result_key+predicate（crosses_zero/equal_to/gt/lt/within/contains/not_contains），与结果 JSON 矛盾 → FAIL；story 旧口径词（插值/KM）vs caption 新口径（Turnbull）→ FAIL | T50、T51 |
| contact sheet 15 页溢出 30 页请求 | rows=ceil(n/cols) 动态布局 + 渲染页数断言；docstring 虚假 `--figures-dir` 清理；单图预览改 primary 全审 ∪ `--figures` 变更集合（废除 mtime 8 张） | T57 |
| 附录清单 render/check 契约矛盾 | check 递归展开 \input/\include（相对 A_code 目录与工作目录双候选），并与生成片段 union；描述表由 docstring（AST）与 listing 同一 manifest 生成 | T54、T56 |
| workflow/skills 单一事实源漂移 | workflow_spec：methodology 产出 `figures/figure_manifest.json`（唯一），废除旧 reports 路径；generated_values 明确 optional + numeric_source_policy(mode=one_of)；7methodology 去 v3 命名；5writing 图表规划改为"只插 manifest 已批准图，禁止 roadmap/flow/pipeline"；新增 docs_sync.py：README 阶段表区块由 spec 渲染，行为文档残留旧路径/政策措辞漂移 → FAIL | T58、T59 |

## 二、新增两种审计（非"更多门"，verification 强制 substage）

- **deployment_utility.py（9.1/P1-05）**：高敏感性筛查模型强制对比 chosen operating point vs
  predict-all-positive baseline 的 PPV；lift≤0 且论文出现强结论词（应否定语境豁免）→ FAIL。
  自动兼容显式审计 JSON 与 woman-level 结果结构。
- **submission_package_gate.py（9.2/P0-06）**：提交包审计（解压/绝对路径/README/requirements/
  附录一致/参考文献三方一致/dangling 引用）+ `--smoke` clean-room 实测（解压→放附件→运行复现脚本）。
- methodology_gate：parsimony_reopen（P1-03：含 ablation/simpler 结果但无 parsimony_review → FAIL）。
- leakage_gate：algorithm_family_selection 登记校验（inner_cv|pre_specified，P1-04）；
  hardcoded_fallback（.get 默认值≥3 位小数=论文数字 fallback → FAIL，P1-14）。

## 三、NIPT golden fixture 重新生成（v4.2 验收）

- 论文修正：7_problem3 似然公式 S(L)-S(U)；10_evaluation 删除非相邻重复项+作用域重写；
  摘要/正文 Z21≥3 事实化表述；6_problem2 三类不确定性分型（Bootstrap CI/模型形式范围/临床窗口）；
  8_problem4 结论降级（风险排序/研究性筛查 + 部署效用审计）与 parsimony 说明；score 措辞统一。
- Figure：Figure 1C 改 LOESS 平滑+Bootstrap 95% 带+浅灰散点；Figure 2 改纵向 scientific
  schematic（节点框+mini-glyph，无完整坐标轴）；fig_q4_roc 只留 ROC（PR 归 Figure 4A）；
  删除 fig_v3_f3_decision（信息并入 fig_q3_curves/表 4）；正文 12→11 张有独有信息图。
- 支撑材料：code 零绝对路径（ROOT 相对定位 + data/附件.xlsx + styles/ 随包），README/
  requirements/run_all.py/repro/（契约+单位注册+图清单+验证摘要）齐全；clean-room smoke 通过。
- 最终验证：十门 12/12 PASS（含 deployment_utility、submission_package）、run_tests 全 PASS、
  visual_review SHA 绑定一致、三席 Reviewer 无 Critical/Blocker。

## 四、文件清单（Agent 仓库）

修改：workflow_spec.yaml、README.md、agent.cordis.yml、docs/{V4_ARCHITECTURE,FINAL_MODEL_SPEC.schema}.md、
skills/1start-mathmodel/SKILL.md、skills/7methodology-review/SKILL.md、skills/5writing/SKILL.md、
skills/6verity/scripts/{text_integrity,figure_story,visual_review,appendix_source_list,leakage_gate,
methodology_gate,run_all_gates,layout_gate}.py、skills/6verity/tests/run_tests.py
新增：skills/6verity/scripts/{deployment_utility,submission_package_gate,docs_sync}.py、docs/V42_CHANGES.md
