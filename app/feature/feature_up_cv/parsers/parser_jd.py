# -*- coding: utf-8 -*-
"""
Enhanced JD Parser - Multi-section skill extraction with importance ranking.

Key improvements:
- Extract skills from EVERY section (responsibilities, requirements, benefits, description)
- Distinguish MUST-HAVE (required) vs NICE-TO-HAVE (preferred) skills
- Skill importance scoring based on frequency and position
- Explicit skill context (why it's mentioned) for better matching
- Self-validation with schema checking
- Post-processing with skill normalization
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from app.feature.feature_up_cv.core.gemini_client import generate_content
from app.feature.feature_up_cv.core.utils import (
    extract_first_json as _extract_first_json,
    criterion_key as _criterion_key,
    normalize_importance as _normalize_importance,
    coerce_string_list as _coerce_string_list,
    criterion_id as _criterion_id,
)


_GENERIC_SKILLS = {
    "problem solving", "communication", "teamwork", "english",
    "english (technical reading)", "data structures", "algorithms",
    "time management", "adaptability", "critical thinking",
    "interpersonal", "leadership", "work ethic", "self-motivation",
    "logical thinking", "analytical thinking", "growth mindset",
    "independent work", "proactiveness", "resilience", "goal achievement",
}

def _build_jd_prompt(jd_text: str) -> str:
    return f"""
Bạn là chuyên gia phân tích JD (Job Description) hàng đầu.
Mục tiêu: trích xuất TẤT CẢ kỹ năng từ mọi phần của JD một cách CHÍNH XÁC và ĐẦY ĐỦ.

QUAN TRỌNG - Phương pháp trích xuất:

1. Đọc TOÀN BỘ JD, không chỉ phần "Yêu cầu kỹ năng"
2. Trích xuất kỹ năng từ MỌI phần:
   - responsibilities (nhiệm vụ) → kỹ năng CẦN CÓ
   - requirements (yêu cầu) → kỹ năng BẮT BUỘC
   - benefits (phúc lợi) → có thể chứa tech stack của công ty
   - job_title, description → kỹ năng implied
   - keywords, industry → kỹ năng domain
3. PHÂN LOẠI chính xác:
   - skills_required (MUST-HAVE): kỹ năng kỹ thuật/domain bắt buộc, không có thì không đạt
   - skills_preferred (NICE-TO-HAVE): kỹ năng ưu tiên, có thì được đánh giá cao hơn
   ⚠️ KHÔNG đưa generic soft skills (Problem Solving, Communication, Teamwork, English,
      Data Structures, Algorithms) vào skills_required trừ khi JD nhấn mạnh đặc biệt.
      Các skill này → skills_preferred hoặc bỏ qua.
4. Đánh dấu MỨC ĐỘ QUAN TRỌNG — BẮT BUỘC cho TẤT CẢ skills:
   - CRITICAL: skill cốt lõi, đề cập nhiều lần hoặc nhấn mạnh rõ trong requirements
   - IMPORTANT: đề cập trong responsibilities hoặc requirements (không phải CRITICAL)
   - BONUS: chỉ dùng cho skills_preferred (nice-to-have)
   ⚠️ skill_importance PHẢI chứa TẤT CẢ skills từ cả skills_required VÀ skills_preferred.
   KHÔNG được bỏ trống bất kỳ skill nào. Mỗi skill trong skills_required → CRITICAL hoặc IMPORTANT.
5. Kỹ năng phải chuẩn tên quốc tế, VIẾT HOA đúng:
   - Ngôn ngữ: "Python", "JavaScript", "TypeScript", "Java", "C++", "Go", "Rust", "C#", "Swift", "Kotlin"
   - Framework: "React", "Vue.js", "Angular", "Django", "FastAPI", "Spring Boot", "Next.js", "NestJS"
   - Database: "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "Cassandra", "Neo4j"
   - Cloud/DevOps: "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform", "Jenkins", "Kafka"
   - AI/ML: "TensorFlow", "PyTorch", "Scikit-learn", "OpenCV", "YOLO", "LangChain", "Hugging Face", "CUDA"
   - Tools: "Git", "GitHub", "Jira", "Linux", "REST API", "GraphQL"

6. VỀ CẤP BẬC (seniority) - phải xác định CHÍNH XÁC:
   - "Junior/Fresher": 0-2 năm kinh nghiệm
   - "Mid-level": 2-4 năm kinh nghiệm
   - "Senior": 4-7 năm kinh nghiệm
   - "Lead/Principal": 7+ năm kinh nghiệm
   - "Manager": quản lý team, không chỉ technical

