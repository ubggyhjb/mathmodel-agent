# MathModel Agent — 数学建模竞赛 Agent

专为数学建模竞赛（CUMCM 国赛、MCM/ICM 美赛、APMCM、华为杯、华数杯等）设计的 AI Agent。
在 DeepSeek Harness（DSH）中作为 agent preset 使用：一条指令，从赛题到一篇可直接提交的论文。

工作流：**头脑风暴 → 赛题分析 → 数学建模 → 代码与图表 → 论文撰写 → 验证验收**。

## 功能亮点

- **12 个 skills 完整流水线**：头脑风暴（每子问题 ≥3 条候选路线）、赛题分析、建模、编程与图表、Drawio/TikZ 流程图、论文撰写、验证验收、环境诊断、参考文献与数据来源纪律。
- **17 套中英文论文模板**（每套含 Typst 与 LaTeX 两个版本）：CUMCM 国赛、MCM/ICM 美赛、APMCM、华为杯、华数杯、电工杯、东三省、华东杯、华中杯、数维杯、五一赛、MathorCup、长三角赛、统计建模赛等，另有通用 default 模板。
- **六门验收引擎（6verity）**：`run_all_gates.py --strict` 一键跑六道门禁，全部通过才可提交：
  1. **manifest**：项目清单与工件哈希（project_manifest.py）
  2. **layout**：PDF 版式（A4/空白页/近空页/页底空白/行距越界）+ LaTeX/Typst 源适配器（图源存在、图内有效字号 <5pt FAIL、图与结果新鲜度）
  3. **trace**：论文每个数字必须追溯到 results/*.json，未登记白名单一律 FAIL
  4. **style**：摘要 600–900 字硬带、摘要加粗率 5–15%、三线表、AI 声明官方定句、附录源码内容哈希
  5. **decision**：决策日志完整性、阶段产物绑定、三席盲评销号链
  6. **refs**：文献逐条 OpenAlex + Crossref 在线核验
- **排版规范基于实证**：从官方展示论文全库统计的摘要加粗优先级、图内字号、配色等阈值（单一事实源 `skills/6verity/style_policy.json`）。
- **三席盲评陪审团**：3 个上下文隔离的评审子代理按固定打分表（摘要/重述/假设/建模求解/结果检验/结构表述/图表/自证附录）独立评分，≥70 才放行。
- **竞赛合规内置**：AI 声明定句、2026 提交格式（无目录、摘要页页码、正文 ≤30 页）、组队与纪律规则、检索边界（禁止浏览交流平台讨论赛题）。

## 目录结构

```
mathmodel/
├── preset.yml            # 预设元数据（name/description）
├── agent.cordis.yml      # DSH preset 组合：persona、工具、skills 注册
├── README.md
├── LICENSE
└── skills/
    ├── 1start-mathmodel/         # 启动：plan.md/todo.md 初始化
    ├── brainstorm-mathmodel/     # 头脑风暴（兼容别名 brainstorming）
    ├── 2analysis-modeling/       # 赛题分析与建模设计
    ├── 3coding-visual/           # 编程实现与图表（代码自证）
    ├── 4drawio/                  # 流程图/架构图
    ├── 5writing/                 # 论文撰写 + templates/ 17 套中英文模板
    ├── 6verity/                  # 六门验收引擎 + style_policy.json + tests/
    ├── doctor/                   # 环境检查与安装向导
    ├── mathmodel-figure-templates/ # 学术图表模板（mpl_paper_style 等）
    ├── references/               # 文献/数据来源模板、版面实证校准
    └── typst-author/             # Typst 排版知识
```

## 使用

### 作为 DSH preset 安装

将本仓库放入 DSH 的 agent-presets 目录（如 `~/.dsh/agent-presets/mathmodel`），
会话中选择 `mathmodel` 预设即可：preset.yml 注册名称与描述，agent.cordis.yml 挂载 persona、
工具映射与 12 个 skills，skills 内的技能会出现在会话目录中。

### 独立使用六门验收引擎

不依赖 DSH 也可以直接把 `skills/6verity/scripts/` 用作论文质检工具（按项目结构约定工作）：

```bash
# 依赖：python 3.10+，pip install pymupdf   # 其余用标准库
python skills/6verity/scripts/run_all_gates.py --workspace <项目目录> --strict
python skills/6verity/scripts/project_manifest.py --workspace <项目目录> --check
```

回归测试（13 项，含真实项目基线用例；未提供真实项目时基线用例自动 SKIP，fixture 用例照常跑）：

```bash
python skills/6verity/tests/run_tests.py                        # 无真实项目：fixture 用例
python skills/6verity/tests/run_tests.py --workspace <项目目录>  # 全量 13 项
```

## 项目目录约定

一个可用 `run_all_gates.py` 验收的项目工作区布局：

```
<workspace>/
├── project.manifest.json   # 引擎/入口/HIL_POLICY/工件哈希（singular source of truth）
├── plan.md / todo.md
├── state/decision_log.json # 阶段状态机 + 关键决策
├── references/             # literature.md / data_sources.md
├── reports/                # ANALYSIS_MODELING_REPORT / VERIFY_REPORT / gates/
├── code/  results/  figures/
└── paper/                  # main.tex | main.typ + sections/
```

## 许可证

[MIT](./LICENSE)。使用前请遵守各竞赛组委会的规则（如 CUMCM 对 AI 工具使用与检索来源的具体规定），本仓库提供的合规基线以 2026 年国赛口径为准，最终以最新官方文件为准。
