"""
Implied-field detection for JD parser output.

When the JD doesn't spell out ``seniority`` or ``years_of_experience``
explicitly (e.g. only the text mentions "3+ years" in the description),
this module can scan the structured output and back-fill them.

This is a deterministic, regex-based check (no LLM call) — it runs
before scoring so the experience caps are not silently misapplied.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Seniority keyword map (mirrors experience_score.py) ───────────
_SENIORITY_KEYWORDS: List[tuple] = [
    # (keyword, level)
    (r"\bintern(ship)?\b|\bthực tập\b", 0),
    (r"\bfresher\b|\bentry[- ]level\b|\bmới ra trường\b", 0),
    (r"\bjunior\b", 1),
    (r"\bmid[- ]?level\b|\bintermediate\b", 2),
    (r"\bsenior\b|\bsr\.?\b", 3),
    (r"\blead\b|\bprincipal\b|\bstaff\b", 4),
    (r"\bmanager\b|\bdirector\b|\bhead\b", 4),
]

_YEARS_PATTERN = re.compile(
    r"(\d+)\s*\+?\s*(?:năm|year|years|yr|yrs|y)\b", re.IGNORECASE
)
_MONTHS_PATTERN = re.compile(
    r"(\d+)\s*\+?\s*(?:tháng|month|months|mo|mos)\b", re.IGNORECASE
)


def _join_jd_text(jd_struct: Dict[str, Any]) -> str:
    """Concatenate the string fields of a JD into one blob for scanning."""
    parts: List[str] = []
    for key in (
        "job_title",
        "summary",
        "description",
        "responsibilities",
        "requirements",
        "seniority",
        "years_of_experience",
    ):
        v = jd_struct.get(key)
        if v:
            parts.append(str(v))
    return " \n ".join(parts)


def infer_seniority(jd_struct: Dict[str, Any]) -> Optional[int]:
    """
    Return the seniority level (0-4) inferred from the JD text, or
    ``None`` if no signal is found.
    """
    text = _join_jd_text(jd_struct).lower()
    if not text.strip():
        return None
    # Highest level wins (we walk the list in priority order)
    best: Optional[int] = None
    for pattern, level in _SENIORITY_KEYWORDS:
        if re.search(pattern, text):
            if best is None or level > best:
                best = level
    return best


def infer_years(jd_struct: Dict[str, Any]) -> Optional[float]:
    """
    Return the minimum years of experience inferred from the JD text,
    or ``None`` if no signal is found.

    Months are converted to years (12 months = 1 year).
    """
    text = _join_jd_text(jd_struct).lower()
    if not text.strip():
        return None
    years_matches = [int(m) for m in _YEARS_PATTERN.findall(text)]
    months_matches = [int(m) for m in _MONTHS_PATTERN.findall(text)]
    candidates: List[float] = []
    candidates.extend(float(y) for y in years_matches if y <= 30)
    if months_matches:
        candidates.append(min(months_matches) / 12.0)
    if not candidates:
        return None
    return min(candidates)  # be lenient: use the smallest stated bar


def backfill_jd_struct(
    jd_struct: Dict[str, Any],
    *,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """
    Return a NEW dict with implied ``seniority`` / ``years_of_experience``
    fields filled in if missing.

    If ``overwrite`` is True, even existing values are replaced. Default
    is ``False`` (respect explicit values).
    """
    out = dict(jd_struct)

    # Seniority: if missing, try to infer
    if overwrite or not out.get("seniority"):
        inferred_s = infer_seniority(out)
        if inferred_s is not None:
            out["seniority"] = _level_to_label(inferred_s)
            out["seniority_level_implied"] = inferred_s
            logger.info(
                "[ImpliedFields] seniority inferred=%d label=%s",
                inferred_s, out["seniority"],
            )

    # Years: same idea
    if overwrite or not out.get("years_of_experience"):
        inferred_y = infer_years(out)
        if inferred_y is not None:
            out["years_of_experience"] = inferred_y
            out["years_of_experience_implied"] = True
            logger.info(
                "[ImpliedFields] years_of_experience inferred=%.1f", inferred_y
            )

    return out


def _level_to_label(level: int) -> str:
    return {
        0: "intern/fresher",
        1: "junior",
        2: "mid",
        3: "senior",
        4: "lead/principal/manager",
    }.get(level, "mid")
