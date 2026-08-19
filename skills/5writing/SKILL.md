
---
name: 5writing
description: "数学建模竞赛论文撰写阶段，支持 Typst 和 LaTeX 双引擎。根据 ANALYSIS_MODELING_REPORT.md、RESULTS_REPORT.md 和 figures/*.pdf 选择比赛模板、排版引擎、组织章节，并在论文正文中按章节直接插入图表。"
whenToUse: "数模工作流中完成建模与代码结果后撰写竞赛论文、选择论文模板、排版编译时使用（通常由 1start-mathmodel 调用）。"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch
---

# 竞赛论文撰写（Typst / LaTeX）

本 skill 承接 `3coding-visual` 和 `4drawio`。前序阶段只提供真实数据、图表 PDF 和记录文件；本阶段负责选择比赛模板和排版引擎、组织论文结构，并决定每张图表放入哪个章节。

**Typst 引擎**下可调用 typst-author skill 学习 typst 写法；**LaTeX 引擎**参考本文件末尾的"LaTeX 写作要点"小节。

## 数学建模规范参考

如需领域判断，读取 `../references/math_modeling_norms.md` 中的“论文写作”“图表与可视化”和“非数据图工具选择”小节。该文件只作为规范知识库，论文结构仍按比赛模板和当前赛题内容决定。

## 模板族

本技能内捆绑的模板位于：

```text
templates/zh/<竞赛>/main.typ         # Typst 模板
templates/zh/<竞赛>-latex/main.tex   # LaTeX 模板
templates/en/<竞赛>/main.typ         # Typst 模板
templates/en/<竞赛>-latex/main.tex   # LaTeX 模板
```

**LaTeX 模板覆盖范围**：所有中文模板和英文模板均已提供 LaTeX 版本（`-latex` 后缀），使用 xelatex 编译。

支持的中文模板（Typst + LaTeX 双版本）：

```text
apmcm, changsanjiao, cumcm, default, diangongbei, dongsansheng,
huashubei, huaweibei, huazhongbei, mathorcup, mcm, shuweibei, stats, wuyibei
```

华为杯、华中杯、五一杯统一使用 `huaweibei`、`huazhongbei`、`wuyibei` 作为模板。

支持的英文模板（Typst + LaTeX 双版本）：

```text
apmcm, default, mcm
```

论文中的所有数值图表结论必须来自 `reports/RESULTS_REPORT.md` 或 `figures/*`。不得编造、估算或使用不同的四舍五入方式。


## 工作流

### 步骤 0：确定排版引擎

**撰写论文前必须让用户选择排版引擎。** 引擎决定后续所有步骤（模板路径、章节文件扩展名、图片插入语法、编译命令），选错会导致整篇论文格式错误。

使用 ask_user_question 询问："撰写论文使用哪种排版引擎？" 选项：

- 选项 1：LaTeX（xelatex）——国赛主流，cumcm-latex 模板 2026 规则全合规、程序门全配套（推荐，放第一位）
- 选项 2：Typst——编译秒级、SVG 直嵌；cumcm Typst 模板已实测编译通过（本机 typst 0.15.1，用全路径调用）
- 选项 3：Word（python-docx）——官方允许的提交格式（格式规范第十条：PDF 或 Word 之一）；本机 Word 16/WPS + python-docx 1.2.0 就绪；公式（OMML）成本高，仅当用户指定或赛区要求时选

引擎选择依据（吸收 pdf-master/latex-engineer 的引擎表）：中文文档 → xelatex 或 Typst；纯英文 → xelatex（pdflatex/lualatex 亦可）；官方要求 Word 或用户偏好 → Word 引擎。不需要在线编译 API（本机 MiKTeX 已装）。

询问前先读取 `plan.md` 的"用户偏好 → 排版引擎"字段作为预选项：
- 若 plan.md 已记录引擎选择，向用户确认："检测到之前选择的引擎是 <LaTeX/Typst/Word>，是否沿用？"
- 若 plan.md 不存在或未记录引擎选择，直接询问用户选择。
- 若用户未明确指定或跳过，**默认使用 LaTeX**。

