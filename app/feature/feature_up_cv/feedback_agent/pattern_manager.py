"""
PatternManager — atomic, safe writer for ``skill_patterns.yaml``.

Complements ``SynonymManager``: while synonyms are 1-to-1 token mapping,
patterns handle two cases learned from user feedback that pure synonym
lookup cannot solve:

  1. **compound_skills** — a skill is recognised only when ALL tokens
     appear in CV evidence. Example: "react" + "typescript" together
     should count as a stronger "react-typescript" match.
  2. **context_phrases** — a free-text phrase in CV work experience
     should count as evidence for a specific skill_key. Useful for
     Vietnamese CVs that describe skills in natural language.

This module mirrors ``SynonymManager``:
  - per-process ``threading.Lock``
  - atomic write via temp file + rename (Windows-safe)
  - preserves YAML comments using ``ruamel.yaml``
  - rejects unsafe tokens (same regex as ``SynonymManager._is_safe_skill``)
"""
from __future__ import annotations

import logging
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Reuse the safety regex from SynonymManager semantics; tokens and phrases
# have slightly different allowed characters (phrases may contain spaces).
_TOKEN_SAFE_RE = re.compile(r"^[A-Za-z0-9.#+_&()\-]{1,80}$")
_FORBIDDEN_TOKENS = set(";|&$<>`\\\"'\n\r/=*?!@%^~:,;[]{}|<>")
# Phrase safety: allow internal spaces and accented Vietnamese letters.
# We still forbid shell metacharacters, control chars, and quotes.
_PHRASE_SAFE_RE = re.compile(r"^[A-Za-zÀ-ỹ0-9 .#+\-_/()]{2,120}$")

_DEFAULT_YAML = (
    Path(__file__).resolve().parents[1] / "scoring" / "skill_patterns.yaml"
)


