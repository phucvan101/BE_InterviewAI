import json
import logging
from typing import Optional

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.feature.conversation.model.conversation import Conversation, ConversationMessage, ConversationStatus, MessageRole
from app.feature.feature_up_cv.gemini_client import generate_content, GeminiConfig

logger = logging.getLogger(__name__)


class ConversationService:
    """Service quản lý conversations và messages"""
    
    def __init__(self, db: AsyncSession):
        self.db = db

    # ──────────────────────────────────────────────────────────────
    # Conversation CRUD
    # ──────────────────────────────────────────────────────────────

    async def create_conversation(
        self,
        user_id: int,
        job_description: str,
        cv_profile: str,
    ) -> Conversation:
        """Tạo conversation mới"""
        conversation = Conversation(
            user_id=user_id,
            job_description=job_description,
            cv_profile=cv_profile,
            status=ConversationStatus.ACTIVE,
        )
        self.db.add(conversation)
        await self.db.flush()  # Get the ID without committing
        await self.db.refresh(conversation)
        logger.info(f"Created conversation: session_id={conversation.session_id}, user_id={user_id}")
        return conversation

    async def get_conversation_by_id(self, conversation_id: int) -> Optional[Conversation]:
        """Lấy conversation theo ID"""
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def get_conversation_by_session_id(self, session_id: str) -> Optional[Conversation]:
        """Lấy conversation theo session ID"""
        result = await self.db.execute(
            select(Conversation).where(Conversation.session_id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_user_conversations(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 10,
        status: Optional[str] = None,
    ) -> tuple[list[Conversation], int]:
        """Lấy tất cả conversations của user (có phân trang)"""
        offset = (page - 1) * page_size

        # Count total
        count_stmt = select(func.count(Conversation.id)).where(
            Conversation.user_id == user_id
        )
        if status:
            count_stmt = count_stmt.where(Conversation.status == status)

        result = await self.db.execute(count_stmt)
        total = result.scalar() or 0

        # Get paginated results
        stmt = select(Conversation).where(
            Conversation.user_id == user_id
        ).order_by(desc(Conversation.created_at))

        if status:
            stmt = stmt.where(Conversation.status == status)

        stmt = stmt.offset(offset).limit(page_size)
        result = await self.db.execute(stmt)
        conversations = result.scalars().all()

        return conversations, total

    async def end_conversation(
        self,
        conversation_id: int,
        result: Optional[dict] = None,
        score: Optional[float] = None,
    ) -> Conversation:
        """Kết thúc conversation"""
        conversation = await self.get_conversation_by_id(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        conversation.status = ConversationStatus.COMPLETED
        if result:
            conversation.result = json.dumps(result, ensure_ascii=False)
        if score is not None:
            conversation.score = score

        await self.db.flush()
        await self.db.refresh(conversation)
        logger.info(f"Ended conversation: id={conversation_id}, score={score}")
        return conversation

    # ──────────────────────────────────────────────────────────────
    # Message Management
    # ──────────────────────────────────────────────────────────────

    async def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        question: Optional[str] = None,
        answer: Optional[str] = None,
    ) -> ConversationMessage:
        """Thêm message vào conversation"""
        message = ConversationMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            question=question,
            answer=answer,
        )
        self.db.add(message)
        await self.db.flush()
        await self.db.refresh(message)
        logger.info(f"Added message: id={message.id}, role={role}, conversation_id={conversation_id}")
        return message

    async def get_conversation_messages(
        self,
        conversation_id: int,
        limit: Optional[int] = None,
    ) -> list[ConversationMessage]:
        """Lấy tất cả messages của conversation"""
        stmt = select(ConversationMessage).where(
            ConversationMessage.conversation_id == conversation_id
        ).order_by(ConversationMessage.created_at)

        if limit:
            stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_last_message(self, conversation_id: int) -> Optional[ConversationMessage]:
        """Lấy message cuối cùng của conversation"""
        result = await self.db.execute(
            select(ConversationMessage).where(
                ConversationMessage.conversation_id == conversation_id
            ).order_by(desc(ConversationMessage.created_at)).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_messages_by_role(
        self,
        conversation_id: int,
        role: str,
    ) -> list[ConversationMessage]:
        """Lấy tất cả messages của role cụ thể trong conversation"""
        result = await self.db.execute(
            select(ConversationMessage).where(
                and_(
                    ConversationMessage.conversation_id == conversation_id,
                    ConversationMessage.role == role,
                )
            ).order_by(ConversationMessage.created_at)
        )
        return result.scalars().all()

    # ──────────────────────────────────────────────────────────────
    # AI Interview Logic
    # ──────────────────────────────────────────────────────────────

    async def generate_initial_question(self, conversation_id: int) -> str:
        """Tạo câu hỏi đầu tiên dựa trên JD và CV"""
        conversation = await self.get_conversation_by_id(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        prompt = f"""
Bạn là một người phỏng vấn AI chuyên nghiệp. Dựa trên Job Description và CV của ứng viên, hãy tạo một câu hỏi phỏng vấn đầu tiên.

Job Description:
{conversation.job_description}

CV Profile:
{conversation.cv_profile}

Hãy tạo một câu hỏi đánh giá kỹ năng và kinh nghiệm của ứng viên liên quan đến vị trí này. Câu hỏi nên:
- Cụ thể và có liên quan đến công việc
- Để lại chỗ cho ứng viên thể hiện kinh nghiệm của họ
- Có thể được trả lời trong khoảng 1-3 phút

Chỉ trả lời câu hỏi, không thêm bất kỳ lời giải thích nào khác.
"""
        try:
            question = generate_content(
                prompt=prompt,
                step="generate_initial_question",
                config=GeminiConfig(model="models/gemini-2.5-flash", temperature=0.7),
            )
            return question.strip()
        except Exception as e:
            logger.error(f"Error generating initial question: {str(e)}")
            raise

    async def generate_next_question(
        self,
        conversation_id: int,
        previous_answer: Optional[str] = None,
    ) -> str:
        """Tạo câu hỏi tiếp theo dựa trên câu trả lời trước"""
        conversation = await self.get_conversation_by_id(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Lấy lịch sử cuộc trò chuyện
        messages = await self.get_conversation_messages(conversation_id)
        
        # Build conversation history
        history = "\n".join([f"{msg.role.upper()}: {msg.content}" for msg in messages[-10:]])  # Last 10 messages

        prompt = f"""
Bạn là một người phỏng vấn AI chuyên nghiệp. Dựa trên Job Description, CV, và lịch sử cuộc trò chuyện, hãy tạo câu hỏi phỏng vấn tiếp theo.

Job Description:
{conversation.job_description}

CV Profile:
{conversation.cv_profile}

Lịch sử cuộc trò chuyện:
{history}

Dựa trên câu trả lời trước đó của ứng viên, hãy tạo một câu hỏi tiếp theo để:
- Đi sâu vào các chi tiết của câu trả lời trước
- Hoặc đánh giá một kỹ năng khác từ job description
- Hoặc kiểm tra tính nhất quán của ứng viên

Câu hỏi nên tự nhiên, chuyên nghiệp, và có thể được trả lời trong khoảng 1-3 phút.

Chỉ trả lời câu hỏi, không thêm bất kỳ lời giải thích nào khác.
"""
        try:
            question = generate_content(
                prompt=prompt,
                step="generate_next_question",
                config=GeminiConfig(model="models/gemini-2.5-flash", temperature=0.7),
            )
            return question.strip()
        except Exception as e:
            logger.error(f"Error generating next question: {str(e)}")
            raise

    async def evaluate_answer(self, conversation_id: int) -> dict:
        """Đánh giá câu trả lời và tạo kết quả"""
        conversation = await self.get_conversation_by_id(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Lấy tất cả messages
        messages = await self.get_conversation_messages(conversation_id)

        # Build evaluation prompt
        messages_text = "\n".join([f"{msg.role.upper()}: {msg.content}" for msg in messages])

        prompt = f"""
Bạn là một người phỏng vấn AI chuyên nghiệp. Hãy đánh giá cuộc phỏng vấn dựa trên Job Description, CV, và lịch sử cuộc trò chuyện.

Job Description:
{conversation.job_description}

CV Profile:
{conversation.cv_profile}

Lịch sử cuộc trò chuyện:
{messages_text}

Vui lòng đánh giá:
1. Điểm mạnh của ứng viên
2. Điểm yếu của ứng viên
3. Mức độ phù hợp với công việc (0-100)
4. Đề xuất quyết định cuối cùng (PASS/FAIL/MAYBE)

Trả lời dưới định dạng JSON:
{{
    "strengths": ["..."],
    "weaknesses": ["..."],
    "fit_score": <0-100>,
    "recommendation": "PASS|FAIL|MAYBE",
    "comments": "..."
}}
"""
        try:
            result_text = generate_content(
                prompt=prompt,
                step="evaluate_answer",
                config=GeminiConfig(model="models/gemini-2.5-flash", temperature=0.0),
            )
            
            # Parse JSON result
            import re
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result
            else:
                return {"error": "Could not parse evaluation result"}
        except Exception as e:
            logger.error(f"Error evaluating answer: {str(e)}")
            raise
