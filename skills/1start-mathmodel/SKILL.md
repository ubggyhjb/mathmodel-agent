
---
name: 1start-mathmodel
description: "数学建模竞赛工作流入口。用于启动完整建模流程：询问用户偏好，生成 plan.md 和 todo.md，并按阶段调用头脑风暴、赛题分析、建模、代码与图表、流程图、论文撰写、验证验收等 skills。"
whenToUse: "用户提供赛题（PDF/文本/图片）要求做数学建模、参加数模竞赛（国赛/美赛/华数杯/华为杯等）、或说'帮我做这道建模题'时使用。"
allowed-tools: pwsh, read, write, edit, grep, glob, subagent, workflow, web_search, ask_user_question
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

HIL_POLICY 单一来源 = `project.manifest.json` 的 `hil_policy` 字段（interactive|auto|disabled），本 skill 启动时初始化写入；与 persona（agent.cordis.yml）同口径，不冲突：

- `interactive`（默认）：在以下 3 个节点用 `ask_user_question` 征询用户（问题少而关键）：
  1. 子问题拆解、假设解释与建模路线/模型选型确定后（2analysis-modeling 结束时，即"模型选型确认"节点；询问是否注入创新方向/领域知识，没有则按"差异化审查"默认走）
  2. 代码结果完成、进入论文撰写前（3coding-visual 结束时）
  3. 论文初稿完成后、验收前（5writing 结束后、6verity 前）
- `auto`：不问任何审批问题直接推进（模型选型也不问）。用户说"全自动 / 别问我"即等价于此，写入 manifest。
- `disabled`：同 auto，且完全不使用审批工具；会话无 `ask_user_question` 工具（或审批被禁用）时等同 auto——不假装已确认、不调用不存在的审批工具。
- 写入/变更：`python <6verity skill>/scripts/project_manifest.py --workspace . --set hil_policy=interactive|auto|disabled`（落盘才生效，不在对话里口头约定）。

## 数学建模规范参考

如需领域判断，读取 `../references/math_modeling_norms.md`。该文件只提供数学建模基本规范和防错知识，不改变本 skill 的阶段顺序和产出约定。

## 必须产出

在当前工作目录中创建或更新以下文件：

- `plan.md`：整体流程方案、建模方向、阶段顺序、预期产物和风险控制。
- `todo.md`：具体待办事项列表，记录每个阶段的任务和状态。
- `state/decision_log.json`：结构化决策日志（阶段状态、关键决策、问题闭环），是断线后唯一的决策记忆，见下文"断点恢复协议"。
- `reports/BRAINSTORM_REPORT.md`：头脑风暴阶段的候选路线与收敛结论（由 `brainstorm-mathmodel` 产出）。

## 工作流

### 0. 阶段顺序单一事实源（v4）

工作流阶段顺序唯一来源 = 仓库根目录 `workflow_spec.yaml`（`version: 4`）。本 skill 的
plan.md / todo.md / 阶段表一律**从该文件生成**，禁止在 plan/todo 里手写阶段顺序。

- 读取方法：`python <6verity skill>/scripts/workflow_spec.py --print`（打印 stage id 列表）；
  阶段全称（skill 名/输入输出/用途）读 `workflow_spec.yaml` 的 `stages` 段。
- `<6verity skill>` = skills/6verity 的实际安装目录——本 skill 被复制/移动后先用
  Get-ChildItem/Test-Path 探测真实位置再拼接，禁止写死绝对路径。
- 一致性校验：`python <6verity skill>/scripts/workflow_spec.py --check --root <repo>`，
  若 FAIL，说明某处仍手写了旧顺序，先修它。

### 0.5 断点恢复（state/decision_log.json + 项目清单）

工作流可能被会话断线、上下文压缩或人工暂停打断。决策不能只存在于对话里——`state/decision_log.json` 是唯一的结构化记忆；`project.manifest.json` 是引擎/入口/HIL_POLICY/工件哈希的单一事实源。

1. 初始化：先运行 `python <6verity skill>/scripts/project_manifest.py --workspace . --init`（创建 project.manifest.json / artifact_manifest.json / state/runtime_manifest.json，自动探测 engine/入口并记录工具版本，已有文件不覆盖），再运行 `python <6verity skill>/scripts/check_decision_log.py --workspace . --create`。`<6verity skill>` = skills/6verity 的实际安装目录——本 skill 被复制/移动后先用 Get-ChildItem/Test-Path 探测真实位置再拼接，禁止写死绝对路径。
2. 断点恢复：若日志显示已有阶段 `done`，先向用户确认"从断点继续 or 重开"。从断点继续时，核对已完成阶段的关键产物仍在磁盘（reports/、code/、results/、figures/、paper/），产物丢失才补跑对应阶段，绝不无脑全部重跑；`project_manifest.py --check` 若报工件漂移（results/figures/paper 哈希与清单不符），说明清单生成后文件被动过——先查原因再 `--refresh` 重录。
3. 每完成一个阶段：更新 `stages[阶段].status = done`、`current_stage = 下一阶段`、`decisions` 追加本阶段关键决策（每条 `decision` 写结论、`reason` 写依据）、更新 `last_updated`。
4. 关键取舍必须落日志：模型选型、参数口径（窗口大小、样本处理、n）、数据排除理由、排版引擎选择等；引擎选择同时写入 project.manifest.json（`--set engine=... --set entry=...`）。`4drawio` 若判定不需要画非数据图，写 `status=skipped` + 一条 decision 说明理由。

