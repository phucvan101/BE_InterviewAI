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

router = APIRouter()


@router.post(
    "",
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
    service = ConversationService(db)
    conversation = await service.create_conversation(
        user_id=current_user.id,
        job_description=request.job_description,
        cv_profile=request.cv_profile,
    )
    await db.commit()
    return ConversationResponse.model_validate(conversation)


@router.get(
    "",
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
    
    if conversation.status != "active":
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
                question = await service.generate_next_question(
                    conversation.id,
                    previous_answer=last_message.answer,
                )
            else:
                # First question
                question = await service.generate_initial_question(conversation.id)
        else:
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
        
        return GetNextQuestionResponse(
            session_id=session_id,
            question=question,
            message_id=message.id,
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
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
    
    if conversation.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phiên phỏng vấn không còn hoạt động",
        )
    
    try:
        # Save candidate answer
        await service.add_message(
            conversation_id=conversation.id,
            role="candidate",
            content=request.answer,
            answer=request.answer,
        )
        
        # Generate next question
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
        
        return GetNextQuestionResponse(
            session_id=session_id,
            question=question,
            message_id=message.id,
        )
    except Exception as e:
        await db.rollback()
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
    
    if conversation.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phiên phỏng vấn không còn hoạt động",
        )
    
    try:
        # Evaluate the interview
        evaluation = await service.evaluate_answer(conversation.id)
        
        # Update conversation with result
        score = evaluation.get("fit_score", 0)
        await service.end_conversation(
            conversation.id,
            result=evaluation,
            score=score,
        )
        await db.commit()
        
        messages = await service.get_conversation_messages(conversation.id)
        
        return InterviewResultResponse(
            session_id=session_id,
            status=conversation.status,
            score=score,
            result=evaluation,
            total_messages=len(messages),
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi kết thúc phỏng vấn: {str(e)}",
        )
