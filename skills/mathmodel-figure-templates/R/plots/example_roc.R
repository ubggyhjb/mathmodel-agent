# fig_q4_roc.R — v4.3（§28 图 9）：各模型 ROC 曲线（R/ggplot2 版）。
# 数据：results/p4_curves.json#pooled.<model>.roc（测试折拼接口径）。
# 语义层级（§26）：primary=LR 深蓝粗线；benchmarks（RF/GBDT）=灰阶细线；
# 单 Z 阈值基线=浅灰；随机基线=浅灰虚线；direct labeling 消解 legend 负担。
suppressMessages({
  library(ggplot2)
  library(dplyr)
})
source("R/theme_mathmodel.R", chdir = TRUE)

d <- jsonlite::fromJSON("results/p4_curves.json", simplifyVector = FALSE)
pooled <- d$pooled
mk <- function(name) {
  c <- pooled[[name]]
  data.frame(model = name, fpr = unlist(c$roc$fpr), tpr = unlist(c$roc$tpr),
             auc = c$auc, stringsAsFactors = FALSE)
}
lines <- bind_rows(lapply(c("lr_full", "rf", "gbdt", "z_base"), mk))
spec <- data.frame(
  model = c("lr_full", "rf", "gbdt", "z_base"),
  label = c("主模型 LR", "RF", "GBDT", "单 Z 阈值"),
  colour = c(PAL$primary, PAL$comparator, PAL$comparator2, PAL$light),
  lw = c(1.4, 0.7, 0.7, 0.7), stringsAsFactors = FALSE
)
lines <- left_join(lines, spec, by = "model") %>%
  mutate(label = sprintf("%s（AUC=%.3f）", label, as.numeric(auc)))
lines$label <- factor(lines$label, levels = unique(lines$label))

p <- ggplot(lines, aes(x = fpr, y = tpr, group = model))
# 随机基线
p <- p + geom_abline(intercept = 0, slope = 1, colour = PAL$baseline,
                     linetype = "dashed", linewidth = 0.5)
for (m in c("z_base", "gbdt", "rf", "lr_full")) {
  sub <- lines[lines$model == m, ]
  if (nrow(sub) == 0) next
  p <- p + geom_line(data = sub, colour = unique(sub$colour),
                     linewidth = unique(sub$lw))
}
p <- p +
  scale_colour_identity() +
  labs(x = "FPR（假阳性率）", y = "TPR（真阳性率）",
       title = "ROC 曲线（测试折拼接口径）") +
  theme_mathmodel(font_size = 8) +
  theme(legend.position = "right", legend.key.size = unit(2.8, "mm"))
# direct labeling：曲线末端标注模型名 + AUC（ggrepel 防重叠）
ends <- lines %>% group_by(model) %>% slice(n()) %>% ungroup()
p <- p + ggrepel::geom_text_repel(
    data = ends, aes(x = fpr, y = tpr, label = label),
    size = 1.9, colour = ends$colour, show.legend = FALSE,
    nudge_x = 0.05, direction = "y", seed = 42,
    min.segment.length = 0, segment.size = 0.2) +
  coord_cartesian(xlim = c(0, 1.02), ylim = c(0, 1.02), clip = "off") +
  theme(plot.margin = margin(6, 20, 4, 4))

save_figure(last_plot(), "fig_q4_roc", width_mm = 120, height_mm = 78)
