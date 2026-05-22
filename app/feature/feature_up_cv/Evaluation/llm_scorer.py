# -*- coding: utf-8 -*-
"""
LLM-based independent scorer.

Uses OpenRouter (claude-sonnet-4-20250514 by default) to score each CV-JD pair
independently, applying the same rubric as the system's scoring engine.

Rubric:
  - Experience:    0-50
  - Skills:        0-30  (keyword overlap + semantic similarity boost)
  - Education:     0-10
  - Career Object: 0-10
  - Total:         0-100
  - Company Fit:   0-10  (separate, not counted in total)

The LLM receives a structured prompt with:
  1. The scoring rubric
  2. The full JD (structured + raw)
  3. The full CV (structured)
  4. A request to score each component with rationale
"""
import os
import json
import time
import httpx
from typing import Optional

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "anthropic/claude-sonnet-4-20250514"

SYSTEM_PROMPT = """You are an expert HR recruiter and technical interviewer evaluating CV-JD compatibility.

SCORING RUBRIC (use EXACTLY this scale):
  - experience_score       (0-50): Work experience relevance + years match + seniority alignment
  - skills_score          (0-30): Technical skill overlap (keyword match) + semantic similarity boost
  - education_score       (0-10): Degree level + field relevance + certifications
  - career_objectives_score (0-10): Alignment of stated career goals with JD role/career path
  - company_fit_score     (0-10): Industry/values alignment — NOT included in total
  - TOTAL                 (0-100): experience + skills + education + career_objectives

Respond ONLY with a valid JSON object in this exact format (no markdown, no extra text):
{
  "experience_score": <float 0-50>,
  "skills_score": <float 0-30>,
  "skills_keyword_score": <float 0-30>,
  "skills_embedding_score": <float 0-10>,
  "education_score": <float 0-10>,
  "career_objectives_score": <float 0-10>,
  "company_fit_score": <float 0-10>,
  "overall_score": <float 0-100>,
  "experience_assessment": "<brief text assessment>",
  "recommendation": "<hiring recommendation>",
  "matched_skills": ["<skill 1>", "<skill 2>"],
  "missing_skills": ["<skill 1>", "<skill 2>"],
  "rationale": "<detailed explanation of scoring for each component>"
}
"""


def _build_llm_prompt(cv_data: dict, jd_data: dict) -> str:
    jd_struct = jd_data.get("structured", jd_data)
    cv_name = (
        cv_data.get("personal_info", {}).get("name", "Unknown")
        or cv_data.get("name", "Unknown")
    )
    jd_title = jd_data.get("job_title", "") or jd_struct.get("job_title", "Unknown JD")

    # Build CV summary
    skills = cv_data.get("skills", []) + cv_data.get("technical_skills", []) + cv_data.get("domain_skills", [])
    exp_list = []
    for exp in cv_data.get("work_experience", []):
        years = f"{exp.get('start','')}-{exp.get('end','')}"
        exp_list.append(f"  - [{years}] {exp.get('title','')} @ {exp.get('company','')}: {'; '.join(exp.get('highlights', []))}")
    edu_list = []
    for e in cv_data.get("education", []):
        edu_list.append(f"  - {e.get('degree','')} in {e.get('major','')} @ {e.get('school','')} ({e.get('start','')}-{e.get('end','')})")
    proj_list = []
    for p in cv_data.get("projects", []):
        proj_list.append(f"  - {p.get('name','')} ({p.get('role','')}): {p.get('description','')} | Tech: {', '.join(p.get('technologies', []))}")

    cv_section = f"""CV — {cv_name}
Domain: {cv_data.get('domain', 'unknown')}
Career Objective: {cv_data.get('career_objectives', '') or cv_data.get('objective', 'N/A')}

EDUCATION:
{chr(10).join(edu_list) if edu_list else '  (none)'}

WORK EXPERIENCE:
{chr(10).join(exp_list) if exp_list else '  (none)'}

PROJECTS:
{chr(10).join(proj_list) if proj_list else '  (none)'}

SKILLS: {', '.join(skills) if skills else 'none'}

CERTIFICATIONS: {', '.join(cv_data.get('certifications', [])) if cv_data.get('certifications') else 'none'}
"""

    # Build JD summary
    jd_section = f"""JOB DESCRIPTION — {jd_title}
Seniority: {jd_struct.get('seniority', 'N/A')} | Years Required: {jd_struct.get('years_of_experience', 'N/A')}
Industry: {jd_struct.get('industry', 'N/A')}
Domain: {jd_struct.get('domain', 'N/A')}

REQUIRED SKILLS: {', '.join(jd_struct.get('skills_required', []))}
PREFERRED SKILLS: {', '.join(jd_struct.get('skills_preferred', []))}

RESPONSIBILITIES:
{chr(10).join(f"  - {r}" for r in jd_struct.get('responsibilities', []))}

REQUIREMENTS:
{chr(10).join(f"  - {r}" for r in jd_struct.get('requirements', []))}

CAREER EXPECTATIONS: {jd_struct.get('career_expectations', 'N/A')}
"""

    return f"""{SYSTEM_PROMPT}

{cv_section}

{'-'*60}

{jd_section}
"""


