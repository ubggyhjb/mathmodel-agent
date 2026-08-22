# 数学建模 Agent 策略手册（progressive disclosure 第 3 层）

> v4.3（§19/§35.10）：persona 只保留身份、不可违反总原则与 workflow_spec 指针；
> **详细纪律全部下沉到本文件**（同一策略只维护一份，persona/skill 不再重复）。
> 各阶段 skill（1start/2analysis/7methodology/3coding-visual/5writing/6verity）是
> 相应纪律的进一步展开；本手册是跨阶段总纲。

## 1. 不可违反总原则（persona 摘要版，详见各节）

1. 数值结论必须来自代码运行结果，绝不编造；论文数字要么命中 `results/*.json`，要么在 `trace_allowlist.json` 登记并注明来源（UNTRACED = FAIL）。
2. 阶段顺序唯一来源 = 仓库根 `workflow_spec.yaml`（与 persona/决策日志冲突时以 spec 为准，`workflow_spec.py --check` 校验）。
3. 合成器/验证器完全只读：6verity 门禁绝不修改被验对象。
4. 防泄漏四定律：同实体不跨折、阈值超参在训练折/内层 CV 内、标准化只在训练集 fit、外部数据一律登记。
5. 竞赛合规：AI 声明官方定句 + 详情 PDF 入支撑包；不浏览交流平台相关讨论；参考文献真实可核实。

## 2. 人机协作（HIL）

- `project.manifest.json` 的 `hil_policy`（interactive|auto|disabled）为唯一事实源，1start 初始化写入。
- interactive（默认）3 节点：① 2analysis 结束（模型选型确认）② 3coding-visual 结束 ③ 5writing 结束。
- auto/disabled：不咨询直接推进；无 `ask_user_question` 时按 auto；`project_manifest.py --set hil_policy=...` 落盘后执行。

## 3. 等待与异步纪律

- 后台子代理/命令完成时以**会话内通知**唤醒；等通知，不轮询（禁止 while+Start-Sleep 轮询）。
- 派发后同一回合做不依赖其结果的工作再结束回合；查状态用 `list_agents`/`job_list`/`job_output` 各一次。
- 长任务（盲评/大编译/抽帧）正常耗时；只有明确报错/超时才重派。

## 4. 容错与验证纪律

- 先加载 `env-profile` 对照本机事实；工具以 manifest/doctor 实时探测为准。
- 失败命令退码→定位→重试≤2 次→第 3 次换写法。
- 脚本交付前假数据实测（--help → 小样本 → 修 bug → 交付）。
- 结果可疑：回建模报告核对公式约束，不直接接受。
- 跨环节同步：动一处跑全链；重跑后 grep 论文旧值 + 重编译 + 重跑门禁。

## 5. 数据质量与外部数据

- 缺失三问：插值必须写方法+比例（＞20% 考虑剔除并声明）；剔除留证（样本 ID+理由进 decision_log）；不可用列上报用户并降级声明。
- 外部数据：权威优先级（统计局/部委/国际组织/DOI 文献 > 行业库 > 百科+第二来源），优先 `web_search`；每点记 URL+日期到 `references/data_sources.md`，数值入 `results/external_data.json` 才准进论文；**禁止浏览/搜索/参与任何平台的赛题相关讨论（贴吧/QQ 群/知乎/CSDN/GitHub 等）——浏览即违纪**。
- 建模契约（FINAL_MODEL_SPEC v2）：变量只引用 `reports/variables.json` 已登记 ID；availability=unavailable 不得入 primary feature set；结果 `_meta` 语义字段必须与契约一致（methodology gate T70-T74）。

## 6. 阶段状态机与决策日志

- 每阶段完成：`state/decision_log.json`（stages[].status=done / current_stage / decisions 追加 decision+reason / last_updated）；模型选型、参数口径、数据排除理由必须落日志。
- `project.manifest.json` = 引擎/入口/HIL/工件哈希唯一源（`project_manifest.py` 维护）；断线恢复先 `--check` 与 `check_decision_log.py`，核对产物在盘上才继续。
- 科学决策账本：关键取舍（模型族/特征集/窗口口径）写入 `reports/decisions/MODEL_SELECTION_DECISION.json`（T75/T76 时序校验）；论文禁用"预指定"除非 frozen_at 可证。

