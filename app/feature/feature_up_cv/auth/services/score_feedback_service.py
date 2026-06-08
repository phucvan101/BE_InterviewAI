import json
import logging
import asyncio
from typing import Optional, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.feature.feature_up_cv.auth.schemas.score_feedback import FeedbackRequest, FeedbackResponse
from app.feature.feature_up_cv.feedback_agent.agent import feedback_agent
from app.feature.feature_up_cv.auth.models.cv_profile import CVProfile
from app.feature.feature_up_cv.auth.models.job_description import JobDescription
from app.feature.feature_up_cv.auth.models.score_override import ScoreOverride
from app.feature.feature_up_cv.auth.models.analysis_session import AnalysisSession
from app.feature.feature_up_cv.scoring.hybrid_scoring import calculate_hybrid_score
from app.feature.feature_up_cv.core.file_storage import save_result_analysis, load_parser_result

logger = logging.getLogger(__name__)


async def _get_cv_text(cv_id: str, db: AsyncSession) -> str:
    try:
        result = await db.execute(
            select(CVProfile).where(CVProfile.id_cv == int(cv_id))
        )
        cv_record = result.scalar_one_or_none()
        if cv_record and cv_record.raw_file_url:
            from app.feature.feature_up_cv.core.text_extract import extract_text_auto
            text = extract_text_auto(cv_record.raw_file_url)
            return text or ""
    except Exception as e:
        logger.warning(f"[FEEDBACK_AGENT] Không lấy được CV text từ id={cv_id}: {e}")
    return ""


async def _get_jd_text(jd_id: str, db: AsyncSession) -> str:
    try:
        result = await db.execute(
            select(JobDescription).where(JobDescription.id_jd == int(jd_id))
        )
        jd_record = result.scalar_one_or_none()
        if jd_record and jd_record.raw_file_url:
            from app.feature.feature_up_cv.core.text_extract import extract_text_auto
            text = extract_text_auto(jd_record.raw_file_url)
            return text or ""
    except Exception as e:
        logger.warning(f"[FEEDBACK_AGENT] Không lấy được JD text từ id={jd_id}: {e}")
    return ""


