#!/usr/bin/env python3
"""结果自证模板（跨平台，Windows/Linux 通用）。

用法：复制本模板为 code/verify_all.py，按项目实际情况填写 SANITY 规则后运行：
    python code/verify_all.py

原则（强制自证）：
  1. 所有求解脚本的产物必须经过本脚本验证，全部 PASS 才能写入 RESULTS_REPORT.md。
  2. 任何一个 FAIL 都必须回到求解代码修复，禁止带着 FAIL 写论文。
  3. 验证覆盖六类硬伤：NaN/Inf、数据串台、越界、缺失率、统计异常、关键一致性。

此模板自带五条"通用断言" + 一条 WARN，拦截同类项目历史上出现过的错误：
  - NAN_GUARD：结果里出现 NaN/Inf 直接 FAIL（拦"交叉验证 NaN 被隐瞒"）
  - UNIQUE_GUARD：同一运动员/样本的行不能完全相同（拦"数据串台"）
  - RANGE_GUARD：关键数值必须在声明的合理区间内（拦"异常值进模型"，物理边界）
  - MISSING_GUARD：单字段缺失率超上限 FAIL（拦"缺失数据静默进模型"）
  - OUTLIER_GUARD：IQR 统计异常 WARN——先解释后处理，剔除留证进 decision_log（拦"异常静默剔除"）
"""
import json
import sys
from pathlib import Path

# ============ 按项目实际情况填写 ============
# 结果 JSON 文件列表（相对 code/ 目录）
RESULT_FILES = [
    "../results/problem1_summary.json",
    "../results/problem2_results.json",
    "../results/problem3_results.json",
    "../results/problem4_results.json",
]
# 每个运动员/样本的唯一标识字段（按实际 JSON 结构改）
ID_FIELD = "athlete_id"
# 判重时忽略的元数据字段：串台事故中 id/condition 往往不同，只有特征列相同
EXCLUDE_FIELDS = ["athlete_id", "athlete", "name", "condition", "file", "source"]
# 数值越界检查：字段名 -> (最小合理值, 最大合理值)。按题目领域填写。
# 示例为立定跳远 E 题的量级；换题必须改。
RANGE_RULES = {
    "dx_pixel": (0.0, 3000.0),       # 水平位移像素，必须非负且量级合理
    "distance": (0.5, 3.0),          # 跳远成绩（米）
    "airborne_time": (0.1, 2.0),     # 滞空时间（秒）
}
# 跨文件一致性守卫：同一 ID 在多个结果文件中这些字段必须一致
CROSS_FIELDS = ["airborne_time", "dx_pixel", "distance"]
# 跨文件允许的相对差异容差（0.01 = 1%）
CROSS_TOL = 0.01
# 缺失率守卫：单字段缺失比例上限（None/空串/NaN 计缺失；超限 FAIL——插值补齐或剔除字段并在论文声明）
MISSING_RATE_MAX = 0.20
# 统计异常守卫（IQR 1.5 倍）：命中者输出 WARN 不自动 FAIL——异常值必须"先解释后处理"，
# 剔除一律留证（样本 ID + 理由进 decision_log）并在论文声明。硬边界仍由 RANGE_RULES 判 FAIL。
OUTLIER_FIELDS = ["distance", "airborne_time", "dx_pixel"]
# ============================================

