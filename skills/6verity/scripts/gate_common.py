#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gate_common.py — v2 门禁公共库：编码、JSON、哈希快照、工具探测、manifest 读写。

所有门禁脚本共享本模块；本文件被复制到其他目录时路径解析以本文件实际位置为准。
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

SCHEMA_VERSION = 1
POLICY_FILE = Path(__file__).resolve().parent / "style_policy.json"
if not POLICY_FILE.is_file():
    POLICY_FILE = Path(__file__).resolve().parent.parent / "style_policy.json"


# ---------- 编码与 JSON ----------

def force_utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def load_json(path: Path, default=None):
    """读取 JSON；损坏或缺失返回 default。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path: Path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return path


def load_policy() -> dict:
    return load_json(POLICY_FILE, {})


# ---------- 哈希与目录快照 ----------

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dir_snapshot(directory: Path, exts=None) -> dict:
    """目录快照：{sha256, files, mtime_max}。按相对路径排序后逐文件哈希。"""
    d = Path(directory)
    files = []
    if d.is_dir():
        for p in sorted(d.rglob("*")):
            if not p.is_file():
                continue
            if exts and p.suffix.lower() not in exts:
                continue
            files.append(p)
    if not files:
        return {"sha256": hashlib.sha256(b"").hexdigest(), "files": 0, "mtime_max": 0}
    h = hashlib.sha256()
    mtime_max = 0.0
    for p in files:
        rel = p.relative_to(d).as_posix()
        h.update((rel + ":" + sha256_file(p) + "\n").encode("utf-8"))
        mtime_max = max(mtime_max, p.stat().st_mtime)
    return {"sha256": h.hexdigest(), "files": len(files), "mtime_max": mtime_max}


def iso_now() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


# ---------- 工具探测 ----------

def detect_tool(name: str, version_args=None) -> dict:
    """探测可执行文件与版本。找不到 path=None，version=None，不编造。"""
    path = shutil.which(name)
    version_args = version_args or ["--version"]
    if not path:
        return {"name": name, "path": None, "version": None}
    version = None
    try:
        proc = subprocess.run([path, *version_args], capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        out = (proc.stdout or proc.stderr or "").strip().splitlines()
        if out:
            version = out[0][:120]
    except Exception:
        version = None
    return {"name": name, "path": str(Path(path)), "version": version}


def detect_all_tools() -> dict:
    return {
        "python": {"name": "python", "path": sys.executable, "version": sys.version.splitlines()[0]},
        "xelatex": detect_tool("xelatex"),
        "pdflatex": detect_tool("pdflatex"),
        "latexmk": detect_tool("latexmk"),
        "typst": detect_tool("typst"),
        "pdftoppm": detect_tool("pdftoppm"),
        "mgs": detect_tool("mgs"),
        "mutool": detect_tool("mutool"),
        "magick": detect_tool("magick"),
        "inkscape": detect_tool("inkscape"),
        "mmdc": detect_tool("mmdc"),
        "drawio": detect_tool("drawio"),
        "git": detect_tool("git"),
    }


# ---------- manifest 路径与读取 ----------

def manifest_path(ws) -> Path:
    return Path(ws) / "project.manifest.json"


def artifact_path(ws) -> Path:
    return Path(ws) / "artifact_manifest.json"


def runtime_path(ws) -> Path:
    return Path(ws) / "state" / "runtime_manifest.json"


def load_manifest(ws) -> dict:
    return load_json(manifest_path(ws), {}) if isinstance(manifest_path(ws), Path) else load_json(Path(ws) / "project.manifest.json", {})


def manifest_engine(ws) -> str:
    return str(load_manifest(ws).get("engine", "unknown")).lower()


def manifest_entry(ws) -> str:
    return str(load_manifest(ws).get("entry", ""))


def manifest_hil_policy(ws) -> str:
    return str(load_manifest(ws).get("hil_policy", "unknown")).lower()
