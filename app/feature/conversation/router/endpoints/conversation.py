import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.feature.auth.models.user import User
from app.feature.conversation.schema import (
    CVPreview,
    ConversationResponse,
    ConversationStartRequest,
    ConversationListResponse,
    ConversationPaginatedResponse,
    ConversationAnalysisReportResponse,
    ConversationAnalysisReportPaginatedResponse,
    SendCandidateAnswerRequest,
    GetNextQuestionResponse,
)
from app.feature.conversation.service import ConversationService
from app.feature.conversation.service import MIN_CANDIDATE_ANSWERS_FOR_ANALYSIS_REPORT
from app.feature.feature_up_cv.auth.models.cv_profile import CVProfile
from app.feature.feature_up_cv.auth.models.analysis_session import AnalysisSession
from app.feature.feature_up_cv.auth.services.cv_profile_service import CVProfileService
from app.feature.feature_up_cv.auth.services.analysis_session_service import AnalysisSessionService
from app.feature.feature_up_cv.file_storage import load_result_analysis

logger = logging.getLogger(__name__)
router = APIRouter()


def _clean_metadata_value(value: str | None) -> str | None:
    if not value:
        return None

    value = re.sub(r"\s+", " ", value).strip(" :-–—\t\r\n")
    return value or None


def _extract_interview_metadata_from_job_description(job_description: str | None) -> tuple[str | None, str | None]:
    if not job_description:
        return None, None

    text = job_description.strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    job_position = None
    company_name = None

    for line in lines[:20]:
        match = re.search(r"^(?:vị\s*trí|vi\s*tri|position|job\s*title)\s*[:：]\s*(.+)$", line, re.IGNORECASE)
        if match:
            job_position = _clean_metadata_value(match.group(1))
            break

    if not job_position and lines:
        first_line = re.sub(r"^\[[^\]]+\]\s*", "", lines[0]).strip()
        first_line = re.sub(
            r"^(?:tuyển\s*dụng|tuyen\s*dung|hiring|recruiting)\s+",
            "",
            first_line,
            flags=re.IGNORECASE,
        )
        job_position = _clean_metadata_value(first_line)

    if lines:
        bracket_match = re.match(r"^\[([^\]]+)\]", lines[0])
        if bracket_match:
            company_name = _clean_metadata_value(bracket_match.group(1))

    if not company_name:
        for line in lines[:20]:
            match = re.search(r"^(?:công\s*ty|cong\s*ty|company)\s*[:：]\s*(.+)$", line, re.IGNORECASE)
            if match:
                company_name = _clean_metadata_value(match.group(1))
                break

    return job_position, company_name


def _extract_interview_metadata(result_file_url: str | None) -> tuple[str | None, str | None]:
    if not result_file_url:
        return None, None

    analysis_result = load_result_analysis(result_file_url) or {}
    job_position = analysis_result.get("job_position") or None

    company_match = analysis_result.get("company_match")
    company_name = None
    if isinstance(company_match, dict):
        company_name = company_match.get("company_name") or None

    return job_position, company_name


def _next_retry_job_position(job_position: str) -> str:
    retry_match = re.search(r"\s*-\s*lần\s*(\d+)\s*$", job_position, re.IGNORECASE)
    if not retry_match:
        return f"{job_position} - lần 2"

    retry_number = int(retry_match.group(1)) + 1
    base_position = job_position[: retry_match.start()].strip()
    return f"{base_position} - lần {retry_number}"