### 1. 询问用户偏好 AskUserQuestions（本环境用 ask_user_question 工具）

在规划前，只询问会实质影响流程的问题。问题要少而关键。

优先询问（按重要性排序）：

1. **排版引擎**：Typst 还是 LaTeX？— 决定 5writing 使用哪套模板和编译命令。两套引擎均覆盖全部模板（14 中 + 3 英）。Typst 使用 `typst` 命令编译；LaTeX 使用 `xelatex` 命令编译（需跑两遍解决交叉引用）。**引擎只在本阶段问一次**，选完立即写入 project.manifest.json（`--set engine=... --set entry=...`），5writing/6verity 只读 manifest，禁止二次询问。
2. **竞赛类型**：国赛/华为杯/华中杯/MCM/...— 决定模板选择，见 5writing 的模板族清单。
3. **论文语言**：中文/英文 — MCM/ICM/COMAP 强制英文，其他默认中文。
4. **子问题数量是否已知**：影响章节文件生成数量。若未知，由 2analysis-modeling 阶段根据题面确定。

将用户的选择记录到 `plan.md` 的"方案"小节中。


### 2. 制定方案
按以下结构编写 `plan.md`（阶段表从 workflow_spec.yaml 生成，禁止手写顺序）：

```markdown
# 方案

要依次调用这些 skill，按照里面要求完成任务。

用户偏好：
- 排版引擎：<Typst / LaTeX>
- 竞赛类型：<国赛 / 华为杯 / MCM / ...>
- 论文语言：<中文 / 英文>
- 子问题数量：<已知 N 个 / 待分析确定>

workflow（来源 workflow_spec.yaml，运行 workflow_spec.py --print 生成）:
   step      skills
0. 头脑风暴与候选路线筛选 - `brainstorm-mathmodel`
1. 赛题分析与建模设计 - `2analysis-modeling`
2. 方法学审查与模型契约（v4 强制） - `7methodology-review` → reports/FINAL_MODEL_SPEC.json
3. 编程实现和图表生成 - `3coding-visual`（只实现 FINAL_MODEL_SPEC.json）
4. 流程与架构图绘制 - `4drawio`
5. 竞赛论文撰写 - `5writing`
6. 验证和验收 - `6verity`
```
（以下目录结构见 2.5 节，阶段表来源 workflow_spec.yaml）

### 2.5 项目目录结构

v4 各阶段按此骨架创建和填充文件（与 workflow_spec.yaml 的 inputs/outputs 对齐）：

```text
.
├── plan.md                      # 1: 本文件（阶段表来源 workflow_spec.yaml）
├── todo.md                      # 1: 待办事项（阶段表来源 workflow_spec.yaml）
├── reports/                     # 各阶段文档报告
│   ├── ANALYSIS_MODELING_REPORT.md  # 1: 赛题分析-建模报告（2analysis-modeling）
│   ├── BRAINSTORM_REPORT.md          # 0: 头脑风暴-候选路线筛选（brainstorm-mathmodel）
│   ├── FINAL_MODEL_SPEC.json         # 2: 可执行模型契约（7methodology-review 强制产出）
│   ├── methodology/*.json            # 2: 方法学审计 7 份（7methodology-review）
│   ├── figure_story_manifest.json    # 2: Figure Story 唯一清单（7methodology-review）
│   ├── RESULTS_REPORT.md            # 3: 结果报告（3coding-visual）
│   ├── DRAWIO_REPORT.md             # 4: 非数据图说明（4drawio）
│   └── VERIFY_REPORT.md             # 6: 验收报告（6verity）
├── state/                       # 1: 工作流状态（断点恢复）
│   └── decision_log.json        #     阶段状态 + 关键决策 + 问题闭环（每阶段更新）
├── code/                        # 3: 代码（3coding-visual）
├── results/                     # 3: 结果记录（3coding-visual；JSON 含 model_spec_sha256）
├── figures/                     # 3+4: 所有图表
│   ├── *.pdf                    #     数据图 + 非数据图 PDF
│   ├── *.meta.json              #     每张正式图的 provenance 元数据（v4 强制）
│   └── *.drawio / *.tex / *.mmd #     非数据图可编辑源（按 renderer）
├── paper/                       # 5: 论文（5writing）
│   ├── main.typ / main.tex      #     论文主文件（按用户选择的引擎）
│   ├── generated_values.tex     #     由 results/*.json 生成的关键数值命令（v4 强制）
│   └── sections/                #     各节文件（.typ 或 .tex）
```

