---
name: 4drawio
description: "数学建模非数据型图示绘制阶段。根据 ANALYSIS_MODELING_REPORT.md、RESULTS_REPORT.md 和已有 figures/ 生成技术路线图、子问题求解流程图、模型结构图、数据处理流程图等（本机首选 TikZ 渲染，DrawIO 源文件保留可编辑性），并导出论文可引用 PDF。"
whenToUse: "数模工作流中论文需要技术路线图、求解流程图、架构图等非数据型图示时使用（通常由 1start-mathmodel 调用）。"
allowed-tools: pwsh, read, write, edit, grep, glob, subagent, workflow, web_search, ask_user_question
---

# DrawIO 非数据图示绘制

本 skill 承接 `3coding-visual`。它只负责论文中的**非数据型图示**，例如技术路线图、求解流程图、模型结构图、数据处理流程图、变量关系图、指标体系图等。

## 数学建模规范参考

如需领域判断，读取 `../references/math_modeling_norms.md` 中的“图表与可视化”和“非数据图工具选择”小节。该文件只作为规范知识库，不要求为了凑数量生成额外图示。

## 阶段边界

- 本阶段负责：DrawIO 源文件、非数据图 PDF、图示生成记录。
- 本阶段不负责：折线图、柱状图、散点图、热力图、箱线图、雷达图等数据图。这些由 `3coding-visual` 生成。
- 本阶段不重跑模型、不修改 `code/`，不改写 `reports/RESULTS_REPORT.md` 的数值结论。

## 必须产出

在当前工作目录创建或更新：

```text
figures/
  fig_roadmap.drawio
  fig_roadmap.pdf
  fig_flow_q1.drawio
  fig_flow_q1.pdf
  ...
reports/DRAWIO_REPORT.md
```

如果某类图不需要生成，必须在 `reports/DRAWIO_REPORT.md` 中说明原因。竞赛论文通常至少需要一张 `fig_roadmap` 技术路线图。

读取这些文件的目的不是提取数据作图，而是理解论文方法、章节结构、子问题关系和已有图表，避免重复。

## 工作流程

### Step 1: 盘点已有图表和需求

先读取以下文件（存在则读取）：`reports/ANALYSIS_MODELING_REPORT.md`、`reports/RESULTS_REPORT.md`、`figures/` 目录列表。

然后从前序文档提取非数据图需求，输出一个清单：

```text
DRAWIO PLAN CHECKLIST:
[ ] fig_roadmap      技术路线图，放在问题重述/绪论
[ ] fig_flow_q1      问题一求解流程图
[ ] fig_flow_q2      问题二求解流程图
[ ] fig_flow_q3      问题三求解流程图
[ ] fig_pipeline     数据处理流程图
[ ] fig_model        模型结构/变量关系图
```

清单不是固定模板，要根据题目实际删减或增补。不要为了凑图生成无意义图示。

### Step 2: 判定图类型

常见图示选择：

| 图类型 | 文件名建议 | 适用场景 |
| --- | --- | --- |
| 技术路线图 | `fig_roadmap` | 展示整体解题路线、章节逻辑、方法串联 |
| 子问题求解流程图 | `fig_flow_q1`, `fig_flow_q2` | 展示单个子问题的输入、判断、算法、输出 |
| 数据处理流程图 | `fig_pipeline` | 展示数据清洗、特征构造、建模输入 |
| 模型结构图 | `fig_model` | 展示模块关系、变量关系、模型层次 |
| 指标体系图 | `fig_index_system` | 展示目标层、准则层、指标层 |
| 决策树/规则图 | `fig_decision_tree` | 展示分类规则、设备选择、策略分支 |
| 时序图 | `fig_sequence` | 多对象交互时序、算法调用链（mermaid `sequenceDiagram`） |
| 泳道图 | `fig_swimlane` | 多角色/多阶段流程职责（mermaid flowchart 泳道样式） |
| 状态机图 | `fig_state` | 状态转移、动态过程（mermaid `stateDiagram`） |

**渲染路由（吸收 diagram-design 图类型清单 + drawio-skill 能力）**：技术路线/子问题流程 → TikZ 模板（`tikz_flow_vertical/layers/decision`）；时序/泳道/状态机 → mermaid（`mmdc` 渲染，本机已装）；输出格式按 5writing 步骤 0 的图源路由表随引擎定（SVG/PNG）。`.drawio` 源文件仍保留可编辑性。

不要用 DrawIO 画这些图：

- 结果对比柱状图
- 预测误差曲线
- 灵敏度曲线
- 相关性热力图
- 分布图和箱线图