async def _get_conversation_cv_profile(
    *,
    conversation,
    db: AsyncSession,
) -> tuple[CVProfile, AnalysisSession] | tuple[None, None]:
    logger.debug(
        f"[cv_profile] session_id={conversation.session_id} "
        f"analysis_session_id={conversation.analysis_session_id}"
    )
    if not conversation.analysis_session_id:
        logger.debug("[cv_profile] SKIP: analysis_session_id is null → cv_preview=None")
        return None, None

    session_service = AnalysisSessionService(db)
    analysis_session = await session_service.get_by_id(conversation.analysis_session_id)
    if not analysis_session:
        logger.warning(
            f"[cv_profile] SKIP: analysis_session {conversation.analysis_session_id} not found"
        )
        return None, None
    if analysis_session.user_id != conversation.user_id:
        logger.warning(
            f"[cv_profile] SKIP: analysis_session.user_id={analysis_session.user_id} "
            f"!= conversation.user_id={conversation.user_id}"
        )
        return None, None

    logger.debug(
        f"[cv_profile] analysis_session found: id_session={analysis_session.id_session} "
        f"id_cv={analysis_session.id_cv}"
    )
    cv_profile = await CVProfileService(db).get_by_id(analysis_session.id_cv)
    if not cv_profile:
        logger.warning(
            f"[cv_profile] SKIP: cv_profile with id_cv={analysis_session.id_cv} not found"
        )
        return None, None

    logger.debug(
        f"[cv_profile] cv_profile found: id_cv={cv_profile.id_cv} "
        f"raw_file_url={cv_profile.raw_file_url!r}"
    )
    return cv_profile, analysis_session


async def _build_cv_preview(
    *,
    conversation,
    db: AsyncSession,
) -> CVPreview | None:
    cv_profile, _ = await _get_conversation_cv_profile(conversation=conversation, db=db)
    if not cv_profile:
        logger.debug("[cv_preview] cv_profile is None → cv_preview=None")
        return None
    if not cv_profile.raw_file_url:
        logger.warning(
            f"[cv_preview] cv_profile.id_cv={cv_profile.id_cv} has no raw_file_url → cv_preview=None"
        )
        return None

    file_path = Path(cv_profile.raw_file_url)
    logger.debug(
        f"[cv_preview] built: id_cv={cv_profile.id_cv} file={file_path.name}"
    )
    return CVPreview(
        id_cv=cv_profile.id_cv,
        file_name=file_path.name,
        preview_url=f"{settings.API_PREFIX}/conversations/{conversation.session_id}/cv-preview",
    )


@router.post(
    "/",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo phiên phỏng vấn mới",
)
async def start_interview(
    request: ConversationStartRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """
    Tạo một phiên phỏng vấn mới.
    
    - job_description: Mô tả công việc
    - cv_profile: Thông tin CV của ứng viên
    """
    logger.info(f"[start_interview] User {current_user.id} ({current_user.email}) starting new interview")
    service = ConversationService(db)

    job_description = request.job_description
    cv_profile = request.cv_profile
    job_position = request.job_position
    company_name = request.company_name
    analysis_session_id = request.analysis_session_id

    if analysis_session_id is None and request.session_id:
        if not request.session_id.isdigit():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="`session_id` cũ phải là ID số của analysis_sessions; hãy dùng `analysis_session_id`",
            )
        analysis_session_id = int(request.session_id)

    if analysis_session_id:
        session_service = AnalysisSessionService(db)
        analysis_session = await session_service.get_by_id(analysis_session_id)
        if not analysis_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session không tìm thấy (analysis_sessions)",
            )
        if analysis_session.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền truy cập session này",
            )
        if not analysis_session.jd_raw_text or not analysis_session.cv_raw_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session chưa có dữ liệu raw text (cv_raw_text/jd_raw_text)",
            )
        job_description = analysis_session.jd_raw_text
        cv_profile = analysis_session.cv_raw_text
        extracted_job_position, extracted_company_name = _extract_interview_metadata(
            analysis_session.result_analysis_file_url
        )
        job_position = job_position or extracted_job_position
        company_name = company_name or extracted_company_name
    else:
        extracted_job_position, extracted_company_name = _extract_interview_metadata_from_job_description(
            job_description
        )
        job_position = job_position or extracted_job_position
        company_name = company_name or extracted_company_name

    job_position = job_position.strip() if job_position else None
    company_name = company_name.strip() if company_name else None

    if not job_position:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Thiếu tên vị trí phỏng vấn (job_position)",
        )

    conversation = await service.create_conversation(
        user_id=current_user.id,
        job_position=job_position,
        company_name=company_name,
        job_description=job_description or "",
        cv_profile=cv_profile or "",
        analysis_session_id=analysis_session_id,
    )
    logger.info(f"[start_interview] Created conversation: session_id={conversation.session_id}, id={conversation.id}")
    await db.commit()
    return ConversationResponse.model_validate(conversation)


