
---
name: 1start-mathmodel
description: "数学建模竞赛工作流入口。用于启动完整建模流程：询问用户偏好，生成 plan.md 和 todo.md，并按阶段调用赛题分析、建模、代码与图表、流程图、论文撰写、验证验收等 skills。"
whenToUse: "用户提供赛题（PDF/文本/图片）要求做数学建模、参加数模竞赛（国赛/美赛/华数杯/华为杯等）、或说'帮我做这道建模题'时使用。"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch
---

# 数学建模工作流

本 skill 是数学建模竞赛项目的总控入口。它不替代后续阶段 skill，而是负责启动流程、询问偏好、记录决策、生成计划，并按顺序调用各阶段 skill。

## 本环境工具映射（DeepSeek Harness 适配）

- Bash → 本环境用 `pwsh` 工具执行命令（Windows）；如有 git-bash 或 wsl 可运行 .sh 脚本。
- WebSearch → 用 `web_search` 工具；WebFetch → 用 `pwsh` + `Invoke-WebRequest`。
- AskUserQuestions → 用 `ask_user_question` 工具（一次最多问几个关键问题）。
- Agent → 用 `subagent` 工具并行派发子任务。
- 后台子代理/后台任务完成会自动以通知唤醒你；等待的姿势是"结束回合等通知"，禁止在 pwsh 里写轮询循环（while+sleep、反复 Test-Path）等结果。

## 人机协作（HIL）审批点

默认在以下节点用 `ask_user_question` 征询用户（问题少而关键）：
1. 子问题拆解与假设解释确定后
2. 建模路线与模型选型确定后（顺带问一句：有没有想注入的创新方向/领域知识？没有就按"差异化审查"默认走）
3. 代码结果完成、进入论文撰写前
4. 论文初稿完成后、验收前

用户若明确说"全自动 / 别问我"，则跳过所有审批点直接推进，只在最终交付前汇报。

## 数学建模规范参考

如需领域判断，读取 `../references/math_modeling_norms.md`。该文件只提供数学建模基本规范和防错知识，不改变本 skill 的阶段顺序和产出约定。

## 必须产出

在当前工作目录中创建或更新以下文件：

- `plan.md`：整体流程方案、建模方向、阶段顺序、预期产物和风险控制。
- `todo.md`：具体待办事项列表，记录每个阶段的任务和状态。
- `state/decision_log.json`：结构化决策日志（阶段状态、关键决策、问题闭环），是断线后唯一的决策记忆，见下文"断点恢复协议"。

## 工作流

### 0. 断点恢复（state/decision_log.json）

工作流可能被会话断线、上下文压缩或人工暂停打断。决策不能只存在于对话里——`state/decision_log.json` 是唯一的结构化记忆：

1. 初始化/校验：先运行 `../6verity/scripts/check_decision_log.py --workspace . --create`（相对本 skill 目录）。文件不存在则创建模板；存在则校验结构（FAIL 时按报错修复日志本身）。
2. 断点恢复：若日志显示已有阶段 `done`，先向用户确认"从断点继续 or 重开"。从断点继续时，核对已完成阶段的关键产物仍在磁盘（reports/、code/、results/、figures/、paper/），产物丢失才补跑对应阶段，绝不无脑全部重跑。
3. 每完成一个阶段：更新 `stages[阶段].status = done`、`current_stage = 下一阶段`、`decisions` 追加本阶段关键决策（每条 `decision` 写结论、`reason` 写依据）、更新 `last_updated`。
4. 关键取舍必须落日志：模型选型、参数口径（窗口大小、样本处理、n）、数据排除理由、排版引擎选择等。`4drawio` 若判定不需要画非数据图，写 `status=skipped` + 一条 decision 说明理由。

### 1. 询问用户偏好 AskUserQuestions（本环境用 ask_user_question 工具）

在规划前，只询问会实质影响流程的问题。问题要少而关键。

优先询问（按重要性排序）：

1. **排版引擎**：Typst 还是 LaTeX？— 决定 5writing 使用哪套模板和编译命令。两套引擎均覆盖全部模板（14 中 + 3 英）。Typst 使用 `typst` 命令编译；LaTeX 使用 `xelatex` 命令编译（需跑两遍解决交叉引用）。
2. **竞赛类型**：国赛/华为杯/华中杯/MCM/...— 决定模板选择，见 5writing 的模板族清单。
3. **论文语言**：中文/英文 — MCM/ICM/COMAP 强制英文，其他默认中文。
4. **子问题数量是否已知**：影响章节文件生成数量。若未知，由 2analysis-modeling 阶段根据题面确定。

将用户的选择记录到 `plan.md` 的"方案"小节中。


### 2. 制定方案

按以下结构编写 `plan.md`：

