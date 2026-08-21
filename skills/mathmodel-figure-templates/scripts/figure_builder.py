#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""figure_builder.py — v4 统一 FigureBuilder（任务书 三十四、三十五条）。

职责：
  * source keys：结果 JSON（results/*.json）的取值与 key 绑定；
  * unit transform：按 reports/variables.json 注册表做单位变换（fraction -> percent 等），
    禁止绘图代码自己写 ylabel 却忘乘 100；
  * panel metadata：每个 panel 记录 expected_marks / min_artist_count / source_keys；
  * artists：保存时统计 line/scatter/patch/text/collection 计数（panel integrity 输入）；
  * annotations：图内标注记录 label/value_key/raw/value（annotation-key trace 输入）；
  * journal style：直接调用 mpl_paper_style 的五色/despine/direct_label；
  * output：保存 PDF（+PNG 可选）并写 figures/<id>.meta.json（provenance + 计数 + 哈希）。

典型用法（在 3coding-visual 阶段）：
    from figure_builder import FigureBuilder
    fb = FigureBuilder("fig_v3_f2_interval", manifest_item, ws, results_dir="results")
    fig, axs = fb.figure(1, 2, figsize=(9, 3.5))
    ...
    fb.save(fig, {"x_unit": "week", "y_unit": "probability"}, out="figures")

manifest_item 字段（docs/figure_manifest.schema.md）：
  id / story.main_message / source.generator / source_results[{file,keys}] /
  panels[{id, source_keys, min_artist_count}] / annotations[{label,value_key}]

variables.json 字段（unit registry）：
  {var: {"storage_unit","storage_range","display": {disp: {"transform","unit","threshold_raw","threshold_display"}}}}
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from mpl_paper_style import palette, despine, primary_line, secondary_line, direct_label  # noqa: F401


def _find(doc, key):
    cur = doc
    for part in str(key).split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit():
            cur = cur[int(part)]
        else:
            return None
    return cur


def transform_value(value, var_entry, display):
    """按 registry 的 display.transform 做单位变换（支持 *100 / /100 / *1 等）。"""
    d = (var_entry or {}).get("display", {}).get(display) if isinstance(var_entry, dict) else None
    if not d or value is None:
        return value
    tf = str(d.get("transform", "1"))
    try:
        if tf.startswith("*"):
            return value * float(tf[1:])
        if tf.startswith("/"):
            return value / float(tf[1:])
    except (TypeError, ValueError):
        return value
    return value


class FigureBuilder:
    def __init__(self, figure_id: str, manifest_item: dict, ws: Path,
                 results_dir: str = "results", registry_rel: str = "reports/variables.json"):
        self.figure_id = figure_id
        self.manifest = manifest_item or {}
        self.ws = Path(ws).resolve()
        self.results_dir = Path(self.ws) / results_dir
        self.registry = self._load_json(self.ws / registry_rel) or {}
        self._models = {}      # rel_path -> doc
        self._source_hash = hashlib.sha256(b"").hexdigest()
        self.panel_meta = {}   # panel_id -> artist counts
        self.anno_meta = []    # annotation records
        self.axes_meta = []

    # ---------- 加载 ----------

    def _load_json(self, path: Path):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def value(self, key: str):
        """从 source_results 声明的 JSON 中点分路径取值（key 不存在 -> None，禁止编造）。"""
        for src in self.manifest.get("source_results", []) or []:
            rel = str(src.get("file", "")).strip().lstrip("/\\")
            if not rel:
                continue
            doc = self._models.get(rel)
            if doc is None:
                doc = self._load_json(self.results_dir / rel) or {}
                self._models[rel] = doc
            v = _find(doc, key)
            if v is not None:
                return v
        return None

    def display(self, key: str, var: str, disp: str):
        """取结果值并做单位变换（unit-safe：禁止图内自己换算）。"""
        raw = self.value(key)
        entry = self.registry.get(var)
        return transform_value(raw, entry, disp)

    def annotate_value(self, ax, label: str, key: str, var: str = "", disp: str = "",
                       xy=None, **kwargs):
        """图内直接标注：值由结果 key 决定并登记到 meta（raw + value）。"""
        raw = self.value(key)
        val = self.display(key, var, disp) if (var and disp) else raw
        if val is None:
            raise ValueError(f"Figure {self.figure_id} annotation {label}: key={key} 无值")
        txt = kwargs.pop("fmt", "{:.2f}").format(val)
        ax.annotate(f"{label} {txt}", xy=xy or (0.02, 0.98), xycoords="axes fraction",
                    va="top", ha="left", **kwargs)
        self.anno_meta.append({"label": label, "value_key": key, "raw": raw,
                               "value": val, "text": txt})

    # ---------- 保存与 meta ----------

    def _count_artists(self, ax):
        counts = {"line_count": 0, "scatter_count": 0, "patch_count": 0,
                  "text_count": 0, "collection_count": 0}
        for line in ax.get_lines():
            counts["line_count"] += 1
        for col in ax.collections:
            counts["collection_count"] += 1
        for patch in ax.patches:
            counts["patch_count"] += 1
        for t in ax.texts:
            counts["text_count"] += 1
        return counts

    def save(self, fig, axes_spec: list, out_dir: str = "figures",
             panels: dict | None = None, caption: str = "", generator: str = ""):
        """保存 PDF（+PNG）+ 写 figures/<id>.meta.json。axes_spec: [{ax, panel_id, variable, display, x_unit, y_unit}]"""
        out = Path(self.ws) / out_dir
        out.mkdir(parents=True, exist_ok=True)
        pdf_path = out / f"{self.figure_id}.pdf"
        fig.savefig(pdf_path, bbox_inches="tight", transparent=False)
        fig.savefig(out / f"{self.figure_id}.png", dpi=300, bbox_inches="tight")

        # panel artist 计数（默认按 axes 顺序映射 panel A/B/C）
        panel_ids = panels or {}
        for spec in axes_spec:
            ax = spec.get("ax")
            pid = spec.get("panel_id") or panel_ids.get(id(ax)) or ""
            if pid is None:
                continue
            rec = self._count_artists(ax)
            if pid:
                self.panel_meta[pid] = rec
            if spec.get("variable") and spec.get("display"):
                self.axes_meta.append({
                    "ylabel": str(getattr(ax, "get_ylabel", lambda: "")()),
                    "variable": spec["variable"], "display": spec["display"],
                    "panel_id": pid,
                    "raw_range": [float(spec.get("raw_min", 0)), float(spec.get("raw_max", 1))]
                    if "raw_min" in spec else None,
                })

        meta = {
            "figure_id": self.figure_id,
            "generator": generator or self.manifest.get("source", {}).get("generator", ""),
            "generator_sha256": self.manifest.get("source", {}).get("generator_sha256", ""),
            "generated_at": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
            "source_results": [
                {"file": s.get("file"), "sha256": self._file_hash(self.results_dir / str(s.get("file", ""))),
                 "keys": s.get("keys", [])}
                for s in (self.manifest.get("source_results", []) or [])
            ],
            "source_hash": self._compute_source_hash(),
            "panels": self.panel_meta,
            "annotations": self.anno_meta,
            "axes": self.axes_meta,
            "caption": caption,
        }
        meta_path = out / f"{self.figure_id}.meta.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return pdf_path, meta_path

    def _file_hash(self, path: Path):
        try:
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return ""

    def _compute_source_hash(self):
        h = hashlib.sha256()
        for src in self.manifest.get("source_results", []) or []:
            rel = str(src.get("file", "")).strip()
            d = self._load_json(self.results_dir / rel)
            if isinstance(d, dict):
                keys = {k: _find(d, k) for k in (src.get("keys", []) or [])}
                h.update(json.dumps(keys, sort_keys=True, ensure_ascii=False).encode("utf-8"))
        return h.hexdigest()


if __name__ == "__main__":
    # 自检：生成迷你图 + meta.json（验证 pipeline 可用）
    import sys
    import tempfile
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ws = Path(tempfile.mkdtemp())
    (ws / "results").mkdir()
    (ws / "reports").mkdir()
    (ws / "results" / "demo.json").write_text(
        json.dumps({"G2": {"recommended": {"low": 0.04, "high": 0.12}}}), encoding="utf-8")
    (ws / "reports" / "variables.json").write_text(
        json.dumps({"Y_fraction": {"storage_unit": "fraction", "storage_range": [0, 1],
                                   "display": {"percent": {"transform": "*100", "unit": "%",
                                                            "threshold_raw": 0.04,
                                                            "threshold_display": 4.0}}}}),
        encoding="utf-8")
    item = {"id": "demo_fig", "story": {"main_message": "demo"},
            "source_results": [{"file": "demo.json", "keys": ["G2.recommended.low", "G2.recommended.high"]}]}
    fb = FigureBuilder("demo_fig", item, ws)
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1, 2], [0, 0.5, 1])
    ax.set_ylabel("Y浓度 (%)")
    fb.annotate_value(ax, "G2 低", "G2.recommended.low", "Y_fraction", "percent", fmt="{:.1f}")
    pdf, meta = fb.save(fig, [{"ax": ax, "panel_id": "A", "variable": "Y_fraction",
                               "display": "percent", "raw_min": 0.0, "raw_max": 0.2}])
    m = json.loads(meta.read_text(encoding="utf-8"))
    assert m["panels"]["A"]["line_count"] >= 1, "artist counting failed"
    assert any(a["label"] == "G2 低" and abs(a["value"] - 4.0) < 1e-9 for a in m["annotations"]), "unit transform failed"
    print(f"FigureBuilder self-check OK: {pdf.name} value=4.0 (raw 0.04 * 100)")
