"""
AgentKnowledgeMemory — FAISS-backed memory for the Feedback Agent.

When the agent extracts a ``learned_rule`` from a valid complaint, we
embed the rule and store it in a small dedicated FAISS index. Future
scoring calls can search this index for similar rules and feed them
into ``apply_learned_rules`` (the rules engine already accepts
``learned_knowledge["rules"]``).

Storage layout (next to the CV/JD FAISS indexes):

    storage/faiss_indexes/agent_rules.faiss
    storage/faiss_indexes/agent_rules_meta.json

The module degrades gracefully when FAISS isn't available - writes
become no-ops and search returns an empty list.
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

try:
    from app.feature.feature_up_cv.vector_search.embedding_service import (
        EMBEDDING_DIM,
        get_embedding_service,
    )
except ImportError:
    EMBEDDING_DIM = 768
    get_embedding_service = None  # type: ignore

logger = logging.getLogger(__name__)


class AgentKnowledgeMemory:
    """Thread-safe FAISS index for learned rules."""

    INDEX_FILENAME = "agent_rules.faiss"
    META_FILENAME = "agent_rules_meta.json"

    def __init__(self, index_dir: Optional[Path] = None) -> None:
        if index_dir is None:
            from app.feature.feature_up_cv.core.file_storage import FAISS_INDEX_DIR

            index_dir = FAISS_INDEX_DIR
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.index_dir / self.INDEX_FILENAME
        self._meta_path = self.index_dir / self.META_FILENAME
        self._index = None
        self._meta: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    # ── Persistence helpers ───────────────────────────────────────────────
    def _load(self):
        if not FAISS_AVAILABLE:
            return
        if self._index_path.exists():
            try:
                self._index = faiss.read_index(str(self._index_path))
            except Exception as e:
                logger.warning("[AgentMemory] failed to read index: %s", e)
                self._index = None
        if self._meta_path.exists():
            try:
                with self._meta_path.open("r", encoding="utf-8") as fh:
                    self._meta = json.load(fh) or []
            except Exception as e:
                logger.warning("[AgentMemory] failed to read meta: %s", e)
                self._meta = []
        if self._index is None and FAISS_AVAILABLE:
            self._index = faiss.IndexFlatIP(EMBEDDING_DIM)
            logger.info("[AgentMemory] created new empty index")

    def _save(self) -> None:
        if not FAISS_AVAILABLE or self._index is None:
            return
        try:
            faiss.write_index(self._index, str(self._index_path))
        except Exception as e:
            logger.warning("[AgentMemory] failed to save index: %s", e)
        try:
            with self._meta_path.open("w", encoding="utf-8") as fh:
                json.dump(self._meta, fh, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("[AgentMemory] failed to save meta: %s", e)

    # ── Public API ────────────────────────────────────────────────────────
    def add_learned_rule(
        self,
        rule_text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """
        Embed ``rule_text`` and append it to the index.

        Returns the position (row id) of the new rule, or None on
        failure (no embedding service / no FAISS).
        """
        if not rule_text or not rule_text.strip():
            return None
        if not FAISS_AVAILABLE or get_embedding_service is None:
            logger.warning(
                "[AgentMemory] FAISS or embedder unavailable; rule not stored"
            )
            return None

        try:
            embedder = get_embedding_service()
            emb = embedder.encode(rule_text)
        except Exception as e:
            logger.error("[AgentMemory] embedding failed: %s", e)
            return None

        emb = np.asarray(emb, dtype=np.float32).reshape(1, -1)
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm

        with self._lock:
            self._load()  # lazy init
            if self._index is None:
                self._index = faiss.IndexFlatIP(EMBEDDING_DIM)
            self._index.add(emb)
            row_id = self._index.ntotal - 1
            entry = {
                "id": row_id,
                "rule": rule_text,
                "context": context or {},
            }
            self._meta.append(entry)
            self._save()
        logger.info(
            "[AgentMemory] stored rule #%d (total=%d)",
            row_id,
            self._index.ntotal,
        )
        return row_id

    def search_similar_rules(
        self,
        query: str,
        k: int = 3,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Return up to k rules semantically similar to ``query``.

        Each item is ``(rule_entry, similarity_score)``. The score is
        in [-1, 1] for ``IndexFlatIP`` with normalised vectors (so it
        is effectively in [0, 1]).
        """
        if not FAISS_AVAILABLE or get_embedding_service is None:
            return []
        if not query or not query.strip():
            return []

        with self._lock:
            self._load()
            if self._index is None or self._index.ntotal == 0:
                return []

        try:
            embedder = get_embedding_service()
            emb = embedder.encode(query)
        except Exception as e:
            logger.error("[AgentMemory] query embed failed: %s", e)
            return []

        emb = np.asarray(emb, dtype=np.float32).reshape(1, -1)
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm

        with self._lock:
            k = min(k, self._index.ntotal)
            scores, indices = self._index.search(emb, k)

        results: List[Tuple[Dict[str, Any], float]] = []
        for score, raw_idx in zip(scores[0], indices[0]):
            if raw_idx < 0:
                continue
            entry = next(
                (m for m in self._meta if m.get("id") == int(raw_idx)),
                None,
            )
            if entry is not None:
                results.append((entry, float(score)))
        return results

    def get_learned_knowledge(self) -> Dict[str, Any]:
        """
        Return the full list of stored rules in the format expected by
        ``apply_learned_rules`` (i.e. ``{"rules": [...]}``).
        """
        with self._lock:
            self._load()
            rules = [m.get("rule", "") for m in self._meta if m.get("rule")]
        return {"rules": rules}

    def get_learned_knowledge_structured(self) -> Dict[str, Any]:
        """
        Like ``get_learned_knowledge`` but each entry is a dict that
        contains BOTH the text rule AND any ``structured_rule`` payload
        stored in context (Hướng 3).

        Output schema::

            {
                "rules": [
                    {"rule": "...text...", "structured_rule": {...} | None,
                     "context": {...}},
                    ...
                ]
            }
        """
        with self._lock:
            self._load()
            entries: List[Dict[str, Any]] = []
            for m in self._meta:
                if not m.get("rule"):
                    continue
                ctx = m.get("context") or {}
                entries.append(
                    {
                        "rule": m.get("rule", ""),
                        "structured_rule": ctx.get("structured_rule"),
                        "context": ctx,
                    }
                )
        return {"rules": entries}

    def count(self) -> int:
        with self._lock:
            self._load()
            return int(self._index.ntotal) if self._index is not None else 0


# ── Module-level singleton ────────────────────────────────────────────────
_memory: Optional[AgentKnowledgeMemory] = None
_memory_lock = threading.Lock()


def get_agent_memory() -> AgentKnowledgeMemory:
    global _memory
    if _memory is None:
        with _memory_lock:
            if _memory is None:
                _memory = AgentKnowledgeMemory()
    return _memory
