import json
import logging
import asyncio
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.feature.feature_up_cv.auth.schemas.score_feedback import FeedbackRequest, FeedbackResponse
from app.feature.feature_up_cv.feedback_agent.prompts import SYSTEM_PROMPT_EVALUATOR
from app.feature.feature_up_cv.feedback_agent.memory_faiss import agent_memory
from app.feature.feature_up_cv.auth.models.score_override import ScoreOverride
from app.feature.feature_up_cv.auth.models.cv_profile import CVProfile
from app.feature.feature_up_cv.auth.models.job_description import JobDescription

# Dùng gemini_client thật của dự án
from app.feature.feature_up_cv.core.gemini_client import generate_content

logger = logging.getLogger(__name__)


def _build_prompt(raw_cv_text: str, jd_text: str, feedback_text: str) -> str:
    """Ghép nội dung CV, JD và phản hồi người dùng thành một prompt hoàn chỉnh."""
    return f"""{SYSTEM_PROMPT_EVALUATOR}

[RAW_CV_TEXT]:
{raw_cv_text[:4000]}

[JD_TEXT]:
{jd_text[:2000]}

[USER_FEEDBACK]:
{feedback_text}
"""


def _parse_llm_response(response_text: str) -> Optional[dict]:
    """Trích xuất JSON từ response của Gemini (đôi khi Gemini bọc trong code block)."""
    try:
        # Thử parse trực tiếp
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        pass

    try:
        # Loại bỏ markdown code block nếu có (```json ... ```)
        import re
        match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", response_text)
        if match:
            return json.loads(match.group(1))
    except (json.JSONDecodeError, AttributeError):
        pass

    logger.warning(f"[FEEDBACK_AGENT] Không parse được JSON từ response: {response_text[:300]}")
    return None


async def _get_cv_text(cv_id: str, db: AsyncSession) -> str:
    """Lấy raw CV text từ file path lưu trong DB."""
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
    """Lấy raw JD text từ file path lưu trong DB."""
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
    Luồng chính của Agent:
    1. Lấy Raw CV và JD text từ DB (qua file path).
    2. Xây dựng Prompt và gọi Gemini.
    3. Phân tích response của LLM.
    4. Nếu phản hồi hợp lệ: lưu Score Override vào PostgreSQL, lưu bài học vào FAISS.
    5. Trả về kết quả cho FE.
    """
    logger.info(f"[FEEDBACK_AGENT] Nhận phản hồi: cv_id={request.cv_id}, jd_id={request.jd_id}")

    # 1. Lấy text
    raw_cv_text = await _get_cv_text(request.cv_id, db)
    jd_text = await _get_jd_text(request.jd_id, db)

    if not raw_cv_text:
        raw_cv_text = "(Không tìm thấy nội dung CV trong hệ thống)"
    if not jd_text:
        jd_text = "(Không tìm thấy nội dung JD trong hệ thống)"

    # 2. Xây dựng prompt
    prompt = _build_prompt(raw_cv_text, jd_text, request.feedback_text)

    # 3. Gọi Gemini (dùng asyncio.to_thread vì generate_content là sync function)
    try:
        response_text = await asyncio.to_thread(
            generate_content,
            prompt=prompt,
            step="feedback_agent_evaluation",
        )
        logger.info(f"[FEEDBACK_AGENT] Gemini response nhận được ({len(response_text)} chars)")
    except Exception as e:
        logger.error(f"[FEEDBACK_AGENT] Lỗi khi gọi Gemini: {e}")
        return FeedbackResponse(
            success=False,
            is_overridden=False,
            rationale=f"Không thể kết nối AI để xử lý phản hồi. Vui lòng thử lại sau. ({str(e)[:100]})"
        )

    # 4. Parse JSON response
    data = _parse_llm_response(response_text)
    if not data:
        return FeedbackResponse(
            success=False,
            is_overridden=False,
            rationale="AI trả về định dạng không hợp lệ. Vui lòng thử lại."
        )

    # 5. Xử lý kết quả
    if data.get("is_valid_complaint"):
        # 5a. Lưu bài học vào FAISS memory (rút kinh nghiệm tổng quát)
        if data.get("learned_rule"):
            agent_memory.add_learned_rule(
                rule_text=data["learned_rule"],
                context=request.feedback_text
            )
            logger.info(f"[FEEDBACK_AGENT] Đã lưu bài học: {data['learned_rule']}")

        # 5b. Lưu Score Override vào PostgreSQL
        try:
            # Kiểm tra nếu đã có override cho cặp cv-jd này thì cập nhật lại
            existing = await db.execute(
                select(ScoreOverride).where(
                    ScoreOverride.cv_id == request.cv_id,
                    ScoreOverride.jd_id == request.jd_id
                )
            )
            override_record = existing.scalar_one_or_none()

            if override_record:
                override_record.overridden_scores = data.get("adjusted_scores", {})
                override_record.rationale = data.get("rationale", "")
            else:
                override_record = ScoreOverride(
                    cv_id=request.cv_id,
                    jd_id=request.jd_id,
                    overridden_scores=data.get("adjusted_scores", {}),
                    rationale=data.get("rationale", "")
                )
                db.add(override_record)

            await db.commit()
            logger.info(f"[FEEDBACK_AGENT] Đã lưu Score Override cho cv={request.cv_id}, jd={request.jd_id}")
        except Exception as e:
            logger.error(f"[FEEDBACK_AGENT] Lỗi khi lưu Score Override vào DB: {e}")
            await db.rollback()

        return FeedbackResponse(
            success=True,
            is_overridden=True,
            rationale=data.get("rationale", "Điểm đã được cập nhật."),
            new_scores=data.get("adjusted_scores"),
            learned_rule=data.get("learned_rule")
        )
    else:
        return FeedbackResponse(
            success=True,
            is_overridden=False,
            rationale=data.get("rationale", "Phản hồi của bạn đã được ghi nhận nhưng chưa đủ cơ sở để điều chỉnh điểm.")
        )
