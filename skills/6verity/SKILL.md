
---
name: 6verity
description: "数学建模竞赛最终验证和验收阶段，支持 Typst 和 LaTeX 双引擎。用于论文写完后检查章节数量、标题顺序、图表引用、数值一致性、论文数字与结果 JSON 双向追溯、盲评量化打分门禁与创新性附加分（国一冲刺诊断）、决策日志闭环、占位符、内部文件泄露、参考文献、代码可复现性、编译和提交就绪状态。"
whenToUse: "数模工作流中论文写完后做最终验证、验收、数值一致性检查、编译检查、提交就绪检查时使用（通常由 1start-mathmodel 调用）。"
allowed-tools: pwsh, read, write, edit, grep, glob, subagent, workflow, web_search, ask_user_question
---

# 验证和验收（Typst / LaTeX）

本 skill 是完整工作流的最后一关。它不重新建模、不生成新结果、不代替写作阶段重写论文；它负责发现硬错误、修复可直接修复的问题，并输出 `reports/VERIFY_REPORT.md`。

## 数学建模规范参考

如需领域判断，读取 `../references/math_modeling_norms.md` 中的"论文验收与一致性"小节。该文件只是规范知识库，不是固定执行流程；具体目录、入口文件、结果文件和图表目录由当前项目结构决定。

## 阶段边界

- 本阶段负责：结构验收、文本质量门禁、图表引用检查、结果一致性检查、Typst/LaTeX 编译检查、PDF 视觉检查、提交清单。
- 本阶段不负责：重新设计模型、重新跑大规模实验、重新组织整篇论文。
- 发现硬错误时，优先做小范围修复；如果需要回到前序阶段，写入 `reports/VERIFY_REPORT.md` 并标记为未通过。

## 输入

由模型先根据当前工作区判断项目布局，再把实际路径传给检查脚本。常见输入包括但不限于：

1. 论文入口文件：`main.typ`（Typst）或 `main.tex`（LaTeX）。
2. 正文章节目录或若干正文文件（`.typ` 或 `.tex`）。
3. 参考文献文件（`references.typ` 或 `references.tex`）。
4. 前序阶段的分析、建模、结果、图示报告。
5. 图表目录
6. 可复现代码目录。
7. 编译后的 PDF，或可由入口文件编译得到的输出 PDF。

不要假设论文目录一定叫 `paper/`，也不要假设结果文件一定在项目根。若项目使用不同命名，按实际结构传参并在 `reports/VERIFY_REPORT.md` 中说明。

## 工作流程

### Step 0: 引擎与工件清单（单一事实源，强制）

所有程序门禁的引擎/入口/HIL_POLICY 只从项目清单 `project.manifest.json` 读取，不靠脚本猜、不靠对话记忆：

```bash
# <6verity skill> = 本 skill 实际安装目录（复制/移动后先探测 scripts/ 真实位置再拼接，禁止写死绝对路径）
python <6verity skill>/scripts/project_manifest.py --workspace . --init     # 缺失则创建三份清单
python <6verity skill>/scripts/project_manifest.py --workspace . --check    # 校验结构 + 工件哈希一致性
```

- 清单三件套：`project.manifest.json`（engine=latex|typst|word、入口、题目数、route.requested/actual——未知一律写 unknown 不编造、hil_policy、工具路径/版本）、`artifact_manifest.json`（results/figures/paper 输入 + main.pdf 输出的 SHA256）、`state/runtime_manifest.json`（每道门运行记录，run_all_gates.py 自动更新）。
- 布局/引擎变更后跑 `--refresh` 重算哈希与工具版本；`--set engine=... --set entry=... --set hil_policy=...` 写声明字段。
- 若 `engine=unknown`：所有引擎适配门禁在 `--strict` 下直接 FAIL，不判伪 PASS——先声明引擎再验收。
- **一键聚合门禁（推荐入口，替代逐条手跑）**：

```bash
python <6verity skill>/scripts/run_all_gates.py --workspace . --strict
# -> reports/gates/gates_report.json（10 门：manifest/layout/text_integrity/trace/style/decision/refs/methodology/leakage/figure_story）
# 总体 PASS 硬条件：每门退出码 0 且确实执行、输入非空（layout 未执行 adapter / trace 数字为 0 = FAIL）
```

所有阈值单一事实源 = `<6verity skill>/style_policy.json`（摘要加粗率 5–15%、正文 0.5–8% 带、图有效字号 5/6pt、DPI 300、近空页 60 字符、底部空白 55% 等）。SKILL 文本与 persona 只引用该文件，禁止各自复制数字。


### Step 0.5: v4 方法学输入（由 7methodology-review 生成，强制）

`7methodology-review`（`2analysis-modeling` 之后、`3coding-visual` 之前的独立强制阶段，v3 新增；v4 起须产出模型契约）已把"模型定义是否成立"审计登记为 `reports/` 下的一组方法学输入。本阶段直接复用；**缺失即代表方法学未审计**，`--strict` 下 v4 各门直接 FAIL：

| 文件 | 用途 | 消费它的门禁 |
| --- | --- | --- |
| `reports/methodology/data_generating_process.json` | 数据生成机制与观测机制（重复测量/删失/缺失/时间依赖） | methodology |
| `reports/methodology/statistical_assumptions.json` | 统计假设一致性（independence/censoring/missingness/random-effect） | methodology |
| `reports/methodology/censoring_report.json` | 删失结构审计（候选模型/插值近似/区间对比） | methodology |
| `reports/methodology/optimization_degeneracy.json` | 优化退化三角对比（objective/constraint/full） | methodology |
| `reports/methodology/model_necessity.json` | 模型必要性分类（Primary/Baseline/Robustness/Rejected） | methodology |
| `reports/methodology/ml_operation_scope.json` | ML 操作允许数据范围（training_fold / inner_cv / outer_test） | leakage |
| `reports/methodology/sample_sizes.json` | 分组样本量与不确定性（有效 n / CI 宽度 / exploratory） | methodology |
| `reports/FINAL_MODEL_SPEC.json` | **v4 可执行模型契约**（逐问题 outcome/机制/likelihood/result_keys/paper_section；results 须带 model_spec_sha256） | methodology（per-problem） |
| `reports/methodology/attack_questions.json` | v4 答辩销号记录（severity/status/answer/evidence；P0/P1 open>0 FAIL） | attack resolution |
| `figures/figure_manifest.json` | v4 Figure 唯一清单（story/source/panels/caption/supersedes） | figure_story |