@router.get(
    "/",
    response_model=ConversationPaginatedResponse,
    summary="Lấy danh sách phiên phỏng vấn",
)
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: str | None = Query(None),
    job_position: str | None = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationPaginatedResponse:
    """
    Lấy danh sách phiên phỏng vấn của người dùng.
    
    - page: Trang (mặc định 1)
    - page_size: Số lượng trên mỗi trang (mặc định 10, tối đa 100)
    - status: Lọc theo trạng thái (active, completed, paused)
    """
    logger.debug(f"[list_conversations] Listing conversations for user {current_user.id}, page={page}, page_size={page_size}, status={status}")
    service = ConversationService(db)
    conversations, total = await service.get_user_conversations(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        status=status,
        job_position=job_position
    )
    
    items = []
    for conv in conversations:
        items.append(ConversationListResponse(
            id=conv.id,
            session_id=conv.session_id,
            analysis_session_id=conv.analysis_session_id,
            user_id=conv.user_id,
            job_position=conv.job_position,
            company_name=conv.company_name,
            status=conv.status,
            score=conv.score,
            started_at=conv.started_at,
            ended_at=conv.ended_at,
            interview_duration_seconds=conv.interview_duration_seconds,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=len(conv.messages),
        ))
    
    logger.info(f"[list_conversations] Found {total} conversations for user {current_user.id}")
    return ConversationPaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


@router.get(
    "/analysis-reports",
    response_model=ConversationAnalysisReportPaginatedResponse,
    summary="Lấy danh sách báo cáo phân tích",
)
async def list_analysis_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: str | None = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationAnalysisReportPaginatedResponse:
    """
    Lấy danh sách báo cáo phân tích đã tạo của người dùng.

    - page: Trang (mặc định 1)
    - page_size: Số lượng trên mỗi trang (mặc định 10, tối đa 100)
    - status: Lọc theo trạng thái báo cáo (mặc định lấy tất cả)
    """
    logger.debug(
        f"[list_analysis_reports] Listing reports for user {current_user.id}, "
        f"page={page}, page_size={page_size}, status={status}"
    )
    service = ConversationService(db)
    report_rows, total = await service.get_user_analysis_reports(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        status=status,
    )

    return ConversationAnalysisReportPaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[
            _build_analysis_report_response(
                report=report,
                conversation=conversation,
                total_messages=total_messages,
            )
            for report, conversation, total_messages in report_rows
        ],
    )


