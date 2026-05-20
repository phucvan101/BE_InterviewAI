import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.feature.auth.models.user import User
from app.feature.conversation.schema import (
    ConversationResponse,
    ConversationStartRequest,
    ConversationListResponse,
    ConversationPaginatedResponse,
    SendCandidateAnswerRequest,
    GetNextQuestionResponse,
    InterviewResultResponse,
)
from app.feature.conversation.service import ConversationService
from app.feature.feature_up_cv.auth.services.analysis_session_service import AnalysisSessionService

logger = logging.getLogger(__name__)
router = APIRouter()


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

    if request.session_id:
        session_service = AnalysisSessionService(db)
        analysis_session = await session_service.get_by_session_id(request.session_id)
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

    conversation = await service.create_conversation(
        user_id=current_user.id,
        job_description=job_description or "",
        cv_profile=cv_profile or "",
        session_id=request.session_id,
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
    )
    
    items = []
    for conv in conversations:
        items.append(ConversationListResponse(
            id=conv.id,
            session_id=conv.session_id,
            user_id=conv.user_id,
            status=conv.status,
            score=conv.score,
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


@router.post(
    "/{session_id}/end",
    response_model=InterviewResultResponse,
    summary="Kết thúc phiên phỏng vấn",
)
async def end_interview(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> InterviewResultResponse:
    """
    Kết thúc phiên phỏng vấn và nhận đánh giá kết quả.
    """
    logger.info(f"[end_interview] Ending interview for session_id={session_id}")
    service = ConversationService(db)
    conversation = await service.get_conversation_by_session_id(session_id)
    
    if not conversation:
        logger.warning(f"[end_interview] Conversation not found: session_id={session_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phiên phỏng vấn không tìm thấy",
        )
    
    if conversation.user_id != current_user.id:
        logger.warning(f"[end_interview] Unauthorized access by user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập phiên phỏng vấn này",
        )
    
    if conversation.status != "active":
        logger.warning(f"[end_interview] Conversation not active: session_id={session_id}, status={conversation.status}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phiên phỏng vấn không còn hoạt động",
        )
    
    try:
        # Evaluate the interview
        logger.info(f"[end_interview] Evaluating interview results for session_id={session_id}")
        evaluation = await service.evaluate_answer(conversation.id)
        
        # Update conversation with result
        score = evaluation.get("fit_score", 0)
        logger.info(f"[end_interview] Interview evaluation complete: score={score}, recommendation={evaluation.get('recommendation')}")
        await service.end_conversation(
            conversation.id,
            result=evaluation,
            score=score,
        )
        await db.commit()
        
        messages = await service.get_conversation_messages(conversation.id)
        logger.info(f"[end_interview] Interview ended successfully: total_messages={len(messages)}, score={score}")
        
        return InterviewResultResponse(
            session_id=session_id,
            status=conversation.status,
            score=score,
            result=evaluation,
            total_messages=len(messages),
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"[end_interview] Error ending interview: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi kết thúc phỏng vấn: {str(e)}",
        )