**图源路由（选引擎时同步确定每张图的输出格式）**：

| 图源 | LaTeX | Typst | Word |
| --- | --- | --- | --- |
| TikZ（技术路线/求解流程图） | ✓ 直接（`mathmodel-figure-templates/tikz/` 模板） | ✗ 改用 mermaid | ✗ 改用 mermaid |
| matplotlib PDF | ✓ 直接 | ✓ 直接 | ✗ 用 SVG |
| matplotlib SVG | inkscape 转 PDF（`--export-filename=a.pdf`） | ✓ 直接 | ✓ 原生支持 |
| mermaid（时序/泳道/状态机/象限图） | `mmdc -i a.mmd -o a.png -b white -s 3`（PNG 300dpi） | `mmdc -o a.svg` | `mmdc -o a.svg` |
| HTML 图（ECharts 等） | Edge headless 截图 PNG 300dpi | PNG | PNG |
| 位图（照片/截图） | PNG ≥300dpi | PNG | PNG |

根据确定的引擎选择对应模板族：

- **Typst 引擎**：使用 `templates/<lang>/<竞赛>/main.typ`，调用 typst-author skill。编译命令 `typst compile main.typ`（全路径）。
- **LaTeX 引擎**：使用 `templates/<lang>/<竞赛>-latex/main.tex`，xelatex 编译（中文和英文均需跑两遍解决交叉引用）。编译命令 `xelatex -interaction=nonstopmode main.tex`（执行两次）。
- **Word 引擎**：python-docx 生成 docx（样式表预设：正文宋体小四/标题黑体/三线表样式），Word COM 转 PDF。

编译失败先查 doctor skill 的"编译错误诊断决策树"，同一命令原样重试 ≤2 次，第 3 次必须换写法。

**后续步骤中的所有代码示例、文件扩展名、图片插入语法都必须按所选引擎选择对应版本，不要混用。**

### 步骤 1：选择语言和模板


除非用户明确要求中文，否则 MCM/ICM/COMAP 一律使用英文。所有中文竞赛名称使用中文。

模板键示例（Typst 引擎）：

```text
长三角 -> zh/changsanjiao
APMCM 英文版 -> en/apmcm
全国赛/国赛/CUMCM -> zh/cumcm
统计建模 -> zh/stats
MCM/ICM/COMAP -> en/mcm
```

模板键示例（LaTeX 引擎）：

```text
全国赛/国赛/CUMCM -> zh/cumcm-latex
MCM/ICM/COMAP -> en/mcm-latex
```

### 步骤 2：准备模板

用以下命令检查捆绑模板是否可访问（`SKILL_DIR` 为本 skill 所在目录）：

**Typst 模板**：

```bash
ls "$SKILL_DIR/templates/zh/<竞赛>/main.typ" 2>/dev/null && echo "OK" || echo "MISSING"
```

- **文件存在（OK）**：直接将 `templates/zh/<竞赛>/` 整目录复制到 `paper/`。这些模板是自包含入口文件，不依赖额外共享样式文件。
- **文件不存在（MISSING）**：说明 skill 未完整安装或在沙箱中，此时依照本 SKILL.md 步骤 3 列出的对应节文件结构，从零重建最小可编译 Typst 框架，并在 `paper/` 内注明"重建自 default 结构"。

存在匹配模板时，绝不从零开始写论文。

**LaTeX 模板**：

```bash
ls "$SKILL_DIR/templates/zh/<竞赛>-latex/main.tex" 2>/dev/null && echo "OK" || echo "MISSING"
```

- **文件存在（OK）**：将 `templates/zh/<竞赛>-latex/` 整目录复制到 `paper/`。
- **文件不存在（MISSING）**：说明 skill 未完整安装或在沙箱中，此时依照本 SKILL.md 步骤 3 列出的对应节文件结构，从零重建最小可编译 LaTeX 框架，并在 `paper/` 内注明"重建自 default-latex 结构"。


