# -*- coding: utf-8 -*-
"""
Analysis endpoints for CV-JD matching

Flow:
1. Extract text from uploaded files (CV, JD, optionally Company)
2. Compute SHA-256 hash of extracted text
3. Check DB for existing record with same hash → if found, load cached parser result
4. If no cache hit → call LLM parser, save parsed JSON to uploads/parser_file/
5. Run score matching and return results
"""
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

# Needed for type hints in async functions
from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.feature.auth.models.user import User
from app.feature.feature_up_cv.file_storage import (
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

# Import utilities from feature_up_cv using absolute imports
try:
    from app.feature.feature_up_cv.hybrid_scoring import calculate_hybrid_score
    from app.feature.feature_up_cv.embedding_service import get_embedding_service
    from app.feature.feature_up_cv.faiss_index_manager import get_faiss_manager
    from app.feature.feature_up_cv.score_matching import calculate_matching_score_from_payload
    from app.feature.feature_up_cv.parser_cv import llm_parser_cv
    from app.feature.feature_up_cv.parser_company import llm_parser_company
    from app.feature.feature_up_cv.text_extract import extract_text_auto, UnsupportedFileTypeError
    from app.feature.feature_up_cv.parser_jd import llm_parser_jd
    from app.feature.feature_up_cv.gemini_client import GeminiQuotaExceededError, GeminiRateLimitedError
except ImportError as e:
    print(f"⚠️ Warning: Could not import from feature_up_cv: {e}")
    calculate_hybrid_score = None
    calculate_matching_score_from_payload = None
    llm_parser_cv = None
    llm_parser_company = None
    GeminiQuotaExceededError = None
    GeminiRateLimitedError = None
    get_embedding_service = None
    get_faiss_manager = None


def calculate_company_cv_fit(cv_data: Dict, company_data: Dict) -> Dict:
    """
    Calculate CV fit with company based on:
    - Industry/skills match
    - Values alignment
    - Company culture preferences
    
    Returns:
    {
        "score": 0-100,
        "industry_match": 0-100,
        "skills_match": 0-100,
        "culture_fit": "High/Medium/Low",
        "assessment": "..."
    }
    """
    
    try:
        # Extract CV data
        cv_skills = set()
        if isinstance(cv_data, dict):
            if "skills" in cv_data:
                cv_skills = set(s.lower() for s in cv_data.get("skills", []))
            elif "technical_skills" in cv_data:
                cv_skills = set(s.lower() for s in cv_data.get("technical_skills", []))
        
        # Extract company requirements
        company_skills = set(s.lower() for s in company_data.get("key_skills", []))
        company_techs = set(s.lower() for s in company_data.get("technologies", []))
        all_company_requirements = company_skills | company_techs
        
        # Calculate skill match
        if all_company_requirements:
            skill_overlap = cv_skills & all_company_requirements
            skills_match_score = int((len(skill_overlap) / len(all_company_requirements)) * 100)
        else:
            skills_match_score = 50  # Default if no company skills listed
        
        # Overall fit = 60% skills + 40% culture guess
        overall_score = int(skills_match_score * 0.6 + 50 * 0.4)  # Culture guess = 50
        
        # Culture assessment
        if overall_score >= 75:
            culture_fit = "High"
        elif overall_score >= 60:
            culture_fit = "Medium"
        else:
            culture_fit = "Low"
        
        return {
            "score": overall_score,
            "industry_match": 70,  # Placeholder
            "skills_match": skills_match_score,
            "culture_fit": culture_fit,
            "matched_company_skills": list(skill_overlap if all_company_requirements else []),
            "assessment": f"CV has {len(skill_overlap)}/{len(all_company_requirements)} required skills for this company"
        }
    
    except Exception as e:
        print(f"⚠️ Company fit calculation error: {e}")
        return {
            "score": 50,
            "industry_match": 50,
            "skills_match": 50,
            "culture_fit": "Medium",
            "assessment": "Unable to calculate fit at this time"
        }


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
) -> tuple[Dict[str, Any], int, bool]:
    cv_service = CVProfileService(db)
    
    # Get current user's CV record (should exist from upload step)
    user_records = await cv_service.get_by_user(user_id)
    record = next((r for r in user_records if r.text_hashed == text_hash), None)
    
    if not record:
        from app.feature.feature_up_cv.auth.schemas.cv_profile import CVProfileCreate
        record = await cv_service.create(user_id=user_id, data=CVProfileCreate(text_hashed=text_hash))
        await db.flush()
        
    # 1. Own cache hit
    if record.text_hashed == text_hash and record.parser_file_url:
        cached = load_parser_result(record.parser_file_url)
        if cached:
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
        record = await ci_service.create(user_id=user_id, data=CompanyInfoCreate(text_hashed=text_hash))
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
    # Suppress SQLAlchemy Engine INFO logs temporarily
    original_echo = engine.echo
    engine.echo = False
    
    print("\n--------------------new session------------------------")
    session_start_time = time.perf_counter()
    """
    Analyze CV and JD match - Extract từ file và thực hiện matching
    Optional: include company research for additional matching context

    Scoring Strategy (Hybrid):
    1. Compute embeddings for CV and JD using sentence-transformers (all-MiniLM-L6-v2)
    2. Compute cosine similarity via FAISS for semantic matching
    3. Apply formula-based scoring:
       - Experience (0-50): years match + seniority level
       - Skills Keyword (0-30): normalized skill overlap (exact match)
       - Skills Embedding (0-30): embedding similarity boost
       - Education (0-10): degree level + certifications
       - Company Fit (0-10): industry/skills alignment
    4. Fallback to LLM scoring if embeddings unavailable

    Hệ thống cache:
    - Sau khi extract text, tính SHA-256 hash
    - Tra cứu DB xem đã có bản ghi nào cùng hash chưa
    - Nếu có và đã có parser_file_url → đọc file parsed từ cache, skip LLM
    - Nếu không → gọi LLM parser, lưu kết quả vào uploads/parser_file/
    - Embeddings được compute và cache trên disk (uploads/embeddings_cache/)
    - FAISS index được persist trên disk (uploads/faiss_indexes/)

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
    
    if not calculate_matching_score_from_payload:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Score matching module not available"
        )
    
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
        cv_data, id_cv, cv_cache_hit = await _parse_cv_with_cache(cv_text, cv_hash, user_id, db)

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
        
        all_cache_hits = cv_cache_hit and jd_cache_hit and ci_cache_hit
        
        if existing_session and existing_session.result_analysis_file_url:
            if os.path.exists(existing_session.result_analysis_file_url):
                cached_result = load_result_analysis(existing_session.result_analysis_file_url)
                if cached_result and all_cache_hits:
                    print(f"[CACHE HIT] MATCH_SCORE - using cached result from session={existing_session.id_session}")
                    return {
                        "success": True,
                        "message": "Analysis completed successfully (from cache)",
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

        # ── Call hybrid scoring (embedding + formula) ───
        step = "hybrid_score"
        score_started_at = time.perf_counter()
        try:
            if cv_embedding is not None and jd_embedding is not None:
                print(f"[SCORING] Using hybrid scoring with embeddings")
                analysis_result = calculate_hybrid_score(
                    cv_data, jd_data, company_data,
                    cv_embedding=cv_embedding, jd_embedding=jd_embedding
                )
            else:
                print(f"[SCORING] Falling back to LLM scoring (embeddings unavailable)")
                analysis_result = calculate_matching_score_from_payload(cv_data, jd_data, company_data)
            _log_parser_result("SCORE", score_started_at, True)
        except Exception as e:
            _log_parser_result("SCORE", score_started_at, False, str(e))
            # Fallback to LLM if hybrid fails
            print(f"[SCORING] Hybrid scoring failed ({e}), falling back to LLM")
            analysis_result = calculate_matching_score_from_payload(cv_data, jd_data, company_data)

        # ── Build response ────────────────────────────
        step = "build_response"
        detailed_scores = analysis_result.get("detailed_scores", {})
        response_data = {
            "overall_score": analysis_result.get("overall_score", 0),
            "detailed_scores": {
                "experience_score": detailed_scores.get("experience_score", 0),
                "skills_keyword_score": detailed_scores.get("skills_keyword_score", detailed_scores.get("skills_score", 0)),
                "skills_embedding_score": detailed_scores.get("skills_embedding_score", 0),
                "skills_total_score": detailed_scores.get("skills_total_score", detailed_scores.get("skills_score", 0)),
                "education_score": detailed_scores.get("education_score", 0),
                "company_fit_score": detailed_scores.get("company_fit_score", 0),
            },
            "embedding_similarity": analysis_result.get("embedding_similarity", None),
            "score_rationale": analysis_result.get("score_rationale", ""),
            "matched_skills": analysis_result.get("matched_skills", []),
            "related_skills": analysis_result.get("related_skills", []),
            "missing_skills": analysis_result.get("missing_skills", []),
            "experience_assessment": analysis_result.get("experience_assessment", ""),
            "experience_detail": analysis_result.get("experience_detail", ""),
            "main_strengths": analysis_result.get("main_strengths", []),
            "areas_for_development": analysis_result.get("areas_for_development", []),
            "recommendation": analysis_result.get("recommendation", ""),
            "cv_candidate": analysis_result.get("cv_candidate", ""),
            "job_position": analysis_result.get("job_position", ""),
        }
        
        # ── Add company matching if available ──────────
        if company_data and company_data.get("success"):
            response_data["company_match"] = {
                "company_name": company_data.get("company_name", ""),
                "industry": company_data.get("industry", ""),
                "company_description": company_data.get("description", ""),
                "mission": company_data.get("mission", ""),
                "values": company_data.get("values", []),
                "company_culture": company_data.get("company_culture", ""),
                "key_skills_needed": company_data.get("key_skills", []),
                "technologies_used": company_data.get("technologies", []),
                "company_achievements": company_data.get("key_achievements", []),
                # Add company-CV alignment score
                "company_cv_fit": calculate_company_cv_fit(cv_data, company_data)
            }
            
        # ── Save Result and Session ───────────────────
        try:
            result_file_path = save_result_analysis(response_data, user_id, id_cv, id_jd)

            detailed_scores = response_data.get("detailed_scores", {})
            score = float(response_data.get("overall_score", 0))
            experience_score = float(detailed_scores.get("experience_score", 0) if isinstance(detailed_scores, dict) else 0)
            skills_score = float(detailed_scores.get("skills_total_score", detailed_scores.get("skills_score", 0) if isinstance(detailed_scores, dict) else 0))
            education_score = float(detailed_scores.get("education_score", 0) if isinstance(detailed_scores, dict) else 0)
            company_fit_score = float(detailed_scores.get("company_fit_score", 0) if isinstance(detailed_scores, dict) else 0)
            
            if existing_session:
                await session_service.update(
                    id_session=existing_session.id_session,
                    data=AnalysisSessionUpdate(
                        score=score,
                        experience_score=experience_score,
                        skills_score=skills_score,
                        education_score=education_score,
                        companyfit_score=company_fit_score,
                        result_analysis_file_url=str(result_file_path),
                    )
                )
                print(f"[CACHE SAVED] Analysis session updated (id={existing_session.id_session}) and result saved")
            else:
                await session_service.create(
                    user_id=user_id,
                    data=AnalysisSessionCreate(
                        id_cv=id_cv,
                        id_jd=id_jd,
                        id_ci=id_ci,
                        score=score,
                        experience_score=experience_score,
                        skills_score=skills_score,
                        education_score=education_score,
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