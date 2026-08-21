#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check paper citations and verify bibliography records with OpenAlex."""
from __future__ import annotations
import argparse, difflib, json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path
try:
    import gate_common as gc
except ImportError:
    gc = None

SCHEMA_VERSION = 1
SIMILARITY_THRESHOLD = 0.85
MAILTO_USER_AGENT = "6verity-verify-refs/1.0 (mailto:6verity@example.com)"

def _text(path):
    return path.read_text(encoding="utf-8", errors="replace")

def _clean_title(value):
    value = re.sub(r"\\[a-zA-Z]+\s*", " ", value or "")
    value = re.sub(r"[{}$]", "", value)
    return re.sub(r"[^\w]+", " ", value, flags=re.UNICODE).casefold().strip()

def normalize_doi(value):
    value = (value or "").strip().casefold()
    value = re.sub(r"^(?:https?://)?(?:dx\.)?doi\.org/", "", value)
    return value.rstrip(" .;,)")

def parse_latex(workspace):
    references, citations = [], []
    for path in sorted((workspace / "paper").rglob("*.tex")):
        if not path.is_file(): continue
        source, rel = _text(path), str(path.relative_to(workspace)).replace("\\", "/")
        for match in re.finditer(r"\\bibitem(?:\s*\[[^]]*\])?\s*\{([^{}]+)\}", source):
            references.append({"key": match.group(1).strip(), "source": rel,
                               "line": source.count("\n", 0, match.start()) + 1,
                               "text": source[match.end():].split("\\bibitem", 1)[0].strip()})
        for line_no, raw in enumerate(source.splitlines(), 1):
            line = re.sub(r"(?<!\\)%.*$", "", raw)
            for match in re.finditer(r"\\cite[a-zA-Z*]*\s*(?:\[[^]]*\]\s*)?\{([^{}]+)\}", line):
                citations.extend({"key": key.strip(), "source": rel, "line": line_no}
                                 for key in match.group(1).split(",") if key.strip())
    return references, citations

def parse_typst(workspace):
    path = workspace / "paper" / "references.typ"
    if not path.is_file(): return [], []
    source, rel = _text(path), "paper/references.typ"
    references = [{"key": m.group(1), "source": rel,
                   "line": source.count("\n", 0, m.start()) + 1, "text": m.group(2).strip()}
                  for m in re.finditer(r"(?m)^\s*\[(\d+)\]\s+(.+)$", source)]
    citations = []
    for line_no, raw in enumerate(source.splitlines(), 1):
        line = re.sub(r"//.*$", "", raw)
        for match in re.finditer(r'#super\s*\(\s*["\'](\d+)["\']\s*\)', line):
            citations.append({"key": match.group(1), "source": rel, "line": line_no})
        for match in re.finditer(r"#super\s*\[([^]]+)\]", line):
            citations.extend({"key": key, "source": rel, "line": line_no} for key in re.findall(r"\d+", match.group(1)))
    return references, citations

def _doi_from_text(text):
    match = re.search(r"(?:https?://doi\.org/|doi:\s*)(10\.\d{4,9}/[-._;()/:a-z0-9]+)", text, re.I)
    return normalize_doi(match.group(1)) if match else ""


def candidate_title(text):
    """从 bibitem 条目文本提取标题候选：中文 [J] 标题 > 引号标题 > 最长的非作者段。"""
    text = (text or "").strip()
    m = re.search(r"([^\s\[].{4,}?)\s*\[[JDCMPRST]\]", text)
    if m:
        return m.group(1).strip().strip("，。.")
    m = re.search(r'["“]([^"”]{4,})["”]', text)
    if m:
        return m.group(1).strip()
    parts = [p.strip() for p in re.split(r"\.\s+", text) if p.strip()]
    parts = [p for p in parts if not re.match(r"^[A-Z][A-Za-z\-]+,\s+[A-Z]", p)]
    if parts:
        return max(parts, key=len).strip().strip(".")
    return text[:120]

def _get_json(url, timeout):
    """带重试的 GET（偶发 SSL EOF 时重试一次，间隔 2s）。"""
    last = None
    for _ in range(2):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": MAILTO_USER_AGENT,
                                                           "Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except Exception as exc:
            last = exc
            time.sleep(2)
    raise last

