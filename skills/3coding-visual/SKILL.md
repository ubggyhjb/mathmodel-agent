---
name: 3coding-visual
description: "数学建模编程实现与数据图表生成阶段。根据 ANALYSIS_MODELING_REPORT.md 编写可复现代码、运行求解、验证约束、输出 RESULTS_REPORT.md 并生成论文可用的数据驱动图表 PDF。"
whenToUse: "数模工作流中完成建模设计后进入编程实现、运行求解、生成数据图表时使用（通常由 1start-mathmodel 调用）。"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch
---

# 编程实现与数据图表生成

本 skill 承接 `2analysis-modeling`。目标是把 `reports/ANALYSIS_MODELING_REPORT.md` 里的模型和算法落实为可复现程序，跑出可信结果，并生成论文中需要的数据型图表。

## 并行子代理策略（本环境用 subagent / workflow 工具）

当子问题之间相互独立（无数据依赖）时，优先并行：同时派出 N 个代码手，每个子代理的 prompt 必须自包含——题目背景、该子问题的模型公式/目标函数/约束条件（从 ANALYSIS_MODELING_REPORT.md 摘录）、数据文件路径、输出文件路径约定（如 `code/problem1.py`、结果写入 `reports/` 或 `figures/` 的约定文件名）。每个子代理独立完成 编写→运行→约束校验→输出。全部完成后由主代理汇总写入 `reports/RESULTS_REPORT.md` 并做跨问题一致性检查（物理常数、数据来源统一）。

存在依赖关系（问题二需要问题一的结果）时，按顺序执行，不要强行并行。

**按角色配模型（可选，非必须）**：默认用 `subagent` 并行即可（子代理继承会话模型，零配置）。只有确实想给代码手换模型时，才用 `workflow` 工具 + `agent(prompt, {provider, model})` 覆盖；prompt 必须自包含（子代理看不到本会话上下文），并明确要求子代理把关键数值写入约定文件。workflow 脚本只能用钩子函数（agent/pipeline/parallel/phase/log/args），不能访问文件系统——文件读写让子代理自己做。

## 数学建模规范参考

如需领域判断，读取 `../references/math_modeling_norms.md` 中的“题型防错速查”“代码实现与结果”“编码阶段常见错误”和“图表与可视化”小节。该文件只作为规范知识库，不新增本阶段的固定产物。

## 阶段边界

- 本阶段负责：代码、实验运行、结果、结果表、数据驱动图表。
- 本阶段不负责：技术路线图、算法流程图、系统架构图、概念示意图。这些交给 `4drawio`。
- 本阶段不写论文正文，只为 `5writing` 提供可信数值和图表资产。


### Step 1: 代码结构

按 `plan.md` 中"项目目录结构"创建 `code/` 和 `figures/` 骨架，再开始写代码。子问题数不一定是 3，按赛题实际数量调整。


### Step 2: 逐子问题实现

按子问题顺序实现，不要一次性写完不跑。

每个子问题必须完成：

1. 读取所需数据。
2. 实现模型或算法。
3. 验证约束。
4. 输出核心结果。
5. 绘制丰富的图表。
6. 在 `reports/RESULTS_REPORT.md` 中写清楚方法、关键数值和校验结果。

优化类问题必须先保证可行解，再优化目标值。预测类问题必须做训练/验证划分或合理误差评估。评价类问题必须说明指标方向、归一化方法和权重来源。

### Step 2b: 强制代码自证（先于任何论文引用）

所有结果 JSON 在写入 RESULTS_REPORT.md 之前，必须跑一遍自证脚本，**全部 PASS 才允许继续**：

1. 复制本 skill 的 `scripts/verify_template.py` 为 `code/verify_all.py`，按项目实际填写 `RESULT_FILES`、`ID_FIELD` 和 `RANGE_RULES`（数值合理区间按题目领域定，不要照抄模板示例）。
2. 运行 `python code/verify_all.py`，读取它的三项通用守卫：
   - **NaN/Inf 守卫**：任何 NaN/Inf 直接 FAIL——若交叉验证等指标算出 NaN，必须换指标（如小样本 LOO 不用 R²，改用 MAE/RMSE）或说明原因，**禁止隐瞒后继续写论文**。
   - **数据串台守卫**：同一标识（运动员/样本）出现完全相同的内容行 → 疑似文件映射错误，FAIL。
   - **越界守卫**：关键数值超出声明的合理区间 → FAIL，回查检测/求解代码。