### 步骤 3：构建图表规划

在写正文各节之前，根据 `figures/*.pdf`、`reports/RESULTS_REPORT.md`，以及 `reports/DRAWIO_REPORT.md`（如果存在）构建图表规划：

```text
图表规划
fig_roadmap.pdf -> 引言/问题重述
fig_flow_q1.pdf -> 问题一模型构建
fig_flow_q2.pdf -> 问题二模型构建
fig_pipeline.pdf -> 数据预处理/方法节
结果图 -> 对应的结果节
```

图片路径相对于写入该图片的文件：写在 `paper/main.typ` 或 `paper/main.tex` 中通常用 `../figures/xxx.pdf`，写在 `paper/sections/*.typ` 或 `paper/sections/*.tex` 中通常用 `../../figures/xxx.pdf`。

**Typst 引擎**图片插入：

```typst
#figure(
  image("../../figures/fig_q1_error_dist.pdf", width: 85%),
  caption: [问题一预测误差分布],
)
```

**LaTeX 引擎**图片插入：

```latex
\begin{figure}[H]
  \centering
  \includegraphics[width=0.85\textwidth]{../../figures/fig_q1_error_dist.pdf}
  \caption{问题一预测误差分布}
  \label{fig:q1_error}
\end{figure}
```

英文论文使用英文图注。

### 步骤 3b：强调与易读性规范（官方展示论文实证，强制）

依据 `optimization` 语料库实证（2025 官方展示论文 + 100 篇文本版优秀论文全库统计），写作时执行以下规范：

**重点标粗（内容性加粗）**：加粗的目的是让评审 30 秒抓住"每问得到了什么结论"，**优先级 = 结论句 > 模型/方法名 > 引导语 > 关键数值**（官方全库统计：结论句 78 > 数值 51 > 术语 40 > 引导语 9，越新越重）。用模板 `\kw{...}`（LaTeX）/ `#kw([...])`（Typst）加粗四类对象：
1. **结论句（最重要，官方占比最高的一类）**：每问的核心发现、机制解释、工程含义——关键数值要**包在结论短语里整体加粗**，如"24 h 内仅到达 \kw{27 个端点}，水流止于局部盆地""调整后\kw{绕行无水备选路线}，代价约 1.3 min""通知推迟到 300 s 时逃生时间\kw{急剧增至 62.81 min}——早一分钟通知带来非线性安全收益"；
2. 模型/方法名：如"BFS 广度优先模型""随机森林回归模型""多信号融合检测算法"；
3. 引导语："针对问题一、""对于问题二："（摘要各段段首）；
4. 关键数值：**只加粗承载结论的主数值**（每问 ≤2 处），且必须与结论词同框。**禁止把一串裸数字逐个加粗**（"15.88、12.17、18.10"全加粗 = 等于没加粗，评审找不到重点——这是本模式犯过的真实错误，全库实证显示官方加粗对象以结论句为主）。
摘要加粗率 5–15%（官方 E030 达 20–25% 为上限标杆）；标题、"关键词"标签不算内容性加粗。自查口诀：**删掉某个加粗后句意不受损，它就不该加粗**；每处加粗都必须回答"这句被标出后评审多得到了什么"。

**摘要规范（2026 格式规范）**：标题+摘要+关键词同页、≤1 页；4 段结构（问题概述 + 针对问题一/二/三/四），每段 = 方法 + 关键数值 + 结论；600–900 字；无需英文摘要；该页页码"1"页脚居中（模板已配置）。摘要数字必须与正文/trace 同源，摘要最后写、从正文复制数值。