7. VỀ KEYWORDS/INDUSTRY:
   - Trích xuất tất cả từ khóa ngành: "AI", "Computer Vision", "Fintech", "E-commerce"...
   - Các domain keywords: "Real-time", "Scalable", "Microservices", "API-first"...

8. VỀ MỤC TIÊU NGHỀ NGHIỆP (career_expectations):
   - Trích xuất định hướng phát triển nghề nghiệp mà JD đề cập (ví dụ: "phát triển lên Senior trong 2 năm", "định hướng Tech Lead")
   - Trích từ benefits, responsibilities hoặc description. Nếu không có, để chuỗi rỗng ""

9. VỀ NGOẠI NGỮ (languages_required):
   - Trích xuất yêu cầu về ngoại ngữ thành mảng các object. Mỗi object gồm "language" (Tên ngôn ngữ, VD: English, Japanese) và "proficiency" (Trình độ yêu cầu, VD: IELTS 6.5, N2, Giao tiếp tốt). Nếu JD không yêu cầu ngoại ngữ, để mảng rỗng.

10. VỀ PHÂN TÍCH CHUYÊN MÔN:
   - domain: phân loại JD vào MỘT trong các nhóm (tech_ai, tech_data, tech_backend, tech_frontend, tech_mobile, tech_qa, sales, marketing, hr, finance, design, management, unknown).
   - is_entry_level: true nếu JD dành cho Thực tập sinh (Intern), Sinh viên kiến tập, Fresher, hoặc Junior yêu cầu dưới 1 năm kinh nghiệm.

11. VỀ evaluation_criteria:
   - Bổ sung danh sách tiêu chí đánh giá nguyên tử để scoring và sinh câu hỏi phỏng vấn.
   - Mỗi criterion phải là một yêu cầu có thể kiểm chứng bằng evidence trong CV.
   - Không atomize quá vụn; gom các yêu cầu thuộc cùng một năng lực nếu JD viết liền nhau.
   - Không thay thế skills_required/skills_preferred; evaluation_criteria là field mở rộng backward-compatible.
   - category gợi ý: technical_skill, domain_skill, tool, experience, responsibility, education, soft_skill, culture.
   - importance chỉ dùng CRITICAL, IMPORTANT, BONUS.
   - question_intent gợi ý: validate_depth, verify_gap, transferability, motivation, culture_fit.

Ràng buộc:
- CHỈ trả về 1 JSON object. KHÔNG text/markdown khác. KHÔNG giải thích.
- Không chắc chắn -> "" hoặc [] (không bịa).
- Loại bỏ trùng lặp.
- Giữ thứ tự quan trọng trước trong list.

Schema output:
{{
  "job_title": "",
  "location": "",
  "domain": "",
  "is_entry_level": false,
  "seniority": "",
  "years_of_experience": "",
  "employment_type": "",
  "languages_required": [{{"language": "", "proficiency": ""}}],
  "skills_required": [],
  "skills_preferred": [],
  "responsibilities": [],
  "requirements": [],
  "benefits": [],
  "industry": "",
  "keywords": [],
  "skill_importance": {{}},
  "evaluation_criteria": [
    {{
      "id": "crit_01",
      "name": "",
      "category": "",
      "importance": "IMPORTANT",
      "evidence_needed": "",
      "acceptable_equivalents": [],
      "source": "",
      "source_text": "",
      "question_intent": "validate_depth"
    }}
  ],
  "experience_context": "",
  "career_expectations": "",
  "culture_keywords": [],
  "evidence": {{
    "job_title": "",
    "years_of_experience": "",
    "skills_required": [],
    "skills_preferred": [],
    "responsibilities": [],
    "requirements": []
  }}
}}

NOTE: evidence là bản sao các trường chính, KHÔNG phải nơi để bổ sung thêm skills.
skills_required và skills_preferred trong evidence phải giống hệt trong structured chính.

QUAN TRỌNG - Không trùng lặp:
- `evidence` phải đồng bộ với các trường chính, không thêm skills_extra
- Mỗi skill chỉ nên xuất hiện trong đúng 1 danh sách (required HOẶC preferred, không cả 2)

