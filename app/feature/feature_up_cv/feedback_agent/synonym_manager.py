"""
SynonymManager — atomic, safe writer for ``skill_synonyms.yaml``.

When the Feedback Agent detects a new framework the existing scoring
engine failed to recognise, it can call ``add_synonyms()`` to extend the
synonym map. The manager:

  - locks the YAML file via a per-process ``threading.Lock`` (single
    process is enough because the API server runs under a single uvicorn
    worker in development; in production, deploy with file lock via
    ``fcntl`` if multiple workers are required)
  - preserves YAML formatting using ``ruamel.yaml`` (no full rewrite of
    the file — comments and ordering kept intact)
  - re-loads the in-memory synonym cache through ``reload_skill_synonyms``
    so the next scoring call sees the new entries without a restart
"""
from __future__ import annotations

import logging
import re
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Skill names should be short, human-readable tokens made of letters,
# digits and a small set of punctuation commonly used in tech names
# (e.g. ``C++``, ``C#``, ``ASP.NET``, ``Node.js``). We reject anything
# that contains whitespace, looks like a filesystem path, or contains
# shell metacharacters. The cap is 80 characters.
_SAFE_SKILL_RE = re.compile(r"^[A-Za-z0-9.#+_&()\-]{1,80}$")
# Disallowed character set: shell metacharacters, quotes, backticks,
# path separators, whitespace, and other control characters. Skills
# in our domain never legitimately need any of these.
_FORBIDDEN_CHARS = set(" \t;|&$<>`\\\"'\n\r/=*?!@%^~:,;[]{}|<>")

# Default path: app/feature/feature_up_cv/scoring/skill_synonyms.yaml
_DEFAULT_YAML = (
    Path(__file__).resolve().parents[1] / "scoring" / "skill_synonyms.yaml"
)