def query_openalex(reference, timeout):
    """返回 (best_record, error)。best_record 为 OpenAlex/Crossref 最佳候选。"""
    entry = reference.get("text", "")
    title = candidate_title(entry)
    doi = _doi_from_text(entry)
    wanted = _clean_title(title)
    best, best_sim, errors = None, 0.0, []

    if doi:
        try:
            data = _get_json("https://api.openalex.org/works/https://doi.org/"
                             + urllib.parse.quote(doi, safe="/"), timeout)
            rec = {"title": str(data.get("title") or ""), "doi": str(data.get("doi") or ""),
                   "id": data.get("id")}
            return rec, None
        except Exception as exc:
            errors.append(f"OpenAlex DOI: {exc}")

    # OpenAlex 标题搜索
    try:
        data = _get_json("https://api.openalex.org/works?search=" + urllib.parse.quote(title)
                         + "&per-page=5&mailto=mathmodel@example.com", timeout)
        for item in data.get("results", []) or []:
            rec = {"title": str(item.get("title") or ""), "doi": str(item.get("doi") or ""),
                   "id": item.get("id")}
            sim = difflib.SequenceMatcher(None, wanted, _clean_title(rec["title"])).ratio()
            if sim > best_sim:
                best, best_sim = rec, sim
    except Exception as exc:
        errors.append(f"OpenAlex: {exc}")
    time.sleep(0.3)

    # Crossref bibliographic 兜底/交叉
    try:
        data = _get_json("https://api.crossref.org/works?query.bibliographic="
                         + urllib.parse.quote(re.sub(r"\s+", " ", entry[:200])) + "&rows=5",
                         timeout)
        for item in data.get("message", {}).get("items", []) or []:
            rec = {"title": (item.get("title") or [""])[0], "doi": str(item.get("DOI") or ""),
                   "id": item.get("DOI")}
            rec_doi = normalize_doi(rec["doi"])
            if doi and rec_doi and (doi in rec_doi or rec_doi in doi):
                return rec, None
            sim = difflib.SequenceMatcher(None, wanted, _clean_title(rec["title"])).ratio()
            if sim > best_sim:
                best, best_sim = rec, sim
    except Exception as exc:
        errors.append(f"Crossref: {exc}")

    if best is None and errors:
        return None, "; ".join(errors)
    return best, None


def verify(reference, record, error):
    if record is None:
        return {"status": "unverified", "reason": "offline or OpenAlex unavailable", "error": error}
    wanted, actual = _doi_from_text(reference.get("text", "")), normalize_doi(str(record.get("doi", "")))
    doi_match = bool(wanted and actual and wanted == actual)
    similarity = difflib.SequenceMatcher(None, _clean_title(candidate_title(reference.get("text", ""))),
                                         _clean_title(str(record.get("title", "")))).ratio()
    ok = doi_match or similarity >= SIMILARITY_THRESHOLD
    return {"status": "verified" if ok else "unverified", "doi_match": doi_match,
            "similarity": round(similarity, 4), "openalex_id": record.get("id"), "title": record.get("title"),
            "reason": "DOI matched" if doi_match else ("title similarity matched" if ok else "title similarity below 0.85")}

def main(argv=None):
    if gc: gc.force_utf8()
    parser = argparse.ArgumentParser(description="Verify LaTeX/Typst references with OpenAlex")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--report", default="reports/gates/references_check.json")
    parser.add_argument("--timeout", type=float, default=12.0)
    args = parser.parse_args(argv)
    workspace = Path(args.workspace).resolve()
    latex_refs, latex_cites = parse_latex(workspace)
    typst_refs, typst_cites = parse_typst(workspace)
    references, citations = latex_refs + typst_refs, latex_cites + typst_cites
    keys, cited_keys = {r["key"] for r in references}, {c["key"] for c in citations}
    missing = sorted(cited_keys - keys)
    entries = []
    for reference in references:
        record, error = query_openalex(reference, args.timeout)
        entries.append({"reference": reference, "verification": verify(reference, record, error)})
    unverified = sum(e["verification"]["status"] != "verified" for e in entries)
    problems = [{"type": "missing_citation", "key": key} for key in missing]
    if not references:
        problems.append({"type": "missing_references", "reason": "no bibliography entries found"})
    problems += [{"type": "unverified_reference", "key": e["reference"]["key"]} for e in entries if e["verification"]["status"] != "verified"]
    report = {"schema_version": SCHEMA_VERSION, "workspace": str(workspace), "provider": "OpenAlex",
              "references": entries, "citations": citations, "missing_citations": missing, "problems": problems,
              "summary": {"references": len(references), "citations": len(citations), "verified": len(entries)-unverified,
                          "unverified": unverified, "missing_citations": len(missing)}, "strict": args.strict}
    output = Path(args.report)
    if not output.is_absolute(): output = workspace / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"references={len(references)} verified={len(entries)-unverified} unverified={unverified} missing={len(missing)} report={output}")
    return 1 if args.strict and problems else 0

if __name__ == "__main__": sys.exit(main())