**摘要写作强化（2026-08 吸收 GitHub 两个国赛专用 skill 的实证结论）**：
1. **公式清零（硬性）**：摘要不出现含"="的公式本体（`$v_e=Q_e/A_0$` 这类），模型公式一律文字点名（"推进速度由流量守恒确定"）；参数符号与行内数值记号保留（$t_d$、R₀₁≈0.19 这类合法）。依据：93 篇官方优秀摘要语料零公式。style_audit 检查项 15 程序强制。
2. **四拍闭环**：每问段按"问题转述 → 方法 → 精确数值（带单位/有效位数）→ 结论判定"四拍写全，缺哪拍补哪拍——特别是"问题转述"拍（该问要什么、输入是什么），这是本模式摘要最容易漏的一拍。
3. **开头段压缩**：总起不超过 3 句、约 100–150 字，只交代背景 + 本文做了什么 + 整体路线，不写求解过程与中间细节。
4. **创新点 + 对比证据**：留 1–2 句点明"本文哪里不同"，必须带对比数据或验证结果（"较静态 Dijkstra 提升 X%"），不写"效果显著"类空话。
5. **书面化与减 AI 味**：全文书面语、主语统一"本文"；禁 `→`/`✓` 等非书面符号与条目式罗列；实义连接词（据此/由此/进一步）做因果递进，长短句交替，不用"值得注意的是/综上所述"套话。
6. **30 秒评审路径自检**：成稿后模拟评委 30 秒阅读路径逐项过——①结构扫描（逐问锚点"针对问题X"）；②逐问找结果（每问有数值）；③找模型名（具体、带缩写）；④找创新（1–2 句有证据）；⑤找验证（误差/灵敏度/交叉验证）。任一环节找不到对应内容 → 回补。
7. **收束与关键词页位**：正文与关键词之间留白过多时，补 1–3 句收束段（"本文创新在于：一是……；二是……"）；关键词 4–6 个（模型/算法名为主，不写空泛词），用 `\vfill` 压在摘要页页尾。
8. **关键词不与标题重复**：关键词以方法/算法名为主，避免直接复制标题词（如标题已有"水流漫延"则关键词不再用"漫延"类重复词）；摘要内不出现引用标注（通用学术摘要 checklist 实证，国赛摘要同样适用）。
9. **模糊词替换与证据分层**：改写/润色摘要时把"显著/先进/有效/鲁棒"等模糊词替换为可检验判定词 + 数值条件（"精确最优""偏差不超过 0.94 s"）；区分"原文数据 / 用户确认 / 上下文推断"三层，未确认的机制性表述不落稿——数字层由 trace 门程序强制，机制层靠本纪律兜底。

**易读性五条**：
1. 小节开头写 1–2 句引导（本小节做什么、为什么），再进公式/推导；
2. 图前必须有引出句（"如图 X 所示"置于图**前**的段落里），图后至少一句解读；
3. 表前解释表为什么重要，表后至少一句解读结论（"从表 X 可见……"）；
4. 段落长度 ≤8 行，超长段落拆段；公式独立行后必须跟一句文字解释；
5. 图表紧跟首次引用它的段落，禁止图表与引用文字隔页。

**正文括号政策（2026-08 吸收 cumcm-paper-writing.skill）**：正文少用括号——频繁的括号旁注使论文读起来像生成文本。括号只允许五类：公式内分组、数值单位（含表头）、引用标注、缩写首次定义、坐标/区间/函数参数；其余旁注改写为完整句或逗号（"结果稳定（误差小于 2%）"→"结果保持稳定，误差小于 2%"）。不得机械删括号（公式/引用/单位/代码内不动）。

**AI 套话禁用清单（2026-08 扩充）**：以下短语仅当字面含义确实需要时使用，否则替换为实义逻辑连接（因果/条件/对比/数值比较）："首先、其次、再次、最后"排比堆砌、"值得注意的是"、"不难发现"、"显而易见"、"综上所述"、"通过上述分析可以看出"、"有效提升了"、"充分体现了"、"具有重要意义"、"为……提供了新的思路"、"具有较强的鲁棒性和普适性"、"不仅……而且……"。删除不承载新证据的句子。