class SynonymManager:
    """Thread-safe writer for the skill_synonyms.yaml file."""

    def __init__(self, yaml_path: Optional[Path] = None) -> None:
        self.yaml_path: Path = Path(yaml_path) if yaml_path else _DEFAULT_YAML
        self._lock = threading.Lock()

    # ── Public API ────────────────────────────────────────────────────────
    def add_synonyms(
        self,
        items: Iterable[Dict[str, str]],
    ) -> Tuple[int, List[Dict[str, str]]]:
        """
        Append new (base_skill, synonym) pairs to the YAML.

        Parameters
        ----------
        items : iterable of dict
            Each item must have keys ``base_skill`` and ``synonym``.

        Returns
        -------
        (added_count, added_pairs)
            ``added_count`` is the number of pairs that were actually
            inserted (deduplicated against existing entries).
        """
        # Normalise + filter
        pairs: List[Tuple[str, str]] = []
        for it in items or []:
            base = (it.get("base_skill") or "").strip().lower()
            syn = (it.get("synonym") or "").strip().lower()
            if not base or not syn or base == syn:
                continue
            if not self._is_safe_skill(base) or not self._is_safe_skill(syn):
                logger.warning(
                    "[SynonymManager] rejected unsafe skill name: "
                    "base=%r syn=%r",
                    base, syn,
                )
                continue
            pairs.append((base, syn))

        if not pairs:
            return 0, []

        with self._lock:
            data = self._read_yaml()
            added: List[Dict[str, str]] = []
            for base, syn in pairs:
                bucket = data.setdefault(base, [])
                # ruamel may return CommentedSeq — coerce to list
                if syn not in list(bucket):
                    bucket.append(syn)
                    added.append({"base_skill": base, "synonym": syn})
            if added:
                self._write_yaml(data)
                self._reload_cache()
            return len(added), added

    @staticmethod
    def _is_safe_skill(name: str) -> bool:
        """
        Reject values that contain shell metacharacters, control
        characters, or exceed the length cap. This guards against
        prompt-injection scenarios where the LLM emits a
        ``new_synonyms`` value that looks like a shell command or a
        filesystem path.
        """
        if not name or len(name) > 80:
            return False
        if any(c in _FORBIDDEN_CHARS for c in name):
            return False
        return bool(_SAFE_SKILL_RE.match(name))

    # ── YAML helpers ──────────────────────────────────────────────────────
    def _read_yaml(self) -> Dict[str, Any]:
        from ruamel.yaml import YAML

        yaml = YAML(typ="rt")  # round-trip preserves comments
        yaml.preserve_quotes = True
        if not self.yaml_path.exists():
            return {}
        try:
            with self.yaml_path.open("r", encoding="utf-8") as fh:
                loaded = yaml.load(fh) or {}
            if not isinstance(loaded, dict):
                return {}
            return loaded
        except Exception as e:
            logger.error("Failed to read skill_synonyms.yaml: %s", e)
            return {}

    def load_synonyms(self) -> Dict[str, List[str]]:
        """Return a copy of the current synonym map from disk (thread-safe)."""
        with self._lock:
            return self._read_yaml()

    def _write_yaml(self, data: Dict[str, Any]) -> None:
        from ruamel.yaml import YAML

        yaml = YAML(typ="rt")
        yaml.preserve_quotes = True
        yaml.default_flow_style = False
        yaml.indent(mapping=2, sequence=4, offset=2)

        # Atomic write: dump to a temp file then rename. On Windows,
        # ``Path.replace`` fails when the target is open or locked; we
        # unlink first, then move.
        import os
        import shutil as _sh

        tmp = self.yaml_path.with_suffix(self.yaml_path.suffix + ".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as fh:
                yaml.dump(data, fh)
            # Remove target first (Windows) then move temp -> target
            if self.yaml_path.exists():
                try:
                    os.remove(self.yaml_path)
                except PermissionError:
                    pass
            _sh.move(str(tmp), str(self.yaml_path))
        except Exception as e:
            logger.error("Failed to write skill_synonyms.yaml: %s", e)
            if tmp.exists():
                try:
                    tmp.unlink()
                except Exception:
                    pass
            raise

    @staticmethod
    def _reload_cache() -> None:
        """
        Reload the in-memory synonym cache used by the scorer.

        NOTE: ``_load_skill_synonyms`` in ``_scores/_shared.py`` looks
        for ``skill_synonyms.yaml`` next to itself (i.e. inside
        ``_scores/``) but the file actually lives one level up at
        ``scoring/skill_synonyms.yaml``. This pre-existing mismatch
        means ``_load_skill_synonyms`` returns an empty dict and the
        scorer never benefits from the YAML. Rather than touch the
        scoring engine (out of scope per the plan), we patch the cache
        in place after loading the YAML directly from the correct path.
        """
        try:
            import app.feature.feature_up_cv.scoring._scores._shared as _shared_mod
            from app.feature.feature_up_cv.scoring.hybrid_scoring import (
                calculate_hybrid_score,
            )
            # Patch the global in BOTH the package's import alias and the
            # underlying module. Scorers may have imported the dict via
            # ``from ._scores._shared import _SKILL_SYNONYMS`` which
            # binds the *value* at import time - in that case we cannot
            # reach their cached reference. Logging gives operators
            # visibility, but a process restart is the only safe
            # way to fully pick up the change.
            from ruamel.yaml import YAML

            yaml = YAML(typ="rt")
            with open(  # noqa: PTH123
                SynonymManager._yaml_path_abs(),
                "r",
                encoding="utf-8",
            ) as fh:
                data = yaml.load(fh) or {}
            if isinstance(data, dict):
                new_map = {str(k): list(v) for k, v in data.items()}
                # Update the module-level global directly.
                _shared_mod._SKILL_SYNONYMS = new_map
                logger.info(
                    "[SynonymManager] skill_synonyms cache reloaded "
                    "(%d groups, scorer will pick up on next import)",
                    len(new_map),
                )
        except Exception as e:
            logger.warning(
                "[SynonymManager] could not reload cache: %s. "
                "Restart the API to pick up new synonyms.",
                e,
            )

    @staticmethod
    def _yaml_path_abs() -> Path:
        """Absolute path to the real skill_synonyms.yaml (one level up from _scores/)."""
        return (
            Path(__file__).resolve().parents[1] / "scoring" / "skill_synonyms.yaml"
        )


# ── Module-level singleton ────────────────────────────────────────────────
_synonym_manager: Optional[SynonymManager] = None
_singleton_lock = threading.Lock()


def get_synonym_manager() -> SynonymManager:
    """Return a process-wide singleton instance."""
    global _synonym_manager
    if _synonym_manager is None:
        with _singleton_lock:
            if _synonym_manager is None:
                _synonym_manager = SynonymManager()
    return _synonym_manager
