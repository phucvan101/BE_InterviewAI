import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
import numpy as np

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

from app.feature.feature_up_cv.vector_search.embedding_service import get_embedding_service, EMBEDDING_DIM

logger = logging.getLogger(__name__)

class AgentKnowledgeMemory:
    """
    Manages the Agent's learned rules using FAISS for semantic similarity search.
    """
    def __init__(self):
        self.index_dir = Path("app/feature/feature_up_cv/storage/faiss_indexes")
        self.index_dir.mkdir(parents=True, exist_ok=True)
        
        self.index_path = self.index_dir / "agent_rules.faiss"
        self.meta_path = self.index_dir / "agent_rules_meta.json"
        
        self.embedder = get_embedding_service()
        self.index: Optional[faiss.IndexFlatIP] = None
        self.rules_meta: List[Dict] = []
        
        self._load()

    def _load(self):
        # Load meta
        if self.meta_path.exists():
            try:
                with open(self.meta_path, 'r', encoding='utf-8') as f:
                    self.rules_meta = json.load(f)
            except Exception as e:
                logger.error(f"[AgentMemory] Failed to load meta: {e}")
                self.rules_meta = []
        
        # Load index
        if FAISS_AVAILABLE and self.index_path.exists():
            try:
                self.index = faiss.read_index(str(self.index_path))
            except Exception as e:
                logger.error(f"[AgentMemory] Failed to load index: {e}")
                self._init_index()
        else:
            self._init_index()

    def _init_index(self):
        if FAISS_AVAILABLE:
            self.index = faiss.IndexFlatIP(EMBEDDING_DIM)
            # Re-index if meta exists but index failed to load
            if self.rules_meta:
                self._rebuild_index_from_meta()

    def _save(self):
        with open(self.meta_path, 'w', encoding='utf-8') as f:
            json.dump(self.rules_meta, f, ensure_ascii=False, indent=2)
            
        if FAISS_AVAILABLE and self.index is not None:
            faiss.write_index(self.index, str(self.index_path))

    def _rebuild_index_from_meta(self):
        if not FAISS_AVAILABLE:
            return
        logger.info("[AgentMemory] Rebuilding FAISS index from metadata...")
        self.index = faiss.IndexFlatIP(EMBEDDING_DIM)
        if not self.rules_meta:
            return
            
        texts = [r["rule"] for r in self.rules_meta]
        embeddings = self.embedder.encode_batch(texts, normalize=True)
        self.index.add(embeddings)

    def add_learned_rule(self, rule_text: str, context: str = ""):
        """Adds a new rule and indexes it."""
        if not rule_text.strip():
            return
            
        # Avoid exact duplicates
        if any(r["rule"] == rule_text for r in self.rules_meta):
            logger.info(f"[AgentMemory] Rule already exists: {rule_text}")
            return
            
        self.rules_meta.append({
            "rule": rule_text,
            "context": context
        })
        
        if FAISS_AVAILABLE and self.index is not None:
            embedding = self.embedder.encode(rule_text, normalize=True)
            embedding = embedding.reshape(1, -1).astype(np.float32)
            self.index.add(embedding)
            
        self._save()
        logger.info(f"[AgentMemory] Added new learned rule. Total rules: {len(self.rules_meta)}")

    def get_relevant_rules(self, query: str, top_k: int = 3, threshold: float = 0.7) -> List[str]:
        """Searches for relevant rules based on semantic similarity."""
        if not FAISS_AVAILABLE or self.index is None or self.index.ntotal == 0:
            return []
            
        if not query.strip():
            return []

        try:
            query_emb = self.embedder.encode(query, normalize=True)
            query_emb = query_emb.reshape(1, -1).astype(np.float32)
            
            scores, indices = self.index.search(query_emb, min(top_k, self.index.ntotal))
            
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx >= 0 and score >= threshold:
                    if idx < len(self.rules_meta):
                        results.append(self.rules_meta[idx]["rule"])
            
            return results
        except Exception as e:
            logger.error(f"[AgentMemory] Search failed: {e}")
            return []

agent_memory = AgentKnowledgeMemory()