### Step 3: 生成 DrawIO 源文件

每张图一个 `.drawio` 文件，放在 `figures/`。

DrawIO 内容要求：

- 文字语言与论文语言一致。
- 节点文字短，必要时双行，不堆长句。
- 同类节点样式统一。
- 箭头方向清晰，避免交叉。
- 图中不写大段解释，解释留给论文正文。
- 不使用装饰性阴影和过度渐变。

生成大 XML 时，分段写入，避免截断。示例：

```bash
mkdir -p figures
cat << 'XMLEOF' > figures/fig_roadmap.drawio
<mxfile>
  <diagram name="Page-1">
    <mxGraphModel>
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        <!-- nodes and edges -->
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
XMLEOF
```

### Step 4: 渲染 PDF

本机首选 **TikZ**（xelatex/MiKTeX 已装），模板在 `../mathmodel-figure-templates/tikz/`：
- `tikz_flow_vertical.tex` 纵向技术路线 / `tikz_flow_layers.tex` 分层架构 / `tikz_flow_decision.tex` 带判断的子问题流程。
- 用法：把模板里的 `tikzpicture` 整段复制到论文 `\begin{figure}[H]\centering ... \end{figure}`（论文导言区需 `\usepackage{tikz}` 和对应 `\usetikzlibrary`），节点文字换成真实内容。图内字体自动与正文一致、矢量、公式可直接进节点。
- **禁止用 matplotlib 画流程图**（历史教训：盒子感强、观感差，模型四因此被批"图没有论文感"）。

mermaid 路线（时序图/泳道图/状态机图，`mmdc` 已装）：
```bash
mmdc -i figures/fig_sequence.mmd -o figures/fig_sequence.svg          # Typst/Word 直嵌
mmdc -i figures/fig_sequence.mmd -o figures/fig_sequence.png -b white -s 3   # LaTeX 用（≈300dpi 级）
```
SVG 进 LaTeX 需先 inkscape 转 PDF：`& "C:\Program Files\Inkscape\bin\inkscape.exe" a.svg --export-filename=a.pdf`。

若 drawio CLI 可用（本机通常没有），也可用它导出：

```bash
DRAWIO_BIN="$(command -v drawio 2>/dev/null || command -v draw.io.exe 2>/dev/null || true)"
if [ -n "$DRAWIO_BIN" ]; then
  "$DRAWIO_BIN" --export --format pdf --crop --output figures/fig_roadmap.pdf figures/fig_roadmap.drawio
else
  echo "DrawIO command not found; 用 TikZ/mermaid 渲染，保留 .drawio 源文件。"
fi
```

无论哪种渲染路径（TikZ/mermaid/drawio），`.drawio` 源文件都保留（可编辑性）；全部不可用时保留 `.drawio` 并在 `reports/DRAWIO_REPORT.md` 记录原因。

### Step 5: 自检和修复

每张图必须检查：

- `.drawio` 文件非空。
- 若导出成功，`.pdf` 文件非空。
- 节点没有明显重叠。
- 箭头不穿过核心节点。
- 字号、颜色、边框风格一致。
- 图内文字与论文同字体（TikZ 天然满足；matplotlib 数据图用 SimHei）。
- 灰度打印可辨（关键信息不能只靠颜色区分）。
- 文件名和图意一致。
- 没有与 `3coding-visual` 的数据图重复。

发现问题要修 `.drawio` 并重新导出，不要只在报告里解释。

### Step 6: 写生成记录

创建 `reports/DRAWIO_REPORT.md`，至少包含：

```markdown
# DrawIO 图示生成报告

## 图示清单
| 文件 | 类型 | 来源依据 | 用途 | 状态 |
| --- | --- | --- | --- | --- |

## 未生成图示及原因

## 导出与自检记录

## 给论文阶段的嵌入建议
```

嵌入建议只说明每张图适合放入哪个章节和建议 caption，不生成 `*_typst_includes.typ`。最终的图表插入代码（Typst 的 `#figure(image(...), caption: [...])` 或 LaTeX 的 `\begin{figure}...\end{figure}`）由 `5writing` 根据论文结构和所选引擎决定。

## 质量要求

- 图示服务论文论证，不为装饰而画。
- 每张图必须能对应到`reports/ANALYSIS_MODELING_REPORT.md` 中的真实方法。
- 数据型图表不得在本阶段重复生成。
- 论文阶段引用的非数据图都应有 `.drawio` 源文件和 PDF，或者在 `reports/DRAWIO_REPORT.md` 说明导出失败。