3. 任何 FAIL：回到求解代码修复后重跑，修复记录写进 RESULTS_REPORT.md 的"校验"小节。
4. 自证通过后，在 RESULTS_REPORT.md 中写"自证：python code/verify_all.py → 全部 PASS"，并把 verify_all.py 留在 code/ 供 6verity 复查。
5. 论文（5writing）引用的任何数值必须来自自证通过的产物。

历史教训（本机真实发生）：运动者3数据与运动者1完全相同（串台）、dx_pixel=-1325 异常值进回归、LOO-CV R² 全 NaN 被隐瞒——这三类错误全部会被本自证拦截。

### Step 2c: 重跑后全链路强制比对（改动传播纪律）

**任何求解代码改动并重跑之后，严禁只更新一个文件**——按依赖顺序重跑全部下游并逐层核对：

1. 改 problemX.py → 重跑 problemX 及所有依赖其结果的下游脚本（如 problem2 依赖 problem1 的特征、problem3/4 依赖 problem2）。
2. 重跑后立即运行 `code/verify_all.py`——若某处仍引用旧值，跨文件一致性守卫会 FAIL。
3. 论文已写的前提下改任何结果：**必须**用 grep 在 paper/ 全文搜索被改数字的旧值，逐处替换或核实（历史教训：优先级表抄了过期 REPORT，数字合理但已失效——量级守卫查不出"过期值"，只有全链路比对能查）。
4. RESULTS_REPORT.md 同步更新，且与论文同一数字。
5. 重编译 PDF 并确认页数/时间戳变化。

口诀：**动一处，跑全链；改一数，查全文。**

### Step 2d: 实验与生产隔离（灵敏度/交叉验证禁止污染主结果）

- 灵敏度、参数扫描、交叉验证等实验脚本**禁止持久化写主结果文件**（如 `p4_mine*.json`、`result*.xlsx`）：要么给求解函数加 dry-run/不落盘参数，要么实验结束后以**基线参数重跑一次主求解**恢复。
- 实验脚本运行后必须立即打开主结果文件核对：关键字段仍为基线值（如 `t_adj=300/360`、主结果数字与论文一致），核对结果写进 RESULTS_REPORT.md。
- 历史教训（本机真实发生）：sensitivity 的 S7 循环复用 `solve_mine()`（该函数会写盘），循环末次的扰动值（`t_adj=330/390`）覆盖了 p4 主结果，导致论文数字与提交文件两套数据。根因是"实验复用生产写入函数 + 写后不核验"。

### Step 3: 结果文件格式


AI 在实现、求解和作图过程中，必须把关键中间过程保存成数据并做好记录，例如清洗后的数据摘要、模型参数、迭代历史、约束检查、灵敏度分析过程、图表所用数据和运行日志。中间数据优先保存到 `figures/` 或 `code/outputs/`，并在 `reports/RESULTS_REPORT.md` 中说明文件用途。

`reports/RESULTS_REPORT.md` 推荐结构：

```markdown
# 计算结果

## 运行环境
## 数据读取与预处理
## 问题一结果
## 问题二结果
## 问题三结果
## 灵敏度分析
## 约束与一致性校验
## 与建模报告的一致性说明
## 可复现运行方式
```

所有数据和图表结果都必须出现在 `reports/RESULTS_REPORT.md` 中引用

### Step 4: 生成数据驱动图表

根据 `reports/ANALYSIS_MODELING_REPORT.md` 和 `reports/RESULTS_REPORT.md` 规划图表，生成 PDF 到 `figures/`。

典型图表：

- 预测类：真实值-预测值对比、误差分布、指标对比。
- 优化类：收敛曲线、成本对比、资源利用率、方案前后对比。
- 评价类：综合得分排序、雷达图、热力图、敏感性曲线。
- 数据理解：分布图、趋势图、相关性图、箱线图。

图表要求：

- PDF 矢量输出，适合论文。
- 不在图内写大标题，标题交给论文 caption（Typst 的 `caption:` 或 LaTeX 的 `\caption{}`）。
- 中文论文图表使用中文坐标轴和图例；英文论文使用英文。
- 不生成流程图/架构图/路线图。

图表可以由主程序或独立脚本生成，不强制固定脚本名。无论采用哪种方式，都必须保存图表对应的数据来源和生成记录。
