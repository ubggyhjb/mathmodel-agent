# theme_mathmodel.R — v4.3 论文统计图主题（posting 级：8pt 字号、去顶右 spine、
# 浅网格、字体内置逻辑=中文字体经 systemfonts 探测、绝不绑定本机字体绝对路径）
source("palette_mathmodel.R")  # 经调用方 chdir=TRUE（本文件所在 R/ 目录）解析

theme_mathmodel <- function(font_size = 8) {
  theme_bw(base_size = font_size) +
    theme(
      panel.grid.minor = element_blank(),
      panel.grid.major = element_line(linewidth = 0.25, colour = "#e6e6e6"),
      panel.border = element_blank(),
      axis.line = element_line(colour = "black", linewidth = 0.35, lineend = "square"),
      axis.ticks = element_line(colour = "black", linewidth = 0.35),
      legend.position = "right",
      legend.key.size = unit(3.2, "mm"),
      legend.text = element_text(size = font_size - 0.5),
      legend.title = element_blank(),
      axis.text = element_text(size = font_size - 0.5),
      axis.title = element_text(size = font_size, margin = margin(t = 2, r = 2)),
      plot.title = element_text(size = font_size, hjust = 0.5, face = "bold"),
      strip.background = element_blank(),
      strip.text = element_text(size = font_size, face = "bold"),
      text = element_text(family = cjk_family())
    )
}

# cjk_family：中文字体动态探测（禁止绝对路径；systemfonts 按字体名匹配）
cjk_family <- function() {
  if (requireNamespace("systemfonts", quietly = TRUE)) {
    fams <- systemfonts::system_fonts()
    for (f in c("Microsoft YaHei", "SimHei", "Source Han Sans SC", "Noto Sans CJK SC")) {
      if (any(grepl(f, fams$family, fixed = TRUE))) {
        return(f)
      }
    }
  }
  ""  # 无匹配则回退默认
}

# 中文渲染：showtext 接管（cairo 设备 + 系统字体名），避免 invalid font type
if (requireNamespace("showtext", quietly = TRUE)) {
  showtext::showtext_auto()
  showtext::showtext_opts(dpi = 300)
}

save_figure <- function(p, stem, dir = "figures", width_mm = 170, height_mm = 90,
                        ppi = 300) {
  # 输出：矢量 PDF（论文）+ PNG 300dpi（preview）；final-width 约束：
  # 170mm=正文通栏 / 84mm=双栏；字号 8pt（对应正文 12pt）
  dir.create(dir, showWarnings = FALSE)
  ggsave(file.path(dir, paste0(stem, ".pdf")), p,
         width = width_mm / 25.4, height = height_mm / 25.4, units = "in",
         device = cairo_pdf, antialias = "default")
  ggsave(file.path(dir, paste0(stem, ".png")), p,
         width = width_mm / 25.4, height = height_mm / 25.4, units = "in", dpi = ppi)
  cat("[save] figures/", stem, ".pdf/.png\n", sep = "")
}
