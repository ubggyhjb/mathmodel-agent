# figure_manifest.json — v4 Figure 清单（唯一事实源）

> 位置：`figures/figure_manifest.json`（**唯一**）。v3 的 `reports/figure_story_manifest.json`
> 与写作期的旧 `figures/figure_manifest.json` 双清单就此合并；`figure_story.py` 只读本文件
> （发现旧路径文件时 WARN 提示迁移，最终删除旧清单）。

## schema（数组，每张正式图一条）

```json
{
  "id": "fig_v3_f2_interval",
  "story": {
    "main_message": "G2/G3 推荐时点依赖区间删失口径，与插值对照差 1.8 周",
    "audience_takeaway": "用区间删失而非插值恢复时间",
    "unique_information": "四组删失分布 + 推荐窗口 + 与旧插值口径差异"
  },
  "visual_priority": "primary",
  "files": ["figures/fig_v3_f2_interval.pdf"],
  "source": {
    "generator": "code/make_figures_v3.py",
    "generator_sha256": "<code 文件哈希>",
    "source_results": [
      {"file": "results/p2_ic.json", "sha256": "<results 哈希>",
       "keys": ["G2.recommended.low", "G2.recommended.high"]}
    ]
  },
  "panels": [
    {
      "id": "A",
      "title": "四组达标时间删失分布",
      "expected_marks": ["bar:km", "vline:recommended_low", "vline:recommended_high"],
      "min_artist_count": 3,
      "x_unit": "week",
      "y_unit": "probability",
      "source_keys": ["G2.recommended.low"]
    }
  ],
  "annotations": [
    {"label": "G2 推荐区间", "value_key": "G2.recommended.low"}
  ],
  "caption": "图 2 四组达标时间（区间删失口径）与推荐窗口",
  "paper_ref": "sections/6_problem2.tex",
  "redundant_with": [],
  "supersedes": ["fig_q2_km"],
  "keep_both_reason": "",
  "status": "approved"
}
```

## 字段说明

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 与 figures/<id>.pdf、论文 label 对齐 |
| `story.main_message` / `audience_takeaway` / `unique_information` | 是 | 先回答"这张图证明什么"再画 |
| `visual_priority` | 是 | primary（正文核心 ≤5-6 张）/ secondary / appendix |
| `files` | 是 | 相对项目根的图文件（文件名匹配正文 includegraphics） |
| `source.generator` / `generator_sha256` / `source_results[{file,sha256,keys}]` | 建议 | provenance：图由哪个代码文件、哪些结果 JSON 的哪些 key 生成 |
| `panels[]` | 建议 | `expected_marks`（期望 artist 类型）、`min_artist_count`（下限，缺失→panel integrity FAIL）、`x_unit`/`y_unit`（unit audit 用）、`source_keys` |
| `annotations[]` | 建议 | 图内标注与结果 key 的绑定（annotation-key trace：key 必须在 source_results 中存在） |
| `caption` | 建议 | **论文 caption 必须与它一致**（figure_story 门比对 caption，不一致 FAIL——禁止"图由代码定义 panel、caption 再手写一次"） |
| `paper_ref` | 建议 | 引用该图的论文章节 |
| `redundant_with` | 建议 | 冗余声明；**双方都出现在正文且无 `keep_both_reason` → FAIL** |
| `supersedes` | 建议 | 本图取代的旧图 id；**旧图仍在正文 → FAIL** |
| `keep_both_reason` | 条件 | 保留冗余图时必须说明各自独有信息 |
| `status` | 建议 | approved/draft |

## 伴随文件 `figures/<id>.meta.json`（v4 强制）

每张正式图生成时由 FigureBuilder 写：

```json
{
  "figure_id": "fig_v3_f2_interval",
  "generator": "code/make_figures_v3.py",
  "generator_sha256": "...",
  "generated_at": "...",
  "source_results": [{"file": "results/p2_ic.json", "sha256": "...", "keys": [...]}],
  "source_hash": "<sha256(source_results 内容)>",
  "panels": {"A": {"line_count": 3, "scatter_count": 0, "patch_count": 2,
                    "text_count": 5, "collection_count": 0}},
  "annotations": [{"label": "...", "value_key": "G2.recommended.low", "value": "15.0"}],
  "axes": [{"ylabel": "Y浓度 (%)", "variable": "Y_fraction", "display": "percent", "raw_range": [0.0, 0.16]}]
}
```

门禁行为：meta.json 缺失 → WARN（v4 建议强制，P5 起新图必带）；
meta.json 存在但 panel artist 计数 < min_artist_count → FAIL（空 panel 直接拦截）；
annotations value_key 不在 source_results 中 → FAIL；axes 的 variable/display 与
`reports/variables.json`（unit registry）声明不一致 → FAIL。
