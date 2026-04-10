# -*- coding: utf-8 -*-
"""
Analysis endpoints for CV-JD matching
"""
import os
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from ...models.user import User


# Pydantic model for analysis request
class AnalysisCVJDRequest(BaseModel):
    cv_file_path: str
    jd_file_path: str
    company_file_path: str | None = None  # Optional company research file


router = APIRouter(prefix="/analysis", tags=["Analysis"])

# Upload directories
CV_UPLOAD_DIR = Path(tempfile.gettempdir()) / "interview_cv_uploads"
JD_UPLOAD_DIR = Path(tempfile.gettempdir()) / "interview_jd_uploads"
COMPANY_UPLOAD_DIR = Path(tempfile.gettempdir()) / "interview_company_uploads"


def _log_parser_result(parser_name: str, started_at: float, success: bool, error: str | None = None) -> None:
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    status = "SUCCESS" if success else "FAILED"
    if success:
        print(f"[PARSER] {parser_name}: {status} ({elapsed_ms:.1f} ms)")
    else:
        print(f"[PARSER] {parser_name}: {status} ({elapsed_ms:.1f} ms) - {error or 'unknown error'}")

# Import utilities from feature_up_cv using absolute imports
try:
    from app.feature.feature_up_cv.score_matching import calculate_matching_score_from_payload
    from app.feature.feature_up_cv.parser_cv import llm_parser_cv
    from app.feature.feature_up_cv.parser_company import llm_parser_company
    from app.feature.feature_up_cv.text_extract import extract_text_auto, UnsupportedFileTypeError
    from app.feature.feature_up_cv.parser_jd import llm_parser_jd, UnsupportedFileTypeError as UnsupportedFileTypeErrorJD
    from app.feature.feature_up_cv.gemini_client import GeminiQuotaExceededError, GeminiRateLimitedError
except ImportError as e:
    print(f"⚠️ Warning: Could not import from feature_up_cv: {e}")
    calculate_matching_score_from_payload = None
    llm_parser_cv = None
    llm_parser_company = None
    GeminiQuotaExceededError = None
    GeminiRateLimitedError = None


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


@router.post("/match-cv-jd", status_code=status.HTTP_200_OK)
async def analyze_cv_jd_match(
    request_body: AnalysisCVJDRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Analyze CV and JD match - Extract từ file và thực hiện matching
    Optional: include company research for additional matching context
    
    Request body:
    {
        "cv_file_path": "/tmp/interview_cv_uploads/cv_1_cv.pdf",
        "jd_file_path": "/tmp/interview_jd_uploads/jd_1_jd.pdf",
        "company_file_path": "/tmp/interview_company_uploads/company_1_company.pdf"  # Optional
    }
    
    Returns:
    {
        "success": true,
        "data": {
            "overall_score": 85,
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
        
        # ── LLM parser CV ─────────────────────────────
        step = "llm_parser_cv"
        cv_started_at = time.perf_counter()
        try:
            cv_data = llm_parser_cv(cv_text)
            _log_parser_result("CV", cv_started_at, True)
        except Exception as e:
            _log_parser_result("CV", cv_started_at, False, str(e))
            raise

        # ── Text extract: JD ───────────────────────
        step = "extract_jd_text"
        jd_text = extract_text_auto(str(jd_file_path))
        
        if not jd_text or len(jd_text.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không thể trích xuất văn bản từ file JD"
            )
        
        # ── LLM parser JD ──────────
        step = "llm_parser_jd"
        jd_started_at = time.perf_counter()
        try:
            jd_data = llm_parser_jd(jd_text=jd_text)
            _log_parser_result("JD", jd_started_at, True)
        except Exception as e:
            _log_parser_result("JD", jd_started_at, False, str(e))
            raise
        
        # ── Extract Company Research (optional) ───────
        step = "maybe_extract_company_info"
        company_data = None
        if company_file_path:
            try:
                step = "extract_company_text"
                company_text = extract_text_auto(str(company_file_path))
                if not company_text or len(company_text.strip()) == 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Không thể trích xuất văn bản từ file Công ty"
                    )

                step = "llm_parser_company"
                company_started_at = time.perf_counter()
                company_info = llm_parser_company(company_text)
                if company_info.get("success"):
                    _log_parser_result("COMPANY", company_started_at, True)
                    company_data = company_info
                    print(f"parser company info success")
                else:
                    _log_parser_result("COMPANY", company_started_at, False, company_info.get("error"))
                    print(f"⚠️ Company extraction failed: {company_info.get('error')}")
            except Exception as e:
                if "company_started_at" in locals():
                    _log_parser_result("COMPANY", company_started_at, False, str(e))
                print(f"⚠️ Company extraction error: {e}")
        
        # ── Call score_matching (LLM) ───────────────
        step = "llm_match_score"
        score_started_at = time.perf_counter()
        try:
            analysis_result = calculate_matching_score_from_payload(cv_data, jd_data)
            _log_parser_result("MATCH_SCORE", score_started_at, True)
        except Exception as e:
            _log_parser_result("MATCH_SCORE", score_started_at, False, str(e))
            raise
        
        # ── Build response ────────────────────────────
        step = "build_response"
        response_data = {
            "overall_score": analysis_result.get("overall_score", 0),
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
            pass