async def handle_feedback(request: FeedbackRequest, db: AsyncSession) -> FeedbackResponse:
    """
    Luồng xử lý Feedback của LangChain Agent có Override:
    1. Trích xuất văn bản từ CV và JD.
    2. Chạy LangChain Agent để phân tích, kích hoạt Tools (YAML, FAISS).
    3. Nếu feedback hợp lệ và có đề xuất ghi đè (proposed_overrides):
       - Lưu hoặc cập nhật ScoreOverride vào DB.
       - Kích hoạt Re-scoring để chấm lại điểm và cập nhật AnalysisSession.
    """
    logger.info(f"[FEEDBACK_AGENT] Nhận phản hồi LangChain: cv_id={request.cv_id}, jd_id={request.jd_id}")

    raw_cv_text = await _get_cv_text(request.cv_id, db)
    jd_text = await _get_jd_text(request.jd_id, db)

    if not raw_cv_text:
        raw_cv_text = "(Không tìm thấy nội dung CV trong hệ thống)"
    if not jd_text:
        jd_text = "(Không tìm thấy nội dung JD trong hệ thống)"

    try:
        # Gọi LangChain Agent
        agent_result = await feedback_agent.run(
            cv_text=raw_cv_text,
            jd_text=jd_text,
            feedback_text=request.feedback_text
        )
    except Exception as e:
        logger.error(f"[FEEDBACK_AGENT] Lỗi trong quá trình chạy LangChain Agent: {e}", exc_info=True)
        return FeedbackResponse(
            success=False,
            is_overridden=False,
            rationale=f"Lỗi hệ thống Agent: {str(e)[:100]}"
        )

    # Nếu khiếu nại không hợp lý
    if not agent_result.is_valid_complaint:
        return FeedbackResponse(
            success=True,
            is_overridden=False,
            rationale=agent_result.rationale,
            learned_rule=None
        )

    # Xử lý khiếu nại hợp lý
    is_overridden = False
    new_scores_response = None

    if agent_result.proposed_overrides:
        # 1. Lưu điểm ghi đè (ScoreOverride) vào DB
        try:
            # Kiểm tra xem đã có override chưa
            stmt = select(ScoreOverride).where(
                ScoreOverride.cv_id == str(request.cv_id),
                ScoreOverride.jd_id == str(request.jd_id)
            )
            res = await db.execute(stmt)
            existing_override = res.scalar_one_or_none()

            # Chuẩn hóa overrides
            clean_overrides = {k: float(v) for k, v in agent_result.proposed_overrides.items()}
            
            if existing_override:
                existing_override.overridden_scores = clean_overrides
                existing_override.rationale = agent_result.rationale
            else:
                new_override = ScoreOverride(
                    cv_id=str(request.cv_id),
                    jd_id=str(request.jd_id),
                    overridden_scores=clean_overrides,
                    rationale=agent_result.rationale
                )
                db.add(new_override)
            
            await db.flush()
            is_overridden = True
            new_scores_response = {k: int(v) for k, v in clean_overrides.items()}
            logger.info(f"[FEEDBACK_AGENT] Đã lưu ScoreOverride vào DB: {clean_overrides}")

            # 2. Tự động chạy lại scoring (Re-scoring) cho các session liên quan
            session_stmt = select(AnalysisSession).where(
                AnalysisSession.id_cv == int(request.cv_id),
                AnalysisSession.id_jd == int(request.jd_id)
            )
            session_res = await db.execute(session_stmt)
            sessions = session_res.scalars().all()

            if sessions:
                for session in sessions:
                    # Đọc parser cached results của CV, JD, CI nếu có
                    cv_svc = CVProfile(id_cv=session.id_cv)
                    # Lấy record CV và JD gốc để nạp parsed json
                    cv_record_stmt = select(CVProfile).where(CVProfile.id_cv == session.id_cv)
                    jd_record_stmt = select(JobDescription).where(JobDescription.id_jd == session.id_jd)
                    
                    cv_rec = (await db.execute(cv_record_stmt)).scalar_one_or_none()
                    jd_rec = (await db.execute(jd_record_stmt)).scalar_one_or_none()

                    cv_data = load_parser_result(cv_rec.parser_file_url) if cv_rec and cv_rec.parser_file_url else {}
                    jd_data = load_parser_result(jd_rec.parser_file_url) if jd_rec and jd_rec.parser_file_url else {}
                    
                    # Gọi tính điểm với overrides mới
                    analysis_result = calculate_hybrid_score(
                        cv_data=cv_data,
                        jd_data=jd_data,
                        score_overrides=clean_overrides
                    )

                    # Lưu kết quả mới vật lý
                    from app.feature.feature_up_cv.auth.api.endpoints.analysis import (
                        _build_skills_detail,
                        _build_main_strengths,
                        _build_areas_for_development,
                        _build_recommendation_response,
                        _build_experience_detail_response
                    )
                    
                    response_data = {
                        "overall_score": analysis_result.get("overall_score", 0),
                        "summary": analysis_result.get("summary", ""),
                        "detailed_scores": analysis_result.get("detailed_scores", {}),
                        "embedding_similarity": analysis_result.get("embedding_similarity", 0.0),
                        "score_rationale": analysis_result.get("score_rationale", ""),
                        "career_objectives_rationale": analysis_result.get("career_objectives_rationale", ""),
                        "company_fit_rationale": analysis_result.get("company_fit_rationale", ""),
                        "matched_skills": analysis_result.get("matched_skills", []),
                        "related_skills": analysis_result.get("related_skills", []),
                        "missing_skills": analysis_result.get("missing_skills", []),
                        "skills_detail": _build_skills_detail(analysis_result),
                        "experience_assessment": analysis_result.get("experience_assessment", ""),
                        "experience_detail": _build_experience_detail_response(analysis_result),
                        "main_strengths": _build_main_strengths(analysis_result),
                        "areas_for_development": _build_areas_for_development(analysis_result),
                        "recommendation": _build_recommendation_response(analysis_result),
                        "cv_candidate": analysis_result.get("cv_candidate", ""),
                        "job_position": analysis_result.get("job_position", ""),
                    }

                    result_file_path = save_result_analysis(
                        response_data,
                        user_id=session.user_id,
                        id_cv=session.id_cv,
                        id_jd=session.id_jd,
                        id_ci=session.id_ci
                    )

                    # Cập nhật điểm trong record Session DB
                    session.score = response_data["overall_score"]
                    session.experience_score = clean_overrides.get("experience_score", session.experience_score)
                    session.skills_score = clean_overrides.get("skills_score", session.skills_score)
                    session.education_score = clean_overrides.get("education_score", session.education_score)
                    session.career_objectives_score = clean_overrides.get("career_objectives_score", session.career_objectives_score)
                    session.companyfit_score = clean_overrides.get("company_fit_score", session.companyfit_score)
                    session.result_analysis_file_url = str(result_file_path)
                    
                await db.commit()
                logger.info("[FEEDBACK_AGENT] Đã re-scoring và cập nhật thành công tất cả session liên quan.")

        except Exception as ex:
            logger.error(f"[FEEDBACK_AGENT] Không thể lưu override hoặc re-score: {ex}", exc_info=True)
            await db.rollback()

    return FeedbackResponse(
        success=True,
        is_overridden=is_overridden,
        rationale=agent_result.rationale,
        new_scores=new_scores_response,
        learned_rule=agent_result.learned_rule
    )