def score_with_llm(
    cv_data: dict,
    jd_data: dict,
    model: str = DEFAULT_MODEL,
    api_key: str = OPENROUTER_API_KEY,
    timeout: float = 60.0,
    max_retries: int = 2,
) -> dict:
    """
    Score a CV-JD pair using an independent LLM via OpenRouter.

    Returns the same dict format as system_scorer.score_with_system().
    """
    if not api_key:
        return {
            "overall_score": 0, "experience_score": 0, "skills_score": 0,
            "skills_keyword_score": 0, "skills_embedding_score": 0,
            "education_score": 0, "career_objectives_score": 0,
            "company_fit_score": 0, "embedding_similarity": None,
            "score_rationale": "", "matched_skills": [], "missing_skills": [],
            "experience_assessment": "", "recommendation": "",
            "cv_candidate": "", "job_position": "",
            "error": "OPENROUTER_API_KEY not set",
        }

    prompt = _build_llm_prompt(cv_data, jd_data)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://cv-jd-benchmark.local",
        "X-Title": "CV-JD Evaluation Benchmark",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 1024,
    }

    last_error = ""
    for attempt in range(max_retries + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(
                    f"{OPENROUTER_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                )
            if resp.status_code == 200:
                data = resp.json()
                raw = data["choices"][0]["message"]["content"].strip()
                # Strip markdown code fences if present
                if raw.startswith("```"):
                    lines = raw.splitlines()
                    raw = "\n".join(lines[1:] if lines[0].startswith("```") else lines)
                    if raw.endswith("```"):
                        raw = raw[:-3].strip()

                parsed = json.loads(raw)
                return {
                    "overall_score": float(parsed.get("overall_score", 0)),
                    "experience_score": float(parsed.get("experience_score", 0)),
                    "skills_score": float(parsed.get("skills_score", 0)),
                    "skills_keyword_score": float(parsed.get("skills_keyword_score", 0)),
                    "skills_embedding_score": float(parsed.get("skills_embedding_score", 0)),
                    "education_score": float(parsed.get("education_score", 0)),
                    "career_objectives_score": float(parsed.get("career_objectives_score", 0)),
                    "company_fit_score": float(parsed.get("company_fit_score", 0)),
                    "embedding_similarity": None,  # LLM doesn't compute embedding sim
                    "score_rationale": str(parsed.get("rationale", "")),
                    "matched_skills": parsed.get("matched_skills", []),
                    "missing_skills": parsed.get("missing_skills", []),
                    "experience_assessment": str(parsed.get("experience_assessment", "")),
                    "recommendation": str(parsed.get("recommendation", "")),
                    "cv_candidate": str(
                        cv_data.get("personal_info", {}).get("name", "Unknown")
                        or cv_data.get("name", "Unknown")
                    ),
                    "job_position": str(
                        jd_data.get("job_title", "")
                        or jd_data.get("structured", {}).get("job_title", "Unknown JD")
                    ),
                    "error": None,
                }
            else:
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                if resp.status_code == 429:
                    time.sleep(5 * (attempt + 1))
                    continue
                break
        except json.JSONDecodeError as e:
            last_error = f"JSON parse error: {e} | raw: {raw[:200] if 'raw' in dir() else 'N/A'}"
            if attempt < max_retries:
                time.sleep(2)
                continue
            break
        except Exception as e:
            last_error = str(e)
            if attempt < max_retries:
                time.sleep(2)
                continue
            break

    return {
        "overall_score": 0, "experience_score": 0, "skills_score": 0,
        "skills_keyword_score": 0, "skills_embedding_score": 0,
        "education_score": 0, "career_objectives_score": 0,
        "company_fit_score": 0, "embedding_similarity": None,
        "score_rationale": "", "matched_skills": [], "missing_skills": [],
        "experience_assessment": "", "recommendation": "",
        "cv_candidate": "", "job_position": "",
        "error": last_error,
    }
