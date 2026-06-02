# 📊 Báo Cáo Logic Chấm Điểm CV-JD - InterviewAI

**Ngày tạo:** 30/05/2026  
**Phiên bản:** v6 (Enhanced Response)

---

## 📋 Nội Dung

1. [Tổng quan hệ thống chấm điểm](#tổng-quan)
2. [Main Scoring Files](#main-files)
3. [Scoring Components (_scores)](#scoring-components)
4. [Semantic Analysis (_semantic)](#semantic-analysis)

---

## 🎯 Tổng Quan Hệ Thống Chấm Điểm {#tổng-quan}

### Công Thức Chấm Điểm Tổng Hợp

```
Điểm Tổng (0-100) = Exp + Skills + Edu + Career
├─ Experience Score: 0-50 (50%)
├─ Skills Score: 0-30 (30%)
├─ Education Score: 0-10 (10%)
└─ Career Objectives Score: 0-10 (10%)

Company Fit Score: 0-10 (Riêng biệt, không tính vào tổng)
```

**Xác suất thành công = Điểm Tổng / 100**

---

## 📁 Main Scoring Files {#main-files}

### 1️⃣ `cross_encoder_reranker.py`

**Mục đích:** Xác định lại thứ tự (rerank) các ứng viên sử dụng Cross-Encoder model

#### Class: `CrossEncoderReranker`

| Hàm | Chức Năng | Input | Output |
|-----|----------|-------|--------|
| `__init__()` | Khởi tạo model Cross-Encoder | `model_name` (str), `device` (str) | None |
| `score()` | Chấm điểm sự phù hợp giữa query và candidates | `query` (str), `candidates` (List[str]) | `List[float]` (0-1) |

**Chi tiết hàm `score()`:**
- **Input:** Một câu query và danh sách các candidate strings
- **Output:** Mảng điểm từ 0 đến 1 (được normalize qua sigmoid)
- **Logic:**
  - Nếu model Cross-Encoder khả dụng: dùng nó để chấm
  - Fallback: dùng embedding dot-product similarity
  - Normalize scores về [0, 1]

---

### 2️⃣ `hybrid_scoring.py`

**Mục đích:** Orchestrator chính — phối hợp tất cả các module chấm điểm

#### Main Function: `calculate_hybrid_score()`

| Thuộc tính | Chi tiết |
|-----------|---------|
| **Chức năng** | Tính điểm CV-JD tổng hợp với response giàu thông tin |
| **Input** | `cv_data` (dict), `jd_data` (dict), `company_data` (dict), `cv_embedding`, `jd_embedding`, `score_overrides`, `learned_knowledge` |
| **Output** | `dict` chứa tất cả điểm chi tiết, strengths, areas, recommendations |

**Quy trình chính:**

```
1. Domain Detection
   ├─ detect_cv_domain()
   ├─ detect_jd_domain()
   └─ compute_domain_penalty()

2. Individual Scoring
   ├─ score_experience() → 0-50
   ├─ score_skills() → 0-30
   ├─ score_education() → 0-10
   ├─ score_career_objectives() → 0-10
   └─ score_company_fit() → 0-10 (riêng biệt)

3. Apply Score Overrides (nếu có)

4. Build Rich Response
   ├─ Strengths & Areas for Improvement
   ├─ Recommendations & Interview Tips
   ├─ Skills Detail Analysis
   ├─ Domain Analysis
   └─ Metadata & Evidence
```

**Output Response Structure:**
```json
{
  "overall_score": 0-100,
  "summary": "text",
  "detailed_scores": {
    "experience_score": 0-50,
    "skills_total_score": 0-30,
    "education_score": 0-10,
    "career_objectives_score": 0-10,
    "company_fit_score": 0-10
  },
  "score_badges": { "visual_labels" },
  "experience_detail": { "rich_data" },
  "skills_detail": { "rich_data" },
  "education_detail": { "rich_data" },
  "company_fit_detail": { "rich_data" },
  "domain_analysis": { "domain_match_info" },
  "main_strengths": [ "list" ],
  "areas_for_improvement": [ "list" ],
  "recommendation": { "level", "action_items", "interview_tips" },
  "matched_skills": [ "perfect_match_skills" ],
  "related_skills": [ "relevant_match_skills" ],
  "missing_skills": [ "miss_match_skills" ]
}
```

---

### 3️⃣ `response_builder.py`

**Mục đích:** Xây dựng response giàu thông tin cho Frontend

#### Classes & Functions:

| Hàm | Input | Output | Mục đích |
|-----|-------|--------|---------|
| `build_main_strengths()` | Tất cả điểm + features | `List[StrengthItem]` | Liệt kê điểm mạnh nổi bật |
| `build_areas_for_improvement()` | Tất cả điểm + missing skills | `List[AreaItem]` | Liệt kê điểm cần cải thiện |
| `build_recommendation()` | Điểm tổng + domain penalty | `RecommendationItem` | Khuyến nghị cho ứng viên |
| `build_experience_detail()` | experience_score + rationale | dict | Chi tiết kinh nghiệm |
| `build_education_detail()` | education_score + rationale | dict | Chi tiết học vấn |
| `build_career_detail()` | career_score + rationale | dict | Chi tiết mục tiêu nghề |
| `build_company_fit_detail()` | company_score + rationale | dict | Chi tiết phù hợp công ty |
| `get_score_badge()` | score, max_score | str | Nhãn điểm (eg: "Excellent") |

#### Data Classes:

```python
@dataclass
class StrengthItem:
    type: str                          # strength_experience_full, skills_strong, etc.
    title: str                         # Tiêu đề điểm mạnh
    description: str                   # Mô tả chi tiết
    score_impact: Optional[float]      # Điểm ảnh hưởng
    icon: Optional[str]                # Icon cho FE

@dataclass
class AreaItem:
    type: str                          # experience_gap, skills_missing, etc.
    title: str                         # Tiêu đề vấn đề
    description: str                   # Mô tả
    priority: str                      # high/medium/low
    suggestions: List[str]             # Gợi ý cải thiện

@dataclass
class RecommendationItem:
    level: str                         # very_high/high/medium/low/very_low
    summary: str                       # 1 câu tổng kết
    summary_detail: str                # Vài câu giải thích
    action_items: List[str]            # Danh sách hành động
    interview_tips: List[str]          # Tips phỏng vấn
    score_range: str                   # eg: "75-85"
```

---

## 📊 Scoring Components (_scores) {#scoring-components}

### 1️⃣ `experience_score.py`

**Mục đích:** Chấm điểm kinh nghiệm làm việc (0-50)

#### Main Function: `score_experience()`

| Thuộc tính | Chi tiết |
|-----------|---------|
| **Input** | `cv_data`, `jd_data`, `cv_domain`, `jd_domain`, `skill_overlap`, `embedder` |
| **Output** | Tuple: `(score, rationale, features, cv_level, req_level, seniority_gap, is_entry_level, all_exp_years, years_req, cert_count, total_work_years, project_years)` |

**Công thức chấm:**

```
Total Experience = (Years Score + Seniority Score + Bonus) × (1 - Domain Penalty)
                   capped at 0-50

Thành phần:
├─ Years Score (0-40): Dựa vào số năm vs yêu cầu
├─ Seniority Score (0-10): Level junior/mid/senior
├─ Bonus (0-8): Có cả work experience + projects
└─ Domain Penalty (0-1): Phạt nếu domain không khớp
```

#### Helper Functions:

| Hàm | Input | Output | Mục đích |
|-----|-------|--------|---------|
| `parse_years()` | `start` (str), `end` (str) | float | Tính số năm từ date strings |
| `_semantic_seniority_detection()` | `titles` (List[str]), `descriptions` (List[str]), `embedder` | int (0-4) | Detect seniority level |
| `build_experience_features()` | experience metrics | dict | Build feature dict |
| `build_experience_detail()` | cv_data | str | Human-readable summary |

**Seniority Levels:**
- 0 = Intern/Fresher
- 1 = Junior (1-2 năm)
- 2 = Mid-level (2-5 năm)
- 3 = Senior (5+ năm)
- 4 = Principal/Lead/Manager (7+ năm)

---

### 2️⃣ `skills_score.py`

**Mục đích:** Chấm điểm kỹ năng kỹ thuật (0-30)

#### Main Function: `score_skills()`

| Thuộc tính | Chi tiết |
|-----------|---------|
| **Input** | `cv_data`, `jd_data`, `embedder`, `domain_penalty`, `cv_embedding`, `jd_embedding` |
| **Output** | Tuple: `(score, perfect_requirements, missing_requirements, similarity, relevant_requirements, skills_breakdown, criteria_match_results)` |

**Công thức chấm:**

```
Skills Score = (Perfect Match Score + Relevant Match Score) × (1 - Domain Cap)
               capped at 0-30

Perfect Match: 1.0 điểm × số requirements
Relevant Match: 0.7 điểm × số requirements
Miss Match: 0.0 điểm
```

#### Key Functions:

| Hàm | Input | Output | Mục đích |
|-----|-------|--------|---------|
| `collect_cv_evidence()` | cv_data | `(List[str], List[str])` | Thu thập skill pool từ CV |
| `build_jd_criteria()` | jd_data | `List[Dict]` | Build criteria list từ JD |
| `match_criteria_to_cv()` | criteria, cv_data, embedder | `(List[Dict], List[str])` | Match criteria vs CV |
| `find_exact_criterion_evidence()` | criterion, cv_skill_pool | `(str, str)` | Find exact/equivalent match |
| `build_match_reason()` | criterion, match_status, evidence | str | Generate explanation |
| `compute_skill_overlap_ratio()` | cv_skills, jd_skills, embedder | float (0-1) | Tính overlap ratio |

**Match Status:**
- `PERFECT_MATCH` (1.0): Tìm thấy kỹ năng trực tiếp
- `RELEVANT_MATCH` (0.7): Tìm thấy kỹ năng liên quan
- `MISS_MATCH` (0.0): Không tìm thấy

**Importance Levels:**
- `CRITICAL`: Bắt buộc (3x weight)
- `IMPORTANT`: Quan trọng (2x weight)
- `BONUS`: Tùy chọn (1x weight)

---

### 3️⃣ `education_score.py`

**Mục đích:** Chấm điểm học vấn (0-10)

#### Main Function: `score_education()`

| Thuộc tính | Chi tiết |
|-----------|---------|
| **Input** | `cv_data`, `jd_data`, `embedder`, `domain_penalty` |
| **Output** | Tuple: `(score, rationale)` |

**Công thức chấm:**

```
Base Score = Degree Match + Major Relevance
Bonus = Certifications (mỗi +0.5, max +2.0)
Final Score = min(Base + Bonus, 10.0)
              capped by domain_penalty if severe_mismatch
```

#### Helper Functions:

| Hàm | Input | Output | Mục đích |
|-----|-------|--------|---------|
| `_major_relevance_score()` | cv_education, jd_data, embedder | float (0-1) | Semantic major match score |
| `_semantic_major_relevance()` | cv_education, jd_data, embedder | bool | Legacy: returns score >= threshold |

**Degree Levels:**
- PhD/Tiến sĩ = 5
- Thạc sĩ/Master = 4
- Cử nhân/Bachelor = 3
- Cao đẳng/College = 2
- Trung cấp = 1

---

### 4️⃣ `career_score.py`

**Mục đích:** Chấm điểm mục tiêu nghề nghiệp (0-10)

#### Main Function: `score_career_objectives()`

| Thuộc tính | Chi tiết |
|-----------|---------|
| **Input** | `cv_data`, `jd_data`, `embedder`, `domain_penalty` |
| **Output** | Tuple: `(score, rationale, details)` |

**Công thức chấm:**

```
Base Score = Semantic Similarity(0-10)
Adjustments:
├─ Keyword Boost: Nếu CV objective chứa JD title keywords (+1-2.5 điểm)
├─ Overqualified Penalty: Nếu mục tiêu cao hơn JD (-2 điểm)
└─ Domain Penalty: Nếu domain khác hoàn toàn (cap ≤1.0)

Final Score = min(adjusted_score, 10.0)
```

#### Helper Functions:

| Hàm | Input | Output | Mục đích |
|-----|-------|--------|---------|
| `_score_proxy_fallback()` | cv_data, jd_data, embedder | Tuple | Score khi không có objective |
| `_score_with_objective()` | cv_objective, cv_data, jd_data | Tuple | Score khi có objective |

**Keyword Matching:**
- 2+ keywords match → 8.5+
- 1 keyword match → 6.0+
- Overqualified → -2.0

---

### 5️⃣ `company_fit_score.py`

**Mục đích:** Chấm điểm phù hợp công ty (0-10) - **RIÊNG BIỆT, KHÔNG TÍNH VÀO TỔNG**

#### Main Function: `score_company_fit()`

| Thuộc tính | Chi tiết |
|-----------|---------|
| **Input** | `cv_data`, `company_data`, `jd_data`, `embedder` |
| **Output** | Tuple: `(score, rationale)` |

**Công thức chấm:**

```
Company Fit Score = Tech Stack Match + Domain/Industry Fit + Culture Fit + Engineering Bonus
                    0-10

Thành phần:
├─ [A] Tech Stack Match (0-4): F1-score của tech overlap
├─ [B] Domain/Industry Fit (0-3): Semantic similarity
├─ [C] Culture Fit (0-2): CV objective vs company culture
└─ [D] Engineering Practices Bonus (0-1): CV evidence vs practices
```

#### Helper Functions:

| Hàm | Input | Output | Mục đích |
|-----|-------|--------|---------|
| `_get_ci_tech()` | company_data | List[str] | Collect tech stack |
| `_score_tech_stack()` | cv_data, company_data | Tuple | Tech match (F1-score) |
| `_score_domain_fit()` | cv_data, company_data, embedder | Tuple | Industry match |
| `_score_culture_fit()` | cv_data, company_data, embedder | Tuple | Culture match |
| `_score_engineering_bonus()` | cv_data, company_data, embedder | Tuple | Engineering practices |

---

### 6️⃣ `_shared.py`

**Mục đích:** Utilities, constants, helpers chia sẻ

#### Key Classes & Constants:

```python
@dataclass(frozen=True)
class ScoringConfig:
    EXPERIENCE_WEIGHT: float = 50.0
    SKILLS_WEIGHT: float = 30.0
    EDUCATION_WEIGHT: float = 10.0
    CAREER_WEIGHT: float = 10.0
    
    PERFECT_MATCH_THRESHOLD: float = 0.80
    RELEVANT_MATCH_THRESHOLD: float = 0.60
    
    DOMAIN_CAP_SEVERE: float = 12.0          # Experience cap nếu domain severe mismatch
    DOMAIN_CAP_MODERATE: float = 18.0        # Experience cap nếu domain moderate mismatch
    
    UNDERQUALIFIED_CAP: float = 30.0
    SEVERE_GAP_CAP: float = 25.0
    SPECIALIZATION_MISMATCH_CAP: float = 35.0
```

#### Key Functions:

| Hàm | Input | Output | Mục đích |
|-----|-------|--------|---------|
| `normalize_skill_key()` | skill (str) | str | Normalize skill to canonical key |
| `build_skill_groups()` | skills (List[str]) | set | Build normalized skill groups |
| `skill_group_match()` | cv_group, jd_group | Tuple | Find matched & missing skills |
| `qprefix()` / `pprefix()` | text, embedder | str | E5 model query/passage prefix |
| `get_sim_calibration()` | embedder | Tuple | Get SIM_MIN, SIM_MAX calibrated |
| `build_cv_text()` | cv_data | str | Concatenate CV content |
| `build_jd_text()` | jd_data | str | Concatenate JD content |
| `compute_domain_penalty()` | cv_domain, jd_domain, skill_overlap | Tuple | Compute domain penalty |
| `expand_proj_tech()` | proj_tech | List[str] | Expand tech to equivalents |

#### Domain & Seniority Anchors:

```python
_DOMAIN_ANCHORS = {
    "tech_ai": "AI Machine Learning...",
    "tech_software": "Software Engineer...",
    "tech_data": "Data Engineer...",
    # ... more domains
}

_SENIORITY_ANCHORS = {
    0: "Internship Fresher entry level...",
    1: "Junior Developer...",
    2: "Mid-level Developer...",
    3: "Senior Developer...",
    4: "Principal Lead Manager...",
}
```

---

## 🧠 Semantic Analysis (_semantic) {#semantic-analysis}

### 1️⃣ `domain.py`

**Mục đích:** Detect domain (lĩnh vực) từ CV và JD sử dụng semantic similarity

#### Main Functions:

| Hàm | Input | Output | Mục đích |
|-----|-------|--------|---------|
| `detect_cv_domain()` | cv_data, embedder, threshold | str | Detect CV domain (14 loại) |
| `detect_jd_domain()` | jd_data, embedder, threshold | str | Detect JD domain |
| `detect_cv_domain_from_text()` | text, embedder, threshold | str | Detect từ arbitrary text |

#### Class: `SemanticDomainDetector`

```python
class SemanticDomainDetector:
    def __init__(self, embedder, threshold=0.40)
    def detect(self, text: str) -> str
```

**Supported Domains:**
```
Tech: tech_ai, tech_software, tech_data, tech_devops, tech_security
Business: sales, marketing, finance, hr, operations, healthcare, education, design
Fallback: unknown
```

**Algorithm:**
1. Embed CV/JD text
2. Compare similarity với tất cả domain anchors
3. Return domain có highest similarity (nếu > threshold)
4. Fallback to "unknown" nếu không đủ confident

---

### 2️⃣ `project_relevance.py`

**Mục đích:** Tính điểm relevance của project cá nhân vs JD

#### Main Function: `compute_project_relevance()`

| Thuộc tính | Chi tiết |
|-----------|---------|
| **Input** | `projects` (List[dict]), `jd_data`, `embedder`, `default_duration` (float), `use_reranker` (bool) |
| **Output** | Tuple: `(total_project_years, relevance_scores_per_project, project_descriptions)` |

**Công thức chấm per-project:**

```
Relevance = α × Tech Score + (1-α) × Semantic Score

Tech Score: sqrt(intersection_count) up to 0.70
Semantic Score: Normalized embedding similarity

α (weight):
├─ 0.70 nếu có 2+ matching techs hoặc critical hits
├─ 0.60 nếu có 1 matching tech
└─ 0.55 nếu có tech nhưng ít match
└─ 0.70 (semantic only) nếu không có matching techs

Total Project Years = Σ(duration × relevance)
```

#### Helper Functions:

| Hàm | Input | Output | Mục đích |
|-----|-------|--------|---------|
| `_apply_reranking()` | relevance_scores, proj_texts, resp_text, embedder | None | Apply cross-encoder reranking |
| `_parse_years()` | start, end | float | Parse project duration |

**Algorithm:**
1. Collect JD skills (critical, important, bonus)
2. For each project:
   - Expand technologies vs JD skills
   - Compute tech match score
   - Embed project description vs JD responsibilities
   - Blend tech + semantic scores
3. Optional: rerank top-K using cross-encoder
4. Sum up project years weighted by relevance

---

### 3️⃣ `seniority.py`

**Mục đích:** Detect seniority level từ titles và descriptions

#### Main Functions:

| Hàm | Input | Output | Mục đích |
|-----|-------|--------|---------|
| `detect_seniority_level()` | titles (List[str]), descriptions (List[str]), embedder | int (0-4) | Detect seniority level |

#### Class: `SemanticSeniorityDetector`

```python
class SemanticSeniorityDetector:
    def __init__(self, embedder)
    def detect(self, titles: List[str], descriptions: List[str]) -> int
```

**Algorithm:**
1. Combine titles + descriptions into CV text
2. Embed CV text
3. Compare similarity với tất cả seniority anchor embeddings
4. Return level có highest similarity

**Seniority Levels (0-4):**
- **0:** Intern, Fresher, entry level, trainee
- **1:** Junior Developer/Engineer (1-2 years)
- **2:** Mid-level Developer (2-5 years)
- **3:** Senior Developer/Engineer/Lead (5+ years)
- **4:** Principal, Lead, Manager, Director (7+ years)

---

## � Chi Tiết Cách Thực Hiện Các Hàm {#implementation-details}

### 1️⃣ `calculate_hybrid_score()` - Quy trình chính

**Bước thực hiện:**

```
Step 1: Khởi tạo Embedding Service
└─ Lấy embedding service để mã hóa text

Step 2: Phát hiện Domain
├─ detect_cv_domain(cv_data, embedder, threshold=0.40)
│  └─ Embed CV text, so sánh với 14 domain anchors → domain có sim cao nhất
├─ detect_jd_domain(jd_data, embedder, threshold=0.40)
│  └─ Cùng cách với CV domain
└─ compute_domain_penalty(cv_domain, jd_domain, skill_overlap)
   └─ Xác định mức phạt (0-1) dựa vào:
      ├─ Nếu same domain → 0.0
      ├─ Nếu khác nhau + skill_overlap < 0.1 → 0.85
      ├─ Nếu khác nhau + skill_overlap < 0.2 → 0.70
      └─ Nếu khác nhau + skill_overlap >= 0.2 → 0.50

Step 3: Tính Skill Overlap
├─ Lấy JD skills_required + skills_preferred
├─ Lấy CV skills từ collect_cv_evidence()
├─ compute_skill_overlap_ratio(cv_skills, jd_skills, embedder)
│  ├─ Normalize cả cv_skills và jd_skills
│  ├─ Embed từng skill, tính similarity (threshold=0.72)
│  ├─ Đếm skills khớp / tổng skills JD
│  └─ Return ratio (0-1)
└─ Skill overlap được dùng cho domain_penalty & experience scoring

Step 4: Tính Score Components (SONG SONG)
├─ score_experience(cv_data, jd_data, cv_domain, jd_domain, skill_overlap, embedder)
│  ├─ Parse JD seniority → req_level (0-4)
│  ├─ Parse JD years_of_experience → years_req
│  ├─ Tính total_work_years từ work_experience
│  ├─ Tính project_years từ compute_project_relevance()
│  ├─ all_exp_years = total_work_years + project_years
│  ├─ Tính years_score (0-40) dựa vào ratio & gaps
│  ├─ Tính seniority_score (0-10) từ _semantic_seniority_detection()
│  ├─ Thêm bonus nếu có cả work + projects
│  └─ Final = (years + seniority + bonus) × (1 - domain_penalty), cap 0-50
│
├─ score_skills(cv_data, jd_data, embedder, domain_penalty, ...)
│  ├─ collect_cv_evidence() → cv_skill_pool + evidence_strings
│  ├─ build_jd_criteria() → criteria list từ JD
│  ├─ match_criteria_to_cv(criteria, cv_data, embedder)
│  │  ├─ For each criterion:
│  │  │  ├─ find_exact_criterion_evidence() → Check exact match
│  │  │  ├─ Nếu không match: dùng semantic embedding
│  │  │  │  ├─ Embed criterion + all CV evidence
│  │  │  │  ├─ Tính similarity matrix
│  │  │  │  ├─ Find best match
│  │  │  │  └─ Normalize similarity bằng SIM_MIN/MAX
│  │  │  ├─ So sánh với thresholds:
│  │  │  │  ├─ sim >= 0.80 → PERFECT_MATCH (1.0)
│  │  │  │  ├─ sim 0.60-0.80 → RELEVANT_MATCH (0.7)
│  │  │  │  └─ sim < 0.60 → MISS_MATCH (0.0)
│  │  │  └─ Tính score = match_status × importance_weight
│  │  └─ Accumulate scores theo importance level
│  ├─ perfect_score = PERFECT_MATCH × criteria_count
│  ├─ relevant_score = RELEVANT_MATCH × criteria_count
│  ├─ Apply domain_penalty cap
│  └─ Final skills_score = (perfect + relevant) × (1 - cap), 0-30
│
├─ score_education(cv_data, jd_data, embedder, domain_penalty)
│  ├─ Tìm degree requirement từ JD text
│  ├─ Tìm degree level trong CV (PhD=5, Bach=3, etc.)
│  ├─ _semantic_major_relevance()
│  │  ├─ Embed CV major text
│  │  ├─ Embed JD context (job_title + responsibilities + requirements)
│  │  ├─ Tính similarity
│  │  └─ Return True nếu similarity >= 0.40
│  ├─ base_score = degree_match + major_relevance_bonus
│  ├─ cert_bonus = min(cert_count × 0.5, cert_bonus_max)
│  └─ Final = min(base + cert_bonus, 10.0)
│
├─ score_career_objectives(cv_data, jd_data, embedder, domain_penalty)
│  ├─ Nếu CV không có objective:
│  │  ├─ _score_proxy_fallback()
│  │  └─ Dùng skills + experience titles làm proxy
│  └─ Nếu CV có objective:
│     ├─ _score_with_objective()
│     ├─ Embed CV objective + JD goal text
│     ├─ Tính similarity, map to 0-10 score
│     ├─ Keyword boost: Nếu objective chứa JD job title keywords
│     │  └─ 2+ keywords → score = max(score, 8.5)
│     │  └─ 1 keyword → score = max(score, 6.0)
│     ├─ Overqualified penalty: Nếu objective targets senior nhưng JD junior
│     │  └─ score -= 2.0
│     └─ Final score cap 0-10
│
└─ score_company_fit(cv_data, company_data, jd_data, embedder)
   ├─ Tech Stack Match (0-4): F1-score
   │  ├─ Lấy CV technologies từ skills + projects
   │  ├─ Lấy company tech stack
   │  ├─ Tính precision = matched / cv_count
   │  ├─ Tính recall = matched / company_count
   │  └─ f1 = 2 × precision × recall / (precision + recall)
   ├─ Domain Fit (0-3): Semantic similarity
   │  ├─ Embed CV domain + text
   │  ├─ Embed company industry
   │  └─ Scaled similarity × 3.0
   ├─ Culture Fit (0-2): Semantic similarity
   │  ├─ Embed CV career_objectives (hoặc proxy)
   │  ├─ Embed company culture + values
   │  └─ Scaled similarity × 2.0
   └─ Engineering Bonus (0-1): Evidence match
      ├─ Embed CV skills + experience highlights
      ├─ Embed company engineering practices
      └─ Scaled similarity × 1.0

Step 5: Apply Score Overrides (nếu có)
└─ Nếu score_overrides dict được truyền:
   ├─ experience_score = override value
   ├─ skills_score = override value
   ├─ education_score = override value
   ├─ career_objectives_score = override value
   └─ company_fit_score = override value

Step 6: Tính Overall Score
└─ overall = min(exp + skills + edu + career, 100.0)

Step 7: Build Rich Response
├─ build_experience_detail() → Chi tiết kinh nghiệm
├─ build_education_detail() → Chi tiết học vấn
├─ build_career_detail() → Chi tiết mục tiêu
├─ build_company_fit_detail() → Chi tiết công ty fit
├─ build_main_strengths() → Liệt kê điểm mạnh
├─ build_areas_for_improvement() → Liệt kê điểm yếu
└─ build_recommendation() → Khuyến nghị

Step 8: Return Comprehensive Response Dict
└─ Chứa 25+ fields với tất cả thông tin chi tiết
```

---

### 2️⃣ `score_experience()` - Tính Kinh Nghiệm (0-50)

**Bước thực hiện:**

```
Step 1: Parse JD Seniority Requirements
├─ Tìm "seniority" field trong JD
├─ Map text to level 0-4:
│  ├─ intern/fresher → 0
│  ├─ junior → 1
│  ├─ mid → 2
│  ├─ senior → 3
│  └─ lead/manager → 4
└─ years_req_map = {0:0, 1:1, 2:2, 3:3, 4:4}

Step 2: Tính Total Work Years
├─ For each work experience entry:
│  ├─ parse_years(start_date, end_date)
│  │  ├─ Extract năm/tháng từ date strings
│  │  ├─ Handle "Present" → use current date
│  │  ├─ month_index_start = year × 12 + month
│  │  ├─ month_index_end = year × 12 + month
│  │  └─ total_months = end - start
│  │     return total_months / 12
│  └─ Add to total_work_years
└─ Extract job titles for seniority detection

Step 3: Tính Project Years
├─ compute_project_relevance(projects, jd_data, embedder, ...)
│  ├─ For each project:
│  │  ├─ Expand technologies vs JD skills
│  │  ├─ Tính intersection count
│  │  ├─ Embed project description
│  │  ├─ Embed JD responsibilities
│  │  ├─ Tính semantic similarity
│  │  ├─ Normalize similarity bằng SIM_MIN/MAX
│  │  ├─ Tech score = sqrt(intersection_count), cap 0.70
│  │  ├─ Blend tech_score + semantic_score
│  │  └─ relevance_scores.append(blended_score)
│  ├─ Optional: _apply_reranking() với cross-encoder
│  └─ total_project_years = Σ(duration × relevance)
└─ all_exp_years = total_work_years + project_years

Step 4: Tính Years Score (0-40)
├─ Case 1: Entry-level (junior fresher) & years_req == 0
│  ├─ Nếu total_work_years > 0:
│  │  ├─ Nếu skill_overlap < 0.1 → years_score = 5.0
│  │  └─ Else → years_score = 35.0
│  ├─ Else (chỉ projects):
│  │  ├─ avg_rel = Σ(relevance) / len(projects)
│  │  ├─ Nếu avg_rel >= 0.55 → years_score = 40.0
│  │  ├─ Nếu avg_rel 0.20-0.55 → 15 + (avg_rel - 0.20) / 0.35 × 25
│  │  ├─ Nếu avg_rel > 0 → 10 + avg_rel / 0.25 × 5
│  │  └─ Else → 8.0 (has projects) hoặc 5.0 (no projects)
│
├─ Case 2: Non-entry & years_req > 0
│  ├─ ratio = min(all_exp_years / years_req, 2.0)
│  ├─ Nếu all_exp_years < years_req:
│  │  ├─ gap_ratio = all_exp_years / years_req
│  │  └─ years_score = min(40 × gap_ratio², 40)  (quadratic penalty)
│  └─ Else:
│     ├─ years_score = min(40 × ratio, 40)
│     └─ Nếu overqualified (entry-level + exp >> 2×req):
│        └─ years_score -= min(8, (all_exp_years - req×2) × 2)
│
└─ Case 3: No requirement → years_score = min(all_exp_years × 20, 40)

Step 5: Tính Experience Quality Multiplier
├─ Nếu JD có experience_context description:
│  ├─ Embed CV work experience text
│  ├─ Embed JD context
│  ├─ Tính similarity
│  ├─ Normalize bằng SIM_MIN/MAX
│  ├─ quality_multiplier = 0.6 + (0.4 × normalized_sim)
│  └─ years_score *= quality_multiplier
└─ Else → quality_multiplier = 1.0

Step 6: Tính Seniority Score (0-10)
├─ _semantic_seniority_detection(titles, descriptions, embedder)
│  ├─ Combine titles + descriptions
│  ├─ Embed combined text
│  ├─ For each seniority level (0-4):
│  │  ├─ Tính dot product vs anchor embedding
│  │  └─ Find max similarity level
│  └─ cv_level = best_level
│
├─ Nếu domain_penalty >= 0.7 → seniority_base = 0.0
├─ Else nếu entry-level:
│  ├─ Nếu total_work_years > 0:
│  │  └─ seniority_base = min(total_work_years / years_req × 10, 10)
│  ├─ Else (projects):
│  │  ├─ avg_rel >= 0.70 → 7.0
│  │  ├─ avg_rel >= 0.45 → 5.0
│  │  ├─ avg_rel >= 0.25 → 3.0
│  │  └─ Else → 1.0
├─ Else (non-entry):
│  ├─ Nếu cv_level >= req_level → 10.0
│  ├─ Nếu cv_level == req_level - 1 → 5.0
│  ├─ Nếu cv_level > 0 → 2.0
│  └─ Else → 0.0
│
├─ Apply scaling nếu cv_level < req_level:
│  └─ seniority_score = seniority_base × (cv_level / req_level)
│
└─ Apply hard caps cho severe gap:
   ├─ Nếu gap >= 3 → 0.0
   ├─ Nếu gap >= 2 → cap 2.0
   └─ Else → no additional cap

Step 7: Tính Bonus (0-8)
├─ Nếu domain_penalty < 0.4:
│  ├─ Nếu total_work_years > 0 AND project_years > 0 → +8.0
│  ├─ Else nếu project_years > 0:
│  │  ├─ avg_rel = Σ(relevance) / len(projects)
│  │  ├─ Nếu avg_rel >= rel_threshold_high → +5.0
│  │  ├─ Nếu avg_rel >= rel_threshold_mid → +3.0
│  │  └─ Else → no bonus
│  └─ Else → 0.0
│
└─ Nếu entry-level & years_req <= 1.0 → cap bonus at 3.0

Step 8: Tính Raw Total
└─ raw_total = years_score + seniority_score + bonus

Step 9: Apply Penalties & Caps
├─ Nếu domain_penalty >= 0.5 AND total_work_years > 0 AND skill_overlap < 0.10:
│  └─ years_score *= 0.65
│
├─ Nếu not entry-level AND all_exp_years <= years_req × 0.5:
│  └─ seniority_score *= (all_exp_years / years_req)
│
├─ Nếu not entry-level AND all_exp_years <= years_req × 0.86 AND domain < 0.7:
│  └─ raw_total = safe_cap(raw_total, 30.0)  # UNDERQUALIFIED_CAP
│
├─ Nếu not entry-level AND years_req - all_exp_years >= 2.0:
│  └─ raw_total = safe_cap(raw_total, 25.0)  # SEVERE_GAP_CAP
│
└─ Nếu domain < 0.4 AND skill_overlap < 0.40 AND not entry-level:
   └─ raw_total = safe_cap(raw_total, 35.0)  # SPECIALIZATION_CAP

Step 10: Final Score với Domain Penalty
└─ total_exp = min(raw_total × (1 - domain_penalty), 50.0)

Step 11: Tạo Features Dict
└─ Chứa: years_ratio, skill_overlap, domain_penalty, seniority_gap, etc.

Step 12: Tạo Rationale String
└─ Mô tả chi tiết nguyên nhân của điểm
```

---

### 3️⃣ `score_skills()` - Tính Kỹ Năng (0-30)

**Bước thực hiện:**

```
Step 1: Thu Thập CV Evidence
├─ collect_cv_evidence(cv_data)
│  ├─ Extract từ fields:
│  │  ├─ technical_skills, domain_skills, skills
│  │  ├─ Project technologies
│  │  ├─ Certifications
│  │  ├─ Languages
│  │  └─ Work experience highlights
│  ├─ Deduplicate strings
│  └─ Return (skill_pool, full_evidence_strings)
└─ skill_pool: [python, javascript, machine learning, ...]

Step 2: Build JD Criteria
├─ build_jd_criteria(jd_data)
│  ├─ Lấy skills_required, skills_preferred
│  ├─ Lấy evaluation_criteria (nếu có)
│  ├─ Lấy requirements, responsibilities (fallback)
│  ├─ For each item:
│  │  ├─ Tạo criterion dict:
│  │  │  ├─ id: unique identifier
│  │  │  ├─ name: skill/requirement name
│  │  │  ├─ importance: CRITICAL / IMPORTANT / BONUS
│  │  │  ├─ acceptable_equivalents: [list of synonyms]
│  │  │  ├─ evidence_needed: description
│  │  │  └─ question_intent: validate_depth / verify_gap
│  │  └─ Deduplicate bằng criterion_key()
│  └─ Return criteria list (max 30)

Step 3: Match Criteria to CV
├─ match_criteria_to_cv(criteria, cv_data, embedder)
│  ├─ Pre-compute embedding similarity matrix:
│  │  ├─ Embed all CV evidence với pprefix (passage:)
│  │  ├─ Embed all criteria text với qprefix (query:)
│  │  ├─ Compute dot product matrix
│  │  └─ Normalize bằng SIM_MIN/MAX
│  │
│  ├─ For each criterion (j):
│  │  ├─ Step 3a: Try Exact/Equivalent Match
│  │  │  ├─ find_exact_criterion_evidence(criterion, cv_skill_pool)
│  │  │  ├─ Nếu tìm thấy → PERFECT_MATCH, best_sim = 1.0
│  │  │  ├─ Else nếu "requires_named" (enumerated list) → MISS_MATCH
│  │  │  └─ Else → continue to semantic matching
│  │  │
│  │  ├─ Step 3b: Semantic Matching (nếu không exact)
│  │  │  ├─ Get column j từ similarity matrix
│  │  │  ├─ Find best matching evidence index
│  │  │  ├─ Filter theo category (skill ≠ soft_skill, etc.)
│  │  │  ├─ raw_sim = similarity[best_idx, j]
│  │  │  ├─ Normalize: best_sim = (raw_sim - SIM_MIN) / (SIM_MAX - SIM_MIN)
│  │  │  ├─ So sánh thresholds:
│  │  │  │  ├─ best_sim >= 0.80 → PERFECT_MATCH
│  │  │  │  ├─ best_sim 0.60-0.80 → RELEVANT_MATCH
│  │  │  │  └─ best_sim < 0.60 → MISS_MATCH
│  │  │  └─ evidence = cv_evidence[best_idx]
│  │  │
│  │  ├─ Step 3c: Cross-Encoder Verification (optional)
│  │  │  ├─ Nếu CE_VERIFY_ENABLED:
│  │  │  │  ├─ Lấy top-3 candidates từ similarity scores
│  │  │  │  ├─ Use cross-encoder để rerank
│  │  │  │  ├─ Update best_sim nếu CE score cao hơn
│  │  │  │  └─ Blend CE score: α × original + (1-α) × CE
│  │  │  └─ ce_score = blended_score
│  │  │
│  │  └─ Step 3d: Tạo Result Item
│  │     ├─ Tạo match reason bằng build_match_reason()
│  │     ├─ Store:
│  │     │  ├─ id, name, importance
│  │     │  ├─ match_status (PERFECT/RELEVANT/MISS)
│  │     │  ├─ confidence (best_sim)
│  │     │  ├─ reason (human readable)
│  │     │  └─ evidence (CV text)
│  │     └─ Append to results

Step 4: Separate Results by Match Status
├─ perfect_requirements = [r for r in results if r.match_status == PERFECT]
├─ relevant_requirements = [r for r in results if r.match_status == RELEVANT]
└─ missing_requirements = [r for r in results if r.match_status == MISS]

Step 5: Tính Perfect & Relevant Scores
├─ perfect_count = len(perfect_requirements)
├─ important_perfect = count(perfect where importance == IMPORTANT)
├─ critical_perfect = count(perfect where importance == CRITICAL)
│
├─ perfect_score = perfect_count × 1.0
├─ relevant_count = len(relevant_requirements)
├─ relevant_score = relevant_count × 0.7
│
└─ raw_skills_score = perfect_score + relevant_score

Step 6: Apply Domain Cap
├─ Nếu domain_penalty >= 0.7:
│  └─ skills_score = min(raw_skills_score, 8.0)  # DOMAIN_CAP_SEVERE
├─ Nếu domain_penalty >= 0.4 AND skill_overlap < 0.35:
│  └─ skills_score = min(raw_skills_score, 12.0)  # DOMAIN_CAP_MODERATE
├─ Nếu domain_penalty >= 0.5 AND skill_overlap < 0.20:
│  └─ skills_score = min(raw_skills_score, 8.0)
└─ Else:
   └─ skills_score = raw_skills_score

Step 7: Cap at Maximum
└─ skills_score = min(skills_score, 30.0)

Step 8: Build Skills Breakdown Dict
├─ perfect_score, relevant_score
├─ coverage_ratio = perfect_count / total_criteria
├─ critical_matched, critical_total
├─ important_matched, important_total
└─ domain_cap_applied (bool)

Step 9: Return Results
└─ (skills_score, perfect_requirements, missing_requirements, 
    similarity, relevant_requirements, skills_breakdown, criteria_match_results)
```

---

### 4️⃣ `match_criteria_to_cv()` - Chi Tiết Semantic Matching

**Bước thực hiện:**

```
Step 1: Collect Evidence
├─ cv_skill_pool = [python, react, docker, ...]  # normalized
└─ cv_evidence = [long_strings_from_cv]

Step 2: Prepare Embeddings (Batch)
├─ For all CV evidence strings:
│  ├─ Add prefix "passage: " (nếu E5 model)
│  └─ Embed batch
├─ For all criterion texts:
│  ├─ Add prefix "query: "
│  └─ Embed batch
└─ Similarity matrix = CV_embeddings @ Criterion_embeddings.T

Step 3: For Each Criterion
├─ Get matched evidence từ exact match function
├─ Nếu exact match found:
│  ├─ match_status = PERFECT_MATCH
│  ├─ best_sim = 1.0
│  └─ evidence = matched_skill
│
├─ Else:
│  ├─ Get column j từ similarity matrix (criterion j)
│  ├─ For each row (cv_evidence):
│  │  ├─ raw_sim[i] = similarity_matrix[i, j]
│  │  ├─ Normalize: norm_sim[i] = (raw_sim[i] - SIM_MIN) / (SIM_MAX - SIM_MIN)
│  │  └─ Check category compatibility (avoid skill-soft_skill mix)
│  │
│  ├─ Find best index: best_idx = argmax(norm_sim)
│  ├─ best_sim = norm_sim[best_idx]
│  ├─ evidence = cv_evidence[best_idx]
│  │
│  ├─ Classify:
│  │  ├─ Nếu best_sim >= 0.80 → PERFECT_MATCH
│  │  ├─ Nếu best_sim 0.60-0.80 → RELEVANT_MATCH
│  │  ├─ Nếu best_sim < 0.60 → MISS_MATCH
│  │  └─ Set evidence = "" cho MISS_MATCH
│  │
│  └─ Optional: Cross-Encoder reranking
│     ├─ Get top-3 candidates từ best_sim
│     ├─ Use CrossEncoderReranker.score(criterion_text, candidates)
│     ├─ ce_scores = normalized crossencoder scores
│     ├─ Blend: final_sim = 0.60 × best_sim + 0.40 × ce_score
│     └─ Re-classify based on blended score

Step 4: Generate Reason
├─ build_match_reason(criterion, match_status, evidence, ...)
│  ├─ Nếu PERFECT_MATCH:
│  │  └─ "Tìm thấy '{name}' trong CV. Đáp ứng đầy đủ yêu cầu."
│  ├─ Nếu RELEVANT_MATCH:
│  │  └─ "Phát hiện nội dung liên quan '{name}'. Có thể đáp ứng cơ bản."
│  └─ Nếu MISS_MATCH:
│     ├─ Nếu importance == CRITICAL:
│     │  └─ "Không tìm thấy. Đây là yêu cầu BẮT BUỘC."
│     └─ Else:
│        └─ "Không tìm thấy. Nên bổ sung để cải thiện."

Step 5: Create Result Dict
├─ id, name, importance
├─ match_status, confidence
├─ reason
├─ evidence
└─ acceptable_equivalents
```

---

### 5️⃣ `compute_project_relevance()` - Tính Relevance Dự Án

**Bước thực hiện:**

```
Step 1: Prepare JD Skills
├─ jd_skills_all = skills_required + skills_preferred
├─ jd_critical = skills_required
├─ jd_important = skills_required (marked as important)
├─ total_required = len(jd_critical)
├─ total_important = max(len(jd_important), 1)
└─ skill_importance = JD importance mapping

Step 2: For Each Project - Tech Analysis
├─ expanded_techs = expand_proj_tech(project.technologies)
│  └─ Maps equiv: yolov5 → {yolo}, pytorch → {pytorch}, etc.
├─ intersection = expanded_techs ∩ jd_skills_all
├─ critical_hits = intersection ∩ jd_critical
├─ important_hits = intersection ∩ jd_important
├─ quality_score = (2 × critical_hits / total_required + 1 × important_hits / total_important) / 3
└─ Store: intersection, intersection_count, critical_hits, quality_score

Step 3: Build Embedding Inputs
├─ resp_text = JD responsibilities + requirements
├─ For each project:
│  └─ proj_text = name + description + highlights
└─ If resp_text too short: add req_text

Step 4: Semantic Embeddings
├─ jd_emb = embedder.encode(qprefix(resp_text))  # query prefix
├─ For all projects:
│  ├─ proj_prefixed = pprefix(proj_text)  # passage prefix
│  ├─ proj_embs = embedder.encode_batch(proj_prefixed)
│  └─ sims = proj_embs @ jd_emb  # dot product
└─ Normalize sims to [0, 1]

Step 5: Parse Project Durations
├─ For each project:
│  ├─ Nếu start + no end:
│  │  └─ duration = default_duration (0.5 cho entry-level)
│  ├─ Else nếu start hoặc end:
│  │  ├─ _parse_years(start, end)
│  │  ├─ Extract year/month từ date strings
│  │  └─ duration = (end_month - start_month) / 12
│  └─ Else:
│     └─ duration = default_duration

Step 6: Compute Per-Project Hybrid Relevance
├─ For each project i:
│  ├─ raw_sim = sims[i]
│  ├─ normalized_sim = (raw_sim - SIM_MIN) / (SIM_MAX - SIM_MIN)
│  │
│  ├─ Tính Tech Score:
│  │  ├─ intersection_count = tech_info[i].intersection_count
│  │  ├─ tech_score = min(0.10 + 0.35 × sqrt(intersection_count), 0.70)
│  │  └─ has_tech = intersection_count > 0
│  │
│  ├─ Xác định Weighting:
│  │  ├─ Nếu 2+ techs hoặc critical_hits > 0:
│  │  │  └─ α (tech_weight) = 0.70
│  │  ├─ Nếu 1 tech:
│  │  │  └─ α = 0.60
│  │  └─ Else:
│  │     └─ α = 0.55
│  │
│  ├─ Blend Scores:
│  │  ├─ Nếu has_tech:
│  │  │  └─ relevance = α × tech_score + (1-α) × normalized_sim
│  │  └─ Else:
│  │     └─ relevance = 0.70 × normalized_sim (semantic only)
│  │
│  └─ relevance_scores.append(clipped_relevance)

Step 7: Optional Cross-Encoder Reranking
├─ _apply_reranking(relevance_scores, proj_texts, resp_text, embedder, top_k=3)
│  ├─ Get top-3 projects by relevance score
│  ├─ Use CrossEncoderReranker.score(resp_text, candidates)
│  ├─ ce_scores = normalized cross-encoder scores
│  ├─ For top-3 projects:
│  │  ├─ orig = relevance_scores[idx]
│  │  ├─ ce_score = ce_scores[idx]
│  │  ├─ new_rel = 0.60 × orig + 0.40 × ce_score
│  │  └─ relevance_scores[idx] = new_rel
│  └─ Update top-K in-place

Step 8: Compute Total Project Years
├─ For each project i:
│  ├─ total_years += duration[i] × relevance_scores[i]
│  └─ Weighted by relevance score
└─ Return: (total_years, relevance_scores, project_descriptions)
```

---

### 6️⃣ `detect_cv_domain()` & `detect_jd_domain()` - Phát hiện Lĩnh vực

**Bước thực hiện:**

```
Step 1: Khởi tạo Domain Anchors
├─ ensure_anchor_embs(embedder)
│  ├─ Nếu cache empty:
│  │  ├─ For each domain (14 loại):
│  │  │  ├─ Embed domain anchor text
│  │  │  └─ Cache embedding
│  │  └─ For each seniority level (0-4):
│  │     ├─ Embed seniority anchor text
│  │     └─ Cache embedding
│  └─ Else: use cached embeddings

Step 2: Build Input Text
├─ detect_cv_domain(cv_data):
│  ├─ Nếu cv_data.domain != "unknown":
│  │  └─ Return existing domain (cache hit)
│  └─ Else:
│     ├─ build_cv_text(cv_data)
│     │  ├─ Concatenate:
│     │  │  ├─ objective, career_objectives
│     │  │  ├─ all skills (technical, domain, soft)
│     │  │  ├─ project names, descriptions, technologies
│     │  │  ├─ work titles, descriptions
│     │  │  └─ education info
│     │  └─ Return concatenated text
│     └─ Call detect_cv_domain_from_text()

Step 3: Embed Input Text
├─ Add query prefix (nếu E5 model):
│  └─ "query: " + text
└─ Embed text, normalize

Step 4: Compare với Domain Anchors
├─ For each domain anchor (14 domains):
│  ├─ scores[domain] = dot(input_emb, anchor_emb)
│  └─ Range [0, 1] after normalization
│
├─ Find best match:
│  ├─ best_domain = argmax(scores)
│  ├─ best_score = scores[best_domain]
│  └─ second_best = 2nd highest score

Step 5: Validation & Fallback
├─ Nếu best_score >= threshold (0.40):
│  ├─ Nếu (best_score - second_best) >= 0.03:
│  │  └─ Return best_domain  ✓ Confident
│  └─ Else:
│     └─ Ambiguous → Return "unknown"
└─ Else:
   └─ Score too low → Return "unknown"

Step 6: Domain Categories
Domains (14 types):
├─ Tech:
│  ├─ tech_ai: AI, ML, Deep Learning, CV, NLP, Neural Networks
│  ├─ tech_software: Software, Backend, Frontend, API, Database
│  ├─ tech_data: Data Engineer, ETL, Analytics, SQL, DW
│  ├─ tech_devops: DevOps, CI/CD, Infrastructure, Container
│  └─ tech_security: Security, Penetration, Encryption
│
└─ Business:
   ├─ sales: Sales, Account Management, CRM, Revenue
   ├─ marketing: Digital Marketing, SEO, Content, Brand
   ├─ finance: Finance, Accounting, Investment, Audit
   ├─ hr: HR, Recruitment, Training, L&D
   ├─ operations: Operations, Supply Chain, Logistics
   ├─ healthcare: Healthcare, Medical, Clinical
   ├─ education: Education, Teaching, Training
   └─ design: Design, UI/UX, Graphics
```

---

### 7️⃣ `_semantic_seniority_detection()` - Phát hiện Cấp Độ Senior

**Bước thực hiện:**

```
Step 1: Combine Input Text
├─ titles = CV job titles
├─ descriptions = CV experience descriptions
├─ cv_text = " ".join(titles + descriptions)
└─ If empty → Return 0 (Intern/Fresher)

Step 2: Embed CV Text
├─ Add query prefix (nếu E5 model):
│  └─ "query: " + cv_text
└─ cv_emb = embedder.encode(prefixed_text, normalize=True)

Step 3: Load Seniority Anchors
├─ ensure_anchor_embs(embedder)
│  ├─ _seniority_anchors_embs = {
│  │  0: embedding("Internship Fresher entry level..."),
│  │  1: embedding("Junior Developer..."),
│  │  2: embedding("Mid-level Developer..."),
│  │  3: embedding("Senior Developer..."),
│  │  4: embedding("Principal Lead Manager...")
│  │ }
│  └─ Cached from first call

Step 4: Compare với All Levels
├─ For level in [0, 1, 2, 3, 4]:
│  ├─ sim = dot(cv_emb, anchor_emb[level])
│  ├─ Track max similarity
│  └─ best_level = argmax(similarities)

Step 5: Return Best Match
└─ Return best_level (0-4)

Seniority Levels:
├─ 0: Intern, Fresher (no experience)
├─ 1: Junior (1-2 years)
├─ 2: Mid-level (2-5 years)
├─ 3: Senior (5+ years)
└─ 4: Lead, Principal, Manager (7+ years)
```

---

## �🔗 Quy trình Chọn Lựa Ứng Viên (Recommendation Level)

```
Overall Score ≥ 80 và Domain Penalty < 0.3
└─→ Level: very_high (Recommended)

Overall Score ≥ 65 và Domain Penalty < 0.5
└─→ Level: high (Consider)

Overall Score ≥ 50 và Domain Penalty < 0.7
└─→ Level: medium (Maybe)

Overall Score ≥ 35
└─→ Level: low (Long shot)

Overall Score < 35
└─→ Level: very_low (Not recommended)
```

---

## 📌 Ưu tiên Areas for Improvement

**HIGH Priority:**
- Thiếu kinh nghiệm đáng kể (gap > 0.5 năm)
- Thiếu kỹ năng CRITICAL (bắt buộc)
- Chênh lệch seniority ≥ 2 level
- Domain mismatch đáng kể (penalty ≥ 0.5)

**MEDIUM Priority:**
- Thiếu kỹ năng IMPORTANT
- Seniority gap = 1 level
- Degree level thấp hơn yêu cầu
- Mục tiêu nghề nghiệp chưa rõ ràng

**LOW Priority:**
- Thiếu kỹ năng BONUS
- Có sự khác biệt nhỏ về domain

---

## 📊 Metric Thống Kê

| Metric | Min | Max | Mô tả |
|--------|-----|-----|-------|
| Overall Score | 0 | 100 | Tổng điểm, default 0 nếu lỗi |
| Experience Score | 0 | 50 | Kinh nghiệm, skill overlap, seniority |
| Skills Score | 0 | 30 | Đáp ứng JD requirements |
| Education Score | 0 | 10 | Degree level, major relevance, certs |
| Career Score | 0 | 10 | Alignment với mục tiêu JD |
| Company Fit | 0 | 10 | Phù hợp công ty (riêng biệt) |
| Domain Penalty | 0 | 1.0 | Penalization factor for mismatch |
| Skill Overlap | 0 | 1.0 | Ratio of matched skills |
| Seniority Gap | -∞ | +∞ | Req Level - CV Level |

---

## 🛠️ Scoring Thresholds

| Threshold | Value | Mục đích |
|-----------|-------|---------|
| SIM_MIN | 0.45 (calibrated) | Unrelated similarity floor |
| SIM_MAX | 0.92 (calibrated) | Perfect match similarity ceiling |
| PERFECT_MATCH | 0.80 | Embedding similarity cho PERFECT |
| RELEVANT_MATCH | 0.60 | Embedding similarity cho RELEVANT |
| Domain Penalty SEVERE | ≥ 0.7 | Cap experience ≤ 12, skills ≤ 8 |
| Domain Penalty MODERATE | 0.4-0.7 | Cap experience ≤ 18, skills ≤ 12 |

---

## 🎓 Tóm Tắt Luồng Chấm Điểm

```
Input: CV Data, JD Data, Company Data
         ↓
1. Domain Detection
   ├─ CV Domain (14 categories)
   └─ JD Domain (14 categories)
         ↓
2. Skill Overlap Calculation
   ├─ Extract CV skills
   ├─ Extract JD requirements
   └─ Compute overlap ratio
         ↓
3. Score Components (Parallel)
   ├─ Experience (0-50)
   │  ├─ Years vs requirement
   │  ├─ Seniority level match
   │  ├─ Project relevance
   │  └─ Domain penalty
   │
   ├─ Skills (0-30)
   │  ├─ Criteria matching (PERFECT/RELEVANT/MISS)
   │  ├─ Domain cap
   │  └─ Cross-encoder verification
   │
   ├─ Education (0-10)
   │  ├─ Degree level match
   │  ├─ Major relevance (semantic)
   │  └─ Certifications
   │
   ├─ Career (0-10)
   │  ├─ Objective alignment (semantic)
   │  ├─ Keyword boost
   │  └─ Overqualified penalty
   │
   └─ Company Fit (0-10, riêng)
      ├─ Tech stack match
      ├─ Industry fit
      ├─ Culture fit
      └─ Engineering practices
         ↓
4. Apply Score Overrides (nếu có)
         ↓
5. Build Rich Response
   ├─ Main Strengths
   ├─ Areas for Improvement
   ├─ Recommendation + Interview Tips
   └─ Skills, Experience, Education Details
         ↓
Output: Comprehensive Scoring Report
```

---

## 📝 Ghi Chú Quan Trọng

### ⚠️ Domain Penalty

Domain penalty được áp dụng khi CV domain khác JD domain:
- **0.0 (no penalty):** Same domain hoặc same tech/business family
- **0.1-0.2:** One side missing domain nhưng skill overlap tốt
- **0.4-0.7:** Different tech functions nhưng cùng family
- **0.7-0.85:** Completely different domain + low skill overlap
- **0.85:** Hoàn toàn khác, skill overlap rất thấp

### ⚠️ Entry-Level Jobs (Intern/Fresher)

- Không yêu cầu experience → Score based on projects
- Project relevance score ≥ 0.55 → years_score = 40 (full)
- Project relevance 0.20-0.55 → Scaled score
- No projects → Hard cap at 5-10

### ⚠️ Overqualification

- Nếu CV exp >> JD requirement (2x+) trên entry-level jobs
- → Penalize experience score
- → Bonus penalty nếu career objective targets higher level

### ⚠️ Skill Importance Weights

- **CRITICAL (3x):** Must-have, bắt buộc để xem xét
- **IMPORTANT (2x):** Strongly preferred
- **BONUS (1x):** Nice-to-have

### ⚠️ Cross-Encoder Verification

- Enabled by default để re-verify top-3 project relevance scores
- Uses weight 0.60 để blend với original embedding scores

---

**End of Report**

*Generated: 2026-05-30*
*Version: v6 (Enhanced Response)*