Ví dụ Few-shot:
INPUT: "Backend Engineer. 3+ years. Python, FastAPI, PostgreSQL required. Docker, AWS preferred."
OUTPUT:
{{
  "job_title": "Backend Engineer",
  "location": "",
  "domain": "tech_backend",
  "is_entry_level": false,
  "seniority": "Mid-level",
  "years_of_experience": "3+",
  "employment_type": "",
  "languages_required": [],
  "skills_required": ["Python", "FastAPI", "PostgreSQL", "REST API", "Git"],
  "skills_preferred": ["Docker", "AWS", "Kubernetes", "Redis", "MongoDB"],
  "responsibilities": ["Phát triển API", "Thiết kế database", "Tối ưu hiệu suất"],
  "requirements": ["3+ năm kinh nghiệm backend", "Thành thạo Python"],
  "benefits": [],
  "industry": "Software/Tech",
  "keywords": ["Backend", "API", "Microservices"],
  "skill_importance": {{"Python": "CRITICAL", "FastAPI": "CRITICAL", "PostgreSQL": "IMPORTANT", "REST API": "IMPORTANT", "Git": "IMPORTANT", "Docker": "BONUS", "AWS": "BONUS", "Kubernetes": "BONUS", "Redis": "BONUS", "MongoDB": "BONUS"}},
  "evaluation_criteria": [
    {{"id":"crit_01","name":"Develop backend APIs with Python and FastAPI","category":"technical_skill","importance":"CRITICAL","evidence_needed":"Candidate has built backend APIs/services using Python and FastAPI or a close Python web framework equivalent.","acceptable_equivalents":["Django REST Framework","Flask API"],"source":"requirements","source_text":"Python, FastAPI required","question_intent":"validate_depth"}},
    {{"id":"crit_02","name":"Work with PostgreSQL database","category":"technical_skill","importance":"IMPORTANT","evidence_needed":"Candidate has used PostgreSQL or a comparable relational database in real projects.","acceptable_equivalents":["MySQL","SQL Server","Oracle Database"],"source":"requirements","source_text":"PostgreSQL required","question_intent":"validate_depth"}}
  ],
  "experience_context": "Cần 3+ năm kinh nghiệm backend development với Python",
  "career_expectations": "Cơ hội phát triển lên Senior Backend Engineer trong 2 năm.",
  "culture_keywords": [],
  "evidence": {{"job_title":"Backend Engineer","years_of_experience":"3+","skills_required":["Python","FastAPI","PostgreSQL"],"skills_preferred":["Docker","AWS"],"responsibilities":[],"requirements":[]}}
}}

Self-check:
- Đã đọc toàn bộ JD chưa?
- Skills_required có thiếu kỹ năng nào từ responsibilities không?
- Tất cả skills có đúng chính tả không?
- seniority và years_of_experience có nhất quán không?
- skill_importance có đủ TẤT CẢ skills từ skills_required (CRITICAL/IMPORTANT) và skills_preferred (BONUS) không?
- Có skill nào trong skills_required/preferred bị thiếu trong skill_importance không? Nếu có → thêm vào.
- Generic soft skills (Problem Solving, English, Teamwork...) có nằm sai trong skills_required không?
- career_expectations có được trích xuất chưa?
- evaluation_criteria có bao phủ các yêu cầu chính của JD nhưng không phá vỡ schema cũ không?

