# -*- coding: utf-8 -*-
"""
FAISS Index Manager - Semantic vector search for CV-JD matching.
Maintains separate indexes for CVs and JDs with persistent storage on disk.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

from app.feature.feature_up_cv.vector_search.embedding_service import get_embedding_service, EMBEDDING_DIM


class FAISSIndexManager:
    """
    Manages FAISS indexes for semantic similarity search between CVs and JDs.

    We maintain:
    - One CV index (all user CV embeddings) for JD→CV search
    - One JD index (all job description embeddings) for CV→JD search
    """

    INDEX_TYPE_CV = "cv"
    INDEX_TYPE_JD = "jd"

    def __init__(self, index_dir: Optional[Path] = None):
        self.embedder = get_embedding_service()

        if index_dir is None:
            from app.feature.feature_up_cv.core.file_storage import FAISS_INDEX_DIR
            index_dir = FAISS_INDEX_DIR

        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)  # safety net

        self._cv_index: Optional[object] = None
        self._jd_index: Optional[object] = None
        self._cv_meta: Dict[int, dict] = {}
        self._jd_meta: Dict[int, dict] = {}
        self._cv_meta_path = self.index_dir / "cv_meta.json"
        self._jd_meta_path = self.index_dir / "jd_meta.json"
        self._cv_id_map_path = self.index_dir / "cv_id_map.json"
        self._jd_id_map_path = self.index_dir / "jd_id_map.json"

    # ── Index persistence ────────────────────────────────────────────────────

    def _save_index(self, index_type: str) -> None:
        index = self._get_index(index_type)
        if index is None:
            return
        path = self.index_dir / f"{index_type}_index.faiss"
        faiss.write_index(index, str(path))
        print(f"[FAISS] Saved {index_type} index to {path}")

    def _load_index(self, index_type: str) -> Optional[object]:
        if not FAISS_AVAILABLE:
            return None
        path = self.index_dir / f"{index_type}_index.faiss"
        if not path.exists():
            return None
        index = faiss.read_index(str(path))
        return index

    def _save_meta(self, index_type: str) -> None:
        meta = self._get_meta(index_type)
        path = self._cv_meta_path if index_type == self.INDEX_TYPE_CV else self._jd_meta_path
        with open(path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    def _load_meta(self, index_type: str) -> Dict[int, dict]:
        path = self._cv_meta_path if index_type == self.INDEX_TYPE_CV else self._jd_meta_path
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
                return {int(k): v for k, v in raw.items()}
        except (json.JSONDecodeError, ValueError):
            return {}

    def _get_index(self, index_type: str) -> Optional[object]:
        if not FAISS_AVAILABLE:
            return None
        if index_type == self.INDEX_TYPE_CV:
            if self._cv_index is None:
                self._cv_index = self._load_index(index_type)
            return self._cv_index
        else:
            if self._jd_index is None:
                self._jd_index = self._load_index(index_type)
            return self._jd_index

    def _get_meta(self, index_type: str) -> Dict[int, dict]:
        if index_type == self.INDEX_TYPE_CV:
            if not self._cv_meta:
                self._cv_meta = self._load_meta(index_type)
            return self._cv_meta
        else:
            if not self._jd_meta:
                self._jd_meta = self._load_meta(index_type)
            return self._jd_meta

    def _init_index(self, index_type: str) -> object:
        index = faiss.IndexFlatIP(EMBEDDING_DIM)
        return index

    def _get_or_init_index(self, index_type: str) -> object:
        idx = self._get_index(index_type)
        if idx is None:
            idx = self._init_index(index_type)
            if index_type == self.INDEX_TYPE_CV:
                self._cv_index = idx
            else:
                self._jd_index = idx
        return idx

    # ── Public API ───────────────────────────────────────────────────────────

    def add_cv(self, cv_id: int, embedding: np.ndarray, metadata: dict) -> None:
        if not FAISS_AVAILABLE:
            return
        idx = self._get_or_init_index(self.INDEX_TYPE_CV)

        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        embedding = embedding.reshape(1, -1).astype(np.float32)
        idx.add(embedding)

        meta = self._get_meta(self.INDEX_TYPE_CV)
        meta[int(cv_id)] = metadata
        self._save_index(self.INDEX_TYPE_CV)
        self._save_meta(self.INDEX_TYPE_CV)
        print(f"[FAISS] Added CV id={cv_id} to index (total={idx.ntotal})")

    def add_jd(self, jd_id: int, embedding: np.ndarray, metadata: dict) -> None:
        if not FAISS_AVAILABLE:
            return
        idx = self._get_or_init_index(self.INDEX_TYPE_JD)

        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        embedding = embedding.reshape(1, -1).astype(np.float32)
        idx.add(embedding)

        meta = self._get_meta(self.INDEX_TYPE_JD)
        meta[int(jd_id)] = metadata
        self._save_index(self.INDEX_TYPE_JD)
        self._save_meta(self.INDEX_TYPE_JD)
        print(f"[FAISS] Added JD id={jd_id} to index (total={idx.ntotal})")

    def search_jd_to_cv(self, jd_embedding: np.ndarray, top_k: int = 5) -> List[Tuple[int, float, dict]]:
        if not FAISS_AVAILABLE:
            return []
        idx = self._get_index(self.INDEX_TYPE_CV)
        if idx is None or idx.ntotal == 0:
            return []

        norm = np.linalg.norm(jd_embedding)
        if norm > 0:
            jd_embedding = jd_embedding / norm
        jd_embedding = jd_embedding.reshape(1, -1).astype(np.float32)

        scores, indices = idx.search(jd_embedding, min(top_k, idx.ntotal))

        meta = self._get_meta(self.INDEX_TYPE_CV)
        results = []
        for score, raw_idx in zip(scores[0], indices[0]):
            if raw_idx < 0:
                continue
            cv_id = raw_idx
            results.append((int(cv_id), float(score), meta.get(int(cv_id), {})))

        return results

    def search_cv_to_jd(self, cv_embedding: np.ndarray, top_k: int = 5) -> List[Tuple[int, float, dict]]:
        if not FAISS_AVAILABLE:
            return []
        idx = self._get_index(self.INDEX_TYPE_JD)
        if idx is None or idx.ntotal == 0:
            return []

        norm = np.linalg.norm(cv_embedding)
        if norm > 0:
            cv_embedding = cv_embedding / norm
        cv_embedding = cv_embedding.reshape(1, -1).astype(np.float32)

        scores, indices = idx.search(cv_embedding, min(top_k, idx.ntotal))

        meta = self._get_meta(self.INDEX_TYPE_JD)
        results = []
        for score, raw_idx in zip(scores[0], indices[0]):
            if raw_idx < 0:
                continue
            jd_id = raw_idx
            results.append((int(jd_id), float(score), meta.get(int(jd_id), {})))

        return results

    def remove_cv(self, cv_id: int) -> bool:
        print(f"[FAISS] Remove CV id={cv_id} - Note: IndexFlatIP does not support removal, recommend rebuilding")
        return False

    def remove_jd(self, jd_id: int) -> bool:
        print(f"[FAISS] Remove JD id={jd_id} - Note: IndexFlatIP does not support removal, recommend rebuilding")
        return False

    def get_index_stats(self) -> dict:
        cv_idx = self._get_index(self.INDEX_TYPE_CV)
        jd_idx = self._get_index(self.INDEX_TYPE_JD)
        return {
            "cv_index_count": int(cv_idx.ntotal) if cv_idx else 0,
            "jd_index_count": int(jd_idx.ntotal) if jd_idx else 0,
            "cv_meta_count": len(self._get_meta(self.INDEX_TYPE_CV)),
            "jd_meta_count": len(self._get_meta(self.INDEX_TYPE_JD)),
            "faiss_available": FAISS_AVAILABLE,
        }

    def rebuild_index(self, index_type: str, id_embedding_pairs: List[Tuple[int, np.ndarray, dict]]) -> None:
        if not FAISS_AVAILABLE:
            return
        idx = self._init_index(index_type)

        embeddings = []
        for record_id, embedding, _ in id_embedding_pairs:
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            embeddings.append(embedding.astype(np.float32))

        if embeddings:
            idx.add(np.stack(embeddings))

        if index_type == self.INDEX_TYPE_CV:
            self._cv_index = idx
            self._cv_meta = {int(rid): meta for rid, _, meta in id_embedding_pairs}
        else:
            self._jd_index = idx
            self._jd_meta = {int(rid): meta for rid, _, meta in id_embedding_pairs}

        self._save_index(index_type)
        self._save_meta(index_type)
        print(f"[FAISS] Rebuilt {index_type} index with {len(id_embedding_pairs)} entries")


_faiss_manager: Optional[FAISSIndexManager] = None


def get_faiss_manager() -> FAISSIndexManager:
    global _faiss_manager
    if _faiss_manager is None:
        _faiss_manager = FAISSIndexManager()
    return _faiss_manager
