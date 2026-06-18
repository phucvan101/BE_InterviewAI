# -*- coding: utf-8 -*-
"""
Step 3: Merge LLM-as-judge (me) verdicts into the final report.

Input:  eval_hallucination/fields_for_judge.json
        eval_hallucination/judgments.json        (written by the LLM judge)
Output: prints a summary table + per-doc detail; optional --json dump.

Judgments file format
---------------------
Two equivalent shapes are supported per document:

1. Per-field (granular): each atomic value is judged individually
     "<doc_id>": {
         "<field_id>": {"verdict": "grounded|fabricated", "reason": "..."}
     }

2. Per-unique-value (compact): a single verdict is shared by all fields with
   the same value within a document.  Use this when many fields are
   duplicates of the same string (e.g. 'Python' appears in `skills` and
   `technical_skills`).
     "<doc_id>": {
         "__by_value__": {
             "<value>": {"verdict": "...", "reason": "..."}
         }
     }

The two shapes can be mixed within the same document.  If neither shape
provides a verdict for a field, it is counted as "missing".

Verdicts:
  - "grounded"   : the value is supported by the source (literal, paraphrase,
                   translation, alias, or a faithful normalization).
  - "fabricated" : the value introduces information NOT present in the source
                   in a way the parser should not reasonably have inferred.
                   THIS is a hallucination.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

VERDICTS = ("grounded", "fabricated")


def load_inputs(fields_path: Path, judgments_path: Path) -> tuple[list[dict], dict]:
    documents = json.loads(fields_path.read_text(encoding="utf-8"))
    if not judgments_path.exists():
        print(f"[fatal] judgments file not found: {judgments_path}", file=sys.stderr)
        sys.exit(2)
    judgments = json.loads(judgments_path.read_text(encoding="utf-8"))
    return documents, judgments


def aggregate(documents: list[dict], judgments: dict) -> dict[str, Any]:
    by_type: dict[str, dict[str, int]] = defaultdict(
        lambda: {"docs": 0, "total": 0, "grounded": 0, "fabricated": 0, "missing": 0}
    )
    overall = {"docs": 0, "total": 0, "grounded": 0, "fabricated": 0, "missing": 0}
    per_doc: list[dict[str, Any]] = []

    for d in documents:
        doc_j = judgments.get(d["doc_id"], {})
        per_value = doc_j.get("__by_value__", {})
        per_field = {k: v for k, v in doc_j.items() if k != "__by_value__"}
        counts = {"total": 0, "grounded": 0, "fabricated": 0, "missing": 0}
        for f in d["fields"]:
            counts["total"] += 1
            j = per_field.get(f["id"]) or per_value.get(f["value"])
            if j is None:
                counts["missing"] += 1
                continue
            v = j.get("verdict")
            if v not in VERDICTS:
                counts["missing"] += 1
                continue
            counts[v] += 1

        bucket = by_type[d["file_type"]]
        bucket["docs"] += 1
        for k, v in counts.items():
            bucket[k] += v
        for k, v in counts.items():
            overall[k] += v
        overall["docs"] += 1

        per_doc.append(
            {
                "doc_id": d["doc_id"],
                "raw_file": d["raw_file"],
                "parser_file": d["parser_file"],
                "file_type": d["file_type"],
                **counts,
                "hallucination_rate": (counts["fabricated"] / counts["total"])
                if counts["total"]
                else 0.0,
            }
        )

    def _flatten(b: dict[str, int]) -> dict[str, Any]:
        t = b["total"]
        return {
            "documents": b["docs"],
            "atomic_values": t,
            "grounded": b["grounded"],
            "fabricated": b["fabricated"],
            "missing_judgment": b["missing"],
            "coverage": (b["grounded"] / t) if t else 0.0,
            "hallucination_rate": (b["fabricated"] / t) if t else 0.0,
        }

    return {
        "summary": {
            "overall": _flatten(overall),
            "by_file_type": {k: _flatten(v) for k, v in sorted(by_type.items())},
        },
        "per_doc": per_doc,
        "details_by_doc": _collect_details(documents, judgments),
    }


def _collect_details(documents: list[dict], judgments: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for d in documents:
        items: list[dict] = []
        doc_j = judgments.get(d["doc_id"], {})
        per_value = doc_j.get("__by_value__", {})
        per_field = {k: v for k, v in doc_j.items() if k != "__by_value__"}
        for f in d["fields"]:
            j = per_field.get(f["id"]) or per_value.get(f["value"])
            items.append(
                {
                    "field_id": f["id"],
                    "path": f["path"],
                    "value": f["value"],
                    "verdict": (j or {}).get("verdict"),
                    "reason": (j or {}).get("reason"),
                }
            )
        out[d["doc_id"]] = items
    return out


def print_report(agg: dict[str, Any], top: int = 10) -> None:
    s = agg["summary"]
    print("=" * 96)
    print("PARSER HALLUCINATION REPORT  (judge = LLM semantic)")
    print("=" * 96)
    print(
        f"  {'TYPE':<5} {'DOCS':>4} {'VALUES':>6} {'GROUNDED':>9} {'FABRIC':>7} "
        f"{'MISSING':>7} {'COVERAGE':>9} {'HALLUC':>8}"
    )
    for ftype, stats in s["by_file_type"].items():
        print(
            f"  [{ftype.upper():>3}]  {stats['documents']:>4} {stats['atomic_values']:>6} "
            f"{stats['grounded']:>9} {stats['fabricated']:>7} {stats['missing_judgment']:>7} "
            f"{stats['coverage']:>8.2%} {stats['hallucination_rate']:>7.2%}"
        )
    o = s["overall"]
    print("-" * 96)
    print(
        f"  [ALL ]  {o['documents']:>4} {o['atomic_values']:>6} "
        f"{o['grounded']:>9} {o['fabricated']:>7} {o['missing_judgment']:>7} "
        f"{o['coverage']:>8.2%} {o['hallucination_rate']:>7.2%}"
    )
    print("=" * 96)

    for d in agg["per_doc"]:
        print(
            f"\n  - {d['raw_file']}  <->  {d['parser_file']}\n"
            f"      type={d['file_type']}  total={d['total']}  "
            f"grounded={d['grounded']}  fabricated={d['fabricated']}  "
            f"missing={d['missing']}  hallucination={d['hallucination_rate']:.2%}"
        )
        details = agg["details_by_doc"].get(d["doc_id"], [])
        fab = [x for x in details if x["verdict"] == "fabricated"]
        if fab:
            print(f"      fabricated fields (showing up to {top}):")
            for x in fab[:top]:
                preview = x["value"] if len(x["value"]) <= 120 else x["value"][:117] + "..."
                print(f"        - {x['path']}: {preview!r}  [{x['reason']}]")
        miss = [x for x in details if not x["verdict"]]
        if miss:
            print(f"      [{len(miss)} fields have no judgment -- still pending from LLM judge]")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--fields",
        type=Path,
        default=Path(__file__).resolve().parent / "fields_for_judge.json",
    )
    ap.add_argument(
        "--judgments",
        type=Path,
        default=Path(__file__).resolve().parent / "judgments.json",
    )
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()

    documents, judgments = load_inputs(args.fields, args.judgments)
    agg = aggregate(documents, judgments)
    print_report(agg, top=args.top)

    if args.json:
        args.json.write_text(
            json.dumps(agg, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n[info] full report written to {args.json}")

    # non-zero exit if any hallucinations exist (CI-friendly)
    fab = agg["summary"]["overall"]["fabricated"]
    miss = agg["summary"]["overall"]["missing_judgment"]
    if miss:
        print(f"\n[warn] {miss} fields still missing judgment")
    return 0 if fab == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
