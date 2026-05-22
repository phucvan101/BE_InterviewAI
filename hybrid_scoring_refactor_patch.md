# Hybrid Scoring Refactor Patch

## Các vấn đề chính đã được fix

### 1. Centralized Config
Thay vì hardcode threshold/cap ở nhiều nơi:

```python
raw_total = min(raw_total, 30.0)
raw_total = min(raw_total, 25.0)
raw_total = min(raw_total, 35.0)
```

Refactor thành:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ScoringConfig:
    EXPERIENCE_WEIGHT: float = 50.0
    SKILLS_WEIGHT: float = 30.0
    EDUCATION_WEIGHT: float = 10.0
    CAREER_WEIGHT: float = 10.0

    SEMANTIC_MATCH_THRESHOLD: float = 0.80
    RELATED_MATCH_THRESHOLD: float = 0.62

    UNDERQUALIFIED_CAP: float = 30.0
    SEVERE_GAP_CAP: float = 25.0
    SPECIALIZATION_MISMATCH_CAP: float = 35.0

SCORING_CONFIG = ScoringConfig()
```

---

## 2. Reusable Cap Helper

Thêm helper:

```python
def _safe_cap(value: float, cap: float) -> float:
    return min(value, cap)
```

Thay:

```python
raw_total = min(raw_total, 30.0)
```

bằng:

```python
raw_total = _safe_cap(
    raw_total,
    SCORING_CONFIG.UNDERQUALIFIED_CAP
)
```

---

## 3. Feature-based Architecture Foundation

Thêm:

```python
def _build_experience_features(
    all_exp_years: float,
    years_req: float,
    skill_overlap: float,
    domain_penalty: float,
    seniority_gap: int,
):
    return {
        "years_ratio": round(all_exp_years / max(years_req, 1.0), 4),
        "skill_overlap": round(skill_overlap, 4),
        "domain_penalty": round(domain_penalty, 4),
        "seniority_gap": seniority_gap,
    }
```

Mục tiêu:
- giảm rule stacking
- dễ tuning
- dễ debug
- chuẩn bị cho learning-to-rank sau này

---

## 4. Những phần mình khuyên refactor tiếp

### A. Tách riêng:

```text
feature extraction
scoring
explanation
reranking
```

---

### B. Skill ontology

Hiện tại:

```python
_SKILL_SYNONYMS
```

sẽ rất khó maintain khi scale.

Nên chuyển sang:
- YAML
- DB
- ontology graph

---

### C. LLM reranker

Pipeline nên là:

```text
embedding retrieval
→ hybrid scoring
→ LLM reranker
→ final score
```

---

## 5. Những điểm mạnh hiện tại của code

### Đã làm tốt:

- E5 query/passage prefix
- embedding calibration
- anti false-positive
- intern/fresher handling
- semantic criteria matching
- hybrid exact + semantic matching
- domain-aware scoring

---

## 6. Refactor quan trọng nhất

Hiện tại file đang:

```text
business logic + heuristics + configs + ranking
```

trộn chung.

Nên tách:

```text
/config
/features
/scoring
/reranking
/explanations
```

thì hệ thống sẽ dễ maintain hơn rất nhiều.

---

## 7. Recommendation kiến trúc production

### Current

```text
CV → Embedding → Rules → Score
```

### Better

```text
CV
 → feature extraction
 → semantic retrieval
 → hybrid scoring
 → LLM reranking
 → explanation engine
 → final ranking
```

---

## 8. Những hardcoded rules nên giảm dần

Ví dụ:

```python
if domain_penalty >= 0.7:
```

nên chuyển thành:

```python
if features["domain_penalty"] >= CONFIG.DOMAIN_SEVERE:
```

vì:
- dễ tune
- dễ AB testing
- dễ logging
- dễ explain.

