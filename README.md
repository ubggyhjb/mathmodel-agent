# MathModel Agent — 数学建模竞赛 Agent

专为数学建模竞赛（CUMCM 国赛、MCM/ICM 美赛、APMCM、华为杯、华数杯等）设计的 AI Agent。
在 DeepSeek Harness（DSH）中作为 agent preset 使用：一条指令，从赛题到一篇可直接提交的论文。

工作流（v4，来源 `workflow_spec.yaml`，单一事实源）：
**头脑风暴 → 赛题分析 → 方法学审查(模型契约) → 代码与图表 → 概念图 → 论文撰写 → 验证验收**。

## 功能亮点

- **12 个 skills 完整流水线**：头脑风暴（每子问题 ≥3 条候选路线）、赛题分析、方法学审查、
  编程与图表、概念图、论文撰写、验证验收、环境诊断、参考文献与数据来源纪律。
- **工作流单一事实源（v4）**：`workflow_spec.yaml` 定义全部阶段顺序/输入输出，
  `workflow_spec.py --check` 校验 1start/persona/README/docs/decision_log 与它一致；
  禁止在文档中手写第二份阶段顺序。
- **可执行模型契约（v4）**：`reports/FINAL_MODEL_SPEC.json`——7methodology-review 产出，
  3coding 只实现它、结果 JSON 写 `model_spec_sha256`、methodology 门逐问题核验
  （同一 outcome 跨问题观察机制不一致自动 FAIL）。
- **17 套中英文论文模板**（每套含 Typst 与 LaTeX 两个版本）：CUMCM 国赛、MCM/ICM 美赛、
  APMCM、华为杯、华数杯、电工杯、东三省、华东杯、华中杯、数维杯、五一赛、MathorCup、
  长三角赛、统计建模赛等，另有通用 default 模板。
