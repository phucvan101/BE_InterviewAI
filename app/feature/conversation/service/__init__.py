import json
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import delete as sa_delete


from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.feature.conversation.model.conversation import (
    Conversation,
    ConversationAnalysisReport,
    ConversationMessage,
    ConversationStatus,
    MessageRole,
)
from app.feature.conversation.schema import AnalysisReportPayload
from app.feature.feature_up_cv.gemini_client import generate_content, GeminiConfig

logger = logging.getLogger(__name__)


def _ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _calculate_duration_seconds(started_at: datetime, ended_at: datetime) -> int:
    started_at = _ensure_aware_utc(started_at)
    ended_at = _ensure_aware_utc(ended_at)
    return max(0, int((ended_at - started_at).total_seconds()))


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
        job_position: str,
        job_description: str,
        cv_profile: str,
        company_name: str | None = None,
        analysis_session_id: int | None = None,
        session_id: str | None = None,
    ) -> Conversation:
        """Tạo conversation mới"""
        if analysis_session_id:
            existing = await self.get_conversation_by_analysis_session_id(
                user_id=user_id,
                analysis_session_id=analysis_session_id,
            )
            if existing:
                return existing

        # Idempotent: nếu session_id đã có conversation thì trả về luôn
        if session_id:
            existing = await self.get_conversation_by_session_id(session_id)
            if existing:
                return existing

        conversation_kwargs = {
            "user_id": user_id,
            "job_position": job_position,
            "company_name": company_name,
            "job_description": job_description,
            "cv_profile": cv_profile,
            "analysis_session_id": analysis_session_id,
            "status": ConversationStatus.ACTIVE,
        }
        if session_id:
            conversation_kwargs["session_id"] = session_id

        conversation = Conversation(**conversation_kwargs)
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

    async def get_conversation_by_analysis_session_id(
        self,
        user_id: int,
        analysis_session_id: int,
    ) -> Optional[Conversation]:
        """Lấy conversation đã tạo từ một analysis session của user."""
        result = await self.db.execute(
            select(Conversation).where(
                Conversation.user_id == user_id,
                Conversation.analysis_session_id == analysis_session_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_user_conversations(
    self,
    user_id: int,
    page: int = 1,
    page_size: int = 10,
    status: Optional[str] = None,
    job_position: Optional[str] = None,
    ) -> tuple[list[Conversation], int]:
        """Lấy tất cả conversations của user (có phân trang)"""
        offset = (page - 1) * page_size

        base_where = [Conversation.user_id == user_id]

        if status:
            base_where.append(Conversation.status == status)

        if job_position:
            base_where.append(Conversation.job_position.ilike(f"%{job_position}%"))

        # Count total
        result = await self.db.execute(
            select(func.count(Conversation.id)).where(*base_where)
        )
        total = result.scalar() or 0

        # Get paginated results
        result = await self.db.execute(
            select(Conversation)
            .where(*base_where)
            .order_by(desc(Conversation.created_at))
            .offset(offset)
            .limit(page_size)
        )
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
        ended_at = datetime.now(timezone.utc)
        conversation.ended_at = ended_at
        conversation.interview_duration_seconds = _calculate_duration_seconds(
            conversation.started_at,
            ended_at,
        )

        await self.db.flush()
        await self.db.refresh(conversation)
        logger.info(f"Ended conversation: id={conversation_id}, score={score}")
        return conversation

    async def get_analysis_report_by_conversation_id(
        self,
        conversation_id: int,
    ) -> Optional[ConversationAnalysisReport]:
        """Lấy báo cáo phân tích theo conversation ID"""
        result = await self.db.execute(
            select(ConversationAnalysisReport).where(
                ConversationAnalysisReport.conversation_id == conversation_id
            )
        )
        return result.scalar_one_or_none()

    async def get_user_analysis_reports(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 10,
        status: Optional[str] = None,
    ) -> tuple[list[tuple[ConversationAnalysisReport, Conversation, int]], int]:
        """Lấy danh sách báo cáo phân tích của user (có phân trang)"""
        offset = (page - 1) * page_size

        count_stmt = (
            select(func.count(ConversationAnalysisReport.id))
            .join(Conversation, ConversationAnalysisReport.conversation_id == Conversation.id)
            .where(Conversation.user_id == user_id)
        )
        if status:
            count_stmt = count_stmt.where(ConversationAnalysisReport.status == status)

        result = await self.db.execute(count_stmt)
        total = result.scalar() or 0

        message_count = func.count(ConversationMessage.id).label("message_count")
        stmt = (
            select(ConversationAnalysisReport, Conversation, message_count)
            .join(Conversation, ConversationAnalysisReport.conversation_id == Conversation.id)
            .outerjoin(
                ConversationMessage,
                ConversationMessage.conversation_id == Conversation.id,
            )
            .where(Conversation.user_id == user_id)
            .group_by(ConversationAnalysisReport.id, Conversation.id)
            .order_by(desc(ConversationAnalysisReport.created_at))
            .offset(offset)
            .limit(page_size)
        )
        if status:
            stmt = stmt.where(ConversationAnalysisReport.status == status)

        result = await self.db.execute(stmt)
        return [(report, conversation, message_count) for report, conversation, message_count in result.all()], total

    async def create_analysis_report(self, conversation_id: int) -> ConversationAnalysisReport:
        """Tạo báo cáo phân tích nâng cao cho cuộc phỏng vấn"""
        existing = await self.get_analysis_report_by_conversation_id(conversation_id)
        if existing:
            return existing

        conversation = await self.get_conversation_by_id(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        payload, raw_ai_response = await self.generate_analysis_report_payload(conversation_id)

        report = ConversationAnalysisReport(
            conversation_id=conversation_id,
            status="completed",
            overall_score=payload.overall_score,
            overall_grade=payload.overall_grade,
            level=payload.level,
            summary=payload.summary,
            tags=payload.tags,
            scores=payload.scores.model_dump(),
            ai_coach_insights=[item.model_dump() for item in payload.ai_coach_insights],
            strengths=payload.strengths,
            weaknesses=payload.weaknesses,
            knowledge_gaps=[item.model_dump() for item in payload.knowledge_gaps],
            study_plan=[item.model_dump() for item in payload.study_plan],
            raw_ai_response=raw_ai_response,
        )
        self.db.add(report)

        conversation.status = ConversationStatus.COMPLETED
        conversation.score = payload.overall_score
        conversation.result = json.dumps(payload.model_dump(), ensure_ascii=False)
        ended_at = datetime.now(timezone.utc)
        conversation.ended_at = ended_at
        conversation.interview_duration_seconds = _calculate_duration_seconds(
            conversation.started_at,
            ended_at,
        )

        await self.db.flush()
        await self.db.refresh(report)
        await self.db.refresh(conversation)
        logger.info(
            f"Created analysis report: conversation_id={conversation_id}, "
            f"score={payload.overall_score}, grade={payload.overall_grade}"
        )
        return report


    async def delete_conversation(self, conversation_id: int, user_id: int) -> bool:
        """Xóa conversation cùng toàn bộ dữ liệu liên quan"""
        conversation = await self.get_conversation_by_id(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        if conversation.user_id != user_id:
            raise PermissionError(
                f"User {user_id} does not have permission to delete conversation {conversation_id}"
            )

        # 1. Xóa analysis report (nếu có)
        await self.db.execute(
            sa_delete(ConversationAnalysisReport).where(
                ConversationAnalysisReport.conversation_id == conversation_id
            )
        )

        # 2. Xóa toàn bộ messages
        await self.db.execute(
            sa_delete(ConversationMessage).where(
                ConversationMessage.conversation_id == conversation_id
            )
        )

        # 3. Xóa conversation
        await self.db.delete(conversation)
        await self.db.flush()

        logger.info(
            f"Deleted conversation and related data: id={conversation_id}, user_id={user_id}"
        )
        return True
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

    async def generate_analysis_report_payload(self, conversation_id: int) -> tuple[AnalysisReportPayload, str]:
        """Gọi AI tạo payload báo cáo phân tích và validate bằng Pydantic"""
        conversation = await self.get_conversation_by_id(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        messages = await self.get_conversation_messages(conversation_id)
        messages_text = "\n".join(
            f"{idx}. {msg.role.upper()}: {msg.content}"
            for idx, msg in enumerate(messages, start=1)
        )

        prompt = self._build_analysis_report_prompt(
            conversation=conversation,
            messages_text=messages_text,
        )

        result_text = generate_content(
            prompt=prompt,
            step="generate_analysis_report",
        )
        payload_dict = self._extract_json_object(result_text)
        payload = AnalysisReportPayload.model_validate(payload_dict)
        self._apply_analysis_report_business_rules(
            payload=payload,
            messages=messages,
            company_name=conversation.company_name,
        )
        return payload, result_text

    def _apply_analysis_report_business_rules(
        self,
        *,
        payload: AnalysisReportPayload,
        messages: list[ConversationMessage],
        company_name: str | None,
    ) -> None:
        if self._has_company_knowledge_question(messages=messages, company_name=company_name):
            return

        payload.scores.company_knowledge.score = 0
        payload.scores.company_knowledge.evidence = (
            "Không có câu hỏi nào trong phiên phỏng vấn được đặt ra để đánh giá mức độ hiểu biết "
            "của ứng viên về công ty, sản phẩm, domain, văn hóa hoặc bối cảnh kinh doanh. "
            "Theo quy ước chấm điểm, tiêu chí company_knowledge được tính là 0 khi không có dữ liệu đánh giá."
        )
        payload.overall_score = self._calculate_overall_score(payload)
        payload.overall_grade = self._grade_from_score(payload.overall_score)
        payload.level = self._level_from_score(payload.overall_score)

    def _has_company_knowledge_question(
        self,
        *,
        messages: list[ConversationMessage],
        company_name: str | None,
    ) -> bool:
        company_terms = [
            "công ty",
            "cong ty",
            "sản phẩm",
            "san pham",
            "product",
            "domain",
            "b2b",
            "saas",
            "khách hàng",
            "khach hang",
            "văn hóa",
            "van hoa",
            "sứ mệnh",
            "su menh",
            "giá trị",
            "gia tri",
            "business",
            "thị trường",
            "thi truong",
        ]
        if company_name:
            company_terms.append(company_name.lower())

        for message in messages:
            if message.role not in {MessageRole.INTERVIEWER, MessageRole.INTERVIEWER.value}:
                continue
            question_text = f"{message.question or ''}\n{message.content or ''}".lower()
            if any(term in question_text for term in company_terms):
                return True
        return False

    def _calculate_overall_score(self, payload: AnalysisReportPayload) -> int:
        scores = [
            payload.scores.technical.score,
            payload.scores.communication.score,
            payload.scores.confidence.score,
            payload.scores.soft_skills.score,
            payload.scores.company_knowledge.score,
        ]
        return round(sum(scores) / len(scores))

    def _grade_from_score(self, score: int) -> str:
        if score >= 90:
            return "A"
        if score >= 80:
            return "B+"
        if score >= 70:
            return "B"
        if score >= 60:
            return "C+"
        if score >= 50:
            return "C"
        return "D"

    def _level_from_score(self, score: int) -> str:
        if score >= 80:
            return "Tốt"
        if score >= 65:
            return "Khá"
        if score >= 50:
            return "Cần cải thiện"
        return "Yếu"

    def _build_analysis_report_prompt(
        self,
        *,
        conversation: Conversation,
        messages_text: str,
    ) -> str:
        return f"""
Bạn là AI Interview Evaluator cho hệ thống InterviewAI.

Hãy phân tích kết quả phỏng vấn dựa DUY NHẤT trên dữ liệu được cung cấp:
- Job description
- CV profile
- Lịch sử câu hỏi và câu trả lời

Không bịa thêm dữ kiện. Nếu thiếu dữ liệu để đánh giá tiêu chí nào, vẫn cho điểm nhưng phải ghi rõ trong evidence.
Riêng company_knowledge: nếu lịch sử phỏng vấn không có câu hỏi nào trực tiếp về công ty, sản phẩm, domain, văn hóa, khách hàng, thị trường hoặc bối cảnh kinh doanh thì score bắt buộc là 0.

Quy ước điểm:
- Tất cả score là số nguyên từ 0 đến 100.
- technical: độ đúng, độ sâu và tính thực tế của kiến thức/kỹ năng chuyên môn so với JD.
- communication: cách trình bày, độ rõ ràng, có cấu trúc, đúng trọng tâm.
- confidence: độ tự tin thể hiện qua câu chữ, gồm trả lời dứt khoát, có ví dụ cụ thể, ít né tránh, ít ngôn ngữ mơ hồ. Không đánh giá giọng nói/khuôn mặt.
- soft_skills: tư duy hợp tác, xử lý xung đột, ownership, chủ động, problem-solving.
- company_knowledge: mức độ hiểu công ty, sản phẩm, domain, yêu cầu vị trí và sự phù hợp văn hóa. Chỉ chấm điểm tiêu chí này khi interviewer đã hỏi câu liên quan công ty/sản phẩm/domain/văn hóa; nếu không có câu hỏi như vậy thì score = 0.

Quy ước overall_grade:
- 90-100: A
- 80-89: B+
- 70-79: B
- 60-69: C+
- 50-59: C
- 0-49: D

Yêu cầu output:
- Chỉ trả về JSON hợp lệ.
- Không trả markdown.
- Không thêm text ngoài JSON.
- Dùng đúng key và kiểu dữ liệu trong schema bên dưới.
- impact chỉ được là "low", "medium" hoặc "high".
- ai_coach_insights.type chỉ được là "positive", "warning" hoặc "improvement".

Schema JSON bắt buộc:
{{
  "overall_score": 78,
  "overall_grade": "B+",
  "level": "Tốt",
  "summary": "Tóm tắt đánh giá ngắn gọn bằng tiếng Việt.",
  "tags": ["Kỹ thuật tốt", "Cần cải thiện kiến thức công ty"],
  "scores": {{
    "technical": {{"score": 0, "evidence": "Bằng chứng cụ thể từ câu trả lời."}},
    "communication": {{"score": 0, "evidence": "Bằng chứng cụ thể từ câu trả lời."}},
    "confidence": {{"score": 0, "evidence": "Bằng chứng cụ thể từ câu trả lời dạng text."}},
    "soft_skills": {{"score": 0, "evidence": "Bằng chứng cụ thể từ câu trả lời."}},
    "company_knowledge": {{"score": 0, "evidence": "Bằng chứng cụ thể từ câu trả lời."}}
  }},
  "ai_coach_insights": [
    {{"type": "positive", "title": "Tiêu đề ngắn", "description": "Mô tả ngắn."}}
  ],
  "strengths": ["Điểm mạnh cụ thể"],
  "weaknesses": ["Điểm yếu cụ thể"],
  "knowledge_gaps": [
    {{
      "title": "Tên lỗ hổng",
      "impact": "high",
      "evidence": "Bằng chứng từ câu trả lời.",
      "recommendation": "Khuyến nghị ôn tập cụ thể."
    }}
  ],
  "study_plan": [
    {{
      "priority": 1,
      "topic": "Chủ đề cần ôn",
      "reason": "Lý do nên ôn chủ đề này.",
      "actions": ["Hành động cụ thể 1", "Hành động cụ thể 2"]
    }}
  ]
}}

Thông tin phiên phỏng vấn:
Vị trí: {conversation.job_position}
Công ty: {conversation.company_name or "Không rõ"}

Job Description:
{conversation.job_description}

CV Profile:
{conversation.cv_profile}

Lịch sử phỏng vấn:
{messages_text or "Chưa có câu hỏi/câu trả lời nào."}
"""

    def _extract_json_object(self, text: str) -> dict:
        """Trích JSON object từ output AI"""
        if not text:
            raise ValueError("AI returned empty analysis report")

        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        import re

        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if not json_match:
            raise ValueError("Could not parse analysis report JSON")

        parsed = json.loads(json_match.group())
        if not isinstance(parsed, dict):
            raise ValueError("Analysis report JSON must be an object")
        return parsed