**v4 聚合入口**：`run_all_gates.py` 现共 **10 门**（manifest/layout/text_integrity/trace/style/decision/refs/methodology/leakage/figure_story），一条命令聚合：

```bash
python <6verity skill>/scripts/run_all_gates.py --workspace . --strict
# -> reports/gates/gates_report.json（10 门 + workflow_order 校验）
```

**验证器只读（v4 强制）**：run_all_gates 及其任何子门**绝不修改被验对象**（不刷 decision_log 时间戳、不改 results/figures/paper）；freshness 若 FAIL，正确动作是写者更新 decision_log 后重跑，禁止绕过。

门禁程序化复检并补齐论文侧交叉验证（"相互独立"修饰词、Rejected 模型残留正文、弱证据强结论词、契约逐问证据词、图登记覆盖、空 panel、caption 一致性、supersedes、annotation-key、占位符/悬空引用、关键词分隔、物理越界）。


### Step 1: 运行文本质量门禁

优先运行本 skill 的脚本。脚本按入口文件扩展名自动选择检查逻辑（`.typ` → Typst 检查，`.tex` → LaTeX 检查）：

```bash
set -o pipefail
mkdir -p _tmp
SCRIPT_PATH="<按当前 skill 实际位置确定>/scripts/writing_check.sh"
bash "$SCRIPT_PATH" \
  --paper-dir "$PAPER_DIR" \
  --main "$MAIN_FILE" \
  --sections-dir "$SECTIONS_DIR" \
  --references "$REFERENCES_FILE" \
  --figures-dir "$FIGURES_DIR" \
  --results-file "$RESULTS_FILE" \
  --problem-analysis "$PROBLEM_ANALYSIS_FILE" \
  --all-results "$ALL_RESULTS_FILE" \
  | tee _tmp/writing_check.log
```

如果本 skill 被复制到其他目录，使用实际脚本路径。可以先运行 `bash <script> --help` 查看参数。不要把脚本路径、论文目录或文件名写死在验收逻辑中。

**Windows 环境**：若无 bash（git-bash/wsl），writing_check.sh 无法直接运行——不要跳过验收，改用本 skill 的 `scripts/numeric_check.py`（Python，跨平台）做数值一致性检查，并按本文件 Step 2-6 的检查清单逐项人工核对后记录到验收报告。

脚本只扫描文本，不生成论文，也不编译 PDF。它的 `FAIL` 属于硬错误，必须修复后重跑。

### Step 2: 章节数量和标题顺序

**Typst 引擎**检查：

- 入口 `.typ` 文件中 `#include("...")` 的数量是否与实际正文结构匹配。
- include 顺序是否符合文件名前缀顺序，例如 `1_...`, `2_...`, `3_...`。
- 每个 section 是否有明确一级标题（`= 标题`，等号后有空格）。
- 标题顺序是否符合所选论文类型。

**LaTeX 引擎**检查：

- 入口 `.tex` 文件中 `\input{...}` 或 `\include{...}` 的数量是否与实际正文结构匹配。
- 章节顺序是否符合文件名前缀顺序。
- 每个 section 是否有 `\section{}` 或对应级别标题。

通用检查（两种引擎）：

- 章节文件是否缺失、重复引用、未被引用。
- 如果题目不是三问，不强行要求三段问题章节；按 `ANALYSIS_MODELING_REPORT.md` 的子问题数量核对。

### Step 3: 图表和章节匹配

**Typst 引擎**检查：

- 图表目录中的 PDF 是否在正文中被引用。
- `#figure(image(...), caption: [...])` 的图片是否真实存在。图片路径必须相对于 `.typ` 文件。
- 数据图是否放在对应结果/分析章节，非数据流程图是否放在方法/总体思路章节。

**LaTeX 引擎**检查：

- `\includegraphics{}` 引用的图片文件是否真实存在。路径相对于 `.tex` 文件。
- `\caption{}` 是否存在。
- 数据图是否放在对应结果/分析章节。

通用检查（两种引擎）：

- 连续图表之间是否有足够解释文字。
- caption 是否过长、过泛或与图意不一致。
- 图表编号、正文引用和章节语义是否一致。
- 图内文字与论文同字体、同语言（TikZ 天然满足；matplotlib 数据图必须经过 `mathmodel-figure-templates/scripts/mpl_paper_style.py`，即 SimHei + 8pt + 矢量 Type42）。
- 灰度打印可辨：关键信息不能只靠颜色区分。
- **新增/改动图表必查（2026-08 补丁，硬性流程）**：本阶段新生成或改动的每一张图、每一个表，必须单独渲染该区域（高 DPI 裁剪）目检——只抽查旧页面不算完成。历史教训：优化会话给图19 新增 (f) 面板时两个表 bbox 重叠、表内数字还是过期的中间结果，却声称"PDF 视觉检查 PASS（抽查旧图页）"。程序兜底：trace 的图内追溯（Step 5d）+ layout_audit + style_audit 的新鲜度检查（Step 8c）三者共同拦这类错误，但新增内容的目检是最后一道。

不要生成 `*_typst_includes.typ` 或 `*_latex_includes.tex`；图表必须直接嵌在对应 section 中。

### Step 4: 写作质量和泄露检查

检查并修复：

- `TODO`、`PLACEHOLDER`、`待补充`、`待续写`、`示例数据` 等占位符。
- 论文正文出现内部工作流文件名、临时目录名、代码目录名或结果 JSON 路径。
- 过多列表式写作（Typst 中大量 `#list`、`enum`，LaTeX 中大量 `\begin{itemize}`、`\begin{enumerate}`）。
- 段落反复以"如图""由图""图 X 展示了"开头。
- 图表后没有解释、公式后没有变量含义、结论只报数不解释。

### Step 5: 数值和结果一致性

检查：

- 论文中的关键数值必须来自当前工作流声明的结果记录或结果 JSON。
- 目标函数值、误差指标、排名、权重、阈值、灵敏度结果不得与结果记录冲突。
- 如果存在汇总结果 JSON，抽取关键指标并确认论文正文中有对应结果。
- 公式中的符号应在符号说明或正文首次出现处解释。

跨平台数值一致性校验（Windows 无 bash 时优先用此脚本，Linux/macOS 也可用）：

