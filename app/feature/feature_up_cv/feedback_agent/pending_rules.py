"""
Phase 7 — Pending rule queue for human-in-the-loop review.

When the LLM proposes a ``CUSTOM_PROPOSED`` rule (Hướng 3) the system
must NOT apply it directly — operators need to review it first.
This module:

  1. Persists each proposed rule to a JSON file
     (``storage/pending_rules/pending_rules.json``) so it survives
     restarts.
  2. Exposes ``approve(id)`` and ``reject(id)`` operations that move
     a rule from ``pending`` to ``approved`` (or remove it).
  3. Exposes ``approved_rules()`` which the rules engine can read on
     next scoring call.

The review process is intentionally simple (no auth, no status codes);
it can be wrapped by a FastAPI endpoint later.
"""
from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_PATH = (
    Path(__file__).resolve().parents[1] / "storage" / "pending_rules" / "pending_rules.json"
)


class PendingRuleStore:
    """Thread-safe JSON file store for proposed rules awaiting review."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path: Path = Path(path) if path else _DEFAULT_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        # Eagerly create the file so consumers don't race the first read.
        if not self.path.exists():
            self._write({"rules": []})

    # ── Internal ────────────────────────────────────────────────
    def _read(self) -> Dict[str, Any]:
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                return json.load(fh) or {"rules": []}
        except Exception as e:
            logger.warning("[PendingRules] read failed: %s", e)
            return {"rules": []}

    def _write(self, data: Dict[str, Any]) -> None:
        import os
        import shutil as _sh

        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
            if self.path.exists():
                try:
                    os.remove(self.path)
                except PermissionError:
                    pass
            _sh.move(str(tmp), str(self.path))
        except Exception as e:
            logger.error("[PendingRules] write failed: %s", e)
            if tmp.exists():
                try:
                    tmp.unlink()
                except Exception:
                    pass
            raise

    # ── Public API ──────────────────────────────────────────────
    def enqueue(
        self,
        rule_payload: Dict[str, Any],
        *,
        proposed_by: str = "agent",
        rationale: str = "",
    ) -> str:
        """
        Append a proposed rule. Returns the assigned id.
        """
        rid = uuid.uuid4().hex[:12]
        with self._lock:
            data = self._read()
            data["rules"].append(
                {
                    "id": rid,
                    "status": "pending",
                    "rule": rule_payload,
                    "proposed_by": proposed_by,
                    "rationale": rationale,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "decided_at": None,
                }
            )
            self._write(data)
        logger.info("[PendingRules] enqueued id=%s by=%s", rid, proposed_by)
        return rid

    def list_pending(self) -> List[Dict[str, Any]]:
        with self._lock:
            data = self._read()
        return [r for r in data["rules"] if r.get("status") == "pending"]

    def list_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            data = self._read()
        return list(data["rules"])

    def approve(self, rule_id: str, reviewer: str = "operator") -> Optional[Dict[str, Any]]:
        with self._lock:
            data = self._read()
            for r in data["rules"]:
                if r["id"] == rule_id and r["status"] == "pending":
                    r["status"] = "approved"
                    r["decided_at"] = datetime.now(timezone.utc).isoformat()
                    r["reviewer"] = reviewer
                    self._write(data)
                    return r
        return None

    def reject(self, rule_id: str, reviewer: str = "operator") -> Optional[Dict[str, Any]]:
        with self._lock:
            data = self._read()
            for r in data["rules"]:
                if r["id"] == rule_id and r["status"] == "pending":
                    r["status"] = "rejected"
                    r["decided_at"] = datetime.now(timezone.utc).isoformat()
                    r["reviewer"] = reviewer
                    self._write(data)
                    return r
        return None

    def approved_rules(self) -> List[Dict[str, Any]]:
        """Return payloads of approved rules in insertion order."""
        with self._lock:
            data = self._read()
        return [r["rule"] for r in data["rules"] if r.get("status") == "approved"]

    def count(self) -> Dict[str, int]:
        with self._lock:
            data = self._read()
        out: Dict[str, int] = {"pending": 0, "approved": 0, "rejected": 0}
        for r in data["rules"]:
            s = r.get("status")
            if s in out:
                out[s] += 1
        return out


# ── Module-level singleton ──────────────────────────────────────
_store: Optional[PendingRuleStore] = None
_singleton_lock = threading.Lock()


def get_pending_rule_store() -> PendingRuleStore:
    global _store
    if _store is None:
        with _singleton_lock:
            if _store is None:
                _store = PendingRuleStore()
    return _store
