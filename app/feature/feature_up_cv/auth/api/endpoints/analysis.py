# -*- coding: utf-8 -*-
"""
Analysis endpoints for CV-JD matching

Flow:
1. Extract text from uploaded files (CV, JD, optionally Company)
2. Compute SHA-256 hash of extracted text
3. Check DB for existing record with same hash → if found, load cached parser result
4. If no cache hit → call LLM parser, save parsed JSON to storage/parser_file/
5. Run score matching and return results
"""
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

# Needed for type hints in async functions
from app.core.database import get_db
from app.core.dependencies import get_current_active_user, get_current_authenticated_user
from app.feature.auth.models.user import User
from app.feature.feature_up_cv.core.file_storage import (
    compute_text_hash,
    save_parser_result,
    load_parser_result,
    save_result_analysis,
    load_result_analysis,
    FILE_TYPE_CV,
    FILE_TYPE_JD,
    FILE_TYPE_CI,
)
from app.feature.feature_up_cv.auth.services.cv_profile_service import CVProfileService
from app.feature.feature_up_cv.auth.services.job_description_service import JobDescriptionService
from app.feature.feature_up_cv.auth.services.company_info_service import CompanyInfoService
from app.feature.feature_up_cv.auth.services.analysis_session_service import AnalysisSessionService
from app.feature.feature_up_cv.auth.schemas.analysis_session import AnalysisSessionCreate, AnalysisSessionUpdate
from app.core.database import engine

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore


# Pydantic model for analysis request
class AnalysisCVJDRequest(BaseModel):
    cv_file_path: str
    jd_file_path: str
    company_file_path: str | None = None  # Optional company research file


router = APIRouter(prefix="/analysis", tags=["Analysis"])


def _log_parser_result(parser_name: str, started_at: float, success: bool, error: str | None = None) -> None:
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    status_str = "SUCCESS" if success else "FAILED"
    if success:
        print(f"[PARSER] {parser_name}: {status_str} ({elapsed_ms:.1f} ms)")
    else:
        print(f"[PARSER] {parser_name}: {status_str} ({elapsed_ms:.1f} ms) - {error or 'unknown error'}")