**图表规范**：图注在**图下方居中**、表注在**表上方居中**（三线表模板已内置）；图片一律用矢量 PDF（TikZ/mpl_paper_style 产物）；配色 = 蓝橙双强调色 + 灰（禁彩虹色）；图内字号 = 正文 0.75–0.8 倍；子图用 (a)(b) 标注；表格禁止封闭网格样式（一律 booktabs 三线表，表头加粗）。

### 步骤 4：撰写各节

**以下章节文件名按所选引擎使用 `.typ`（Typst）或 `.tex`（LaTeX）扩展名。** 例如 Typst 引擎用 `1_restatement.typ`，LaTeX 引擎用 `1_restatement.tex`。文件名主体保持一致。

中文数学建模通用模板各节文件（`changsanjiao`、`diangongbei`、`huashubei`、`mathorcup`、`wuyibei`）：

```text
1_restatement.typ  - 问题重述与分析
2_analysis.typ     - 数据理解与总体思路
3_assumptions.typ  - 模型假设
4_symbols.typ      - 符号说明
5_problem1.typ     - 问题一建模与求解
6_problem2.typ     - 问题二建模与求解
7_problem3.typ     - 问题三建模与求解
...         - 根据题目调整问题数量  
8_evaluation.typ   - 灵敏度分析、模型评价与推广
A_code.typ         - 附录代码
```

国赛/华中杯/华为杯（`cumcm`、`huazhongbei`、`huaweibei`）按以下章节结构：

```text
1_restatement.typ
2_analysis.typ
3_assumptions.typ
4_symbols.typ
5_problem1.typ
6_problem2.typ
7_problem3.typ
...        - 根据题目调整问题数量
8_sensitivity.typ
9_evaluation.typ
A_code.typ
```

东三省模板（`dongsansheng`）额外使用单独摘要文件：

```text
abstract.typ
1_restatement.typ
2_analysis.typ
3_assumptions.typ
4_symbols.typ
5_problem1.typ
6_problem2.typ
7_problem3.typ
...       - 根据题目调整问题数量
8_evaluation.typ
A_code.typ
```

数维杯模板（`shuweibei`）保留原 LaTeX 的示例入口命名：

```text
Abstract.typ
Introduction.typ
2_analysis.typ
3_assumptions.typ
4_symbols.typ
5_problem1.typ
6_problem2.typ
7_problem3.typ
...      - 根据题目调整问题数量
8_evaluation.typ
Appendices1.typ
A_code.typ
```

中文默认模板（`default`）：

```text
1_restatement.typ
2_assumptions.typ
3_symbols.typ
4_problem1.typ
5_problem2.typ
6_problem3.typ
...      - 根据题目调整问题数量
7_sensitivity.typ
8_evaluation.typ
A_code.typ
```

中文统计建模各节文件：

```text
1_introduction.typ
2_method.typ
3_data.typ
4_analysis.typ
5_results.typ
6_conclusion.typ
A_code.typ
```

英文 MCM/APMCM 各节文件（`en/mcm`、`en/apmcm`、`zh/mcm`、`zh/apmcm`）：

```text
1_introduction.typ
2_assumptions.typ
3_model_design.typ
4_solution.typ
5_sensitivity.typ
6_strengths_weaknesses.typ
7_conclusions.typ
A_code.typ
```

**LaTeX 模板章节文件**（对应 `-latex` 后缀模板，结构与 Typst 版本一一对应）：

国赛 LaTeX 模板（`zh/cumcm-latex`，对应 `cumcm` Typst 版本）：

```text
1_restatement.tex
2_analysis.tex
3_assumptions.tex
4_symbols.tex
5_problem1.tex
6_problem2.tex
7_problem3.tex
8_sensitivity.tex
9_evaluation.tex
A_code.tex
```

MCM/ICM LaTeX 模板（`en/mcm-latex`）：

```text
1_introduction.tex
2_assumptions.tex
3_model_design.tex
4_solution.tex
5_sensitivity.tex
6_strengths_weaknesses.tex
7_conclusions.tex
A_code.tex
```