方案必须明确每个阶段由哪个下游 skill 负责，以及该阶段应产出什么文件。

### 3. 生成待办

将 `todo.md` 写成阶段性 checklist（条目从 workflow_spec.yaml 生成）：

```markdown
# 待办事项

- [ ] 0. 头脑风暴与候选路线筛选 - `brainstorm-mathmodel`
- [ ] 1. 赛题分析与建模设计 - `2analysis-modeling`
- [ ] 2. 方法学审查与模型契约（v4 强制） - `7methodology-review`
- [ ] 3. 编程实现和图表生成 - `3coding-visual`
- [ ] 4. 流程与架构图绘制 - `4drawio`
- [ ] 5. 竞赛论文撰写 - `5writing`
- [ ] 6. 验证和验收 - `6verity`
```

每完成一个阶段，都要更新 `todo.md` 中对应任务的状态。

### 4. 依次执行阶段

按 workflow_spec.yaml 定义的顺序调用下游 skills（阶段表来源 spec，禁止另写）：

| 阶段 | Skill | 作用 | 主要产物 |
| --- | --- | --- | --- |
| 头脑风暴 | `brainstorm-mathmodel`（兼容别名 `brainstorming`） | 在读题后发散生成多套候选建模思路，评估可行性、区分度与风险，并收敛出主选/备选路线。 | `reports/BRAINSTORM_REPORT.md` |
| 赛题分析与建模设计 | `2analysis-modeling` | 解析题意、识别变量/约束/数据/评价指标，并建立数学模型、目标函数、约束条件和求解策略。 | `ANALYSIS_MODELING_REPORT.md` |
| 方法学审查与模型契约 | `7methodology-review` | 审计 DGP/假设/删失/退化/必要性/泄露/样本量，并产出**可执行模型契约** `reports/FINAL_MODEL_SPEC.json`（v4 强制；后续 coding/writing 只消费该契约）。 | `FINAL_MODEL_SPEC.json`, `methodology/*.json`, `figure_story_manifest.json` |
| 编程实现和图表生成 | `3coding-visual` | 只实现 FINAL_MODEL_SPEC.json 声明的模型；结果 JSON 写 model_spec_sha256；每张正式图生成 .meta.json。 | `code/`, `results/`, `RESULTS_REPORT.md`, `figures/*.pdf+*.meta.json` |
| 流程与架构图绘制 | `4drawio` | 仅在存在无法用正文/数据图表达的结构关系时绘制概念图（concept figure ≤1）。 | `figures/*.tex|*.mmd|*.drawio`, `DRAWIO_REPORT.md` |
| 竞赛论文撰写 | `5writing` | 数值用 paper/generated_values.tex 命令；caption 由 figure manifest 生成；模型契约变更后失效段落重生成。 | `paper/` |
| 验证和验收 | `6verity` | 九门+text_integrity+物理完整性聚合（只读验证，绝不修改被验对象），终审三席 + 答辩销号。 | `VERIFY_REPORT.md` |

每完成一个阶段，除更新 `todo.md` 外，必须同步更新 `state/decision_log.json`（见"断点恢复协议"）：stages 状态、current_stage、decisions 关键决策（decision+reason）、last_updated。

## 阶段边界
- `brainstorm-mathmodel` 只负责思路发散与筛选，不写最终模型公式、不写论文、不生成正式图表；详细建模仍由 `2analysis-modeling` 完成。

- `3coding-visual` 负责生成所有依赖计算结果或实验输出的数据图表。
- `4drawio` 只负责概念图、算法流程图、架构图、路线图等非数据型图示。
- 不要让 `4drawio` 重复绘制 `3coding-visual` 已经生成的统计图或数据图。
- `5writing` 负责决定图表在论文中的位置，并按所选引擎写入图表代码：
  - Typst：`#figure(image("../../figures/xxx.pdf", width: 85%), caption: [...])`
  - LaTeX：`\begin{figure}[H]\centering\includegraphics[width=0.85\textwidth]{../../figures/xxx.pdf}\caption{...}\label{fig:xxx}\end{figure}`
- 不要让 `5writing` 编造数值结论。论文中的数值必须来自 `RESULTS_REPORT.md`、结果表或已生成图表的数据。