```bash
python numeric_check.py --paper-dir "$PAPER_DIR" --results "$RESULTS_FILE"
```

脚本位置为本 skill 的 `scripts/numeric_check.py`（按实际位置传路径）。它抽取论文与结果记录的全部数值 token 并比对，输出疑似编造数值（WARN，需人工核对）和未被引用数值（INFO）。WARN 项需人工确认后再修改论文，不要直接删除论文中来自题面的合法常数。

发现数值冲突时，不要自行发明新结果；应回到结果记录或代码输出修正论文。

### Step 5b: 代码自证复查

- 检查 `code/verify_all.py` 是否存在：不存在则 FAIL（3coding-visual 阶段遗漏了强制自证）。
- 若存在，重跑一遍：`python code/verify_all.py`，退出码非 0 或输出含 FAIL 则 FAIL。
- 对照 `reports/RESULTS_REPORT.md` 是否记录了"自证 PASS"声明；论文中引用的数值必须全部来自自证通过的产物。
- 结果 JSON 中若发现 NaN/Inf、重复数据行、越界异常值而 verify_all.py 未拦截，说明自证规则没写全——回到 code/verify_all.py 补规则后重跑。

### Step 5c: 跨文件一致性与语义矛盾检查

- **跨文件一致性**：同一实体（运动员/样本）在 problem1/2/3/4 各 JSON 中的核心数值（滞空时间、位移、成绩等）必须一致；若两个模块算出的同一人特征不同，说明参数口径不统一（历史教训：速度窗口 window=3 vs window=5 导致两套运动学值），必须统一口径后重跑。verify_all.py 的跨文件守卫覆盖此项，但验收时应人工抽查至少 1 个实体逐字段比对。
- **过期值排查**：任何代码重跑后，用 grep 在 paper/ 全文搜索旧值的数字串，确认无残留（历史教训：优先级表抄了过期 REPORT，量级合理但已失效）。搜索范围必须同时覆盖 `reports/RESULTS_REPORT.md`、`code/`（尤其 make_figures 等作图脚本）与 `figures/figure_manifest.json`：任何一处残留旧模型数字（旧最优值、旧系数、旧扰动口径）即 FAIL，更新后重跑对应脚本（历史教训：P3 改成 BMI-only 多因素 AFT 后 RESULTS_REPORT 仍保留 bmi=+0.523/16.6/17.4/20.0，而 trace 只扫 paper 查不到 REPORT 里的过期值）。
- **语义矛盾检查**：逐节通读，找"建议与结论打架"的句子——例如某节说"增加预蹲深度"、另一节结论是"预蹲越深成绩越差（r=-0.69）"。发现矛盾必须改其一并在验收报告记录。此类矛盾数值脚本查不出，只能靠通读。
- **统计口径核对**：相关/回归的样本量 n、均值口径（训练集 or 全部）、检验单双侧声明，逐项与 results JSON 核对，并按 `references` 知识库"统计口径条款"五条自查。

### Step 5d: 论文↔结果双向数值追溯（强制，AutoMCM/EZ 式门禁）

论文正文出现的每一个数字都必须能追溯到 `results/` 下的结果 JSON，或写明合法来源——用程序强制，不靠人工抽查：

```bash
python <6verity skill>/scripts/trace_numbers.py --workspace . --strict
```

- 脚本按 `project.manifest.json` 的 engine 选择适配器：engine=latex 扫全部 .tex（原行为）；engine=typst 扫 .typ（含 #include 递归、image() 图源）；engine=word 或 unknown 且无对应源文件 → 明确 FAIL，不返回 PASS（先 `project_manifest.py --set engine=...` 声明）。报告含 engine/mode/manifest 字段。
  - `TRACED`：命中结果 JSON，有出处；
  - `PAPER_ONLY`：论文有、结果无，但已在白名单登记来源（内置常量 + 工作区 `trace_allowlist.json`）；
  - `UNTRACED`：论文有、结果无、白名单也没有 → `--strict` 下直接 FAIL；
  - `UNUSED`：结果 JSON 有、论文没用（INFO，可能是正常的中介指标）。