- **十门验收引擎（6verity）**：`run_all_gates.py --strict` 一键运行，全部 PASS 才可提交：
  1. **manifest**：项目清单与工件哈希（project_manifest.py）
  2. **layout**：PDF 版式 + 源适配器（图源存在、图内有效字号 <5pt FAIL、新鲜度）+
     **内嵌物理越界检查**（表格/图片越出心、行重叠，layout_audit 合入）
  3. **text_integrity（v4 新门）**：`图 ??`/`表 ??`/`式 ??`/TODO/TBD/PLACEHOLDER/待补 +
     编译日志 undefined reference/citation、multiply-defined labels、severe overfull；关键词分隔符检查
  4. **trace**：论文数字必须追溯到 results/*.json；v4 支持 `paper/generated_values.tex`
     命令溯源（数值由结果文件生成，天然带 key）
  5. **style**：v4 每条规则带 severity（must=官方硬规则才 FAIL；recommended=WARN；
     摘要长度/粗体率等为推荐带不硬 FAIL）
  6. **decision**：决策日志完整性（stages 从 workflow_spec 加载）、阶段产物绑定、三席盲评销号链
  7. **refs**：文献逐条 OpenAlex + Crossref 在线核验 + method_citation_map 核心方法引用检查
  8. **methodology**：v4 逐问题契约审查 + 条件必需输入（有删失→censoring_report；
     optimization→degeneracy；supervised_ml→ml_operation_scope）
  9. **leakage**：ML 操作范围 + v4 运行时 fold provenance（results/leakage_audit.json）
  10. **figure_story**：唯一 figure manifest（story/source/hash/panels/caption）+ panel
      integrity（空面板 FAIL）+ annotation-key trace + `supersedes` 硬 fail + caption 一致性
- **验证器只读（v4）**：run_all_gates 绝不修改被验对象（不刷 decision_log 时间戳）；
  writer updates, verifier verifies。
- **排版规范基于实证**：从官方展示论文全库统计的摘要加粗优先级、图内字号、配色等阈值
  （单一事实源 `skills/6verity/style_policy.json`；官方硬规则与推荐经验分层）。
- **三席盲评陪审团 + 致命否决（v4）**：3 个上下文隔离的评审子代理按固定打分表独立评分，
  ≥70 放行；Reviewer B 的 leakage/wrong likelihood/invalid censoring/invalid test protocol
  任一 Critical、Reviewer C 的 figure blank/table clipped/unresolved reference 任一
  Submission blocker → 总分再高也 FAIL。
- **答辩门（v4）**：attack_questions 每条带 severity/status/answer/evidence；
  P0/P1 open > 0 → FAIL（真正"答辩通过才 final PASS"）。
- **竞赛合规内置**：AI 声明定句、2026 提交格式（无目录、摘要页页码、正文 ≤30 页）、
  组队与纪律规则、检索边界（禁止浏览交流平台讨论赛题）。

## 目录结构

```
mathmodel/
├── preset.yml            # 预设元数据（name/description）
├── agent.cordis.yml      # DSH preset 组合：persona、工具、skills 注册
├── workflow_spec.yaml    # v4 工作流单一事实源（阶段/门禁/终审定义）
├── README.md
├── LICENSE
└── skills/
    ├── 1start-mathmodel/         # 启动：plan.md/todo.md 初始化（阶段表读 workflow_spec）
    ├── brainstorm-mathmodel/     # 头脑风暴（兼容别名 brainstorming）
    ├── 2analysis-modeling/       # 赛题分析与建模设计
    ├── 7methodology-review/      # 方法学审查 + FINAL_MODEL_SPEC 契约（v4）
    ├── 3coding-visual/           # 编程实现与图表（只实现契约）
    ├── 4drawio/                  # 概念图/流程图（≤1 张，不再默认 roadmap）
    ├── 5writing/                 # 论文撰写 + templates/ 17 套中英文模板
    ├── 6verity/                  # 十门验收引擎 + style_policy.json + tests/
    ├── mathmodel-figure-templates/ # 学术图表模板（mpl_paper_style、FigureBuilder 等）
    ├── doctor/                   # 环境检查与安装向导
    ├── references/               # 文献/数据来源模板、版面实证校准
    └── typst-author/             # Typst 排版知识
```

## 使用

### 作为 DSH preset 安装

将本仓库放入 DSH 的 agent-presets 目录（如 `~/.dsh/agent-presets/mathmodel`），
会话中选择 `mathmodel` 预设即可：preset.yml 注册名称与描述，agent.cordis.yml 挂载 persona、
工具映射与 12 个 skills，skills 内的技能会出现在会话目录中。

### 独立使用验收引擎

不依赖 DSH 也可以直接把 `skills/6verity/scripts/` 用作论文质检工具（按项目结构约定工作）：

```bash
# 依赖：python 3.10+，pip install pymupdf   # 其余用标准库
python skills/6verity/scripts/run_all_gates.py --workspace <项目目录> --strict
python skills/6verity/scripts/project_manifest.py --workspace <项目目录> --check
python skills/6verity/scripts/workflow_spec.py --check --root <仓库根>  # 单一事实源一致性
```

回归测试（含 fixture 与负向 regression 用例；未提供真实项目时基线用例自动 SKIP，
fixture 用例照常跑）：

```bash
python skills/6verity/tests/run_tests.py                        # 无真实项目：fixture 用例
python skills/6verity/tests/run_tests.py --workspace <项目目录>  # 全量（含基线）
```

## 项目目录约定

一个可用 `run_all_gates.py` 验收的项目工作区布局（与 workflow_spec.yaml 的 inputs/outputs 对齐）：

```
<workspace>/
├── project.manifest.json    # 引擎/入口/HIL_POLICY/工件哈希（singular source of truth）
├── plan.md / todo.md        # 阶段表来源 workflow_spec.yaml
├── state/decision_log.json  # 阶段状态机 + 关键决策（v4 阶段集合）
├── references/              # literature.md / data_sources.md
├── reports/
│   ├── FINAL_MODEL_SPEC.json          # v4 模型契约（3coding/5writing 只消费它）
│   ├── methodology/*.json             # 7methodology-review 审计 7 份
│   ├── figure_story_manifest.json     # Figure Story 唯一清单
│   ├── variables.json                 # v4 单位注册（unit registry）
│   └── gates/                         # 门禁报告
├── code/  results/  figures/          # 结果 JSON 带 model_spec_sha256；正式图带 .meta.json
└── paper/                  # main.tex | main.typ + sections/ + generated_values.tex
```

## 许可证

[MIT](./LICENSE)。使用前请遵守各竞赛组委会的规则（如 CUMCM 对 AI 工具使用与检索来源的具体规定），本仓库提供的合规基线以 2026 年国赛口径为准，最终以最新官方文件为准。
