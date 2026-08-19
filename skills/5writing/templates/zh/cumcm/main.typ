#let body-font = ("Times New Roman", "SimSun", "NSimSun", "Songti SC", "STSong")
#let song-font = ("SimSun", "NSimSun", "Songti SC", "STSong", "Times New Roman")
#let hei-font = ("SimHei", "Heiti SC", "STHeiti", "STSong")
#let kai-font = ("KaiTi", "Kaiti SC", "STKaiti", "SimSun", "Songti SC")

#let cn-numbering(..nums) = {
  let ns = nums.pos()
  if ns.len() == 1 {
    numbering("一、", ns.at(0))
  } else if ns.len() == 2 {
    numbering("1.1", ns.at(0), ns.at(1))
  } else {
    numbering("1.1.1", ns.at(0), ns.at(1), ns.at(2))
  }
}

#set document(title: "[论文标题]", author: ())
#set page(
  paper: "a4",
  margin: (top: 2.8cm, bottom: 2.8cm, left: 3cm, right: 3cm),
  numbering: "1",
)
#set text(font: body-font, size: 12.05pt, lang: "zh")
#set par(
  first-line-indent: (amount: 2em, all: true),
  justify: true,
  leading: 0.45em,
  spacing: 0.35em,
)
#set heading(numbering: cn-numbering)
#set enum(numbering: "1.")
#set table(inset: 0.45em)
#show heading.where(level: 1): set align(center)
#show heading.where(level: 1): set text(size: 17.3pt, weight: "bold")
#show heading.where(level: 1): set block(above: 1.25em, below: 0.82em)
#show heading.where(level: 2): set text(size: 14.45pt, weight: "bold")
#show heading.where(level: 2): set block(above: 1.15em, below: 0.55em)
#show heading.where(level: 3): set text(size: 12.05pt, weight: "bold")
#show heading.where(level: 3): set block(above: 1.15em, below: 0.55em)
#show figure.caption: it => text(size: 10.5pt, weight: "bold")[#it]
#show raw: set text(size: 10pt, font: ("Courier New", "Menlo", "SimSun", "Songti SC"))
#show raw.where(block: true): set block(
  fill: luma(97%),
  stroke: 0.8pt + luma(70%),
  inset: 0.7em,
  above: 0.7em,
  below: 0.7em,
)

#let song = (body) => text(font: song-font, body)
#let hei = (body) => text(font: hei-font, weight: "bold", body)
#let kai = (body) => text(font: kai-font, body)
#let paper-title(body) = {
  align(center)[#text(size: 17.3pt, weight: "bold")[#body]]
  v(1em)
}
#let abstract-title() = align(center)[#text(size: 14pt, weight: "bold")[摘要]]
#let keywords-cn(body) = block(above: 1em)[
  #text(font: hei-font, size: 12pt, weight: "bold")[关键字：] #body
]
#let abstract-cn(body, keywords) = {
  abstract-title()
  block(above: 0.15em)[#body]
  keywords-cn(keywords)
  pagebreak()
}
// 2026 格式规范：不要目录 → 本模板无目录页

// 内容性加粗（官方展示论文通行做法）：优先级 = 结论句 > 模型/方法名 > 引导语 > 关键数值
// （全库统计：结论句 78 > 数值 51 > 术语 40 > 引导语 9）。关键数值包进结论短语整体加粗（#kw([仅到达 27 个端点])），
// 禁止裸数字逐个加粗（#kw([15.88])、#kw([12.17]) 一串 = 等于没加粗）；摘要 5-15%，正文关键结论句 1-4%。
#let kw(body) = text(weight: "bold", body)

// 三线表函数（先定义，供下方 support-files-cn 调用；Typst 要求先定义后使用）
#let threeline_table(caption, columns, header, body, inset: (x: 0.35em, y: 0.52em), cell-align: center) = {
  let col-count = header.len()
  let body-rows = calc.floor(body.len() / col-count)
  let bottom-y = body-rows + 1
  let styled-header = header.map(cell => strong(cell))

  block(width: 100%, breakable: false)[
    #align(center)[
      #box[
        #align(center)[#text(font: hei-font, size: 10.5pt, weight: "bold")[#caption]]
        #v(0.6em)
        #table(
          columns: columns,
          align: cell-align,
          stroke: none,
          inset: inset,
          table.hline(y: 0, stroke: 0.8pt),
          table.hline(y: 1, stroke: 0.5pt),
          table.hline(y: bottom-y, stroke: 0.8pt),
          ..styled-header,
          ..body,
        )
      ]
    ]
  ]
}

#let references-cn() = [
#heading(numbering: none, outlined: false)[参考文献]
#{ set par(first-line-indent: 0pt, spacing: 0.35em); include("references.typ") }
]
#let support-files-cn() = [
#heading(numbering: none, outlined: false)[附录 A #h(1em) 支撑材料文件列表]
支撑材料已按《全国大学生数学建模竞赛论文格式规范（2026 年修订稿）》压缩为单个 ZIP 文件，内容如下：
#threeline_table([支撑材料文件列表], (auto, auto, auto), ([序号], [文件], [说明]), ("1", [code/\*.py], [全部可运行源程序（问题一至问题四）], "2", [results/\*.json], [全部结果数据], "3", [figures/\*.pdf], [论文图表矢量源文件], "4", [data_sources.md / external_data.json], [自主查阅使用的数据资料（赛题原始数据除外）], "5", [AI工具使用详情.pdf], [AI 工具使用详情说明（官方规定文件名）]))
]
#let appendix-cn(file: "sections/A_code.typ") = [
#heading(numbering: none, outlined: false)[附录 B #h(1em) 源程序代码]
#include(file)
]
#let ai-decl-not-used() = [
#heading(numbering: none, outlined: false)[AI 工具使用声明]
本参赛队在竞赛过程中未使用任何 AI 工具。
]
#let ai-decl-used(usage) = [
#heading(numbering: none, outlined: false)[AI 工具使用声明]
本参赛队在竞赛过程中使用了 AI 工具，主要用于 #usage，详细使用情况见支撑材料。
]

#counter(page).update(1)

#paper-title[[论文标题]]

#abstract-cn[
  [中文摘要内容：问题概述 + 每个子问题的方法和数值结果 + 结论（关键数值包进结论短语加粗，如 #kw([仅到达 27 个端点，水流止于局部盆地])）]
][
  [关键词1] #h(1em) [关键词2] #h(1em) [关键词3]
]

#include("sections/1_restatement.typ")
#include("sections/2_analysis.typ")
#include("sections/3_assumptions.typ")
#include("sections/4_symbols.typ")
#include("sections/5_problem1.typ")
#include("sections/6_problem2.typ")
#include("sections/7_problem3.typ")
#include("sections/8_sensitivity.typ")
#include("sections/9_evaluation.typ")

#pagebreak()
#ai-decl-used([语言润色、代码调试与图表绘制等])
#pagebreak()
#references-cn()
#pagebreak()
#support-files-cn()
#appendix-cn()