## 7. 方法学与建模纪律

- 方法学先行：不为"更高级"堆算法；新增方法必须回答"它解决了现有方法无法解决的什么问题？"。
- Brainstorm 契约：三档候选（minimal/recommended/advanced）、失败条件必填、被淘汰方案隔离（Code/Figure/Writing 禁用）、禁止实验结论词（T65-T69）。
- 差异化学：众数解清单+差异化审查；偏离众数须真实文献/数据依据。
- 选型速查：评价/排名→AHP/TOPSIS/熵权法；预测/时序→ARIMA/回归（按时间划分）；优化→LP/IP/GA/PSO/DP（约束写全）；机理→ODE/PDE；图论→最短路/最大流/TSP；统计/ML→聚类/回归/分类（标准化只在训练集）。

## 8. 实验隔离

- 实验脚本禁止持久化写主结果；dry-run 或不落盘；重跑 results/ 前先哈希快照，跑后逐文件比对，漂移查清原因再继续（历史教训：扰动覆盖主结果）。

## 9. 数值追溯与门禁

- 6verity 必跑 `trace_numbers.py --strict`（engine 适配：typst/word 无适配器=FAIL）；`run_all_gates.py --strict` 全量；总体 PASS 要求每门执行且输入非空。
- 强制代码自证：结果 JSON 过 `verify_all.py` 三项守卫（NaN/Inf、串台、越界）；NaN 换指标（小样本 LOO 用 MAE/RMSE）。
- 图表打印：TikZ 画流程图、mpl_paper_style 画数据图（SimHei/图内 9pt/Type42）。

## 10. 盲评与验收

- 3 席独立评审（A 数学建模 / B 统计ML / C 科学编辑与视觉；roster 唯一事实源 = workflow_spec.yaml final_review），固定打分表（摘要10/重述5/假设10/建模25/结果检验15/结构15/图表10/自证10）。
- ≥70 且核心维度（建模求解/结果检验）≥满分 50%、其余≥40% 才 PASS；任一席<70 定向修复；最多 3 轮。
- 每轮问题编号进 todo.md + decision_log.open_issues，全销号才能宣布 PASS；分数轨迹 `reports/blind_scores.json`（禁止取均值）。
- Reviewer C 视觉 veto 语义：blank/orphan spill/near-empty page/clipped/overlap/unresolved ref/孤立标题等 BLOCKER 不被总分平均掉；产出 `reports/page_visual_review.json`（SHA/覆盖/裁决）后才能过 visual_review_gate。
- 提交线：<62 未达 / 62-69 提交线（仍须复评）/ ≥70 真国一观察范围（实证锚定 `references/guoyi-calibration.md`）；创新附加分 0-10 仅诊断。

## 11. 合规（2026 国赛）

- AI 声明官方定句、位于参考文献前；使用 AI 生成 `AI 工具使用详情.pdf`（4 项）入支撑包；AI 仅执行类环节。
- 无目录、摘要页页码"1"、正文 ≤30 页、首行=摘要页、附录全部完整源码、支撑包 ≤20MB。
- 参考文献真实可核实；违规（交流平台讨论/抄袭/指导教师参与/超员）取消评奖资格。

## 12. 论文写作与排版

- 摘要 600-900 字 4 段（问题→主方法→核心结果→决策意义/边界）、一页完整、每问方法名+精确数值；摘要+关键词同页（orphan spill 先压缩内容，禁止先缩字号）。
- 关键词默认 `\quad` 固定间距（官方模板要求分号时例外）。
- 加粗优先级：结论句 > 模型/方法名 > 引导语 > 数值；裸数字串禁加粗；正文一段 ≤1 处内容性粗体。
- 图注图下居中、表注表上、三线表；图内字号=正文 0.75-0.8 倍；配色语义层级（primary 深蓝/comparators 灰/baseline 浅灰虚线/alert 橙红），颜色非唯一编码。
- 正式主图必须 `figures/specs/<id>.figure.json`（FIGURE_SPEC：claim/evidence_type/renderer/layout/visual_encoding/label_budget/final_width_mm）。
