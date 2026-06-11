# app/core/ml_models.py
from functools import lru_cache
from app.feature.conversation.service.hallucination_guard import HallucinationGuard

@lru_cache(maxsize=1)
def get_hallucination_guard() -> HallucinationGuard:
    """Load model 1 lần duy nhất khi app start"""
    return HallucinationGuard()