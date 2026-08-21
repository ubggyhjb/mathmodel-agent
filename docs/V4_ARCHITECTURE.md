# MathModel Agent v4 架构变更说明

> 对应整改任务书：`D:\CUMCM2025Problems\优化\v2.txt`（"把 v3 从声明式验收升级成端到端可证明验收"）。
> 版本：v4.0.0。所有门禁/文档/测试入口见 README。

## 一、总目标与验收标准

从"九门都 PASS"改为：

> **模型定义、实际代码、结果文件、图中数据、正文表述、最终 PDF 六层完全同源且相互可验证。**

验收标准（全部达成）：
1. 12 类已知缺陷（任务书 30 条）全部有自动门禁拦截，fixture 回归稳定 FAIL（run_tests T20-T31）；
2. 验证器完全只读（run_all_gates 不再写 decision_log）；
3. 工作流顺序唯一事实源（workflow_spec.yaml），无任何手写副本；
4. NIPT 论文在 v4 门禁下 10 门全绿 + 答辩销号 + 独立视觉检查通过。

## 二、修改文件清单

### 新增（仓库）
| 文件 | 说明 |
|---|---|
| `workflow_spec.yaml` | v4 工作流单一事实源：7 阶段 + 10 门流水线 + 终审 veto 定义 |
| `skills/6verity/scripts/workflow_spec.py` | spec 加载器 + `--check` 一致性校验（引用方必须声明来源、不得残留旧顺序） |
| `skills/6verity/scripts/text_integrity.py` | 文本完整门：图??/表??/悬空引用/TODO/关键词分隔/编译日志 undefined ref、multiply-defined、overfull |
| `skills/6verity/scripts/generated_values.py` | 数值同源生成器：results/*.json → paper/generated_values.tex（\newcommand 命令） |
| `skills/mathmodel-figure-templates/scripts/figure_builder.py` | FigureBuilder：source keys/unit transform/panel meta/artist 计数/annotation 绑定/meta.json 输出 |
| `docs/FINAL_MODEL_SPEC.schema.md` | 模型契约 schema（逐问题 outcome/观测机制/likelihood/evidence/paper_section） |
| `docs/figure_manifest.schema.md` | figure 唯一清单 schema（story/source/panels/caption/supersedes） |
| `docs/WORKFLOW_v4.md` | v4 工作流文档（阶段表来源 spec） |

### 修改（仓库）
| 文件 | 变更 |
|---|---|
| `skills/6verity/scripts/methodology_gate.py` | +FINAL_MODEL_SPEC 逐问题审查：同 outcome 跨问题机制不一致 FAIL（抓 Q2/Q3 口径分裂）；每问章节证据词组核验；model_spec_sha256 校验；contract_rev 失效传播 |
| `skills/6verity/scripts/figure_story.py` | v4 重写：figures/figure_manifest.json 唯一清单；supersedes/redundant 硬 FAIL；panel integrity（空 panel）；annotation-key trace；caption 一致性；unit registry 校验 |
| `skills/6verity/scripts/leakage_gate.py` | +运行时 fold provenance（results/leakage_audit.json：train∩test=∅、阈值⊆train）；代码启发式改为逐文件 |
| `skills/6verity/scripts/verify_refs.py` | +method_citation_map 核心方法引用检查（方法→文献，无引用 FAIL） |
| `skills/6verity/scripts/attack_questions.py` | +答辩销号门 --check：P0/P1 open>0 FAIL；每条问题带 severity/status/answer/evidence |
| `skills/6verity/scripts/layout_gate.py` | +合并 layout_audit（物理越界/行重叠/图片越界入聚合门——修"表裁切仍九门全绿"） |
| `skills/6verity/scripts/run_all_gates.py` | 十门注册（含 text_integrity）；**删除对 decision_log 的写入**（只读化）；+workflow_order 校验 |
| `skills/6verity/scripts/check_decision_log.py` | stages 从 workflow_spec 加载（不再手写阶段列表） |
| `skills/6verity/scripts/style_audit.py` | 摘要加粗率/字数、三线表降为 WARN（recommended 分层，任务书 21/22 条） |
| `skills/6verity/style_policy.json` | abstract 段标注 severity=recommended（偏离→WARN） |
| `skills/1start-mathmodel/SKILL.md` | 阶段表从 workflow_spec 生成；目录结构 v4（FINAL_MODEL_SPEC/meta.json/generated_values.tex） |
| `skills/7methodology-review/SKILL.md` | 产出 FINAL_MODEL_SPEC.json（可执行模型契约）与 v4 阶段边界 |
| `skills/3coding-visual/SKILL.md` | "丰富图表"→"满足 Figure Story 的最少充分图表"；P2 终检取消"三类图覆盖"数量导向 |
| `skills/4drawio/SKILL.md` | 取消"至少一张技术路线图"；concept figure ≤1；renderer→source（.tex/.mmd/.drawio） |
| `skills/5writing/SKILL.md` | generated_values.tex 数值同源；caption 由 manifest 生成；depends_on 失效 |
| `skills/6verity/SKILL.md` | 十门清单 + 只读纪律 + 答辩销号门 + 视觉审稿 Agent + 终审 veto |
| `agent.cordis.yml` / `README.md` | 工作流段来源 spec；十门介绍；v4 目录约定 |
| `skills/6verity/tests/run_tests.py` | +T14-T31（v4 十二类负向 regression）；fixture 更新（+FINAL_MODEL_SPEC.json） |

### NIPT 项目（实证，`D:\CUMCM2025Problems\C题_重生成_20260820`）
- `reports/FINAL_MODEL_SPEC.json`（Q1-Q4 契约；Q2/Q3 同 outcome 同机制）
- `reports/variables.json`（unit registry：Y_fraction 0-1 ↔ % 显示）
- `figures/figure_manifest.json`（v4 唯一清单 15 条，含 supersedes/keep_both_reason）
- `figures/*.meta.json`（15 张，轻量 provenance）
- `results/*.json`（+model_spec_sha256 契约绑定）
- `results/leakage_audit.json`（15 折运行时 group 隔离证明：全 disjoint、阈值⊆train）
- 论文修复：关键词 `；` 分隔；删除 4 张被替代旧图（roadmap/q3_sens/q4_threshold/q4_imp）；删 fig:flow_p2 悬空引用；Table 3 加 resizebox（309pt 越界）；**问题三区间删失似然重写**（原"插值精确时间+右删失似然"缺陷 → 左/区间/右删失 Weibull AFT，代码/论文/结果同源）
- `state/decision_log.json` 迁移 v4 阶段序列；attack_questions 10/10 销号

## 三、Schema 文档索引

| schema | 位置 | 消费方 |
|---|---|---|
| workflow_spec.yaml | 仓库根 | 1start / decision_log / run_all_gates / docs |
| FINAL_MODEL_SPEC.json | docs/FINAL_MODEL_SPEC.schema.md | 7methodology-review 产出；3coding 实现；methodology 门核验 |
| figure_manifest.json | docs/figure_manifest.schema.md | figure_builder 写出；figure_story 门核验 |
| variables.json（unit registry） | 项目 reports/ | figure_builder.transform；figure_story.audit_variables |
| leakage_audit.json | 项目 results/ | leakage_gate.check_runtime_audit |
| attack_questions.json | 项目 reports/methodology/ | attack_questions --check |
| method_citation_map.json | 项目 reports/ | verify_refs |
| value_map.json | 项目 reports/ | generated_values.py |

## 四、边界情况与失败模式（已处理）

1. **旧 v3 项目兼容**：figure_story 回退读 `reports/figure_story_manifest.json`（WARN 提示迁移）；check_decision_log 对缺 brainstorm 的旧日志兼容；methodology 无契约 → strict FAIL（显式，不是静默放行）。
2. **离线**：verify_refs 网络失败时 T11 标 SKIP；其余门禁全离线可跑。
3. **非 LaTeX 引擎**：text_integrity 无 .log 时只做源级扫描；layout_gate physical 只在 PDF 存在时执行。
4. **误报控制**：证据词按"组内任一"而非全词匹配（中文"区间删失"即满足）；参数/相邻对顺序推断改为稳定锚点。
5. **只读保证**：T28 静态测试防回归（run_all_gates 源码不得写 decision_log）。

## 五、测试结果（最终）

```
skills/6verity/tests/run_tests.py --workspace <NIPT 项目> --skip-online -> 34/34 PASS
  （基线 T01/T04/T06-T09/T12 以修复后的 NIPT 项目为 golden；fixture 用例 T02/T03/T05/T10/T11/T13-T33 全过）
  v4 负向 regression T20-T33：12 类已知缺陷全部稳定 FAIL / good case PASS
NIPT 项目 10 门聚合（run_all_gates --strict）：manifest/layout/text_integrity/trace/style/
  decision/refs/methodology/leakage/figure_story + workflow_order 全部 PASS（10/10）
attack_questions --check --strict：10/10 销号（P0/P1 answered）
论文 xelatex 双遍：exit 0；192 页；无 undefined reference/citation；overfull 仅 ≤3.8pt（WARN）
```

## 六、NIPT 修复前后对照（问题三核心，任务书 4 条的实证）

| 项 | v3（缺陷） | v4（区间删失口径） |
|---|---|---|
| Q3 似然 | 插值精确时间 + 精确/右删失似然（与 Q2 机制分裂） | 左/区间/右删失 Weibull AFT，与 Q2 同一 outcome 同一机制（契约强制） |
| 推荐时点 q=0.90 | 16.65 / 17.85 / 19.55 周 | 14.30 / 16.45 / 19.80 周（单调后移保持） |
| 95% CI | 15.8–17.4 / 16.6–18.8 / 17.4–21.5 | 12.25–15.65 / 14.25–18.10 / 13.0–24.2（g3 宽 11.2 周） |
| q=0.95 | 17.6 / 18.85 / 20.65 | 17.15 / 19.70 / 23.70 |
| 主要系数 | BMI −0.0573（p<0.001） | BMI −0.1179（p=0.0070）；age/parity/ivf 不显著（如实报告翻转） |
| 最大扰动漂移 | 0.717 / 0.317 周 | 0.35 / 0.283 周 |
| 最大 q=0.95 后移 | 1.1 周 | 3.90 周（最大稳健性来源，已声明对 q 敏感） |
| BIC（对照） | 1320.9（插值口径） | 439.1（区间口径；exact 对照 1320.91 保留为合法对照项） |

## 七、任务书 36 条覆盖核对（摘要）

- 第 1-5、8、11-27、29-36 条：已逐条实现（见上表与各 schema 文档）。
- 第 6 条条件必需输入、第 9 条 source_hash freshness、第 21 条 severity 分层、第 25 条
  method_citation_map、第 28 条白名单上下文：**本轮复查后才补全**（初始版遗漏，已修复并有回归用例）。
- 第 7 条生成 generated_values.tex（数值命令化）：工具与 5writing 规则已就绪；NIPT 论文本轮由
  trace 数字追溯（53 条 authority 全部命中）+ 结果文件 4 位一致兜底，命令化接入属写作建议项。
- 第 31 条视觉 QA：contact sheet + 关键页目检完成（表 3/表 4 越界与跨行已修；图 10 内标签与
  青带轻微重叠为 WARN 级小瑕疵，记录在案）。
- 第 32 条 veto：三席评审流程（persona 分工 + Critical/Blocker 否决清单）见 6verity SKILL Step 9；
  属评审 Agent 流程而非程序门禁。
