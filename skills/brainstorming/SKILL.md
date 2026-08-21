---
name: brainstorming
description: "数学建模头脑风暴兼容入口（与 brainstorm-mathmodel 同义）：在读题后、详细建模前，发散生成多套候选建模路线，评估可行性、区分度与风险，并输出 BRAINSTORM_REPORT.md。"
whenToUse: "当用户要求“头脑风暴 / brainstorming”，或需要为数学建模赛题生成候选建模思路时使用。实际工作流请以 `brainstorm-mathmodel` 阶段为准。"
allowed-tools: pwsh, read, write, edit, grep, glob, subagent, web_search, ask_user_question
---

# 数学建模头脑风暴（兼容入口）

本 skill 是 `brainstorm-mathmodel` 的兼容别名入口，避免名称不确定时找不到头脑风暴能力。

实际执行时请加载并遵循：

- `../brainstorm-mathmodel/SKILL.md`

流程、产出与纪律完全一致：

- 每个子问题至少 3 条候选路线；
- 覆盖主流解、改进解、交叉/创新解、反直觉/压力测试解；
- 评估数据可得性、可实现性、区分度与风险；
- 输出 `reports/BRAINSTORM_REPORT.md`；
- 在 `state/decision_log.json` 记录主选/备选/淘汰理由（stage=`brainstorm-mathmodel`）。
