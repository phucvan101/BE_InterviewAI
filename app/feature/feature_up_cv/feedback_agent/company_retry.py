"""
Auto-retry company data lookup (Hướng 7).

The standard scoring flow expects ``company_data`` to be already
present (uploaded by the user as a CI file). When the user does NOT
provide one, ``score_company_fit`` returns 0/10 with a flat rationale
— which leads to a noisy experience for fresh-grad candidates.

This module provides a graceful fallback:

  1. Try to extract a company name from the JD (regex on the title or
     description).
  2. If found, call the existing ``llm_parser_company`` to derive a
     minimal company data structure on the fly.
  3. Return a dict that ``company_fit_score`` can consume directly.

The fallback is best-effort and never raises — if the parser fails,
we just return ``None`` and the scoring engine gets the original
empty input.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Heuristics: "at <Company>", "<Company> is looking for", "join <Company>".
# The company name must be a sequence of capitalised words terminated by
# a boundary (end of string, period, comma, "đang", "tuyển", "với", "for",
# "is", "looking", "in", "at"). This avoids the regex from greedily
# picking up the rest of the sentence.
_BOUNDARY = r"(?=$|[\s,.;:!?]|\bđang\b|\btuyển\b|\bvới\b|\bfor\b|\bis\b|\blooking\b|\bjoin\b|\btrong\b)"
_COMPANY_PATTERNS = [
    # Use a strict class that does NOT include punctuation inside the
    # token — otherwise "VNG Corporation." reads as one word and the
    # boundary lookahead never fires.
    re.compile(
        r"\bat\s+([A-Z][A-Za-z0-9&\-]+(?:\s+[A-Z][A-Za-z0-9&\-]+){0,3})"
        + _BOUNDARY
    ),
    re.compile(
        r"\b([A-Z][A-Za-z0-9&\-]+(?:\s+[A-Z][A-Za-z0-9&\-]+){0,3})\s+"
        r"(?:is|đang)\s+(?:looking|hiring|recruiting|tuyển)"
        + _BOUNDARY
    ),
    re.compile(
        r"\b(?:join|về|gia nhập)\s+([A-Z][A-Za-z0-9&\-]+(?:\s+[A-Z][A-Za-z0-9&\-]+){0,3})"
        + _BOUNDARY
    ),
]


def extract_company_name_from_jd(jd_data: Dict[str, Any]) -> Optional[str]:
    """
    Return the first plausible company name found in the JD, or None.
    """
    if not isinstance(jd_data, dict):
        return None
    jd_struct = jd_data.get("structured", jd_data) or {}
    # Use a clear separator so the regex's boundary check sees
    # sentence-ending punctuation between the fields.
    blob = " . ".join(
        str(jd_struct.get(k, ""))
        for k in ("job_title", "summary", "description", "company_name")
    )
    if not blob.strip():
        return None
    for pat in _COMPANY_PATTERNS:
        m = pat.search(blob)
        if m:
            name = m.group(1).strip()
            # filter out common false-positives
            low = name.lower()
            if low in {
                "we", "our", "the", "a", "an", "company",
                "fresher", "junior", "senior", "mid", "lead",
            }:
                continue
            return name
    return None


def maybe_research_company(
    jd_data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Best-effort: try to obtain a minimal company_data dict from the JD.

    Returns ``None`` when no company name can be found or the parser
    fails. The returned dict is shaped like
    ``llm_parser_company`` output (includes ``success=True``).
    """
    name = extract_company_name_from_jd(jd_data)
    if not name:
        logger.debug("[CompanyRetry] no company name extracted from JD")
        return None

    try:
        from app.feature.feature_up_cv.parsers.parser_company import (
            llm_parser_company,
        )
    except Exception as e:  # pragma: no cover
        logger.warning("[CompanyRetry] cannot import parser: %s", e)
        return None

    try:
        info = llm_parser_company(f"Company: {name}")
    except Exception as e:
        logger.warning("[CompanyRetry] parser call failed: %s", e)
        return None

    if not isinstance(info, dict) or not info.get("success"):
        logger.info("[CompanyRetry] parser returned no success for %r", name)
        return None

    # Stamp source so the consumer knows this was derived on the fly.
    info["company_name"] = info.get("company_name") or name
    info["source"] = "auto_retry"
    logger.info("[CompanyRetry] derived company data for %r", name)
    return info