def walk(obj, path=""):
    """递归遍历 JSON，产出 (路径, 数值) 对。"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, f"{path}[{i}]")
    else:
        yield path, obj


def main():
    fails = []
    rows = []
    for rel in RESULT_FILES:
        p = Path(__file__).parent / rel
        if not p.exists():
            print(f"[FAIL] 结果文件不存在: {rel}")
            fails.append(rel)
            continue
        data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        # 收集运动员级别的行（列表或字典里的记录）
        if isinstance(data, dict):
            for key in ("athletes", "records", "rows", "results"):
                if isinstance(data.get(key), list):
                    for item in data[key]:
                        if isinstance(item, dict):
                            rows.append((rel, item))
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    rows.append((rel, item))

        # 1) NaN/Inf 守卫
        for path, value in walk(data):
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                import math
                if math.isnan(value) or math.isinf(value):
                    print(f"[FAIL] {rel}: 字段 {path} 是 NaN/Inf —— 禁止带着无效值写论文")
                    fails.append(f"{rel}:{path}")

        # 2) 越界守卫
        for path, value in walk(data):
            for field, (lo, hi) in RANGE_RULES.items():
                if path.endswith(f".{field}") and isinstance(value, (int, float)):
                    if not (lo <= value <= hi):
                        print(f"[FAIL] {rel}: {path}={value} 超出合理区间 [{lo}, {hi}]")
                        fails.append(f"{rel}:{path}")

    # 3) 数据串台守卫：同一文件中出现特征完全相同的两行（忽略 id/condition 等元数据）
    #    真正的串台事故：A3-after 的特征行 == A1-before 的特征行（文件映射错误）→ 必须 FAIL
    seen_sigs = {}
    for rel, row in rows:
        features = {k: v for k, v in row.items() if k not in EXCLUDE_FIELDS}
        if not features:
            continue
        sig = json.dumps(features, sort_keys=True, ensure_ascii=False, default=str)
        key = rel
        if key in seen_sigs and sig in seen_sigs[key]:
            ident = row.get(ID_FIELD)
            print(f"[FAIL] {rel}: 出现特征完全相同的两行（其一为 {ID_FIELD}={ident}）—— 疑似数据串台/文件映射错误")
            fails.append(f"dup:{rel}:{ident}")
        seen_sigs.setdefault(key, set()).add(sig)

    # 4) 跨文件同实体一致性守卫：同一标识（运动员/样本）在不同结果文件中的
    #    核心数值必须一致（或给出允许差异容差）。历史教训：同一运动员在两个
    #    模块里用不同参数（如速度窗口 window=3 vs window=5）算出两套运动学值，
    #    两个 JSON 互相打脸。此守卫按 CROSS_FIELDS 逐字段比对，差异超 CROSS_TOL 即 FAIL。
    cross = {}
    for rel, row in rows:
        ident = row.get(ID_FIELD)
        if ident is None:
            continue
        key = (ident,)
        entry = cross.setdefault(key, {})
        for field in CROSS_FIELDS:
            v = row.get(field)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                if field in entry:
                    prev_rel, prev_v = entry[field]
                    tol = CROSS_TOL * max(abs(prev_v), abs(v), 1e-9)
                    if abs(prev_v - v) > tol:
                        print(f"[FAIL] 跨文件不一致: {ID_FIELD}={ident} 的 {field} 在 {prev_rel}={prev_v} 与 {rel}={v} 差异超容差 —— 检查各模块参数口径是否统一")
                        fails.append(f"cross:{ident}:{field}")
                else:
                    entry[field] = (rel, v)

    # 5) 缺失率守卫：单字段缺失比例超限 FAIL（要么补、要么剔字段并在论文声明）
    if len(rows) >= 5:
        from collections import Counter
        miss, total = Counter(), Counter()
        for _rel, row in rows:
            for k, v in row.items():
                total[k] += 1
                if v is None or v == "" or (isinstance(v, float) and v != v):
                    miss[k] += 1
        for k in total:
            rate = miss[k] / total[k]
            if rate > MISSING_RATE_MAX:
                print(f"[FAIL] 字段 {k} 缺失率 {rate:.0%} 超过上限 {MISSING_RATE_MAX:.0%} —— 插值补齐或剔除该字段并在论文声明")
                fails.append(f"missing:{k}")

    # 6) 统计异常守卫（IQR 1.5 倍）：WARN 不 FAIL——异常值必须"先解释后处理"，
    #    剔除一律留证（样本 ID+理由进 decision_log），论文显式声明。
    for field in OUTLIER_FIELDS:
        vals = []
        for _rel, row in rows:
            v = row.get(field)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                vals.append((row.get(ID_FIELD), float(v)))
        if len(vals) < 8:
            continue
        xs = sorted(x for _, x in vals)
        q1 = xs[len(xs) // 4]
        q3 = xs[(3 * len(xs)) // 4]
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        for ident, x in vals:
            if x < lo or x > hi:
                print(f"[WARN] {ID_FIELD}={ident} 的 {field}={x} 超出 IQR 区间 [{lo:.2f}, {hi:.2f}] —— 先解释后处理；剔除必须留证进 decision_log 并在论文声明")

    if fails:
        print(f"\n共 {len(fails)} 项 FAIL —— 必须回到求解代码修复后才能继续。")
        return 1
    print("全部 PASS —— 结果自证通过，可写入 RESULTS_REPORT.md。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