def _build_skills_detail(analysis_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform matched_skills / related_skills / missing_skills arrays
    into the structured skills_detail object that the FE expects.

    Input arrays can be:
      - list of str (legacy format)
      - list of dict with keys: skill, reason, importance, confidence (from hybrid_scoring)

    FE template accesses skills_detail.{matched,related,missing} as arrays of objects
    with fields: skill, reason, evidence, severity (missing only), importance (missing only).
    """
    def _normalize_matched(item, idx: int) -> Dict[str, Any]:
        if isinstance(item, dict):
            return {
                "skill": item.get("skill", ""),
                "reason": item.get("reason") or "Kỹ năng được tìm thấy trong CV.",
                "importance": item.get("importance", ""),
                "confidence": item.get("confidence", 1.0),
                "evidence": None,
            }
        return {"skill": str(item), "reason": "Kỹ năng được tìm thấy trong CV.", "evidence": None}

    def _normalize_related(item, idx: int) -> Dict[str, Any]:
        if isinstance(item, dict):
            return {
                "skill": item.get("skill", ""),
                "reason": item.get("reason") or "Kỹ năng có liên quan gần với yêu cầu JD.",
                "importance": item.get("importance", ""),
                "confidence": item.get("confidence", 0.0),
                "evidence": None,
            }
        return {"skill": str(item), "reason": "Kỹ năng có liên quan gần với yêu cầu JD.", "evidence": None}

    def _normalize_missing(item, idx: int) -> Dict[str, Any]:
        severity = "high" if idx < 5 else ("medium" if idx < 10 else "low")
        default_importance = "CRITICAL" if idx < 3 else ("IMPORTANT" if idx < 7 else "NORMAL")
        if isinstance(item, dict):
            return {
                "skill": item.get("skill", ""),
                "severity": severity,
                "importance": item.get("importance", default_importance),
                "reason": item.get("reason") or "Kỹ năng yêu cầu nhưng không được tìm thấy trong CV.",
            }
        return {
            "skill": str(item),
            "severity": severity,
            "importance": default_importance,
            "reason": "Kỹ năng yêu cầu nhưng không được tìm thấy trong CV.",
        }

    raw_matched = analysis_result.get("matched_skills", [])
    raw_related = analysis_result.get("related_skills", [])
    raw_missing = analysis_result.get("missing_skills", [])

    return {
        "matched": [_normalize_matched(s, i) for i, s in enumerate(raw_matched)],
        "related": [_normalize_related(s, i) for i, s in enumerate(raw_related)],
        "missing": [_normalize_missing(s, i) for i, s in enumerate(raw_missing)],
    }


def _build_main_strengths(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Build main_strengths for FE.

    Returns a list of dicts with human-readable fields that the FE template can render:
    - title: the main text
    - description: detailed explanation
    - type/icon: for styling
    """
    raw = response.get("main_strengths", [])
    if not raw:
        return []

    results = []
    for item in raw:
        if isinstance(item, dict):
            title = item.get("title", "")
            description = item.get("description", "")
            item_type = item.get("type", "")
            icon = item.get("icon", "")
            # Combine title + description into a readable string for legacy FE
            text = f"{title}. {description}" if description else title
            results.append({
                "type": item_type,
                "title": title,
                "description": description,
                "text": text,  # combined readable text
                "icon": icon,
                "score_impact": item.get("score_impact"),
            })
        elif isinstance(item, str):
            results.append({
                "type": "legacy",
                "title": item,
                "description": item,
                "text": item,
                "icon": "",
                "score_impact": None,
            })
    return results


def _build_areas_for_development(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Build areas_for_development for FE.

    Returns a list of dicts with human-readable fields:
    - title: main issue
    - description: detailed explanation
    - priority: high/medium/low
    - suggestions: list of improvement suggestions
    """
    raw = response.get("areas_for_improvement", []) or response.get("areas_for_development", [])
    if not raw:
        return []

    results = []
    for item in raw:
        if isinstance(item, dict):
            title = item.get("title", "")
            description = item.get("description", "")
            priority = item.get("priority", "medium")
            suggestions = item.get("suggestions", [])
            # Combine all info into a readable string
            suggestions_text = ""
            if suggestions:
                suggestions_text = " | Gợi ý: " + "; ".join(suggestions[:2])
            text = f"{title}. {description}{suggestions_text}"
            results.append({
                "type": item.get("type", ""),
                "title": title,
                "description": description,
                "text": text,
                "priority": priority,
                "suggestions": suggestions,
            })
        elif isinstance(item, str):
            results.append({
                "type": "legacy",
                "title": item,
                "description": item,
                "text": item,
                "priority": "medium",
                "suggestions": [],
            })
    return results


def _build_recommendation_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build recommendation for FE — returns a structured dict.

    The FE template references `analysisData.recommendation` directly.
    We need it to be a string so it renders correctly.
    Fallback: return a dict with a "text" field that can be used.
    """
    raw = response.get("recommendation")
    if not raw:
        return {
            "text": "Không có khuyến nghị.",
            "level": "unknown",
            "summary": "Không có khuyến nghị.",
            "action_items": [],
            "interview_tips": [],
        }

    if isinstance(raw, dict):
        # Build a human-readable text from structured fields
        parts = []
        level = raw.get("level", "unknown")
        summary = raw.get("summary", "")
        summary_detail = raw.get("summary_detail", "")
        action_items = raw.get("action_items", [])
        interview_tips = raw.get("interview_tips", [])

        if summary:
            parts.append(summary)
        if summary_detail and summary_detail != summary:
            parts.append(summary_detail)

        # Add action items as bullet points
        if action_items:
            parts.append("")
            for item in action_items[:3]:
                parts.append(f"• {item}")

        # Add interview tips
        if interview_tips:
            parts.append("")
            for tip in interview_tips[:2]:
                parts.append(f"→ {tip}")

        text = " ".join(parts)
        return {
            "text": text,
            "level": level,
            "summary": summary,
            "action_items": action_items,
            "interview_tips": interview_tips,
        }
    elif isinstance(raw, str):
        return {
            "text": raw,
            "level": "unknown",
            "summary": raw,
            "action_items": [],
            "interview_tips": [],
        }
    return {
        "text": "Không có khuyến nghị.",
        "level": "unknown",
        "summary": "Không có khuyến nghị.",
        "action_items": [],
        "interview_tips": [],
    }


def _build_experience_detail_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build experience_detail for FE.

    Returns a dict with:
    - score (int): experience score
    - score_level (str): xuất sắc/tốt/trung bình/yếu
    - summary (str): human-readable assessment text (legacy compat)
    - years_detail (dict): detailed years breakdown
    - cv_level (str): detected CV seniority level
    - jd_required_level (str): JD required level
    - seniority_gap (int): gap between cv_level and req_level
    - projects (list[str]): list of project names (legacy compat)
    - project_relevance_avg (float): average project relevance score
    """
    raw = response.get("experience_detail")
    detailed_scores = response.get("detailed_scores", {})

    if isinstance(raw, dict):
        years_detail = raw.get("years_detail", {})
        score = raw.get("score", 0)
        score_level = raw.get("score_level", "")
        summary = raw.get("summary", "")

        years_text = ""
        if years_detail:
            total = years_detail.get("total_years", 0)
            work = years_detail.get("work_years", 0)
            proj = years_detail.get("project_years", 0)
            gap_text = years_detail.get("gap_text", "")
            years_text = (
                f"Years: {total:.1f}y total "
                f"(work: {work:.1f}y, project: {proj:.1f}y). "
                f"{gap_text}. "
                f"Score={score}/50."
            )

        project_names = []
        proj_scores = response.get("features", {}).get("experience", {}).get("project_relevance_scores", [])
        for i, proj_text in enumerate(response.get("features", {}).get("experience", {}).get("project_descriptions", [])):
            rel = proj_scores[i] if i < len(proj_scores) else 0
            proj_name = proj_text[:60] if proj_text else f"Dự án {i+1}"
            project_names.append(proj_name)
        projects_text = "Projects: [" + ", ".join(project_names) + "]" if project_names else ""

        legacy_string = f"{summary} {years_text} {projects_text}".strip()

        cv_level = raw.get("cv_level", "")
        seniority_gap = raw.get("seniority_gap", 0)
        bonus_val = max(0, score - years_detail.get("total_years", 0) * 10 if years_detail else 0)

        return {
            "score": score,
            "score_level": score_level,
            "summary": legacy_string,
            "cv_level": cv_level,
            "jd_required_level": raw.get("jd_required_level", ""),
            "seniority_gap": seniority_gap,
            "years_detail": years_detail,
            "project_relevance_avg": raw.get("project_relevance_avg", 0),
            "projects": project_names,
            "seniority_label": f"seniority={cv_level}" if cv_level else "",
            "bonus_val": round(bonus_val, 1),
            "years_score_val": round(score * 0.8, 1),
        }

    elif isinstance(raw, str):
        score = detailed_scores.get("experience_score", 0)
        return {
            "score": score,
            "score_level": "",
            "summary": raw,
            "cv_level": "",
            "jd_required_level": "",
            "seniority_gap": 0,
            "years_detail": {},
            "project_relevance_avg": 0,
            "projects": [],
            "seniority_label": "",
            "bonus_val": 0,
            "years_score_val": score,
        }

    score = detailed_scores.get("experience_score", 0)
    return {
        "score": score,
        "score_level": "",
        "summary": response.get("experience_assessment", "Không có dữ liệu."),
        "cv_level": "",
        "jd_required_level": "",
        "seniority_gap": 0,
        "years_detail": {},
        "project_relevance_avg": 0,
        "projects": [],
        "seniority_label": "",
        "bonus_val": 0,
        "years_score_val": score,
    }


# Import utilities from feature_up_cv using absolute imports
try:
    from app.feature.feature_up_cv.scoring.hybrid_scoring import calculate_hybrid_score
    from app.feature.feature_up_cv.vector_search.embedding_service import get_embedding_service
    from app.feature.feature_up_cv.vector_search.faiss_index_manager import get_faiss_manager
    from app.feature.feature_up_cv.parsers.parser_cv import llm_parser_cv
    from app.feature.feature_up_cv.parsers.parser_company import llm_parser_company
    from app.feature.feature_up_cv.core.text_extract import extract_text_auto, UnsupportedFileTypeError
    from app.feature.feature_up_cv.parsers.parser_jd import llm_parser_jd
    from app.feature.feature_up_cv.core.gemini_client import GeminiQuotaExceededError, GeminiRateLimitedError
except ImportError as e:
    print(f"⚠️ Warning: Could not import from feature_up_cv: {e}")
    calculate_hybrid_score = None
    llm_parser_cv = None
    llm_parser_company = None
    GeminiQuotaExceededError = None
    GeminiRateLimitedError = None
    get_embedding_service = None
    get_faiss_manager = None


# calculate_company_cv_fit removed — now handled by hybrid_scoring._score_company_fit (4 dimensions)


async def _compute_and_cache_embeddings(
    cv_data: Dict[str, Any],
    cv_record,
    jd_data: Dict[str, Any],
    jd_record,
    user_id: int,
    db: AsyncSession,
) -> tuple:
    """
    Compute and cache embeddings for CV and JD using sentence-transformers.
    Also adds entries to FAISS index for semantic search.

    Returns (cv_embedding, jd_embedding, cv_cache_hit, jd_cache_hit)
    """
    if get_embedding_service is None or get_faiss_manager is None or np is None:
        return None, None, False, False

    embedder = get_embedding_service()
    faiss_mgr = get_faiss_manager()

    # ── CV Embedding ──────────────────────────────────
    cv_embedding = None
    cv_cache_hit = False

    if cv_record.embedding_vector_url:
        existing = embedder.load_vector(cv_record.embedding_vector_url)
        if existing is not None:
            print(f"[EMBEDDING] CV cache hit for id_cv={cv_record.id_cv}")
            cv_embedding = existing
            cv_cache_hit = True

    if cv_embedding is None:
        print(f"[EMBEDDING] Computing CV embedding for id_cv={cv_record.id_cv}")
        cv_text = embedder.encode_structured_cv(cv_data)
        cv_embedding = embedder.encode(cv_text)
        vector_path = embedder.save_vector(cv_embedding, cv_record.id_cv, FILE_TYPE_CV)
        cv_record.embedding_vector_url = str(vector_path)
        await db.flush()

        faiss_mgr.add_cv(cv_record.id_cv, cv_embedding, {
            "user_id": user_id,
            "name": cv_data.get("personal_info", {}).get("name", ""),
            "skills": cv_data.get("skills", []),
        })

    # ── JD Embedding ──────────────────────────────────
    jd_embedding = None
    jd_cache_hit = False

    if jd_record.embedding_vector_url:
        existing = embedder.load_vector(jd_record.embedding_vector_url)
        if existing is not None:
            print(f"[EMBEDDING] JD cache hit for id_jd={jd_record.id_jd}")
            jd_embedding = existing
            jd_cache_hit = True

    if jd_embedding is None:
        print(f"[EMBEDDING] Computing JD embedding for id_jd={jd_record.id_jd}")
        jd_text = embedder.encode_structured_jd(jd_data)
        jd_embedding = embedder.encode(jd_text)
        vector_path = embedder.save_vector(jd_embedding, jd_record.id_jd, FILE_TYPE_JD)
        jd_record.embedding_vector_url = str(vector_path)
        await db.flush()

        jd_struct = jd_data.get("structured", jd_data)
        faiss_mgr.add_jd(jd_record.id_jd, jd_embedding, {
            "user_id": user_id,
            "job_title": jd_struct.get("job_title", ""),
            "skills_required": jd_struct.get("skills_required", []),
        })

    return cv_embedding, jd_embedding, cv_cache_hit, jd_cache_hit


async def _parse_cv_with_cache(
    cv_text: str,
    text_hash: str,
    user_id: int,
    db: AsyncSession,
    raw_file_url: str | None = None,
) -> tuple[Dict[str, Any], int, bool]:
    cv_service = CVProfileService(db)
    
    # Get current user's CV record (should exist from upload step)
    user_records = await cv_service.get_by_user(user_id)
    record = next((r for r in user_records if r.text_hashed == text_hash), None)
    
    if not record:
        from app.feature.feature_up_cv.auth.schemas.cv_profile import CVProfileCreate
        record = await cv_service.create(
            user_id=user_id,
            data=CVProfileCreate(text_hashed=text_hash, raw_file_url=raw_file_url),
        )
        await db.flush()
    elif raw_file_url and record.raw_file_url != raw_file_url:
        record.raw_file_url = raw_file_url
        await db.flush()
        
    # 1. Own cache hit
    if record.text_hashed == text_hash and record.parser_file_url:
        cached = load_parser_result(record.parser_file_url)
        if cached:
            if raw_file_url and record.raw_file_url != raw_file_url:
                record.raw_file_url = raw_file_url
                await db.flush()
                await db.commit()
            print(f"[CACHE HIT] CV parser - using user's own cache id_cv={record.id_cv}")
            return cached, record.id_cv, True

    # 2. Global cache hit (same content uploaded by another user)
    global_existing = await cv_service.get_by_text_hash(text_hash)
    if global_existing and global_existing.parser_file_url:
        cached = load_parser_result(global_existing.parser_file_url)
        if cached:
            print(f"[CACHE HIT] CV parser - using global cache from id_cv={global_existing.id_cv}")
            record.parser_file_url = global_existing.parser_file_url
            record.text_hashed = text_hash
            if raw_file_url:
                record.raw_file_url = raw_file_url
            await db.flush()
            await db.commit()
            return cached, record.id_cv, False

    # 3. No cache -> call LLM
    print(f"[CACHE MISS] CV parser - calling LLM")
    cv_started_at = time.perf_counter()
    try:
        cv_data = llm_parser_cv(cv_text)
        _log_parser_result("CV", cv_started_at, True)
    except Exception as e:
        _log_parser_result("CV", cv_started_at, False, str(e))
        raise

    # 4. Save parsed result to file
    parser_path = save_parser_result(
        parsed_data=cv_data,
        file_type=FILE_TYPE_CV,
        user_id=user_id,
        record_id=record.id_cv,
    )
    record.parser_file_url = str(parser_path)
    record.text_hashed = text_hash
    if raw_file_url:
        record.raw_file_url = raw_file_url
    await db.flush()
    await db.commit()
    print(f"[CACHE SAVED] CV parser result saved to id_cv={record.id_cv}")

    return cv_data, record.id_cv, False


async def _parse_jd_with_cache(
    jd_text: str,
    text_hash: str,
    user_id: int,
    db: AsyncSession,
) -> tuple[Dict[str, Any], int, bool]:
    jd_service = JobDescriptionService(db)
    
    # Get current user's JD record
    user_records = await jd_service.get_by_user(user_id)
    record = next((r for r in user_records if r.text_hashed == text_hash), None)
    
    if not record:
        from app.feature.feature_up_cv.auth.schemas.job_description import JobDescriptionCreate
        record = await jd_service.create(user_id=user_id, data=JobDescriptionCreate(text_hashed=text_hash))
        await db.flush()

    # 1. Own cache hit
    if record.text_hashed == text_hash and record.parser_file_url:
        cached = load_parser_result(record.parser_file_url)
        if cached:
            print(f"[CACHE HIT] JD parser - using user's own cache id_jd={record.id_jd}")
            return cached, record.id_jd, True

    # 2. Global cache hit
    global_existing = await jd_service.get_by_text_hash(text_hash)
    if global_existing and global_existing.parser_file_url:
        cached = load_parser_result(global_existing.parser_file_url)
        if cached:
            print(f"[CACHE HIT] JD parser - using global cache from id_jd={global_existing.id_jd}")
            record.parser_file_url = global_existing.parser_file_url
            record.text_hashed = text_hash
            await db.flush()
            await db.commit()
            return cached, record.id_jd, False

    # 3. No cache
    print(f"[CACHE MISS] JD parser - calling LLM")
    jd_started_at = time.perf_counter()
    try:
        jd_data = llm_parser_jd(jd_text=jd_text)
        _log_parser_result("JD", jd_started_at, True)
    except Exception as e:
        _log_parser_result("JD", jd_started_at, False, str(e))
        raise

    # 4. Save parsed result
    parser_path = save_parser_result(
        parsed_data=jd_data,
        file_type=FILE_TYPE_JD,
        user_id=user_id,
        record_id=record.id_jd,
    )
    record.parser_file_url = str(parser_path)
    record.text_hashed = text_hash
    await db.flush()
    await db.commit()
    print(f"[CACHE SAVED] JD parser result saved to id_jd={record.id_jd}")

    return jd_data, record.id_jd, False


async def _parse_company_with_cache(
    company_text: str,
    text_hash: str,
    user_id: int,
    db: AsyncSession,
) -> tuple[Dict[str, Any], int, bool]:
    ci_service = CompanyInfoService(db)

    # Get current user's CI record
    user_records = await ci_service.get_by_user(user_id)
    record = next((r for r in user_records if r.text_hashed == text_hash), None)

    if not record:
        from app.feature.feature_up_cv.auth.schemas.company_info import CompanyInfoCreate
        record = await ci_service.create(user_id=user_id, data=CompanyInfoCreate(text_hashed=text_hash, text_content=company_text))
        await db.flush()

    # 1. Own cache hit
    if record.text_hashed == text_hash and record.parser_file_url:
        cached = load_parser_result(record.parser_file_url)
        if cached:
            print(f"[CACHE HIT] COMPANY parser - using user's own cache id_ci={record.id_ci}")
            return cached, record.id_ci, True

    # 2. Global cache hit
    global_existing = await ci_service.get_by_text_hash(text_hash)
    if global_existing and global_existing.parser_file_url:
        cached = load_parser_result(global_existing.parser_file_url)
        if cached:
            print(f"[CACHE HIT] COMPANY parser - using global cache from id_ci={global_existing.id_ci}")
            record.parser_file_url = global_existing.parser_file_url
            record.text_hashed = text_hash
            await db.flush()
            await db.commit()
            return cached, record.id_ci, False

    # 3. No cache -> call LLM
    print(f"[CACHE MISS] COMPANY parser - calling LLM")
    company_started_at = time.perf_counter()
    try:
        company_info = llm_parser_company(company_text)
        if not company_info.get("success"):
            error_msg = company_info.get("error", "Unknown error")
            _log_parser_result("COMPANY", company_started_at, False, error_msg)
            print(f"⚠️ Company extraction failed: {error_msg}")
            raise ValueError(f"Lỗi khi phân tích thông tin công ty: {error_msg}")
        _log_parser_result("COMPANY", company_started_at, True)
    except Exception as e:
        _log_parser_result("COMPANY", company_started_at, False, str(e))
        print(f"⚠️ Company extraction error: {e}")
        raise

    # 4. Save parsed result to file
    parser_path = save_parser_result(
        parsed_data=company_info,
        file_type=FILE_TYPE_CI,
        user_id=user_id,
        record_id=record.id_ci,
    )
    record.parser_file_url = str(parser_path)
    record.text_hashed = text_hash
    record.text_content = company_text
    await db.flush()
    await db.commit()
    print(f"[CACHE SAVED] Company parser result saved to id_ci={record.id_ci}")

    return company_info, record.id_ci, False


@router.post("/match-cv-jd", status_code=status.HTTP_200_OK)
async def analyze_cv_jd_match(
    request_body: AnalysisCVJDRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    import uuid
    from app.core.database import engine
    
    # Suppress SQLAlchemy Engine INFO logs temporarily
    original_echo = engine.echo
    engine.echo = False
    
    print("\n--------------------new session------------------------")
    session_start_time = time.perf_counter()
    """
    Analyze CV and JD match - Extract từ file và thực hiện matching
    Optional: include company research for additional matching context

    Scoring Strategy (Hybrid):
    1. Parse CV and JD text via LLM (with caching)
    2. Compute embeddings for CV and JD using sentence-transformers (with caching)
    3. Run hybrid_scoring:
       - Experience (0-50): years match + seniority level
       - Skills (0-30): criteria matching + semantic embedding
       - Education (0-10): degree level + certifications
       - Career (0-10): objectives alignment
       - Company Fit (0-10): industry/skills/culture alignment

    Hệ thống cache:
    - Sau khi extract text, tính SHA-256 hash
    - Tra cứu DB xem đã có bản ghi nào cùng hash chưa
    - Nếu có và đã có parser_file_url → đọc file parsed từ cache, skip LLM
    - Nếu không → gọi LLM parser, lưu kết quả vào storage/parser_file/
    - Embeddings được compute và cache trên disk (storage/)
    - FAISS index được persist trên disk (storage/faiss_indexes/)

    Request body:
    {
        "cv_file_path": "/path/to/cv.pdf",
        "jd_file_path": "/path/to/jd.pdf",
        "company_file_path": "/path/to/company.pdf"  # Optional
    }

    Returns:
    {
        "success": true,
        "data": {
            "overall_score": 85,
            "detailed_scores": {...},
            "embedding_similarity": 0.82,
            "matched_skills": [...],
            "company_match": {...}  # Only if company_file_path provided
            ...
        }
    }
    """
    
    # Get file paths from request
    cv_file_path = Path(request_body.cv_file_path)
    jd_file_path = Path(request_body.jd_file_path)
    company_file_path = Path(request_body.company_file_path) if request_body.company_file_path else None
    
    # Validate files exist
    if not cv_file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File CV không tìm thấy: {cv_file_path}"
        )
    
    if not jd_file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File JD không tìm thấy: {jd_file_path}"
        )
    
    # Optional: validate company file if provided
    if company_file_path and not company_file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File Công ty không tìm thấy: {company_file_path}"
        )
    
    user_id = current_user.id
    step = "init"
    try:
        # ── Text extract: CV ───────────────────────
        step = "extract_cv_text"
        cv_text = extract_text_auto(str(cv_file_path))
        
        if not cv_text or len(cv_text.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không thể trích xuất văn bản từ file CV"
            )
        
        # ── Compute hash & parse CV (with cache) ─────
        step = "llm_parser_cv"
        cv_hash = compute_text_hash(cv_text)
        cv_data, id_cv, cv_cache_hit = await _parse_cv_with_cache(
            cv_text,
            cv_hash,
            user_id,
            db,
            raw_file_url=str(cv_file_path),
        )

        # ── Text extract: JD ───────────────────────
        step = "extract_jd_text"
        jd_text = extract_text_auto(str(jd_file_path))
        
        if not jd_text or len(jd_text.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không thể trích xuất văn bản từ file JD"
            )
        
        # ── Compute hash & parse JD (with cache) ─────
        step = "llm_parser_jd"
        jd_hash = compute_text_hash(jd_text)
        jd_data, id_jd, jd_cache_hit = await _parse_jd_with_cache(jd_text, jd_hash, user_id, db)
        
        # ── Extract Company Research (optional) ───────
        step = "maybe_extract_company_info"
        company_data = None
        id_ci = None
        ci_cache_hit = True
        if company_file_path:
            step = "extract_company_text"
            company_text = extract_text_auto(str(company_file_path))
            if not company_text or len(company_text.strip()) == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Không thể trích xuất văn bản từ file Công ty"
                )

            # ── Compute hash & parse Company (with cache) ──
            step = "llm_parser_company"
            company_hash = compute_text_hash(company_text)
            company_result = await _parse_company_with_cache(company_text, company_hash, user_id, db)
            company_data, id_ci, ci_cache_hit = company_result
            print(f"parser company info success")
                
        # ── Check for existing session ────────────────
        session_service = AnalysisSessionService(db)
        existing_session = await session_service.get_by_documents(user_id, id_cv, id_jd, id_ci)

        # Session ID is the primary key id_session
        
        all_cache_hits = cv_cache_hit and jd_cache_hit and ci_cache_hit
        
        if existing_session and existing_session.result_analysis_file_url:
            if os.path.exists(existing_session.result_analysis_file_url):
                cached_result = load_result_analysis(existing_session.result_analysis_file_url)
                if cached_result and all_cache_hits:
                    print(f"[CACHE HIT] MATCH_SCORE - using cached result from session={existing_session.id_session}")
                    # Apply skills_detail transformation even to cached results
                    cached_result["skills_detail"] = _build_skills_detail(cached_result)
                    return {
                        "success": True,
                        "message": "Analysis completed successfully (from cache)",
                        "session_id": existing_session.id_session,
                        "data": cached_result
                    }
                else:
                    if not all_cache_hits:
                        print(f"[CACHE MISS] MATCH_SCORE - underlying files were re-parsed, ignoring existing result for session={existing_session.id_session}")
                    else:
                        print(f"[CACHE MISS] MATCH_SCORE - physical file exists but could not be loaded for session={existing_session.id_session}")
            else:
                print(f"[CACHE MISS] MATCH_SCORE - physical file missing for session={existing_session.id_session}")
        else:
            if existing_session:
                print(f"[CACHE MISS] MATCH_SCORE - no result url, skipping existing session={existing_session.id_session}")
            else:
                print(f"[CACHE MISS] MATCH_SCORE - no existing session found")
        
        # ── Get CV and JD records for embedding cache ───
        from app.feature.feature_up_cv.auth.services.cv_profile_service import CVProfileService
        from app.feature.feature_up_cv.auth.services.job_description_service import JobDescriptionService
        cv_svc = CVProfileService(db)
        jd_svc = JobDescriptionService(db)
        cv_records = await cv_svc.get_by_user(user_id)
        jd_records = await jd_svc.get_by_user(user_id)
        cv_record = next((r for r in cv_records if r.id_cv == id_cv), None)
        jd_record = next((r for r in jd_records if r.id_jd == id_jd), None)

        # ── Compute embeddings (with caching) ───────────
        cv_embedding = None
        jd_embedding = None
        if cv_record and jd_record and get_embedding_service is not None and np is not None:
            cv_embedding, jd_embedding, _, _ = await _compute_and_cache_embeddings(
                cv_data, cv_record, jd_data, jd_record, user_id, db
            )
            await db.commit()

        # ── Call hybrid scoring ───
        step = "hybrid_score"
        score_started_at = time.perf_counter()
        try:
            analysis_result = calculate_hybrid_score(
                cv_data, jd_data, company_data,
                cv_embedding=cv_embedding, jd_embedding=jd_embedding
            )
            _log_parser_result("SCORE", score_started_at, True)
        except Exception as e:
            _log_parser_result("SCORE", score_started_at, False, str(e))
            print(f"[SCORING] Hybrid scoring failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Scoring failed: {str(e)}"
            )

        # ── Build response ────────────────────────────
        step = "build_response"
        detailed_scores = analysis_result.get("detailed_scores", {})
        # company_fit_score & rationale come from hybrid_scoring._score_company_fit (4 dimensions)
        _company_fit_score = detailed_scores.get("company_fit_score", 0)
        _company_fit_rationale = analysis_result.get("company_fit_rationale", "")

        raw_matched = analysis_result.get("matched_skills", [])
        raw_related = analysis_result.get("related_skills", [])
        raw_missing = analysis_result.get("missing_skills", [])

        response_data = {
            "overall_score": analysis_result.get("overall_score", 0),
            "summary": analysis_result.get("summary", ""),
            "detailed_scores": {
                "experience_score": detailed_scores.get("experience_score", 0),
                "skills_keyword_score": detailed_scores.get("skills_keyword_score", detailed_scores.get("skills_score", 0)),
                "skills_embedding_score": detailed_scores.get("skills_embedding_score", 0),
                "skills_total_score": detailed_scores.get("skills_total_score", detailed_scores.get("skills_score", 0)),
                "education_score": detailed_scores.get("education_score", 0),
                "career_objectives_score": detailed_scores.get("career_objectives_score", 0),
                "company_fit_score": _company_fit_score,
            },
            "embedding_similarity": analysis_result.get("embedding_similarity", None),
            "score_rationale": analysis_result.get("score_rationale", ""),
            "career_objectives_rationale": analysis_result.get("career_objectives_rationale", ""),
            "company_fit_rationale": _company_fit_rationale,
            # Flat arrays kept for backward compatibility
            "matched_skills": raw_matched,
            "related_skills": raw_related,
            "missing_skills": raw_missing,
            # Structured skills_detail for FE (AnalysisPanel.vue)
            "skills_detail": _build_skills_detail(analysis_result),
            # Experience detail — supports both new (dict) and legacy (string) formats
            "experience_assessment": analysis_result.get("experience_assessment", ""),
            "experience_detail": _build_experience_detail_response(analysis_result),
            # Main strengths — structured list from hybrid_scoring v6
            "main_strengths": _build_main_strengths(analysis_result),
            # Areas for development — structured list from hybrid_scoring v6
            "areas_for_development": _build_areas_for_development(analysis_result),
            # Recommendation — structured dict from hybrid_scoring v6
            "recommendation": _build_recommendation_response(analysis_result),
            # Legacy string fields (for backward compat with older FE)
            "legacy_main_strengths": analysis_result.get("main_strengths", []),
            "legacy_areas_for_development": analysis_result.get("areas_for_improvement", []),
            "legacy_recommendation": analysis_result.get("recommendation", ""),
            # cv_candidate, job_position
            "cv_candidate": analysis_result.get("cv_candidate", ""),
            "job_position": analysis_result.get("job_position", ""),
        }
        
        # ── Add company matching if available ──────────
        if company_data and company_data.get("success"):
            # Build culture_fit label from company_fit_score (0-10)
            _cfs = _company_fit_score
            _culture_label = "High" if _cfs >= 7 else ("Medium" if _cfs >= 4 else "Low")
            response_data["company_match"] = {
                "company_name": company_data.get("company_name", ""),
                "industry": company_data.get("industry", ""),
                "sub_industry": company_data.get("sub_industry", ""),
                "business_model": company_data.get("business_model", ""),
                "company_description": company_data.get("description", ""),
                "mission": company_data.get("mission", ""),
                "values": company_data.get("values", []),
                "company_culture": company_data.get("company_culture", ""),
                "work_culture": company_data.get("work_culture", ""),
                "remote_policy": company_data.get("remote_policy", ""),
                "key_skills_needed": company_data.get("key_skills", []),
                "technologies_used": company_data.get("technologies", []),
                "primary_languages": company_data.get("primary_languages", []),
                "frameworks": company_data.get("frameworks", []),
                "company_achievements": company_data.get("key_achievements", []),
                "engineering_practices": company_data.get("engineering_practices", []),
                # company_cv_fit now powered by hybrid_scoring._score_company_fit (4 dimensions)
                "company_cv_fit": {
                    "score": round(_cfs * 10),  # convert 0-10 -> 0-100 for FE consistency
                    "score_raw": _cfs,           # 0-10 raw
                    "culture_fit": _culture_label,
                    "assessment": _company_fit_rationale,
                },
            }
            
        # ── Save Result and Session ───────────────────
        saved_session = None
        try:
            result_file_path = save_result_analysis(response_data, user_id, id_cv, id_jd, id_ci=id_ci if id_ci else None)

            detailed_scores = response_data.get("detailed_scores", {})
            score = float(response_data.get("overall_score", 0))
            experience_score = float(detailed_scores.get("experience_score", 0) if isinstance(detailed_scores, dict) else 0)
            skills_score = float(detailed_scores.get("skills_total_score", detailed_scores.get("skills_score", 0) if isinstance(detailed_scores, dict) else 0))
            education_score = float(detailed_scores.get("education_score", 0) if isinstance(detailed_scores, dict) else 0)
            career_objectives_score = float(detailed_scores.get("career_objectives_score", 0) if isinstance(detailed_scores, dict) else 0)
            company_fit_score = float(detailed_scores.get("company_fit_score", 0) if isinstance(detailed_scores, dict) else 0)
            
            if existing_session:
                saved_session = await session_service.update(
                    id_session=existing_session.id_session,
                    data=AnalysisSessionUpdate(
                        cv_raw_text=cv_text,
                        jd_raw_text=jd_text,
                        score=score,
                        experience_score=experience_score,
                        skills_score=skills_score,
                        education_score=education_score,
                        career_objectives_score=career_objectives_score,
                        companyfit_score=company_fit_score,
                        result_analysis_file_url=str(result_file_path),
                    )
                )
                print(f"[CACHE SAVED] Analysis session updated (id={existing_session.id_session}) and result saved")
            else:
                saved_session = await session_service.create(
                    user_id=user_id,
                    data=AnalysisSessionCreate(
                        id_cv=id_cv,
                        id_jd=id_jd,
                        id_ci=id_ci,
                        cv_raw_text=cv_text,
                        jd_raw_text=jd_text,
                        score=score,
                        experience_score=experience_score,
                        skills_score=skills_score,
                        education_score=education_score,
                        career_objectives_score=career_objectives_score,
                        companyfit_score=company_fit_score,
                        result_analysis_file_url=str(result_file_path),
                    )
                )
                print("[CACHE SAVED] Analysis session created and result saved")
            await db.commit()
        except Exception as e:
            print(f"⚠️ Error saving analysis session: {e}")
        
        return {
            "success": True,
            "message": "Analysis completed successfully",
            "session_id": (saved_session.id_session if saved_session else (existing_session.id_session if existing_session else None)),
            "data": response_data
        }
    
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File error: {str(e)}"
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid data: {str(e)}"
        )
    
    except UnsupportedFileTypeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"[step={step}] {str(e)}"
        )
    
    except Exception as e:
        if GeminiQuotaExceededError and isinstance(e, GeminiQuotaExceededError):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"[step={step}] Gemini quota exceeded: {str(e)}"
            )
        if GeminiRateLimitedError and isinstance(e, GeminiRateLimitedError):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"[step={step}] Gemini rate limited: {str(e)}"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"[step={step}] Analysis error: {str(e)}"
        )
    
    finally:
        # Restore SQLAlchemy log level
        engine.echo = original_echo
        
        if 'session_start_time' in locals():
            session_elapsed_ms = (time.perf_counter() - session_start_time) * 1000
            print(f"[SESSION_END] Total time: {session_elapsed_ms:.1f} ms\n")


@router.get(
    "/{id_session}",
    response_model=AnalysisSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get analysis session by ID"
)
async def get_analysis_session(
    id_session: int,
    current_user: User = Depends(get_current_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisSessionResponse:
    """
    Get analysis session data by ID.
    
    Only the user who created the session or admin can access it.
    """
    session_service = AnalysisSessionService(db)
    analysis_session = await session_service.get_by_id(id_session)
    
    if not analysis_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis session with ID {id_session} not found"
        )
    
    # Check if the current user owns this session
    if analysis_session.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this analysis session"
        )
    
    return AnalysisSessionResponse.model_validate(analysis_session)