JD_TEXT:
{jd_text[:8000]}
""".strip()


def _validate_jd_schema(data: Dict) -> bool:
    if not isinstance(data, dict):
        return False
    for key in ("job_title", "skills_required", "skills_preferred", "industry"):
        if key not in data:
            return False
    return True


def _fallback_structured() -> Dict[str, Any]:
    return {
        "job_title": "",
        "location": "",
        "domain": "unknown",
        "is_entry_level": False,
        "seniority": "",
        "years_of_experience": "",
        "employment_type": "",
        "languages_required": [],
        "skills_required": [],
        "skills_preferred": [],
        "responsibilities": [],
        "requirements": [],
        "benefits": [],
        "industry": "",
        "keywords": [],
        "skill_importance": {},
        "evaluation_criteria": [],
        "experience_context": "",
        "career_expectations": "",
        "culture_keywords": [],
        "evidence": {
            "job_title": "",
            "years_of_experience": "",
            "skills_required": [],
            "skills_preferred": [],
            "responsibilities": [],
            "requirements": [],
        },
    }


# _criterion_key, _normalize_importance, _criterion_id, _coerce_string_list
# are now imported from app.feature.feature_up_cv.core.utils


def _criterion_from_requirement(
    name: str,
    category: str,
    importance: str,
    source: str,
    source_text: str,
    index: int,
    equivalents: List[str] | None = None,
) -> Dict[str, Any]:
    clean_name = str(name).strip()
    return {
        "id": _criterion_id(index, clean_name),
        "name": clean_name,
        "category": category,
        "importance": _normalize_importance(importance),
        "evidence_needed": (
            f"CV cần có bằng chứng đã sử dụng hoặc đáp ứng yêu cầu: {clean_name}."
        ),
        "acceptable_equivalents": equivalents or [],
        "source": source,
        "source_text": source_text,
        "question_intent": "validate_depth",
    }


def _normalize_evaluation_criteria(structured: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Keep LLM criteria if present, then backfill from legacy JD fields."""
    raw_criteria = structured.get("evaluation_criteria", [])
    if not isinstance(raw_criteria, list):
        raw_criteria = []

    criteria: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def add_criterion(item: Any) -> None:
        if isinstance(item, str):
            item = {"name": item}
        if not isinstance(item, dict):
            return

        name = str(item.get("name") or item.get("criterion") or "").strip()
        if not name:
            return
        key = _criterion_key(name)
        if not key or key in seen:
            return

        seen.add(key)
        index = len(criteria) + 1
        criteria.append({
            "id": str(item.get("id") or _criterion_id(index, name)),
            "name": name,
            "category": str(item.get("category") or "requirement").strip() or "requirement",
            "importance": _normalize_importance(item.get("importance")),
            "evidence_needed": str(item.get("evidence_needed") or f"CV cần có bằng chứng đáp ứng: {name}.").strip(),
            "acceptable_equivalents": _coerce_string_list(item.get("acceptable_equivalents", [])),
            "source": str(item.get("source") or "").strip(),
            "source_text": str(item.get("source_text") or "").strip(),
            "question_intent": str(item.get("question_intent") or "validate_depth").strip() or "validate_depth",
        })

    for item in raw_criteria:
        add_criterion(item)

    skill_importance = structured.get("skill_importance", {})
    if not isinstance(skill_importance, dict):
        skill_importance = {}

    # Backfill every legacy skill as a criterion so old JD parses remain usable.
    for skill in [s for s in structured.get("skills_required", []) if isinstance(s, str) and s.strip()]:
        key = _criterion_key(skill)
        if key not in seen:
            category = "soft_skill" if skill.lower().strip() in _GENERIC_SKILLS else "skill"
            add_criterion(_criterion_from_requirement(
                name=skill,
                category=category,
                importance=skill_importance.get(skill, "IMPORTANT"),
                source="skills_required",
                source_text=skill,
                index=len(criteria) + 1,
            ))

    for skill in [s for s in structured.get("skills_preferred", []) if isinstance(s, str) and s.strip()]:
        key = _criterion_key(skill)
        if key not in seen:
            category = "soft_skill" if skill.lower().strip() in _GENERIC_SKILLS else "skill"
            add_criterion(_criterion_from_requirement(
                name=skill,
                category=category,
                importance="BONUS",
                source="skills_preferred",
                source_text=skill,
                index=len(criteria) + 1,
            ))

    # If a JD is non-skill-heavy, keep broad responsibilities as criteria.
    if len(criteria) < 3:
        for source in ("requirements", "responsibilities"):
            for text in [s for s in structured.get(source, []) if isinstance(s, str) and s.strip()][:6]:
                add_criterion(_criterion_from_requirement(
                    name=text,
                    category="responsibility" if source == "responsibilities" else "experience",
                    importance="IMPORTANT",
                    source=source,
                    source_text=text,
                    index=len(criteria) + 1,
                ))

    return criteria[:30]


