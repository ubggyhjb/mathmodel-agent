# fig_q3_effects.R — v4.3（§28 Figure 7）：AFT 主模型协变量效应森林图（R/ggplot2 版）。
# 数据：results/p3_models.json#aft（coef/se/p_value，标准化效应 ± 1.96SE = 95% CI）。
# 语义配色（§26）：BMI（唯一显著、primary）深蓝；其余协变量 comparator 灰阶；0 效应线浅灰虚线。
suppressMessages({
  library(ggplot2)
  library(dplyr)
})
source("R/theme_mathmodel.R", chdir = TRUE)

d <- jsonlite::fromJSON("results/p3_models.json", simplifyVector = FALSE)
aft <- d$aft
coef <- unlist(aft$coef)
se <- unlist(aft$se)
pval <- unlist(aft$p_value)
labs <- c(intercept = "截距", bmi_coef = "BMI", age_coef = "年龄",
          parity_coef = "产次", ivf_coef = "IVF")
lab_cn <- c(bmi_coef = "BMI", age_coef = "年龄", parity_coef = "产次", ivf_coef = "IVF")
rows <- data.frame(
  term = names(coef)[names(coef) %in% names(lab_cn)],
  est = as.numeric(coef[names(coef) %in% names(lab_cn)]),
  se = as.numeric(se[names(se) %in% names(lab_cn)]),
  p = as.numeric(pval[names(pval) %in% names(lab_cn)]),
  stringsAsFactors = FALSE
) %>% mutate(low = est - 1.96 * se, high = est + 1.96 * se,
             label = lab_cn[term], is_primary = term == "bmi_coef",
             sig = p < 0.05,
             text = sprintf("%.4f（%s %.1e）", est, ifelse(sig, "p<", "p="), p)) %>%
  arrange(desc(term))

ggplot(rows, aes(x = est, y = reorder(label, est))) +
  geom_vline(xintercept = 0, colour = PAL$baseline, linetype = "dashed", linewidth = 0.5) +
  geom_errorbarh(aes(xmin = low, xmax = high,
                     colour = ifelse(is_primary, PAL$primary, PAL$comparator)),
                 height = 0.22, linewidth = ifelse(rows$is_primary, 1.0, 0.6)) +
  geom_point(aes(colour = ifelse(is_primary, PAL$primary, PAL$comparator)),
             size = ifelse(rows$is_primary, 2.4, 1.6)) +
  scale_colour_identity() +
  geom_text(aes(x = max(low) - 0.004, label = text), hjust = 1, vjust = -1.2,
            size = 2.0, colour = "#404040") +
  labs(x = "标准化效应 ± 1.96SE（95% CI）", y = NULL,
       title = "AFT 主模型协变量效应（区间删失，n=267）") +
  theme_mathmodel(font_size = 8) +
  theme(legend.position = "none",
        plot.margin = margin(6, 8, 4, 4))

save_figure(last_plot(), "fig_q3_effects", width_mm = 128, height_mm = 62)
