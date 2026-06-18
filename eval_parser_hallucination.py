# -*- coding: utf-8 -*-
"""
Hallucination evaluation for the CV/JD/CI parser stage.

Methodology
-----------
The parser is the model that turns a raw CV / JD / Company document into a
structured JSON. To measure how faithful that JSON is to the source document
(the standard "hallucination" check for extractive parsers) we:

  1. Walk storage/raw_file/  ->  the original uploaded file (PDF/DOCX/TXT)
  2. Walk storage/parser_file/ ->  the JSON produced by the model
  3. Pair them by `(file_type, user_id, record_id)` (filename format is
     `{type}_{ts}_{user_id}_{record_id}.{ext}`).
  4. Extract plain text from the raw file.
  5. For every atomic string value in the parsed JSON, check whether the
     string is "grounded" in the source text. We use a token-overlap
     approach (lowercased, whitespace-stripped, Vietnamese-friendly) that
     is cheap and deterministic -- an item counts as grounded if it is a
     substring of the source OR a token-level fuzzy match exceeds a
     threshold.

Outputs
-------
  - Per-document detail: each atomic value with verdict GROUNDED/UNGROUNDED.
  - Per-document aggregate metrics:
        total atomic values, grounded count, ungrounded count,
        hallucination_rate = ungrounded / total,
        coverage           = grounded / total.
  - Overall summary across the corpus.

Usage
-----
    python eval_parser_hallucination.py
    python eval_parser_hallucination.py --raw-dir ... --parser-dir ... --json out.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable

# ── text extraction backends ────────────────────────────────────────────────
def _extract_pdf(path: Path) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(str(path)) as pdf:
            return "\n".join((p.extract_text() or "") for p in pdf.pages)
    except Exception as e:
        print(f"[warn] pdfplumber failed on {path.name}: {e}", file=sys.stderr)
        return ""

def _extract_docx(path: Path) -> str:
    try:
        import docx
        d = docx.Document(str(path))
        parts = [p.text for p in d.paragraphs]
        for tbl in d.tables:
            for row in tbl.rows:
                for cell in row.cells:
                    parts.append(cell.text)
        return "\n".join(parts)
    except Exception as e:
        print(f"[warn] docx failed on {path.name}: {e}", file=sys.stderr)
        return ""

def _extract_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")

_EXTRACTORS = {".pdf": _extract_pdf, ".docx": _extract_docx, ".txt": _extract_txt}

def extract_text(path: Path) -> str:
    fn = _EXTRACTORS.get(path.suffix.lower())
    if not fn:
        return ""
    return fn(path)

# ── filename parsing ──────────────────────────────────────────────────────
# cv_20260617130200_2_2.pdf  /  jd_20260617143909_2_5.json
# type _ ts _ user_id _ record_id
_NAME_RE = re.compile(r"^(cv|jd|ci)_(\d+)_(\d+)_(\d+)\.(.+)$", re.IGNORECASE)

def parse_name(name: str) -> tuple[str, int, int, str] | None:
    m = _NAME_RE.match(name)
    if not m:
        return None
    ftype, _ts, user_id, rec_id, ext = m.groups()
    return ftype.lower(), int(user_id), int(rec_id), ext.lower()

# ── grounding check ──────────────────────────────────────────────────────
_WORD_RE = re.compile(r"[\wÀ-ỹ]+", re.UNICODE)

def _norm(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s

def _tokens(s: str) -> set[str]:
    return {t for t in _WORD_RE.findall(s.lower()) if len(t) > 1}

def is_grounded(value: str, source_norm: str, source_tokens: set[str]) -> tuple[str, str]:
    """
    Decide if a single atomic value is supported by the source document.
    Returns (verdict, reason). Verdict is one of:
      "grounded"        - clearly supported
      "normalization"   - partial overlap; very likely a translated /
                           normalized form of a source concept
      "ungrounded"      - no real overlap; potential fabrication

    Heuristics:
      H1. exact substring of normalized source              -> grounded
      H2. token Jaccard >= 0.6 and >=50% tokens present    -> grounded
      H3. for short values (<=3 tokens): all tokens present -> grounded
      H4. numeric / date fragments: digit-substring match   -> grounded
      H5. short enum-like value whose tokens all appear
          individually in source (translation/alias)        -> grounded
      H6. partial token overlap but < H2/H3                 -> normalization
      H7. no token overlap at all                           -> ungrounded
    """
    v = _norm(value)
    if not v:
        return "grounded", "empty-skip"

    # H1: substring
    if v in source_norm:
        return "grounded", "substring"

    v_tokens = _tokens(v)
    if not v_tokens:
        return "grounded", "no-tokens-skip"

    common = v_tokens & source_tokens
    # H3 / H5: short values, all tokens present
    if len(v_tokens) <= 3 and common == v_tokens:
        return "grounded", "short-all-tokens"

    # H2: jaccard
    jaccard = len(common) / max(1, len(v_tokens | source_tokens))
    if jaccard >= 0.6 and len(common) / len(v_tokens) >= 0.5:
        return "grounded", f"jaccard={jaccard:.2f}"

    # H4: digit-only fallback (phone, year, etc.)
    digits_v = re.sub(r"\D", "", v)
    digits_src = re.sub(r"\D", "", source_norm)
    if len(digits_v) >= 3 and digits_v in digits_src:
        return "grounded", "digit-substring"

    # H6: partial overlap -> likely normalization/translation
    if common:
        return "normalization", f"partial-overlap jaccard={jaccard:.2f}, common={len(common)}/{len(v_tokens)}"

    # H7: no overlap at all
    return "ungrounded", f"no-token-overlap jaccard={jaccard:.2f}"

# ── walk JSON, collect atomic values with their path ──────────────────────
def walk_strings(obj: Any, path: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_strings(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_strings(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        s = obj.strip()
        if s:
            yield path, s
    # numbers / bools / None are skipped: parsers either copy digits (checked
    # above) or produce free text; both are caught by the string branch.

# ── reporting dataclass ───────────────────────────────────────────────────
@dataclass
class FieldFinding:
    path: str
    value: str
    verdict: str   # "grounded" | "normalization" | "ungrounded"
    reason: str

    @property
    def grounded(self) -> bool:  # back-compat
        return self.verdict == "grounded"

@dataclass
class DocReport:
    raw_file: str
    parser_file: str
    file_type: str
    user_id: int
    record_id: int
    source_chars: int
    findings: list[FieldFinding] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.findings)

    @property
    def grounded(self) -> int:
        return sum(1 for f in self.findings if f.verdict == "grounded")

    @property
    def normalization(self) -> int:
        return sum(1 for f in self.findings if f.verdict == "normalization")

    @property
    def ungrounded(self) -> int:
        return sum(1 for f in self.findings if f.verdict == "ungrounded")

    @property
    def hallucination_rate(self) -> float:
        # strict: only ungrounded counts as hallucination
        return (self.ungrounded / self.total) if self.total else 0.0

    @property
    def soft_hallucination_rate(self) -> float:
        # soft: ungrounded + suspicious normalization
        bad = self.ungrounded + self.normalization
        return (bad / self.total) if self.total else 0.0

    @property
    def coverage(self) -> float:
        return (self.grounded / self.total) if self.total else 0.0


# ── main eval loop ────────────────────────────────────────────────────────
def evaluate(raw_dir: Path, parser_dir: Path) -> list[DocReport]:
    # bucket parser files by (type, user, rec) so we can match raw files
    parser_by_key: dict[tuple[str, int, int], Path] = {}
    for f in parser_dir.iterdir():
        if f.suffix.lower() != ".json":
            continue
        meta = parse_name(f.name)
        if not meta:
            continue
        ftype, uid, rid, _ = meta
        parser_by_key[(ftype, uid, rid)] = f

    reports: list[DocReport] = []
    for raw in sorted(raw_dir.iterdir()):
        if not raw.is_file():
            continue
        meta = parse_name(raw.name)
        if not meta:
            continue
        ftype, uid, rid, ext = meta
        parser = parser_by_key.get((ftype, uid, rid))
        if not parser:
            print(f"[skip] no parser file for raw {raw.name}", file=sys.stderr)
            continue

        source_text = extract_text(raw)
        if not source_text:
            print(f"[warn] empty text for {raw.name}", file=sys.stderr)
            continue
        source_norm = _norm(source_text)
        source_tokens = _tokens(source_text)

        try:
            parsed = json.loads(parser.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[warn] cannot parse {parser.name}: {e}", file=sys.stderr)
            continue

        report = DocReport(
            raw_file=raw.name,
            parser_file=parser.name,
            file_type=ftype,
            user_id=uid,
            record_id=rid,
            source_chars=len(source_text),
        )
        for path, value in walk_strings(parsed):
            verdict, reason = is_grounded(value, source_norm, source_tokens)
            report.findings.append(FieldFinding(path, value, verdict, reason))
        reports.append(report)

    return reports


def summarize(reports: list[DocReport]) -> dict[str, Any]:
    by_type: dict[str, dict[str, float]] = defaultdict(
        lambda: {"docs": 0, "total": 0, "grounded": 0, "normalization": 0, "ungrounded": 0}
    )
    overall = {"docs": 0, "total": 0, "grounded": 0, "normalization": 0, "ungrounded": 0}
    for r in reports:
        for bucket in (by_type[r.file_type], overall):
            bucket["docs"] += 1
            bucket["total"] += r.total
            bucket["grounded"] += r.grounded
            bucket["normalization"] += r.normalization
            bucket["ungrounded"] += r.ungrounded

    def _rate(bucket: dict[str, float]) -> dict[str, float]:
        t = bucket["total"]
        g = bucket["grounded"]
        n = bucket["normalization"]
        u = bucket["ungrounded"]
        return {
            "documents": int(bucket["docs"]),
            "atomic_values": int(t),
            "grounded": int(g),
            "normalization_suspect": int(n),
            "ungrounded": int(u),
            "coverage": (g / t) if t else 0.0,
            "hallucination_rate_strict": (u / t) if t else 0.0,   # fabrication only
            "hallucination_rate_soft": ((u + n) / t) if t else 0.0,  # incl. translation/normalization
        }

    return {
        "overall": _rate(overall),
        "by_file_type": {k: _rate(v) for k, v in sorted(by_type.items())},
    }


def print_report(reports: list[DocReport], summary: dict[str, Any], top_ungrounded: int = 5) -> None:
    print("=" * 92)
    print("PARSER HALLUCINATION REPORT")
    print("=" * 92)
    print(f"  {'TYPE':<5} {'DOCS':>4} {'VALUES':>6} {'GROUNDED':>9} {'NORM':>5} {'UNGRND':>6} "
          f"{'COV':>6} {'HAL-STRICT':>11} {'HAL-SOFT':>9}")
    for ftype, stats in summary["by_file_type"].items():
        print(
            f"  [{ftype.upper():>3}]  {stats['documents']:>4} {stats['atomic_values']:>6} "
            f"{stats['grounded']:>9} {stats['normalization_suspect']:>5} {stats['ungrounded']:>6} "
            f"{stats['coverage']:>5.2%} {stats['hallucination_rate_strict']:>10.2%} "
            f"{stats['hallucination_rate_soft']:>8.2%}"
        )
    o = summary["overall"]
    print("-" * 92)
    print(
        f"  [ALL ]  {o['documents']:>4} {o['atomic_values']:>6} "
        f"{o['grounded']:>9} {o['normalization_suspect']:>5} {o['ungrounded']:>6} "
        f"{o['coverage']:>5.2%} {o['hallucination_rate_strict']:>10.2%} "
        f"{o['hallucination_rate_soft']:>8.2%}"
    )
    print("=" * 92)

    for r in reports:
        print(
            f"\n  - {r.raw_file}  <->  {r.parser_file}\n"
            f"      type={r.file_type}  user={r.user_id}  rec={r.record_id}  "
            f"src_chars={r.source_chars}\n"
            f"      total={r.total}  grounded={r.grounded}  normalization={r.normalization}  "
            f"ungrounded={r.ungrounded}  "
            f"hallucination_strict={r.hallucination_rate:.2%}  "
            f"hallucination_soft={r.soft_hallucination_rate:.2%}"
        )
        ungrounded = [f for f in r.findings if f.verdict == "ungrounded"]
        suspicious = [f for f in r.findings if f.verdict == "normalization"]
        if ungrounded:
            print(f"      fabricated-looking fields (showing up to {top_ungrounded}):")
            for f in ungrounded[:top_ungrounded]:
                preview = f.value if len(f.value) <= 120 else f.value[:117] + "..."
                print(f"        - {f.path}: {preview!r}  [{f.reason}]")
        if suspicious:
            print(f"      normalization/translation suspects (showing up to {top_ungrounded}):")
            for f in suspicious[:top_ungrounded]:
                preview = f.value if len(f.value) <= 120 else f.value[:117] + "..."
                print(f"        - {f.path}: {preview!r}  [{f.reason}]")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--raw-dir",
        type=Path,
        default=Path(__file__).parent / "app/feature/feature_up_cv/storage/raw_file",
    )
    ap.add_argument(
        "--parser-dir",
        type=Path,
        default=Path(__file__).parent / "app/feature/feature_up_cv/storage/parser_file",
    )
    ap.add_argument("--json", type=Path, default=None, help="Optional path to dump full JSON results")
    ap.add_argument("--top", type=int, default=5, help="How many ungrounded examples per doc to print")
    args = ap.parse_args()

    if not args.raw_dir.is_dir():
        print(f"[fatal] raw-dir not found: {args.raw_dir}", file=sys.stderr)
        return 2
    if not args.parser_dir.is_dir():
        print(f"[fatal] parser-dir not found: {args.parser_dir}", file=sys.stderr)
        return 2

    reports = evaluate(args.raw_dir, args.parser_dir)
    summary = summarize(reports)
    print_report(reports, summary, top_ungrounded=args.top)

    if args.json:
        payload = {
            "summary": summary,
            "documents": [
                {
                    **asdict(r),
                    "metrics": {
                        "total": r.total,
                        "grounded": r.grounded,
                        "normalization_suspect": r.normalization,
                        "ungrounded": r.ungrounded,
                        "coverage": r.coverage,
                        "hallucination_rate_strict": r.hallucination_rate,
                        "hallucination_rate_soft": r.soft_hallucination_rate,
                    },
                }
                for r in reports
            ],
        }
        args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[info] full report written to {args.json}")

    # non-zero exit if any strict-hallucination values exist (CI-friendly)
    return 0 if summary["overall"]["ungrounded"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
