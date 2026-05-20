# -*- coding: utf-8 -*-
"""
Embedding Service - Sentence Transformers for semantic similarity
Uses all-MiniLM-L6-v2 model for efficient, high-quality embeddings.
"""

import os
from pathlib import Path
from typing import List, Optional

import numpy as np

from app.feature.feature_up_cv.core.file_storage import EMBEDDINGS_CACHE_DIR as _EMBEDDINGS_CACHE_DIR

# Lazy-load model to avoid heavy import at startup
_model = None
_model_name = "intfloat/multilingual-e5-base"
EMBEDDING_DIM = 768


def _get_cache_dir() -> Path:
    # Directory is guaranteed to exist: file_storage creates it at import time.
    return _EMBEDDINGS_CACHE_DIR


def _load_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        print(f"[EMBEDDING] Loading model: {_model_name}")
        _model = SentenceTransformer(_model_name)
        print(f"[EMBEDDING] Model loaded successfully (dim={EMBEDDING_DIM})")
    return _model


class EmbeddingService:
    def __init__(self, model_name: str = _model_name):
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:
            self._model = _load_model()
        return self._model

    def encode(self, text: str, normalize: bool = True) -> np.ndarray:
        vec = self.model.encode(
            text,
            normalize_embeddings=normalize,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return vec.astype(np.float32)

    def encode_batch(self, texts: List[str], normalize: bool = True) -> np.ndarray:
        if not texts:
            return np.array([], dtype=np.float32)
        vecs = self.model.encode(
            texts,
            normalize_embeddings=normalize,
            show_progress_bar=False,
            convert_to_numpy=True,
            batch_size=32,
        )
        return vecs.astype(np.float32)

    def compute_similarity(self, vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        if normalize := np.linalg.norm(vec_a) > 0:
            vec_a = vec_a / np.linalg.norm(vec_a)
        if np.linalg.norm(vec_b) > 0:
            vec_b = vec_b / np.linalg.norm(vec_b)
        sim = float(np.dot(vec_a, vec_b))
        return max(0.0, min(1.0, sim))

    def save_vector(self, vector: np.ndarray, record_id: int, file_type: str) -> Path:
        cache_dir = _get_cache_dir()
        file_path = cache_dir / f"{file_type}_vector_{record_id}.npy"
        np.save(file_path, vector)
        return file_path

    def load_vector(self, file_path: str) -> Optional[np.ndarray]:
        p = Path(file_path)
        if not p.exists():
            return None
        return np.load(p).astype(np.float32)

    def vector_exists(self, record_id: int, file_type: str) -> bool:
        cache_dir = _get_cache_dir()
        return (cache_dir / f"{file_type}_vector_{record_id}.npy").exists()

    def encode_skills_text(self, skills: List[str]) -> str:
        text = " ".join(skills) if skills else ""
        return f"passage: {text}" if text else ""

    def encode_structured_cv(self, cv_data: dict) -> str:
        parts = []

        if name := cv_data.get("personal_info", {}).get("name"):
            parts.append(f"Tên: {name}")

        if objective := cv_data.get("objective"):
            parts.append(f"Mục tiêu: {objective}")

        if career_obj := cv_data.get("career_objectives"):
            parts.append(f"Mục tiêu nghề nghiệp: {career_obj}")

        if skills := cv_data.get("skills"):
            parts.append(f"Kỹ năng: {' '.join(skills)}")

        for exp in cv_data.get("work_experience", []):
            title = exp.get("title", "")
            company = exp.get("company", "")
            highlights = " ".join(exp.get("highlights", []))
            if title or company or highlights:
                parts.append(f"Kinh nghiệm: {title} tại {company}. {highlights}")

        for edu in cv_data.get("education", []):
            degree = edu.get("degree", "")
            major = edu.get("major", "")
            school = edu.get("school", "")
            if degree or major or school:
                parts.append(f"Học vấn: {degree} {major} tại {school}")

        for proj in cv_data.get("projects", []):
            name = proj.get("name", "")
            desc = proj.get("description", "")
            techs = " ".join(proj.get("technologies", []))
            if name or desc:
                parts.append(f"Dự án: {name}. {desc} Công nghệ: {techs}")

        return "passage: " + " . ".join(parts)

    def encode_structured_jd(self, jd_data: dict) -> str:
        parts = []

        if title := (jd_data.get("job_title") or (jd_data.get("structured", {}) or {}).get("job_title")):
            parts.append(f"Vị trí: {title}")

        jd_struct = jd_data.get("structured", jd_data)

        if responsibilities := jd_struct.get("responsibilities"):
            parts.append(f"Nhiệm vụ: {' '.join(responsibilities)}")

        if requirements := jd_struct.get("requirements"):
            parts.append(f"Yêu cầu: {' '.join(requirements)}")

        if skills_req := jd_struct.get("skills_required"):
            parts.append(f"Kỹ năng bắt buộc: {' '.join(skills_req)}")
        if skills_pref := jd_struct.get("skills_preferred"):
            parts.append(f"Kỹ năng ưu tiên: {' '.join(skills_pref)}")

        if seniority := jd_struct.get("seniority"):
            parts.append(f"Cấp bậc: {seniority}")
        if years := jd_struct.get("years_of_experience"):
            parts.append(f"Số năm kinh nghiệm: {years}")

        if benefits := jd_struct.get("benefits"):
            parts.append(f"Phúc lợi: {' '.join(benefits)}")

        if career_exp := jd_struct.get("career_expectations"):
            parts.append(f"Định hướng nghề nghiệp: {career_exp}")

        if keywords := jd_struct.get("keywords"):
            parts.append(f"Từ khóa: {' '.join(keywords)}")

        return "query: " + " . ".join(parts)


_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
