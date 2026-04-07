# -*- coding: utf-8 -*-
"""
Analysis endpoints for CV-JD matching
"""
import os
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from docx import Document as DocxDocument
import pypdf

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

# Import utilities from feature_up_cv using absolute imports
try:
    from app.feature.feature_up_cv.score_matching import calculate_matching_score
    from app.feature.feature_up_cv.extract_cv import extract_text, classify_pdf, robust_parse
    from app.feature.feature_up_cv.extract_company import extract_company_info
except ImportError as e:
    print(f"⚠️ Warning: Could not import from feature_up_cv: {e}")
    calculate_matching_score = None
    extract_text = None
    classify_pdf = None
    robust_parse = None
    extract_company_info = None


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


def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from PDF file"""
    try:
        with open(file_path, "rb") as f:
            pdf_reader = pypdf.PdfReader(f)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        raise Exception(f"Lỗi khi đọc file PDF: {str(e)}")


def extract_text_from_docx(file_path: str) -> str:
    """Extract text from DOCX file"""
    try:
        doc = DocxDocument(file_path)
        text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
        return text.strip()
    except Exception as e:
        raise Exception(f"Lỗi khi đọc file DOCX: {str(e)}")


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
    
    if not calculate_matching_score:
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
    
    temp_cv_json = None
    temp_jd_json = None
    
    try:
        # ── Extract CV from PDF ────────────────────
        cv_text = extract_text(str(cv_file_path))
        
        if not cv_text or len(cv_text.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không thể trích xuất văn bản từ file CV"
            )
        
        # Parse CV using LLM
        cv_data = robust_parse(cv_text)
        
        # ── Extract JD from DOCX/PDF ──────────────────
        if str(jd_file_path).lower().endswith('.docx'):
            jd_text = extract_text_from_docx(str(jd_file_path))
        else:
            jd_text = extract_text_from_pdf(str(jd_file_path))
        
        if not jd_text or len(jd_text.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không thể trích xuất văn bản từ file JD"
            )
        
        # Create JD data structure
        jd_data = {
            "job_title": "Job Description",
            "content": jd_text,
            "word_count": len(jd_text.split()),
            "file_name": jd_file_path.name
        }
        
        # ── Extract Company Research (optional) ─────────
        company_data = None
        if company_file_path:
            try:
                if extract_company_info:
                    company_info = extract_company_info(str(company_file_path))
                    if company_info.get("success"):
                        company_data = company_info
                        print(f"✅ Company info extracted: {company_data}")
                    else:
                        print(f"⚠️ Company extraction failed: {company_info.get('error')}")
                else:
                    print(f"⚠️ extract_company_info function not available")
            except Exception as e:
                print(f"⚠️ Company extraction error: {e}")
        
        # ── Create temporary JSON files for score_matching ────
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as cv_file:
            temp_cv_json = cv_file.name
            json.dump(cv_data, cv_file, ensure_ascii=False, indent=2)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as jd_file:
            temp_jd_json = jd_file.name
            json.dump(jd_data, jd_file, ensure_ascii=False, indent=2)
        
        # ── Call score_matching ──────────────────────
        analysis_result = calculate_matching_score(temp_cv_json, temp_jd_json)
        
        # ── Build response ────────────────────────────
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
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis error: {str(e)}"
        )
    
    finally:
        # Clean up temporary JSON files
        if temp_cv_json and os.path.exists(temp_cv_json):
            try:
                os.remove(temp_cv_json)
            except Exception:
                pass
        
        if temp_jd_json and os.path.exists(temp_jd_json):
            try:
                os.remove(temp_jd_json)
            except Exception:
                pass
            except Exception:
                pass