```markdown
# 方案

要依次调用这些 skill，按照里面要求完成任务。

用户偏好：
- 排版引擎：<Typst / LaTeX>
- 竞赛类型：<国赛 / 华为杯 / MCM / ...>
- 论文语言：<中文 / 英文>
- 子问题数量：<已知 N 个 / 待分析确定>

workflow:
   step      skills
1. 赛题分析与建模设计 - `2analysis-modeling`
2. 编程实现和图表生成 - `3coding-visual`
3. 流程与架构图绘制 - `4drawio`
4. 竞赛论文撰写 - `5writing`
5. 验证和验收 - `6verity`
```

## 项目目录结构

各阶段按此骨架创建和填充文件：

```text
.
├── plan.md                      # 1: 本文件
├── todo.md                      # 1: 待办事项
├── reports/                     # 各阶段文档报告
│   ├── ANALYSIS_MODELING_REPORT.md  # 1: 赛题分析-建模报告（2analysis-modeling）
│   ├── RESULTS_REPORT.md            # 2: 结果报告（3coding-visual）
│   ├── DRAWIO_REPORT.md             # 3: 非数据图说明（4drawio）
│   ├── VERIFY_REPORT.md             # 5: 验收报告（6verity）
├── state/                       # 1: 工作流状态（断点恢复）
│   └── decision_log.json        #     阶段状态 + 关键决策 + 问题闭环（每阶段更新）
├── code/                        # 2: 代码（3coding-visual）
│   ├── problem1.py
│   ├── problem2.py
│   ├── problem3.py               # 问题的数量应该更具题目动态调整
│   ├── ... 
│   └── utils.py
├── results/                     # 2: 结果记录（3coding-visual）
├── figures/                     # 2+3: 所有图表（3coding-visual + 4drawio）
│   ├── *.pdf                    #     数据图 + 非数据图 PDF
│   ├── *.drawio                 #     非数据图源文件
├── paper/                       # 4: 论文（5writing）
│   ├── main.typ / main.tex      #     论文主文件（按用户选择的引擎）
│   └── sections/                #     各节文件（.typ 或 .tex）
```

方案必须明确每个阶段由哪个下游 skill 负责，以及该阶段应产出什么文件。

### 3. 生成待办

将 `todo.md` 写成阶段性 checklist，格式如下：

```markdown
# 待办事项

- [ ] 1. 赛题分析与建模设计 - `2analysis-modeling`
- [ ] 2. 编程实现和图表生成 - `3coding-visual`
- [ ] 3. 流程与架构图绘制 - `4drawio`
- [ ] 4. 竞赛论文撰写 - `5writing`
- [ ] 5. 验证和验收 - `6verity`
```

每完成一个阶段，都要更新 `todo.md` 中对应任务的状态。

### 4. 依次执行阶段

按以下顺序调用下游 skills：

| 阶段 | Skill | 作用 | 主要产物 |
| --- | --- | --- | --- |
| 赛题分析与建模设计 | `2analysis-modeling` | 解析题意、识别变量/约束/数据/评价指标，并建立数学模型、目标函数、约束条件和求解策略。 | `ANALYSIS_MODELING_REPORT.md` |
| 编程实现和图表生成 | `3coding-visual` | 实现可复现代码，运行实验，生成结果表和多种多样的图表。 | `code/`, `results/` ,  `RESULTS_REPORT.md`, `figures/图表` |
| 流程与架构图绘制 | `4drawio` | 在论文确实需要时，绘制方法流程图、架构图和非数据型概念图。 | `figures/*.drawio`, `figures/*.pdf`, `DRAWIO_REPORT.md` |
| 竞赛论文撰写 | `5writing` | 基于分析、建模、代码结果和图表撰写最终竞赛论文，并按章节直接插入图表。 | `paper/` |
| 验证和验收 | `6verity` | 检查可复现性、一致性、产物完整性、格式规范和提交就绪状态。 | `VERIFY_REPORT.md` |

每完成一个阶段，除更新 `todo.md` 外，必须同步更新 `state/decision_log.json`（见"断点恢复协议"）：stages 状态、current_stage、decisions 关键决策（decision+reason）、last_updated。

## 阶段边界

- `3coding-visual` 负责生成所有依赖计算结果或实验输出的数据图表。
- `4drawio` 只负责概念图、算法流程图、架构图、路线图等非数据型图示。
- 不要让 `4drawio` 重复绘制 `3coding-visual` 已经生成的统计图或数据图。
- `5writing` 负责决定图表在论文中的位置，并按所选引擎写入图表代码：
  - Typst：`#figure(image("../../figures/xxx.pdf", width: 85%), caption: [...])`
  - LaTeX：`\begin{figure}[H]\centering\includegraphics[width=0.85\textwidth]{../../figures/xxx.pdf}\caption{...}\label{fig:xxx}\end{figure}`
- 不要让 `5writing` 编造数值结论。论文中的数值必须来自 `RESULTS_REPORT.md`、结果表或已生成图表的数据。