- 处理 `UNTRACED` 只有两条路：①数字确有计算依据 → 把值回写进结果 JSON 后重跑（不要直接改白名单糊弄）；②数字来自题面常数/文献值/显著性水平/样本量等外部事实 → 写进 `trace_allowlist.json`，每条必须带非空 note 说明来源。note 为空 = 未说明来源 = FAIL。
- 白名单格式：`{"entries": [{"value": 0.05, "note": "显著性水平"}, {"pattern": "^1\\.68$", "note": "成人平均身高文献值"}]}`。模板见 `<6verity skill>/trace_allowlist.example.json`（复制为工作区 `trace_allowlist.json`）。
- **权威源校验**：论文关键结果数字除了"存在"之外，还必须命中其**专属权威文件**——写工作区 `trace_authority.json`（模板 `<6verity skill>/trace_authority.example.json`），每条 `{"value": 16.45, "glob": "p4_mine*.json", "note": "..."}`。若该数字在权威文件中不存在（哪怕 sensitivity.json 等别处有同名值），判 FAIL。历史教训：S7 污染后 p4 主文件是 16.47，论文的 16.45 只存在于 sensitivity.json——普通追溯 PASS、权威源校验 FAIL，直接暴露"数字在错的文件里"。
- 容差故意设紧（3e-4）：论文里 0.8634 写成 0.863 这类四舍五入漂移会直接暴露为 UNTRACED，必须统一口径或写 note 说明保留位数——这正是人工通读最容易漏的"看起来对、其实口径漂了"的错误。
- **图内数字追溯（2026-08 补丁，默认开启）**：旧版只扫 .tex，图内文字数字完全不在追溯范围——历史教训：图19 (f) 表内数字 10.80/9.17/16.13 与结果 JSON 完全不符，"全追溯 PASS"照样放行。现在 trace 会提取论文 `\includegraphics` 引用的每张 figures/*.pdf 内的"高精度数值"（≥2 位小数）与节点编号（P/Hxxxx），必须命中 results/*.json 的数值/字符串，或登记进 `trace_figure_allowlist.json`（每条带非空 note，模板 `<6verity skill>/trace_figure_allowlist.example.json`）。坐标轴刻度等派生标注（如色标刻度 9.00/9.25）走图白名单并写明"数据范围自动派生"；结果数值绝不允许进白名单——图里出现结果数字却找不到 JSON 出处，就是图与结果不同步，必须重跑 make_figures 重生成。`--no-figures` 仅限紧急豁免，提交前默认必须开。
- 附录代码块内的常量不会被扫描（代码不是陈述）；但附录代码本身必须是正文真实算法（Step 8c 检查）。

### Step 6: 引用和模板规范

检查：

- 参考文献文件是否存在，或模板是否采用了其他真实参考文献机制。
- 正文引用标记（Typst 的 `@label`/`#super`，LaTeX 的 `\cite{}`）是否能对应到真实参考文献。
- 中文论文 caption、表题、摘要语言保持中文；英文论文保持英文。
- 每个子问题的主方法至少 1 条真实可核实文献支撑（与 `references/literature.md` 对应）；全文方法无文献的论文判 WARN 并回 2analysis 补检索。
- **参考文献程序核验（强制）**：`python <6verity skill>/scripts/verify_refs.py --workspace . --strict`——解析全部 \cite/#super 键与 references 条目，悬空引用 FAIL；每条经 OpenAlex/Crossref 按标题/作者/DOI 核验，unverified/missing 在 strict 下 FAIL；网络不可用时该门明确 FAIL（附"离线核验不可用"），不得把未核验当作通过。竞赛期间只允许学术/官方数据源（参赛规则第 5 条）。
- 若论文使用了外部数据：`references/data_sources.md` 必须存在，每条含来源 URL + 抓取日期；论文引用数值必须命中 `results/external_data.json`（trace 已兜底）；URL 抽查可访问，抓取日期在竞赛窗口内。来源缺失或无法核实 → WARN 并回 2analysis 补检索或上报用户。
- 选定的模板入口是否保留所选比赛模板的必要封面、摘要、编号、页眉页脚或提交格式。
- 不要把模板结构误删成普通空白文档。


### Step 7: 编译

**Typst 编译**：

```bash
command -v typst >/dev/null 2>&1 && typst compile "$MAIN_FILE" "$OUTPUT_PDF"
```

**LaTeX 编译**：

```bash
command -v xelatex >/dev/null 2>&1 && xelatex -interaction=nonstopmode "$MAIN_FILE" && xelatex -interaction=nonstopmode "$MAIN_FILE"
```

xelatex 需跑两遍解决目录和交叉引用。

编译失败必须修复语法、路径、图片引用或模板问题后重跑。编译通过后确认输出 PDF 非空。

### Step 8: PDF 视觉检查

**先跑程序化排版审计（四查 + 引擎无关门禁）**：

```bash
python <6verity skill>/scripts/layout_gate.py --workspace . --strict
# 引擎无关共享 PDF 检查（入口/页面尺寸/底部空白/近空页/被引图源有效字号 <5pt FAIL、5-6pt WARN）
# + LaTeX/Typst 源适配器（include/image 引用存在、图源/论文新鲜度、caption）
# + v4 物理越界审计（layout_audit 已合入本门：越界>15pt FAIL、8-15pt WARN、行重叠、图片越界、
#   按模板 geometry 解析边距；原独立脚本 layout_audit.py 保留为单独运行入口，聚合门以内嵌为准）
# → reports/gates/layout_gate.json（含 supported/executed/coverage/physical_audit）
# word/unknown 引擎无适配器：--strict 下直接 FAIL，不判伪 PASS
```

- layout_gate FAIL（include/image 引用缺失、重复 include、被引图源有效字号 <5pt、main.pdf 早于源文件或被引图源、未知引擎未适配、**physical 越界 >15pt / 页面尺寸异常 / 图片越界**）→ 修复后重编译重跑；越界多为行内不可断 token 硬越界，用 `\emergencystretch=2em`（模板已内置）或 `\allowbreak` 处理，宽表用 `\resizebox{\textwidth}{!}{...}`。
- WARN（小越界 8–15pt、行重叠、近空页、底部大面积空白、page_fill 偏空/偏满、图源有效字号 5-6pt）→ 行重叠多是公式字体提取假阳性，渲染对应页视觉复核即可；近空页/底部空白/page_fill 偏空按“先放大核心图 10–20%、禁止塞字/缩行距”处置（见 5writing 留白纪律）；字号 WARN 应尽量修复（并排图改单列、重绘源图）。page_fill 与 `scripts/whitespace_qa.py` 一律用**行带占用率+最大连续空带**口径（12pt 条带，空带 >25% 内容高即偏空），禁用“内容纵向跨度”判留白（见 whitespace_qa.py 头部说明）。
- **paper-layout-qa 的 check_layout.py（2026-08 已并入五项：标点禁则/表格居中/边距对称/空白页/字体嵌入，硬版心 510pt，跳过宽表页防误报）**：改完 tex/图并双遍编译后，必须跑 `python <paper-layout-qa>/tools/check_layout.py <main.pdf>` 且 **HIGH 清零**（日志层 Overfull>15pt 与 Missing character 必须清零；修法见 5writing“排版细节纪律”），再宣布 6verity PASS。它与 layout_gate/layout_audit 互补：前者管“集中式质检”，十门（run_all_gates）管“门禁基建/规范/追溯/方法学”。

然后做视觉检查：

如果模型有视觉能力，必须把编译后的 PDF 每页导出为 PNG 并逐页查看。这个步骤用于发现纯文本扫描和编译器无法发现的版式错误。

**渲染页新鲜度纪律（2026-08 补丁，防止把旧版当当前版）**：每次编译后必须**重新**渲染页面——先清空输出目录（推荐 `_tmp/pdf-pages`），渲染完成后核对输出目录 mtime 晚于 main.pdf。禁止沿用上一次编译留下的旧 PNG；任何后续环节（含主代理自查、盲评席位复核）引用渲染页之前，必须核对其 mtime ≥ main.pdf，否则该渲染页一律视为过期证据、不得作为当前版结论依据（历史教训：盲评席读了 2:58 的旧渲染页，把已更新的 main.pdf 判为“未反映修订”）。视觉复核优先直接对 main.pdf 用 PyMuPDF/fitz 现渲染关键页，而不是继承历史 PNG。

优先使用系统已有工具导出页面 PNG；不要为了视觉检查引入沉重依赖。用本 skill 的 `scripts/visual_tools.py` 解析可用的光栅化工具（候选：pdftoppm（MiKTeX 自带）→ mgs/gswin64c（Ghostscript）→ mutool → magick → inkscape；探测结果以本机 PATH 为准，不做"某工具未装"式主观断言）：

```bash
python <6verity skill>/scripts/visual_tools.py --probe     # 打印解析到的 (kind, path, version)
python <6verity skill>/scripts/visual_tools.py render --pdf "$OUTPUT_PDF" --out-dir _tmp/pdf-pages --dpi 160
# 无可用光栅化工具时该脚本退出码 1，此时在 VERIFY_REPORT 记录"未执行视觉检查"原因
```

导出后逐页检查：

- 页面是否空白、缺页、页数异常或页面尺寸异常。
- 标题、摘要、正文、页眉页脚、页码是否被裁切或位置明显错误。
- 表格是否超出页边距，单元格文字是否重叠、溢出、被截断。
- 图片、图题、表题、公式、编号是否与正文重叠。
- 公式是否越界，长公式是否压到页边距或下一段文字。
- 列表、段落、脚注、参考文献是否出现异常大空白、重叠或孤立残行。
- 中文/英文/数学符号字体是否明显缺字、乱码或 fallback 异常。
- 封面、摘要页、目录、附录等模板关键页面是否保留比赛要求的视觉结构。

如果是模板转换或已有参考 PDF 的项目，还应将不同引擎的 PDF 都逐页导出 PNG，按页对比版式差异；页数或页面尺寸不一致必须记录为硬错误或明确说明原因。

如果模型没有视觉能力，必须在 `reports/VERIFY_REPORT.md` 中明确写出“未执行视觉检查”的原因，并至少完成 PDF 非空、页数、页面尺寸等可程序化检查。

### Step 8b: 盲评判审（固定打分表 + 阈值 + 轮次上限）

验收阶段最后做一次独立评审，模拟竞赛评委视角发现前序步骤漏掉的问题。评审必须量化：出分、出清单，不许只有"总体不错"式评语。

1. **派 3 席独立评审子代理（陪审团）**：用 `subagent` 工具并行派 3 个互不共享上下文的评审子代理——①通审席（完整 8 维）；②正确性与可复现席（模型/结果/代码/追溯）；③创新与决策效用席（差异化、结论可用性）。每个 prompt 自包含（论文 PDF/正文路径、赛题路径、结果 JSON 路径、下方打分表与评分标准），子代理只拿论文产物本身，模拟盲评。每席必须返回：逐维度分数、总分、按条编号的问题清单（每条给出位置与理由）+ **覆盖声明**（本轮实际读取了哪些文件、抽查了哪几处论文数字 vs JSON、PDF 页数核对结果）。**评审深度底线**：每轮必须通读全部 .tex；复评轮可只精读改动章节，但必须重读摘要/结论/附录，且对上一轮问题清单逐条给出核验证据（文件+行+内容）。只写"已修复"而无逐条证据的评审视为无效评审，重派对应席——历史教训：3 分钟浅读复评产出的裁决分不可信。**三席纪律**：三席之间禁止互相引用结论、禁止主代理向席位透露其他席位的分数；每轮三席分数与清单全部落盘 `reports/blind_scores.json`（分数轨迹），判定以三席总分各自对照阈值（任一席 <70 即定向修复），禁止取均值。有条件时用 workflow 工具的 provider/model 覆盖实现"评者 ≠ 写者"（跨模型评审）；无条件时至少保证三席上下文隔离。首轮详细盲评每席耗时 20–40 分钟属正常——不要因耗时怀疑卡住；怀疑卡住时先用 subagent 状态查询工具确认 running，等待完成通知，只有子代理明确报错或无结果返回时才允许重派。历史教训：主代理曾把跑了 21 分钟的高质量评审误判为卡死，又派了 3 分钟浅读评审并把分数取均值——禁止替代性重复与取均值。**席位执行受限纪律（2026-08 补丁）**：评审子代理运行 verify_all/求解脚本时若被执行环境拦截（沙箱预检失败、权限不足等），必须把"未运行、退出码不可得"如实写进 coverage，禁止凭旧 gate 报告宣称"本轮已运行"，也禁止把"自己没能运行"直接判为论文 FAIL；主代理负责在修复后真实复跑全部相关命令，把 stdout 与退出码落盘 `runs/`（文件名标注轮次），并把该日志路径写入对应 issue 的 resolution。**评审等待期（派完评审后、结果返回前）**：不要干等——在派发评审的同一个回合内完成与评审不冲突的收尾活：①程序门禁复跑（`run_all_gates.py --strict`），把结果写进 VERIFY_REPORT 检查项表；②提交包准备（支撑材料清单：code/、results/、figures/；承诺书 AI 披露提醒；清理 _tmp/、__pycache__/、.idea 等垃圾目录）；③VERIFY_REPORT 骨架先行（检查项、编译、图表引用等已确认部分先填）。等待期禁止重复派发评审、禁止宣布 PASS、禁止修改论文正文（避免与评审返回后的修复冲突）。三席完成通知全部到达后，再按第 4/5 步处理结果。

1b. **盲评销号链数据契约（check_decision_log 程序校验，违规 FAIL）**：`reports/blind_scores.json` 每条终评记录必须含 `{seat, trip, dims(8维), total, gate, issues[], addon}`；**issues 里每个 id 必须出现在 decision_log.open_issues 且 status=closed、resolution 非空**——只写"已修复"没有 resolution（文件+行）的判 WARN，ID 未登记或未 closed 判 FAIL。三席（seat1_overall / seat2_correctness / seat3_innovation）终评必须齐全且各席 total ≥70，缺席或 <70 判 FAIL。分数轨迹禁止取均值，以各席终评单独判定。**席位结论原文落盘（2026-08 补丁）**：席位返回的 gate/coverage/headline/issues 文字必须原样写入 blind_scores.json，主代理不得改写席位 gate 结论；修复完成后如需说明最终状态，只允许**追加** `post_fix_gate` / `post_fix_verified` 字段，禁止替换原始 gate 字符串。席位只给问题编号、未给问题描述时，主代理必须向该席追问补全（文件+行+现象）后再落盘。
2. **固定打分表**（总分 100，权重固定不许改）：

   | 维度 | 权重 |
   | --- | --- |
   | 摘要（独立可读、含硬数字与方法名） | 10 |
   | 问题重述与分析 | 5 |
   | 模型假设与合理性 | 10 |
   | 模型建立与求解 | 25 |
   | 结果分析与检验（误差/灵敏度/优缺点） | 15 |
   | 论文结构与表述 | 15 |
   | 图表与规范 | 10 |
   | 自证、数值追溯与附录完整性 | 10 |

   （本表与《全国大学生数学建模竞赛章程》评奖四标准映射：假设与合理性 → 假设的合理性；模型建立与求解 → 建模的创造性；结果分析与检验 → 结果的正确性；论文结构与表述 + 图表与规范 → 文字表述的清晰程度。分值比例为模式自定，官方未规定比例。）

2b. **国一冲刺附加分（创新性诊断，0–10）**：不计入上面 100 分的 PASS 门槛，但必须出分并写进 VERIFY_REPORT。评审必须额外回答：①这篇论文与"众数解"（大多数队伍会写的方案）的实质差异是什么？无差异给 0 分；②差异是否有依据——真实文献引用或数据/机理证据？③差异是否改变了结论或让结论更可信？附加分 ≥5 记"差异化成立"（诊断标签；实证参考见 `references/guoyi-calibration.md`：5 篇真国一附加分 2–7、中位 5，范文级国一仅 2 分——低附加分不排除国一）。附加分低不是 FAIL，但必须原样报告。

3. **阈值判定**：总分（**不含**国一冲刺附加分）≥70 且核心维度（模型建立与求解 25 分、结果分析与检验 15 分）不低于各自满分的 50%、其余维度不低于满分的 40% → 本轮 PASS；55–69 → 按问题清单定向修改后复评；<55 → 结构性返工（回前序阶段重做对应部分）。多轮评审以**最后一轮分数为准**判定 PASS/FAIL 与档位，禁止取各轮均值。**提交决定以本门禁为准**：总分 ≥70 或用户拍板才放行；62–69 属"提交线"档但按门禁仍须复评，档位仅作诊断标签——禁止模式以"够提交线"为由自行放行。
4. **轮次上限**：最多 3 轮复评。3 轮后仍未 PASS：停止循环，把每轮分数与问题清单原样写入 `reports/VERIFY_REPORT.md` 的"仍需处理的问题"小节，交用户决策。禁止第 4 轮。
5. **问题清单强制闭环（防"报了没修"）**：每轮评审的每条问题编号写入两处——`todo.md` 的"盲评问题清单"小节（状态 `[ ]`）和 `state/decision_log.json` 的 `open_issues`（status=open）；修复一条销号一条（todo 改 `[x]` + 写修复位置"文件+行"；decision_log 改 status=closed + resolution）。**上一轮清单未全部销号前，不得开始下一轮评审、不得宣布验收通过**。历史教训：附录占位代码被盲评报了却漏修——清单闭环就是为了堵这个缝隙。下一轮盲评必须先核验上一轮清单是否全部销号。
6. 评审结论（逐维度分数 + 总分 + 问题与处理）写入 `reports/VERIFY_REPORT.md`，并把"评审结论 + 是否 PASS"追加为 decision_log 的一条 decision。
7. **档位映射（实证校准版，防"PASS 即优秀"误读）**：VERIFY_REPORT 的结论必须写成"PASS（档位）"，禁止只写"PASS"。档位语义按 `references/guoyi-calibration.md` 的实证锚定（7 篇真国一在本表的实测分布 69–88、中位 72）：总分 <62 → 未达提交线；62–69 → 提交线（真国一下界区间）；≥70 → 进入真国一观察范围（本表口径）。**禁止使用"省二稳/省一候选/国一候选"等未经实证的档位词**；创新附加分是诊断标签而非门槛。档位只描述"这篇论文在真国一样本里的位置"，**不改变门禁结论**：62–69 的论文按第 3 条仍须复评，禁止借档位放行。

### Step 8c: 附录与摘要完整性检查

- **附录代码对应性**：`A_code.tex`（或附录）必须包含论文正文**实际使用**算法的核心代码（阶段检测、滤波、集成预测、Bootstrap 等至少其一，可从 `code/` 的真实脚本摘录），禁止放与正文无关的通用占位代码（如教科书式 `read_csv('data.csv')` + `train_test_split` 示例）。评审会据此质疑代码真实性——这是提交前必查项。
- **摘要完整性**：摘要必须覆盖每个子问题的关键结论数字；正文表格中出现的主体（如所有运动者）在摘要中的口径必须与正文一致（不遗漏、不多出、数字相同）。按 5writing"30 秒评审路径"逐项自检：①逐问锚点"针对问题X"；②每问有精确数值（带单位）；③模型名具体；④创新点 1–2 句带对比证据；⑤验证证据（误差/灵敏度/交叉验证）。**摘要公式清零**：摘要出现含"="的公式本体即 FAIL（style_audit 检查项 15；93 篇官方优秀语料零公式，模型公式文字点名）。
- **口径统一性**：全文样本量、均值口径、检验方向等表述必须全局一致——grep 全文搜索旧口径数字（如"10名"vs"8名"）逐一替换，不留任何残留。
- **决策日志完整性**：`python <6verity skill>/scripts/check_decision_log.py --workspace .` 必须 PASS——核心 6 阶段齐全（新项目含可选的头脑风暴 brainstorm-mathmodel 阶段则 7 阶段齐全）、完成状态成前缀、每个已完成阶段有决策记录、open_issues 全部 closed、**freshness（last_updated 晚于全部产物）与阶段产物绑定（done 阶段的关键产物存在）**。FAIL 说明流程状态机坏了，先修日志再谈提交。
- **竞赛规则与 AI 披露合规（2026 试行）**：按 `references` 知识库"竞赛规则与 AI 使用披露"小节自查——论文参考文献前必须有"AI 工具使用声明"且用官方定句（未使用："本参赛队在竞赛过程中未使用任何 AI 工具。"；使用："本参赛队在竞赛过程中使用了 AI 工具，主要用于【简要用途】，详细使用情况见支撑材料。"）；使用 AI 的必须按 `ai_use_report_template.md` 生成详情并以官方文件名 **"AI 工具使用详情.pdf" 放入支撑材料 ZIP**（内容 4 项：工具名称/版本或型号、使用目的和环节、提示方式与过程说明、采纳修改核验情况（语言润色除外））；AI 只能用于执行类环节，核心建模与分析必须参赛队主导、AI 内容逐项核验；参考文献必须真实可核实；严禁虚构或篡改数据（由 verify_all.py + trace_numbers.py 程序兜底）。
- **2026 格式规范 checklist**（逐项核对论文 PDF，任何一项不满足 = FAIL）：① 无目录页；② 标题+摘要+关键词同页且摘要 ≤1 页，该页页码"1"页脚居中；③ 正文 ≤30 页（附录不计）；④ 电子版为单一 PDF ≤20MB 且第一页 = 摘要页（无承诺书/编号页）；⑤ 附录含"支撑材料文件列表"且与提交的支撑材料 ZIP（≤20MB）一一对应（ZIP 须含全部源码、自主查阅的数据资料、AI 工具使用详情.pdf）；⑥ 附录源码**全部完整**（非"核心代码摘录"）且可运行、与正文算法一致——程序化兜底见下方"图表排版强调门"的检查项 12（code/ 下每个源文件都必须被 lstinputlisting/verbatiminput 全文引入，缺一 FAIL）；⑦ 匿名扫描（无学校/姓名/赛区）；⑧ 参考文献格式规范；⑨ 纸质版打印提示：承诺书第 1 页、编号专用页第 2 页（官方模板，队伍自填）、左侧装订，内容与电子版一致。
- **图表排版强调门（程序化）**：跑 `python <6verity skill>/scripts/style_audit.py --workspace . --strict` 必须 PASS——摘要页完整且页码"1"、无目录、**摘要内容性加粗率真实计算（5–15% 推荐带，v4 偏离→WARN；0 加粗或裸数字加粗占比 >50% 仍 FAIL）**、正文加粗密度 0.5-8% 带、嵌图 DPI≥300、图注在图下方、表格默认三线表（v4：非官方硬规则，偏离→WARN 由 contest_profile 放行）、正文 ≤30 页、AI 声明在参考文献前且**官方定句逐字匹配**、附录含支撑材料文件列表、**附录源码全文按内容 sha256 与 code/ 逐一比对（命令存在性不算数）**。任何 FAIL 必须修复后重跑；WARN 逐条给处置说明（修复或声明接受）。此门与 layout_gate（含物理越界合并）互补：style_audit 管"规范"，layout_gate 管"引用/字号/新鲜度/越界"。推荐带规则（摘要字数/加粗率、三线表）一律不因偏离而 FAIL（任务书 21/22 条）。
- **2026-08 补丁的三项新增检查（style_audit 检查项 12/13/14，全部纳入 FAIL 口径）**：⑫ 附录源码全文（见上⑥的程序化版本——历史教训：附录只放 4 段"核心摘录"被认定违规，旧门只查"含支撑材料列表"查不出）；⑬ **交付物新鲜度**——main.pdf 必须晚于全部 .tex 与 figures/*.pdf，否则判定"门禁结果不代表最终版"直接 FAIL（历史教训：改完 tex/图/结果后没重编译没重跑门，交付物与"全 PASS"报告对不上；results/*.json 晚于图 → WARN 提醒重生成图）；⑭ **正文裸数字加粗**——摘要页之外的正文/表格里逐个加粗数字（如表格中 `\textbf{15.88}`）按行级判定为违规（短语加粗如"仅到达 27 个端点"不误报）。
- **最后一版必须重跑全部程序门禁（2026-08 补丁，硬性纪律）**：验收报告里的每个 PASS 必须对应"此刻磁盘上的最终版"。任何 tex/图/代码/结果文件在跑完门禁之后又被修改，必须重新编译 + 全部门禁重跑（style_audit 的新鲜度检查会直接 FAIL 提醒）；禁止把旧结果写进 VERIFY_REPORT 冒充最终版验收。历史教训：优化会话在 23:52–23:58 改了 tex 和图，最后一版编译后零门禁复跑，交付物（图重叠、55pt 越界、附录违规、裸数字加粗）全部存在于"全 PASS"报告里。
- **提交包核验（交付物清单+一致性）**：竞赛提交文件（按附件模板填写的 result*.xlsx 等）必须与 results/ 权威 JSON/xlsx 同源一致：逐个打开提交文件核对行数（表头+数据行）、非空值个数、关键数值与 results/*.json 一致；提交目录中不得残留空模板或错拷贝。任何不一致 = FAIL。历史教训：提交目录里躺着"同一文件的错拷贝 + 9 行空模板"，论文与提交文件两套数据，直接掉档。

### Step 9: 终审重构（v3，三类独立 Persona）

终审不再派"三个相似的国赛评委"，改为三类不同 persona，独立评分后合并。评审范围分工：

- **Reviewer A：数学建模专家** —— 只看问题抽象、优化模型、模型必要性、结论与问题是否匹配。
- **Reviewer B：统计与机器学习审稿人** —— 专攻 independence、repeated measures、censoring、leakage、bias、threshold selection、confidence interval、overfitting。
- **Reviewer C：科学编辑与视觉审稿人** —— 只看摘要、图、表、标粗、视觉层级、30 秒能否理解主结论。

**与 Step 8b 的关系**：Step 8b 规定"派 3 席、8 维固定打分表、总分 ≥70、核心维度 ≥50%、其余 ≥40%、55–69 定向修改复评、<55 结构性返工、最多 3 轮、问题清单强制闭环"的机制；本节只把 3 席**身份**从"通审 / 正确性与可复现 / 创新与决策效用"调整为 A/B/C 三类专家（评分维度、阈值、轮次上限、盲评逻辑、scores 落盘、分席判定全部沿用 8b 不变）。三席独立评分，禁止互相引用结论、禁止主代理向席位泄露其他席分数；有条件时仍用 workflow 的 provider/model 覆盖实现"评者 ≠ 写者"。

**v4 致命否决权（任务书 32 条）**：三席分数只是必要条件；以下任一 **Critical / Submission blocker** 标记 → **总分再高也 FAIL**（veto 优先于平均分）：
- Reviewer B Critical：leakage / wrong likelihood / invalid censoring / invalid test protocol 任一。
- Reviewer C Submission blocker：figure blank / table clipped / unresolved reference（含 `图 ??`、undefined ref）任一。
每席输出中必须显式列出"Critical/Blocker 检查项"清单（无则写"无"），主代理逐个核对，任何触发即进入修复轮回（不因 85+85+60 平均 76.7 放行）。

### Step 10: 攻击式问题答辩与销号（v4 答辩门）

**提交自动运行**攻击式评委问题生成器，生成 ≥10 个最难回答的问题：

```bash
python <6verity skill>/scripts/attack_questions.py --workspace . --min 10
# -> reports/methodology/attack_questions.md + attack_questions.json（每条带 severity/status/answer/evidence）
```

- 每条问题**必须在正文或附录回答**：把答复写入 `attack_questions.json` 的 `answer` + `evidence`（指向 paper:6.2 / results:q2_ic.json 等），`status` 置 `answered`。
- **销号门（v4）**：`python <6verity skill>/scripts/attack_questions.py --workspace . --check --strict` —— **P0/P1 存在 open > 0 → FAIL**；P2 建议级不阻断。任何问题无法回答 → 记 open issue（decision_log.open_issues + todo.md），**不得宣布 final PASS**。
- 无法回答的问题**不是改 status 混过**：要么修复论文/附录补证据，要么把该问题标 P2 并给出"为何不适用"的 evidence。
- `methodology` / `leakage` / `figure_story` 等门任何 FAIL 同理：未修完不得宣布 final PASS。

### Step 10b: 独立视觉审稿 Agent（v4，任务书 31 条）

终审增加一次**看图**审阅：把正文 1-30 页渲染成 contact sheet + 每张本轮新增/修改的 Figure 单独高分辨率图，交给上下文隔离的视觉 Reviewer，只回答：裁切 / 空 panel / 字体太小 / 标签重叠 / 坐标范围异常 / 单位异常 / 视觉中心不明确 / 重复图 / 图注与图意不符。程序化门禁抓不到的问题（曲线全贴底部、标签挤成一团）由这一步兜底；**任何本轮新增或修改的 Figure 必须单独目检，不能只抽查旧页面**。

**v1 十六条（Figure Evidence Consistency Review）并入本步**：每张图进入论文前，独立审稿 Agent 逐图回答：
1. 图是否支持正文声称的结论？（含反向证据检查）
2. 图是否存在与正文相反的证据？
3. 图是否强调了错误的信息（把次要信息当主信息）？
4. 是否存在统计意义与视觉意义冲突（如图内曲线大范围平坦、正文却称"目标函数精确决定"→ WARN）？
五张主 Figure 与所有本轮新增/修改图必须逐张回答，结论写入 reports/VERIFY_REPORT.md 的"图-正文证据一致性"小节。

### Step 11: Paper Simplification Pass（v3）

终稿完成后逐节问一遍，**删掉不影响论证的就删除**：

- 删除一个模型，结论会不会变？
- 删除一张图，信息会不会损失？
- 删除一个表，信息会不会损失？
- 删除一个粗体，阅读会不会变差？
- 删除一个技术术语，摘要会不会更清楚？

目标是"**做得多，但写得少**"。本步与 Step 8c 的图表/摘要完整性互补：8c 保证"该有的信息都在、无冗余残留"，本节主动压缩表述冗余与不必要的模型/图/表/粗体/术语。

### 规则来源说明（v3）

- **一切门禁阈值以 `<6verity skill>/style_policy.json` 为单一事实源**；SKILL 文本与 persona 只引用该文件，禁止各自复制数字。
- `official_rules.json` 只收录**官方硬规则**（必须/禁止级，来源标注官方文件）；`recommended_style.json` 只收录**经验建议**（优秀论文统计/医学期刊惯例）。
- **禁止把"宋体小四""固定粗体率"等推荐风格写成官方规定**——二者分开管理，描述各自口径，严禁混用（spec 二十一条）。

### Step 12: 写验收报告

创建 `reports/VERIFY_REPORT.md`：

```markdown
# 验证和验收报告

## 结论
PASS（档位：提交线 62–69 / 真国一观察范围 ≥70，本表口径） / FAIL

## 检查项
| 检查项 | 结果 | 说明 |
| --- | --- | --- |

## 章节结构

## 图表引用

## 数值一致性

## 国一冲刺附加分（创新性诊断）

## 档位映射
（<62 未达提交线；62–69 提交线；≥70 真国一观察范围，本表口径；创新附加分为诊断标签）

## 文本质量门禁

## 编译

## PDF 视觉检查

## 仍需处理的问题
```

只有当硬错误都修复、文本门禁通过、核心图表都引用、数值一致且 `trace_numbers.py --strict` 追溯通过、决策日志闭环（check_decision_log.py PASS）、编译通过或明确说明不可编译原因、视觉检查通过或明确说明无法执行原因时，才写 `PASS`。

## 硬错误标准

以下问题必须判定 `FAIL`：

- 缺少选定的论文入口文件（`main.typ` 或 `main.tex`）或核心正文。
- 论文入口引用的章节文件不存在。
- Typst 入口缺少 `#include`；LaTeX 入口缺少 `\input`/`\include`。
- 正文章节缺少一级标题（Typst `= ` 后缺空格，LaTeX `\section{}` 缺失）。
- 章节顺序明显错误或重复。
- 正文仍有占位符。
- 正文泄露内部工作流文件名。
- 引用的图片不存在。
- 关键数值与结果记录冲突。
- 编译器可用但论文编译失败。
- 编译后的 PDF 为空、缺页、页数异常或页面尺寸异常且无法解释。
- 视觉检查发现正文、表格、图片、公式、页眉页脚、页码等关键元素重叠、裁切、越界或乱码。
- `trace_numbers.py --strict` 报告存在 UNTRACED 数字（论文数字既无结果 JSON 出处，也无白名单 note 说明来源）。
- `trace_numbers.py --strict` 报告存在 FIG_UNTRACED（被引图内的结果型数字/节点编号与结果 JSON 不符，且未登记图白名单 note）。
- `style_audit.py --strict` 报告"附录未包含全部源程序全文"或"交付物不是最终版"（编译后仍有 .tex/图被修改）。
- `state/decision_log.json` 缺失、阶段顺序异常、已完成阶段无决策记录，或 open_issues 未全部闭环。

## 警告标准

以下问题可判定为 `WARN`，但应尽量修复：

- 未引用的备用图片。
- 某章节过短或明显不均衡。
- caption 偏长。
- 参考文献偏少。
- 图表后解释文字不足。
- 视觉检查工具不可用，但已经记录原因并完成基础 PDF 元数据检查。
- 代码完整复现耗时过长，只做了轻量检查。