其余 LaTeX 模板（`changsanjiao-latex`、`default-latex`、`huashubei-latex`、`mathorcup-latex`、`wuyibei-latex`、`huazhongbei-latex`、`huaweibei-latex`、`diangongbei-latex`、`dongsansheng-latex`、`shuweibei-latex`、`stats-latex`、`apmcm-latex`、`mcm-latex`、`en/apmcm-latex`、`en/default-latex`）的章节文件命名与上述结构类似，以 `main.tex` 中 `\input{}` 引用的文件名为准。

英文默认模板（`en/default`）：

```text
1_introduction.typ
2_assumptions.typ
3_notations.typ
4_model.typ
5_sensitivity.typ
6_evaluation.typ
7_conclusions.typ
A_code.typ
```

**正文写作应使用连贯的学术段落。避免在最终论文中出现工作流内部名称，如 `reports/`、`figures/` 或 `CLAUDE.md`。**

### 步骤 5：参考文献

只使用真实存在的参考文献。文件名按引擎选择：Typst 用 `paper/references.typ`，LaTeX 用 `paper/references.tex`。

**Typst 引擎**：

```typst
#set enum(numbering: "[1]")
#enum[
  作者. 题名[J]. 期刊名, 年份, 卷(期): 页码.
  Author. "Title." Journal or Conference, year.
]
```

正文上标引用：`相关研究已用于物流网络优化#super("[1]")。`

**LaTeX 引擎**：

```latex
\begin{thebibliography}{99}
  \bibitem{ref1} 作者. 题名[J]. 期刊名, 年份, 卷(期): 页码.
  \bibitem{ref2} Author. "Title." Journal, year.
\end{thebibliography}
```

正文引用用 `\cite{ref1}` 或 `\cite{ref1,ref2}`。

### 步骤 6：最后撰写摘要或总结

在所有章节完成后撰写中文摘要或英文 Summary Sheet。必须包含每个子问题的方法和精确的数值结果。

## LaTeX 写作要点

以下要点供 **LaTeX 引擎**使用。Typst 引擎请调用 typst-author skill 获取语法帮助。

### 编译命令

```bash
# 中文模板（xelatex，跑两遍解决交叉引用）
xelatex main.tex && xelatex main.tex

# 英文模板（xelatex，同样跑两遍）
xelatex main.tex && xelatex main.tex
```

### 文档结构

```latex
\documentclass[a4paper,12pt]{article}   % 英文
\documentclass[a4paper,12pt]{ctexart}   % 中文

\usepackage{...}   % 宏包加载
\usepackage{graphicx}   % 图片支持
\usepackage{booktabs}   % 三线表
\usepackage{amsmath,amssymb}   % 数学公式
\usepackage{hyperref}   % 交叉引用（需两遍编译）
```

### 图表插入

```latex
\begin{figure}[H]
  \centering
  \includegraphics[width=0.85\textwidth]{../../figures/fig_q1.pdf}
  \caption{图注}
  \label{fig:q1}
\end{figure}

% 三线表
\begin{table}[htbp]
  \centering
  \caption{表注}
  \begin{tabular}{ccc}
    \toprule
    \textbf{列1} & \textbf{列2} & \textbf{列3} \\
    \midrule
    数据 & 数据 & 数据 \\
    \bottomrule
  \end{tabular}
\end{table}
```

### 交叉引用

```latex
如图~\ref{fig:q1}所示，...   % 图片引用
式~(\ref{eq:objective}) 给出...   % 公式引用
见第~\pageref{fig:q1} 页   % 页码引用
```

### 数学公式

```latex
行内公式：$f(x) = \sum_{i=1}^n \theta_i \phi_i(x)$

行间公式：
\begin{equation}
  \mathcal{L}(\theta) = \frac{1}{N}\sum_{i=1}^N (y_i - \hat{y}_i)^2
  \label{eq:objective}
\end{equation}
```

### 章节和强调

```latex
\section{问题重述}
\subsection{问题背景}
\textbf{问题一：} xxx   % 对应 Typst 的 #strong
```

