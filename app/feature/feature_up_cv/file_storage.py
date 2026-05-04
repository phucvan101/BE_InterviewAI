# -*- coding: utf-8 -*-
"""
File storage utilities for upload & parser cache system.

Handles:
- Saving raw uploaded files to uploads/raw_file/
- Saving parsed JSON results to uploads/parser_file/
- Generating standardized file names: {type}_{timestamp}_{user_id}_{record_id}.{ext}
- Computing SHA-256 hash of extracted text for dedup/cache
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

# ── Base upload directory (relative to feature_up_cv) ─────────────────────────
_BASE_DIR = Path(__file__).resolve().parent / "uploads"
RAW_FILE_DIR = _BASE_DIR / "raw_file"
PARSER_FILE_DIR = _BASE_DIR / "parser_file"
RESULT_FILE_DIR = _BASE_DIR / "result_analysis_file"

# Ensure directories exist at import time
RAW_FILE_DIR.mkdir(parents=True, exist_ok=True)
PARSER_FILE_DIR.mkdir(parents=True, exist_ok=True)
RESULT_FILE_DIR.mkdir(parents=True, exist_ok=True)


# ── File type prefixes ────────────────────────────────────────────────────────
FILE_TYPE_CV = "cv"
FILE_TYPE_JD = "jd"
FILE_TYPE_CI = "ci"


def _timestamp_str() -> str:
    """Return current UTC timestamp as compact string: YYYYMMDDHHmmss"""
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def build_filename(
    file_type: str,
    user_id: int,
    record_id: int,
    extension: str,
) -> str:
    """
    Build a standardized file name.

    Examples:
        cv_20260423081500_3_12.pdf
        jd_20260423081500_3_7.docx
        ci_20260423081500_3_5.pdf
    """
    ts = _timestamp_str()
    ext = extension.lstrip(".")
    return f"{file_type}_{ts}_{user_id}_{record_id}.{ext}"


def save_raw_file(
    content: bytes,
    file_type: str,
    user_id: int,
    record_id: int,
    extension: str,
) -> Path:
    """
    Save a raw uploaded file to uploads/raw_file/ with standard naming.

    Returns the absolute path of the saved file.
    """
    filename = build_filename(file_type, user_id, record_id, extension)
    dest = RAW_FILE_DIR / filename
    dest.write_bytes(content)
    return dest


def save_parser_result(
    parsed_data: dict,
    file_type: str,
    user_id: int,
    record_id: int,
) -> Path:
    """
    Save a parsed JSON result to uploads/parser_file/ with standard naming.

    Returns the absolute path of the saved file.
    """
    filename = build_filename(file_type, user_id, record_id, "json")
    dest = PARSER_FILE_DIR / filename
    dest.write_text(
        json.dumps(parsed_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return dest


def load_parser_result(file_path: str | Path) -> dict | None:
    """
    Load a previously saved parsed JSON file. Returns None on any error.
    """
    try:
        p = Path(file_path)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def save_result_analysis(
    parsed_data: dict,
    user_id: int,
    id_cv: int,
    id_jd: int,
) -> Path:
    """
    Save an analysis result JSON file to uploads/result_analysis_file/.
    """
    ts = _timestamp_str()
    filename = f"result_{ts}_{user_id}_cv{id_cv}_jd{id_jd}.json"
    dest = RESULT_FILE_DIR / filename
    dest.write_text(
        json.dumps(parsed_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return dest


def load_result_analysis(file_path: str | Path) -> dict | None:
    """
    Load a previously saved analysis result JSON file. Returns None on any error.
    """
    try:
        p = Path(file_path)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def compute_text_hash(text: str) -> str:
    """
    Compute SHA-256 hash of the extracted text.
    Used to detect duplicate documents and skip redundant LLM calls.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def delete_file(file_path: str | Path | None) -> bool:
    """
    Delete a file from disk if it exists. Returns True if deleted.
    Used to clean up old uploads when user re-uploads a new file.
    """
    if not file_path:
        return False
    try:
        p = Path(file_path)
        if p.exists() and p.is_file():
            p.unlink()
            return True
    except Exception:
        pass
    return False

