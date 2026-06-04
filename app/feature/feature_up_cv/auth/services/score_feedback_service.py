import json
import logging
import asyncio
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.feature.feature_up_cv.auth.schemas.score_feedback import FeedbackRequest, FeedbackResponse
from app.feature.feature_up_cv.feedback_agent.prompts import SYSTEM_PROMPT_EVALUATOR
from app.feature.feature_up_cv.feedback_agent.memory_faiss import agent_memory
from app.feature.feature_up_cv.feedback_agent.synonym_manager import synonym_manager
from app.feature.feature_up_cv.auth.models.cv_profile import CVProfile
from app.feature.feature_up_cv.auth.models.job_description import JobDescription
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
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        pass

    try:
        import re
        match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", response_text)
        if match:
            return json.loads(match.group(1))
    except (json.JSONDecodeError, AttributeError):
        pass

    logger.warning(f"[FEEDBACK_AGENT] Không parse được JSON từ response: {response_text[:300]}")
    return None


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
    Luồng xử lý Feedback KHÔNG Override (Học tập cho tương lai):
    1. Parse LLM.
    2. Lưu learned_rule vào FAISS.
    3. Lưu new_synonyms vào yaml.
    4. Báo thành công, không chấm lại điểm.
    """
    logger.info(f"[FEEDBACK_AGENT] Nhận phản hồi: cv_id={request.cv_id}, jd_id={request.jd_id}")

    raw_cv_text = await _get_cv_text(request.cv_id, db)
    jd_text = await _get_jd_text(request.jd_id, db)

    if not raw_cv_text:
        raw_cv_text = "(Không tìm thấy nội dung CV trong hệ thống)"
    if not jd_text:
        jd_text = "(Không tìm thấy nội dung JD trong hệ thống)"

    prompt = _build_prompt(raw_cv_text, jd_text, request.feedback_text)

    try:
        response_text = await asyncio.to_thread(
            generate_content,
            prompt=prompt,
            step="feedback_agent_evaluation",
        )
    except Exception as e:
        logger.error(f"[FEEDBACK_AGENT] Lỗi khi gọi Gemini: {e}")
        return FeedbackResponse(
            success=False,
            is_overridden=False,
            rationale=f"Không thể kết nối AI để xử lý phản hồi. ({str(e)[:100]})"
        )

    data = _parse_llm_response(response_text)
    if not data:
        return FeedbackResponse(
            success=False,
            is_overridden=False,
            rationale="AI trả về định dạng không hợp lệ. Vui lòng thử lại."
        )

    if data.get("is_valid_complaint"):
        # 1. Lưu Rule vào FAISS
        learned_rule = data.get("learned_rule")
        if learned_rule:
            agent_memory.add_learned_rule(
                rule_text=learned_rule,
                context=request.feedback_text
            )
            
        # 2. Cập nhật Synonyms vào YAML
        new_synonyms = data.get("new_synonyms", [])
        if isinstance(new_synonyms, list) and len(new_synonyms) > 0:
            synonym_manager.add_synonyms(new_synonyms)

        return FeedbackResponse(
            success=True,
            is_overridden=False, # Không ghi đè trực tiếp
            rationale=data.get("rationale", "Phản hồi đã được ghi nhận vào hệ thống học tập."),
            learned_rule=learned_rule
        )
    else:
        return FeedbackResponse(
            success=True,
            is_overridden=False,
            rationale=data.get("rationale", "Phản hồi của bạn đã được ghi nhận nhưng chưa đủ cơ sở để hệ thống học tập.")
        )
