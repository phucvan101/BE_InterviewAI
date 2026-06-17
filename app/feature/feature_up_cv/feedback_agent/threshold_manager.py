"""
ThresholdOverrideManager — atomic, safe writer for ``threshold_overrides.yaml``.

Stores per-category overrides for the two semantic-match thresholds used
by ``scoring/_scores/skills_score.py``:

  * ``perfect_match``  — default 0.80 (config: ``PERFECT_MATCH_THRESHOLD``)
  * ``relevant_match`` — default 0.60 (config: ``RELEVANT_MATCH_THRESHOLD``)

Overrides are merged into the live scoring call ONLY when the caller
provides ``learned_knowledge`` with at least one rule whose ``context``
contains ``"threshold_adjustments"``. This keeps the override loop
"user-driven": a human-readable ``learned_rule`` must exist in FAISS
before any threshold actually moves.

Layout:

    threshold_overrides.yaml:
        default:
            perfect_match: 0.80
            relevant_match: 0.60
        technical_skill:
            perfect_match: 0.75
            relevant_match: 0.50
"""
from __future__ import annotations

import logging
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Range [0, 1] — keep thresholds inside valid similarity range.
_THRESHOLD_RANGE = (0.0, 1.0)
_THRESHOLD_KEYS = {"perfect_match", "relevant_match"}
_DEFAULT_YAML = (
    Path(__file__).resolve().parents[1] / "scoring" / "threshold_overrides.yaml"
)


def _is_safe_category(cat: str) -> bool:
    if not isinstance(cat, str) or not cat.strip() or len(cat) > 64:
        return False
    return bool(re.match(r"^[A-Za-z0-9_\-]{1,64}$", cat))


def _clamp(value: Any) -> Optional[float]:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    lo, hi = _THRESHOLD_RANGE
    return max(lo, min(hi, f))


