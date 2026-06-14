# -*- coding: utf-8 -*-
"""
Shared utility functions for feature_up_cv module.

Consolidated from parser_cv.py, parser_jd.py, parser_company.py, hybrid_scoring.py
to eliminate code duplication.
"""

import re
from typing import Any, List, Optional


def extract_first_json(text: str) -> Optional[str]:
    """Extract the first balanced JSON object from a string."""
    stack = 0
    start = None
    for i, c in enumerate(text):
        if c == "{":
            if stack == 0:
                start = i
            stack += 1
        elif c == "}":
            stack -= 1
            if stack == 0 and start is not None:
                return text[start : i + 1]
    return None


def criterion_key(text: str) -> str:
    """Normalize criterion text to a dedup key."""
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def normalize_importance(value: Any, fallback: str = "IMPORTANT") -> str:
    """Normalize importance level to CRITICAL/IMPORTANT/BONUS."""
    level = str(value or "").strip().upper()
    return level if level in {"CRITICAL", "IMPORTANT", "BONUS"} else fallback


def coerce_string_list(value: Any) -> List[str]:
    """Coerce a value to a list of non-empty strings."""
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def criterion_id(index: int, name: str) -> str:
    """Generate a criterion ID from index and name."""
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:32]
    return f"crit_{index:02d}" + (f"_{slug}" if slug else "")