class PatternManager:
    """Thread-safe writer for the skill_patterns.yaml file."""

    def __init__(self, yaml_path: Optional[Path] = None) -> None:
        self.yaml_path: Path = Path(yaml_path) if yaml_path else _DEFAULT_YAML
        self._lock = threading.Lock()

    # ── Public API ────────────────────────────────────────────────
    def add_patterns(
        self,
        patterns: List[Dict[str, Any]],
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Append new patterns (compound_skills or context_phrases) to YAML.

        Each pattern dict must have a ``type`` key in
        ``{"compound_skill", "context_phrase"}`` and the relevant fields:

          * ``compound_skill`` → ``{"type": "compound_skill", "tokens": [...], "key": "..."}``
          * ``context_phrase`` → ``{"type": "context_phrase", "phrase": "...", "maps_to": "..."}``

        Returns ``(added_count, added_patterns)`` where each entry in
        ``added_patterns`` is the normalised form.
        """
        normalised: List[Dict[str, Any]] = []
        for p in patterns or []:
            entry = self._normalise(p)
            if entry is None:
                continue
            normalised.append(entry)

        if not normalised:
            return 0, []

        with self._lock:
            data = self._read_yaml()
            added: List[Dict[str, Any]] = []

            for entry in normalised:
                if entry["type"] == "compound_skill":
                    bucket = data.setdefault("compound_skills", [])
                    if not self._compound_exists(bucket, entry):
                        bucket.append(
                            {
                                "tokens": entry["tokens"],
                                "key": entry["key"],
                                "reason": entry.get("reason", ""),
                            }
                        )
                        added.append(entry)
                else:  # context_phrase
                    bucket = data.setdefault("context_phrases", [])
                    if not self._phrase_exists(bucket, entry):
                        bucket.append(
                            {
                                "phrase": entry["phrase"],
                                "maps_to": entry["maps_to"],
                                "reason": entry.get("reason", ""),
                            }
                        )
                        added.append(entry)

            if added:
                self._write_yaml(data)
            return len(added), added

    def load_patterns(self) -> Dict[str, List[Dict[str, Any]]]:
        """Return the in-memory pattern data, defaulting to empty buckets."""
        with self._lock:
            data = self._read_yaml()
        return {
            "compound_skills": list(data.get("compound_skills", []) or []),
            "context_phrases": list(data.get("context_phrases", []) or []),
        }

    @staticmethod
    def _normalise(p: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validate and normalise a single pattern dict."""
        ptype = (p.get("type") or "").strip().lower()
        if ptype == "compound_skill":
            tokens_raw = p.get("tokens") or []
            if not isinstance(tokens_raw, list) or len(tokens_raw) < 2:
                return None
            tokens = [
                str(t).strip().lower()
                for t in tokens_raw
                if isinstance(t, (str, int)) and str(t).strip()
            ]
            if len(tokens) < 2:
                return None
            key = (p.get("key") or "").strip().lower()
            if not key or not _TOKEN_SAFE_RE.match(key):
                logger.warning(
                    "[PatternManager] rejected unsafe key: %r", key
                )
                return None
            for t in tokens:
                if not _TOKEN_SAFE_RE.match(t):
                    logger.warning(
                        "[PatternManager] rejected unsafe token: %r", t
                    )
                    return None
            return {
                "type": "compound_skill",
                "tokens": tokens,
                "key": key,
                "reason": str(p.get("reason") or "").strip(),
            }

        if ptype == "context_phrase":
            phrase = (p.get("phrase") or "").strip().lower()
            maps_to = (p.get("maps_to") or "").strip().lower()
            if not phrase or not _PHRASE_SAFE_RE.match(phrase):
                logger.warning(
                    "[PatternManager] rejected unsafe phrase: %r", phrase
                )
                return None
            if not maps_to or not _TOKEN_SAFE_RE.match(maps_to):
                logger.warning(
                    "[PatternManager] rejected unsafe maps_to: %r", maps_to
                )
                return None
            if any(c in _FORBIDDEN_TOKENS for c in phrase):
                logger.warning(
                    "[PatternManager] phrase has forbidden chars: %r", phrase
                )
                return None
            return {
                "type": "context_phrase",
                "phrase": phrase,
                "maps_to": maps_to,
                "reason": str(p.get("reason") or "").strip(),
            }

        logger.warning("[PatternManager] unknown pattern type: %r", ptype)
        return None

    @staticmethod
    def _compound_exists(
        bucket: List[Dict[str, Any]], entry: Dict[str, Any]
    ) -> bool:
        target = sorted(entry["tokens"])
        for existing in bucket:
            existing_tokens = sorted(
                str(t).strip().lower() for t in existing.get("tokens", [])
            )
            if existing_tokens == target:
                return True
        return False

    @staticmethod
    def _phrase_exists(
        bucket: List[Dict[str, Any]], entry: Dict[str, Any]
    ) -> bool:
        target = entry["phrase"].strip().lower()
        for existing in bucket:
            if str(existing.get("phrase", "")).strip().lower() == target:
                return True
        return False

    # ── YAML helpers ──────────────────────────────────────────────
    def _read_yaml(self) -> Dict[str, Any]:
        from ruamel.yaml import YAML

        yaml = YAML(typ="rt")
        yaml.preserve_quotes = True
        if not self.yaml_path.exists():
            return {"compound_skills": [], "context_phrases": []}
        try:
            with self.yaml_path.open("r", encoding="utf-8") as fh:
                loaded = yaml.load(fh) or {}
            if not isinstance(loaded, dict):
                logger.warning("Pattern YAML root is not a dict; resetting")
                return {"compound_skills": [], "context_phrases": []}
            # Ensure buckets exist
            loaded.setdefault("compound_skills", [])
            loaded.setdefault("context_phrases", [])
            return loaded
        except Exception as e:
            logger.error("Failed to read skill_patterns.yaml: %s", e)
            return {"compound_skills": [], "context_phrases": []}

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
            logger.error("Failed to write skill_patterns.yaml: %s", e)
            if tmp.exists():
                try:
                    tmp.unlink()
                except Exception:
                    pass
            raise


# ── Module-level singleton ────────────────────────────────────────
_pattern_manager: Optional[PatternManager] = None
_singleton_lock = threading.Lock()


def get_pattern_manager() -> PatternManager:
    """Return a process-wide singleton instance."""
    global _pattern_manager
    if _pattern_manager is None:
        with _singleton_lock:
            if _pattern_manager is None:
                _pattern_manager = PatternManager()
    return _pattern_manager