class ThresholdOverrideManager:
    """Thread-safe writer for the threshold_overrides.yaml file."""

    def __init__(self, yaml_path: Optional[Path] = None) -> None:
        self.yaml_path: Path = Path(yaml_path) if yaml_path else _DEFAULT_YAML
        self._lock = threading.Lock()

    # ── Public API ────────────────────────────────────────────────
    def set_override(
        self,
        category: str,
        perfect_match: Optional[float] = None,
        relevant_match: Optional[float] = None,
        note: str = "",
    ) -> Tuple[bool, str]:
        """
        Set or update override for a category. Returns (ok, message).
        """
        if not _is_safe_category(category):
            return False, f"Invalid category name: {category!r}"

        updates: Dict[str, float] = {}
        if perfect_match is not None:
            v = _clamp(perfect_match)
            if v is None:
                return False, f"Invalid perfect_match: {perfect_match!r}"
            updates["perfect_match"] = v
        if relevant_match is not None:
            v = _clamp(relevant_match)
            if v is None:
                return False, f"Invalid relevant_match: {relevant_match!r}"
            updates["relevant_match"] = v
        if not updates:
            return False, "At least one of perfect_match/relevant_match required"

        with self._lock:
            data = self._read_yaml()
            existing = dict(data.get(category, {}) or {})
            existing.update(updates)
            if note:
                existing["note"] = str(note).strip()
            data[category] = existing
            self._write_yaml(data)
        return True, f"Override saved for category {category!r}: {updates}"

    def remove_override(self, category: str) -> Tuple[bool, str]:
        with self._lock:
            data = self._read_yaml()
            if category in data:
                data.pop(category, None)
                self._write_yaml(data)
                return True, f"Removed override for {category!r}"
        return False, f"No override found for {category!r}"

    def load_overrides(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return self._read_yaml()

    # ── YAML helpers (mirror PatternManager) ──────────────────────
    def _read_yaml(self) -> Dict[str, Dict[str, Any]]:
        from ruamel.yaml import YAML

        yaml = YAML(typ="rt")
        yaml.preserve_quotes = True
        if not self.yaml_path.exists():
            return {"default": {"perfect_match": 0.80, "relevant_match": 0.60}}
        try:
            with self.yaml_path.open("r", encoding="utf-8") as fh:
                loaded = yaml.load(fh) or {}
            if not isinstance(loaded, dict):
                return {"default": {"perfect_match": 0.80, "relevant_match": 0.60}}
            return loaded
        except Exception as e:
            logger.error("Failed to read threshold_overrides.yaml: %s", e)
            return {"default": {"perfect_match": 0.80, "relevant_match": 0.60}}

    def _write_yaml(self, data: Dict[str, Any]) -> None:
        from ruamel.yaml import YAML

        yaml = YAML(typ="rt")
        yaml.preserve_quotes = True
        yaml.default_flow_style = False
        yaml.indent(mapping=2, sequence=4, offset=2)

        import os
        import shutil as _sh

        tmp = self.yaml_path.with_suffix(self.yaml_path.suffix + ".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as fh:
                yaml.dump(data, fh)
            if self.yaml_path.exists():
                try:
                    os.remove(self.yaml_path)
                except PermissionError:
                    pass
            _sh.move(str(tmp), str(self.yaml_path))
        except Exception as e:
            logger.error("Failed to write threshold_overrides.yaml: %s", e)
            if tmp.exists():
                try:
                    tmp.unlink()
                except Exception:
                    pass
            raise


# ── Module-level singleton ────────────────────────────────────────
_threshold_manager: Optional[ThresholdOverrideManager] = None
_singleton_lock = threading.Lock()


def get_threshold_manager() -> ThresholdOverrideManager:
    """Return a process-wide singleton instance."""
    global _threshold_manager
    if _threshold_manager is None:
        with _singleton_lock:
            if _threshold_manager is None:
                _threshold_manager = ThresholdOverrideManager()
    return _threshold_manager


def resolve_threshold(
    category: str,
    learned_knowledge: Optional[Dict[str, Any]] = None,
) -> Tuple[float, float]:
    """
    Resolve the (perfect_match, relevant_match) threshold for a category.

    Resolution order (highest priority first):
      1. ``learned_knowledge`` rules whose context includes
         ``"threshold_adjustments"`` (user-driven: requires an active
         rule before the override is honoured).
      2. ``threshold_overrides.yaml`` per-category entry.
      3. ``default`` entry in the YAML.
      4. Built-in fallback (0.80, 0.60).
    """
    from app.feature.feature_up_cv.scoring._scores._shared import (
        SCORING_CONFIG,
    )

    perfect = float(SCORING_CONFIG.PERFECT_MATCH_THRESHOLD)
    relevant = float(SCORING_CONFIG.RELEVANT_MATCH_THRESHOLD)
    active = False

    if learned_knowledge:
        rules = learned_knowledge.get("rules") or []
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            ctx = rule.get("context") or {}
            if not isinstance(ctx, dict):
                continue
            ta = ctx.get("threshold_adjustments")
            if not isinstance(ta, dict):
                continue
            active = True
            cat_overrides = ta.get(category) or ta.get("default") or {}
            if isinstance(cat_overrides, dict):
                p = _clamp(cat_overrides.get("perfect_match"))
                r = _clamp(cat_overrides.get("relevant_match"))
                if p is not None:
                    perfect = p
                if r is not None:
                    relevant = r

    if not active:
        try:
            data = get_threshold_manager().load_overrides()
            cat_entry = data.get(category) or data.get("default") or {}
            if isinstance(cat_entry, dict):
                p = _clamp(cat_entry.get("perfect_match"))
                r = _clamp(cat_entry.get("relevant_match"))
                if p is not None:
                    perfect = p
                if r is not None:
                    relevant = r
        except Exception as e:
            logger.debug("resolve_threshold fallback: %s", e)

    return perfect, relevant
