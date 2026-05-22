from typing import List

try:
    from sentence_transformers import CrossEncoder
    _HAVE_CE = True
except Exception:
    _HAVE_CE = False

from app.feature.feature_up_cv.vector_search.embedding_service import get_embedding_service


class CrossEncoderReranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self.model = None
        if _HAVE_CE:
            try:
                self.model = CrossEncoder(model_name, device=device)
            except Exception as e:
                self.model = None

    def score(self, query: str, candidates: List[str]) -> List[float]:
        if not candidates:
            return []
        if self.model is not None:
            pairs = [(query, c) for c in candidates]
            scores = self.model.predict(pairs, convert_to_numpy=True)
            # Normalize raw cross-encoder scores into [0,1] via a sigmoid.
            try:
                import numpy as _np
                arr = _np.asarray(scores, dtype=float)
                norm = 1.0 / (1.0 + _np.exp(-arr))
                return [float(x) for x in norm]
            except Exception:
                return [float(s) for s in scores]

        # Fallback: use embedding dot-product similarity
        es = get_embedding_service()
        q_vec = es.encode(query)
        c_vecs = es.encode_batch(candidates)
        scores = []
        import numpy as _np
        for v in c_vecs:
            s = float(_np.dot(q_vec, v) / (_np.linalg.norm(q_vec) * max(1e-9, _np.linalg.norm(v))))
            scores.append(max(0.0, min(1.0, s)))
        return scores
