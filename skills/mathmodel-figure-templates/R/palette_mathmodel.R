# palette_mathmodel.R — v4.3 语义层级配色（§26：primary 深蓝 / comparators 灰阶 /
# baseline 浅灰虚线 / alert 橙红；颜色表示角色/语义，不是类别索引；跨图同实体同色）
PAL <- list(
  primary   = "#1f4e79",   # 主模型/主证据
  comparator= "#8c8c8c",   # 对照模型（灰阶）
  comparator2= "#a5a5a5",  # 次级对照
  baseline  = "#bfbfbf",   # 基线 / 随机线
  light     = "#d9d9d9",   # 背景/参考
  alert     = "#e64b35",   # 风险 / 告警
  accent    = "#2a9d8f"    # 次要强调
)