def llm_parser_jd(jd_text: str) -> Dict[str, Any]:
    """
    Enhanced JD parser with multi-section skill extraction.

    Returns:
    {
        "job_title": "Senior AI Engineer",
        "structured": {
            ...full structured data with skill_importance...
        }
    }
    """
    prompt = _build_jd_prompt(jd_text)
    structured: Dict[str, Any] | None = None

    for attempt in range(3):
        raw = generate_content(prompt=prompt, step="llm_parser_jd")
        candidate = _extract_first_json(raw) or raw.strip()

        try:
            parsed = json.loads(candidate)
            if _validate_jd_schema(parsed):
                structured = parsed
                break
        except json.JSONDecodeError:
            pass

    if structured is None:
        structured = _fallback_structured()

    # Ensure nested evidence exists
    if "evidence" not in structured:
        structured["evidence"] = {}
    if "skill_importance" not in structured:
        structured["skill_importance"] = {}
    if "culture_keywords" not in structured:
        structured["culture_keywords"] = []
    if "career_expectations" not in structured:
        structured["career_expectations"] = ""
    if "evaluation_criteria" not in structured:
        structured["evaluation_criteria"] = []

    # Ensure all list fields are lists
    for list_field in (
        "languages_required", "skills_required", "skills_preferred", "responsibilities",
        "requirements", "benefits", "keywords", "culture_keywords",
        "evaluation_criteria",
    ):
        if list_field in structured and not isinstance(structured[list_field], list):
            structured[list_field] = []

    # ── Post-process Fix 1: Auto-fill skill_importance nếu LLM bỏ sót ──────
    # LLM hay "lười" — chỉ điền BONUS cho preferred, bỏ qua required.
    # Đảm bảo TẤT CẢ skills đều có importance level.
    skill_importance = structured.get("skill_importance", {})
    if not isinstance(skill_importance, dict):
        skill_importance = {}

    skills_required = [s for s in structured.get("skills_required", []) if isinstance(s, str)]
    skills_preferred = [s for s in structured.get("skills_preferred", []) if isinstance(s, str)]

    # Required skills: phải là CRITICAL hoặc IMPORTANT — không được thiếu
    for i, skill in enumerate(skills_required):
        if skill not in skill_importance or skill_importance[skill] == "BONUS":
            # 3 skill đầu tiên trong required thường là cốt lõi nhất → CRITICAL
            skill_importance[skill] = "CRITICAL" if i < 3 else "IMPORTANT"

    # Preferred skills: luôn là BONUS
    for skill in skills_preferred:
        if skill not in skill_importance:
            skill_importance[skill] = "BONUS"

    structured["skill_importance"] = skill_importance

    # ── Post-process Fix 2: Infer years_of_experience từ seniority nếu trống ─
    # Khi JD không ghi số năm rõ, scoring engine cần con số để tính đúng.
    seniority_to_years = {
        "intern": "0",
        "fresher": "0-1",
        "junior/fresher": "0-2",
        "junior": "0-2",
        "mid-level": "2-4",
        "mid": "2-4",
        "senior": "4-7",
        "lead": "7+",
        "lead/principal": "7+",
        "principal": "7+",
        "manager": "5+",
    }
    if not structured.get("years_of_experience"):
        seniority_key = structured.get("seniority", "").lower().strip()
        inferred = seniority_to_years.get(seniority_key, "")
        if inferred:
            structured["years_of_experience"] = inferred

    # ── Post-process Fix 3: Dọn generic soft skills ra khỏi skills_required ─
    # Các skill quá chung (Problem Solving, English, Teamwork...) nếu nằm trong
    # required sẽ làm mọi CV bị "missing skill" dù thực tế không liên quan.
    filtered_required = []
    moved_to_preferred = []
    for skill in skills_required:
        if skill.lower().strip() in _GENERIC_SKILLS:
            moved_to_preferred.append(skill)
        else:
            filtered_required.append(skill)

    if moved_to_preferred:
        structured["skills_required"] = filtered_required
        # Thêm vào preferred nếu chưa có
        existing_preferred = set(s.lower() for s in skills_preferred)
        for skill in moved_to_preferred:
            if skill.lower() not in existing_preferred:
                skills_preferred.append(skill)
                # Đảm bảo importance là BONUS
                skill_importance[skill] = "BONUS"
        structured["skills_preferred"] = skills_preferred
        # Recalculate: required skills còn lại giữ importance cũ
        # nhưng generic skills vừa move → BONUS
        structured["skill_importance"] = skill_importance

    structured["evaluation_criteria"] = _normalize_evaluation_criteria(structured)

    # ── Post-process: ensure evidence mirrors the structured fields exactly ─
    evidence = structured.get("evidence", {})
    if not isinstance(evidence, dict):
        evidence = {}
    evidence["skills_required"] = [s for s in structured.get("skills_required", []) if isinstance(s, str)]
    evidence["skills_preferred"] = [s for s in structured.get("skills_preferred", []) if isinstance(s, str)]
    evidence["responsibilities"] = [r for r in structured.get("responsibilities", []) if isinstance(r, str)]
    evidence["requirements"] = [r for r in structured.get("requirements", []) if isinstance(r, str)]
    evidence["job_title"] = structured.get("job_title", "")
    evidence["years_of_experience"] = structured.get("years_of_experience", "")
    structured["evidence"] = evidence

    return {
        "job_title": structured.get("job_title") or "Job Description",
        "structured": structured,
    }
