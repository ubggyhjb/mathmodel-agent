# -*- coding: utf-8 -*-
"""gen_golden.py — 重建 benchmarks 目录下的最小 golden projects（G2/G3/G4）。
每个项目可独立跑：methodology_gate / leakage_gate / idea_gate / figure_story --strict（应全部 PASS）。
G1 = 真实 NIPT 项目（README 引用的基线快照），不在本脚本内。
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE = HERE.parent / "skills" / "6verity" / "tests" / "tmp_methodology"


def jw(base: Path, rel: str, obj):
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def base_v2_spec(tws: Path, pid: str, model: dict, feats: dict, mech: dict,
                 figures=("fig1",), outcome=None, lik="none", evidence=("区间删失",)):
    """从 fixture（reports/FINAL_MODEL_SPEC.json）+ 契约字段构造 v2 spec。"""
    spec = json.loads((tws / "reports" / "FINAL_MODEL_SPEC.json").read_text(encoding="utf-8"))
    spec["schema_version"] = 2
    spec["contract_rev"] = int(spec.get("contract_rev", 1)) + 1
    p = dict(spec["problems"][0])
    p["problem_id"] = pid
    p["outcome"] = outcome or {"id": "Y", "type": "continuous", "unit": "unit",
                               "definition": "合成数据输出"}
    p["observation_mechanism"] = mech
    p["model"] = model
    p["features"] = feats
    p["figure_ids"] = list(figures)
    p["result_keys"] = ["results/p0.json#a"]
    p["paper_section"] = "main.tex"
    p["likelihood"] = lik
    p["likelihood_evidence"] = list(evidence)
    p["selection"] = {"model_family": "design_decision", "feature_selection": "none",
                      "hyperparameter_selection": "none"}
    p["uncertainty"] = {"sampling": "se", "model_form": False, "decision_window": False}
    spec["problems"] = [p]
    jw(tws, "reports/FINAL_MODEL_SPEC.json", spec)
    return spec


def add_registry_and_making(tws: Path, pid: str, dist=None, fsid=None, family=None):
    import hashlib
    spec_hash = hashlib.sha256((tws / "reports" / "FINAL_MODEL_SPEC.json").read_bytes()).hexdigest()
    jw(tws, "reports/variables.json",
       {"bmi": {"storage_unit": "kg_m2", "availability": "available"},
        "z21": {"storage_unit": "z_score", "availability": "available"},
        "y_fraction": {"storage_unit": "fraction", "availability": "unavailable"}})
    (tws / "results").mkdir(exist_ok=True)
    def _meta():
        m = {"problem_id": pid, "role": "paper_authority",
             "model_spec_sha256": spec_hash, "contract_rev": 2,
             "model_family": family, "model_distribution": dist, "feature_set_id": fsid}
        return {"_meta": m, "a": 1}
    jw(tws, "results/p0.json", _meta())
    jw(tws, "results/RESULT_REGISTRY.json",
       {"artifacts": [{"file": "results/p0.json", "role": "paper_authority",
                       "problem_id": pid, "requires_model_spec_binding": True}]})


def add_ideas(tws: Path, pid: str, censoring=True, primary="gold-I02"):
    cands = [
        {"idea_id": "gold-I01", "question_id": pid, "method_family": "baseline_method",
         "tier": "minimal_sufficient_solution", "core_hypothesis": h1,
         "why_applicable": "", "required_variables": [], "required_assumptions": ["a"],
         "data_risks": [], "strengths": [], "weaknesses": [], "validation_plan": [],
         "failure_conditions": ["f"], "complexity": "low", "interpretability": "high",
         "status": "candidate"},
        {"idea_id": "gold-I02", "question_id": pid, "method_family": family2,
         "tier": "recommended_solution", "core_hypothesis": h2, "why_applicable": "",
         "required_variables": ["bmi"], "required_assumptions": ["a"],
         "data_risks": [], "strengths": [], "weaknesses": [], "validation_plan": [],
         "failure_conditions": ["f"], "complexity": "medium", "interpretability": "high",
         "status": "candidate"},
    ]
    if censoring and primary in ("gold-I01",):
        cands[0]["method_family"] = "exact_event_ols"  # 专供 T109 trap 使用
    jw(tws, "reports/contracts/QUESTION_CONTRACT.json",
       {"questions": [{"question_id": pid,
                       "special_data_structure": ["interval_censoring", "left_censoring",
                                                  "right_censoring"] if censoring else ["repeated_measurement"],
                       "decision_target": "x", "analysis_unit": "unit",
                       "observation_unit": "record", "required_outputs": [], "allowed_information": [],
                       "forbidden_information": [], "evaluation_target": []}]})
    jw(tws, "reports/contracts/IDEA_CANDIDATES.json", {"candidates": cands})
    jw(tws, "reports/contracts/IDEA_DECISION.json",
       {"primary": {pid: primary}, "accepted": [c["idea_id"] for c in cands],
        "baseline": ["gold-I01"], "backup": [], "exploratory": [],
        "rejected": ["gold-I99"], "unresolved_questions": [],
        "rejection_reasons": {"gold-I99": "DGP 不兼容"}})


h1 = "简单基线可回答题目"
h2 = "推荐方法具备可解释性"
family2 = "recommended_family"


def build_g2(tws: Path):
    """类别不平衡分类 golden（参考模型：逻辑回归 uncalibrated score + 嵌套阈值）。"""
    spec = base_v2_spec(
        tws, "Q2", 
        model={"family": "logistic_regression", "distribution": None, "role": "primary_decision"},
        feats={"feature_set_id": "G2.LR.v1", "included": [{"id": "z21", "role": "dosage"}],
               "excluded": [{"id": "y_fraction", "reason": "unavailable"}]},
        mech={"left_censoring": False, "interval_censoring": False, "right_censoring": False},
        outcome={"id": "label", "type": "binary", "unit": "label", "definition": "合成不平衡标签"},
        lik="none", evidence=("逻辑回归", "嵌套交叉验证"),
    )
    # prediction_output 契约（§8：uncalibrated score 禁用概率词）——必须在绑定（registry/meta）之前
    spec["problems"][0]["prediction_output"] = {"type": "uncalibrated_score",
                                                "source": "logistic_regression_raw_output",
                                                "probability_interpretation_allowed": False,
                                                "calibration": "none"}
    jw(tws, "reports/FINAL_MODEL_SPEC.json", spec)
    add_registry_and_making(tws, "Q2", family="logistic_regression", fsid="G2.LR.v1")
    add_ideas(tws, "Q2", censoring=False, primary="gold-I02")
    (tws / "paper" / "main.tex").write_text(
        "采用逻辑回归并按孕妇分组做嵌套交叉验证。\n", encoding="utf-8")


def build_g3(tws: Path):
    """时间序列预测 golden（参考模型：ARIMA Box-Jenkins）。"""
    spec = base_v2_spec(
        tws, "Q4",
        model={"family": "arima", "distribution": None, "role": "primary_decision"},
        feats={"feature_set_id": "G3.ARIMA.v1", "included": [{"id": "bmi", "role": "covariate"}],
               "excluded": []},
        mech={"left_censoring": False, "interval_censoring": False, "right_censoring": False},
        outcome={"id": "y_t", "type": "continuous", "unit": "unit", "definition": "合成时间序列"},
        lik="none", evidence=("时间序列", "ARIMA"),
    )
    add_registry_and_making(tws, "Q4", family="arima", fsid="G3.ARIMA.v1")
    add_ideas(tws, "Q4", censoring=False, primary="gold-I02")
    (tws / "paper" / "main.tex").write_text(
        "采用 Box-Jenkins 流程识别 ARIMA 阶数并做滚动预测。\n", encoding="utf-8")


def build_g4(tws: Path):
    """区间删失 + 约束优化决策 golden（参考模型：Turnbull + interval-censored AFT）。"""
    spec = base_v2_spec(
        tws, "Q3",
        model={"family": "aft", "distribution": "lognormal", "role": "primary_decision"},
        feats={"feature_set_id": "G4.AFT.v1", "included": [{"id": "bmi", "role": "covariate"}],
               "excluded": []},
        mech={"left_censoring": True, "interval_censoring": True, "right_censoring": True},
        outcome={"id": "T", "type": "time_to_event", "unit": "week", "definition": "达标时间（合成）"},
        lik="interval", evidence=("区间删失", "Turnbull", "interval-censored"),
    )
    spec["problems"][0]["uncertainty"] = {"sampling": "cluster_bootstrap", "model_form": True,
                                          "decision_window": True}
    jw(tws, "reports/FINAL_MODEL_SPEC.json", spec)
    add_registry_and_making(tws, "Q3", dist="lognormal", family="aft", fsid="G4.AFT.v1")
    add_ideas(tws, "Q3", censoring=True, primary="gold-I02")
    (tws / "paper" / "main.tex").write_text(
        "达标时间按左删失、区间删失与右删失观测（left-censored / interval-censored / "
        "right-censored），候选模型为 Turnbull 与 interval-censored AFT。\n",
        encoding="utf-8")


def main():
    for name, fn in (("ws_G2", build_g2), ("ws_G3", build_g3), ("ws_G4", build_g4)):
        dst = HERE / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(FIXTURE, dst)
        fn(dst)
        print("built", name)
    print("DONE（G2/G3/G4 golden projects 已重建）")


if __name__ == "__main__":
    main()