@router.get(
    "/{session_id}",
    response_model=ConversationResponse,
    summary="Lấy chi tiết phiên phỏng vấn",
)
async def get_conversation(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Lấy thông tin chi tiết về một phiên phỏng vấn"""
    logger.debug(f"[get_conversation] Getting conversation session_id={session_id} for user {current_user.id}")
    service = ConversationService(db)
    conversation = await service.get_conversation_by_session_id(session_id)
    
    if not conversation:
        logger.warning(f"[get_conversation] Conversation not found: session_id={session_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phiên phỏng vấn không tìm thấy",
        )
    
    if conversation.user_id != current_user.id:
        logger.warning(f"[get_conversation] Unauthorized access to conversation {session_id} by user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập phiên phỏng vấn này",
        )
    
    logger.info(f"[get_conversation] Retrieved conversation: session_id={session_id}, status={conversation.status}")
    return ConversationResponse.model_validate(conversation)


@router.post(
    "/{session_id}/retry",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo vòng phỏng vấn lại từ phiên cũ",
)
async def retry_interview(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """
    Tạo một phiên phỏng vấn mới từ JD/CV đã dùng ở phiên cũ.

    Dùng khi người dùng không hài lòng với báo cáo phân tích và muốn phỏng vấn lại
    mà không upload lại CV/JD. Phiên mới sẽ có session_id mới, chưa có messages,
    và giữ liên kết analysis_session_id nếu phiên gốc có.
    """
    logger.info(f"[retry_interview] User {current_user.id} retrying session_id={session_id}")
    service = ConversationService(db)
    conversation = await service.get_conversation_by_session_id(session_id)

    if not conversation:
        logger.warning(f"[retry_interview] Conversation not found: session_id={session_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phiên phỏng vấn không tìm thấy",
        )

    if conversation.user_id != current_user.id:
        logger.warning(f"[retry_interview] Unauthorized access by user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập phiên phỏng vấn này",
        )

    if conversation.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chỉ có thể phỏng vấn lại sau khi phiên cũ đã hoàn thành và có kết quả phân tích",
        )

    existing_report = await service.get_analysis_report_by_conversation_id(conversation.id)
    if not existing_report:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phiên cũ chưa có báo cáo phân tích để bắt đầu phỏng vấn lại",
        )

    try:
        new_conversation = await service.create_conversation(
            user_id=current_user.id,
            job_position=_next_retry_job_position(conversation.job_position),
            company_name=conversation.company_name,
            job_description=conversation.job_description,
            cv_profile=conversation.cv_profile,
            analysis_session_id=conversation.analysis_session_id,
            force_new=True,
        )
        await db.commit()
        logger.info(
            f"[retry_interview] Created retry conversation: "
            f"old_session_id={session_id}, new_session_id={new_conversation.session_id}"
        )
        return ConversationResponse.model_validate(new_conversation)
    except Exception as e:
        await db.rollback()
        logger.error(f"[retry_interview] Error creating retry conversation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi tạo phiên phỏng vấn lại: {str(e)}",
        )


@router.post(
    "/{session_id}/next-question",
    response_model=GetNextQuestionResponse,
    summary="Lấy câu hỏi tiếp theo",
)
async def get_next_question(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> GetNextQuestionResponse:
    """
    Lấy câu hỏi tiếp theo hoặc câu hỏi đầu tiên.
    
    - Nếu không có message nào -> tạo câu hỏi đầu tiên
    - Nếu có message -> tạo câu hỏi dựa trên câu trả lời trước
    """
    logger.debug(f"[get_next_question] Getting next question for session_id={session_id}")
    service = ConversationService(db)
    conversation = await service.get_conversation_by_session_id(session_id)
    
    if not conversation:
        logger.warning(f"[get_next_question] Conversation not found: session_id={session_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phiên phỏng vấn không tìm thấy",
        )
    
    if conversation.user_id != current_user.id:
        logger.warning(f"[get_next_question] Unauthorized access by user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập phiên phỏng vấn này",
        )
    
    if conversation.status != "active":
        logger.warning(f"[get_next_question] Conversation not active: session_id={session_id}, status={conversation.status}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phiên phỏng vấn không còn hoạt động",
        )
    
    try:
        # Get last message or generate initial question
        last_message = await service.get_last_message(conversation.id)
        
        if not last_message or last_message.role == "candidate":
            # Generate next question
            if last_message:
                logger.info(f"[get_next_question] Generating next question after candidate answer")
                question = await service.generate_next_question(
                    conversation.id,
                    previous_answer=last_message.answer,
                )
            else:
                # First question
                logger.info(f"[get_next_question] Generating initial question for session_id={session_id}")
                question = await service.generate_initial_question(conversation.id)
        else:
            logger.warning(f"[get_next_question] Waiting for candidate answer in session_id={session_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chờ ứng viên trả lời câu hỏi trước",
            )
        
        # Save question message
        message = await service.add_message(
            conversation_id=conversation.id,
            role="interviewer",
            content=question,
            question=question,
        )
        await db.commit()
        
        logger.info(f"[get_next_question] Question generated and saved: message_id={message.id}")
        return GetNextQuestionResponse(
            session_id=session_id,
            question=question,
            message_id=message.id,
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"[get_next_question] Error generating question: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi tạo câu hỏi: {str(e)}",
        )


@router.post(
    "/{session_id}/answer",
    response_model=GetNextQuestionResponse,
    summary="Gửi câu trả lời",
)
async def send_answer(
    session_id: str,
    request: SendCandidateAnswerRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> GetNextQuestionResponse:
    """
    Gửi câu trả lời của ứng viên và nhận câu hỏi tiếp theo.
    """
    logger.debug(f"[send_answer] Receiving answer for session_id={session_id}")
    service = ConversationService(db)
    conversation = await service.get_conversation_by_session_id(session_id)
    
    if not conversation:
        logger.warning(f"[send_answer] Conversation not found: session_id={session_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phiên phỏng vấn không tìm thấy",
        )
    
    if conversation.user_id != current_user.id:
        logger.warning(f"[send_answer] Unauthorized access by user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập phiên phỏng vấn này",
        )
    
    if conversation.status != "active":
        logger.warning(f"[send_answer] Conversation not active: session_id={session_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phiên phỏng vấn không còn hoạt động",
        )
    
    try:
        # Save candidate answer
        logger.info(f"[send_answer] Saving candidate answer for session_id={session_id}, answer_length={len(request.answer)}")
        await service.add_message(
            conversation_id=conversation.id,
            role="candidate",
            content=request.answer,
            answer=request.answer,
        )
        
        # Generate next question
        logger.info(f"[send_answer] Generating next question based on answer")
        question = await service.generate_next_question(
            conversation.id,
            previous_answer=request.answer,
        )
        
        # Save question message
        message = await service.add_message(
            conversation_id=conversation.id,
            role="interviewer",
            content=question,
            question=question,
        )
        await db.commit()
        
        logger.info(f"[send_answer] Next question generated: message_id={message.id}")
        return GetNextQuestionResponse(
            session_id=session_id,
            question=question,
            message_id=message.id,
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"[send_answer] Error processing answer: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi gửi câu trả lời: {str(e)}",
        )


def _build_analysis_report_response(
    *,
    report,
    conversation,
    total_messages: int,
    cv_preview: CVPreview | None = None,
) -> ConversationAnalysisReportResponse:
    return ConversationAnalysisReportResponse(
        id=report.id,
        session_id=conversation.session_id,
        conversation_id=conversation.id,
        analysis_session_id=conversation.analysis_session_id,
        user_id=conversation.user_id,
        job_position=conversation.job_position,
        company_name=conversation.company_name,
        job_description=conversation.job_description,
        status=report.status,
        total_messages=total_messages,
        started_at=conversation.started_at,
        ended_at=conversation.ended_at,
        interview_duration_seconds=conversation.interview_duration_seconds,
        cv_preview=cv_preview,
        overall_score=report.overall_score,
        overall_grade=report.overall_grade,
        level=report.level,
        summary=report.summary,
        tags=report.tags,
        scores=report.scores,
        ai_coach_insights=report.ai_coach_insights,
        strengths=report.strengths,
        weaknesses=report.weaknesses,
        knowledge_gaps=report.knowledge_gaps,
        study_plan=report.study_plan,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


@router.get(
    "/{session_id}/cv-preview",
    summary="Preview file CV gốc của báo cáo phỏng vấn",
)
async def preview_conversation_cv(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """
    Trả file CV gốc ở dạng inline để FE render preview PDF.
    """
    service = ConversationService(db)
    conversation = await service.get_conversation_by_session_id(session_id)

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phiên phỏng vấn không tìm thấy",
        )

    if conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập phiên phỏng vấn này",
        )

    cv_profile, _ = await _get_conversation_cv_profile(conversation=conversation, db=db)
    if not cv_profile or not cv_profile.raw_file_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy file CV gốc cho báo cáo này",
        )

    file_path = Path(cv_profile.raw_file_url)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File CV gốc không còn tồn tại trên hệ thống",
        )

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=file_path.name,
        headers={"Content-Disposition": f'inline; filename="{file_path.name}"'},
    )


@router.post(
    "/{session_id}/analysis-report",
    response_model=ConversationAnalysisReportResponse,
    summary="Tạo báo cáo phân tích kết quả phỏng vấn",
)
async def create_analysis_report(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationAnalysisReportResponse:
    """
    Kết thúc phiên phỏng vấn nếu cần và tạo báo cáo phân tích kết quả.
    """
    logger.info(f"[analysis_report] Creating analysis report for session_id={session_id}")
    service = ConversationService(db)
    conversation = await service.get_conversation_by_session_id(session_id)
    
    if not conversation:
        logger.warning(f"[analysis_report] Conversation not found: session_id={session_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phiên phỏng vấn không tìm thấy",
        )
    
    if conversation.user_id != current_user.id:
        logger.warning(f"[analysis_report] Unauthorized access by user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập phiên phỏng vấn này",
        )

    messages = await service.get_conversation_messages(conversation.id)
    existing_report = await service.get_analysis_report_by_conversation_id(conversation.id)

    if existing_report:
        logger.info(f"[analysis_report] Returning saved analysis report for session_id={session_id}")
        return _build_analysis_report_response(
            report=existing_report,
            conversation=conversation,
            total_messages=len(messages),
            cv_preview=await _build_cv_preview(conversation=conversation, db=db),
        )

    if conversation.status not in {"active", "completed"}:
        logger.warning(
            f"[analysis_report] Conversation status does not allow report generation: "
            f"session_id={session_id}, status={conversation.status}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể tạo báo cáo cho trạng thái phiên phỏng vấn hiện tại",
        )

    valid_answer_count = await service.count_valid_candidate_answers(conversation.id)
    if valid_answer_count < MIN_CANDIDATE_ANSWERS_FOR_ANALYSIS_REPORT:
        logger.warning(
            f"[analysis_report] Not enough candidate answers: "
            f"session_id={session_id}, answers={valid_answer_count}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Cần trả lời ít nhất "
                f"{MIN_CANDIDATE_ANSWERS_FOR_ANALYSIS_REPORT} câu hỏi trước khi tạo báo cáo phân tích"
            ),
        )
    
    try:
        logger.info(f"[analysis_report] Generating analysis report for session_id={session_id}")
        report = await service.create_analysis_report(conversation.id)
        await db.commit()
        await db.refresh(conversation)
        messages = await service.get_conversation_messages(conversation.id)
        logger.info(
            f"[analysis_report] Analysis report created successfully: "
            f"total_messages={len(messages)}, score={report.overall_score}"
        )
        
        return _build_analysis_report_response(
            report=report,
            conversation=conversation,
            total_messages=len(messages),
            cv_preview=await _build_cv_preview(conversation=conversation, db=db),
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"[analysis_report] Error creating analysis report: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi tạo báo cáo phân tích: {str(e)}",
        )


@router.get(
    "/{session_id}/analysis-report",
    response_model=ConversationAnalysisReportResponse,
    summary="Lấy báo cáo phân tích kết quả phỏng vấn",
)
async def get_analysis_report(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationAnalysisReportResponse:
    """
    Lấy báo cáo phân tích đã tạo cho phiên phỏng vấn.
    """
    logger.debug(f"[get_analysis_report] Getting analysis report for session_id={session_id}")
    service = ConversationService(db)
    conversation = await service.get_conversation_by_session_id(session_id)

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phiên phỏng vấn không tìm thấy",
        )

    if conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập phiên phỏng vấn này",
        )

    report = await service.get_analysis_report_by_conversation_id(conversation.id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Báo cáo phân tích chưa được tạo",
        )

    messages = await service.get_conversation_messages(conversation.id)
    return _build_analysis_report_response(
        report=report,
        conversation=conversation,
        total_messages=len(messages),
        cv_preview=await _build_cv_preview(conversation=conversation, db=db),
    )


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = ConversationService(db)
    try:
        await service.delete_conversation(conversation_id, user_id=current_user.id)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
