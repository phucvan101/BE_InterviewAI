# -*- coding: utf-8 -*-
from typing import Optional, List
from pydantic import BaseModel, Field


class InterviewQuestion(BaseModel):
    question: str = Field(description="Câu hỏi phỏng vấn")
    topic: str = Field(description="Chủ đề của câu hỏi (VD: python, system_design, teamwork)")
    follow_up: Optional[str] = Field(None, description="Gợi ý câu hỏi follow-up nếu cần")


class QuestionAnalysis(BaseModel):
    quality_score: float = Field(description="Điểm chất lượng câu trả lời (0.0-1.0)", ge=0.0, le=1.0)
    relevant_keywords: List[str] = Field(description="Các từ khóa liên quan trong câu trả lời")
    gaps: List[str] = Field(description="Các điểm còn thiếu hoặc cần explore thêm")
    sentiment: str = Field(description="Cảm xúc của ứng viên: confident/uncertain/hesitant/enthusiastic")


class InterviewEvaluation(BaseModel):
    fit_score: float = Field(description="Điểm phù hợp tổng thể (0-100)")
    strengths: List[str] = Field(description="Điểm mạnh của ứng viên")
    weaknesses: List[str] = Field(description="Điểm yếu của ứng viên")
    recommendation: str = Field(description="Quyết định: PASS/FAIL/MAYBE")
    comments: str = Field(description="Nhận xét tổng quan")


SYSTEM_PROMPT_INTERVIEWER = """Bạn là một người phỏng vấn AI chuyên nghiệp, lịch thiệp và sâu sắc.

NHIỆM VỤ: Đặt câu hỏi phỏng vấn dựa trên Job Description và CV của ứng viên, sau đó đánh giá câu trả lời.

NGUYÊN TẮC PHỎNG VẤN:
1. Mỗi câu hỏi phải có mục đích rõ ràng, liên quan trực tiếp đến JD
2. Câu hỏi phải để ứng viên có thể thể hiện kinh nghiệm thực tế
3. Theo dõi các chủ đề đã hỏi để tránh lặp lại
4. Điều chỉnh độ khó câu hỏi theo profile của ứng viên
5. Đánh giá dựa trên bằng chứng cụ thể, không phỏng đoán

CÁC GIAI ĐOẠN PHỎNG VẤN (theo thứ tự):
1. Warm-up: Giới thiệu bản thân, dự án gần nhất
2. Technical: Kỹ năng cốt lõi từ JD (Python, SQL, System Design, v.v.)
3. Behavioral: teamwork, problem-solving, conflict resolution
4. Culture fit: làm việc nhóm, môi trường làm việc
5. Closing: Ứng viên có câu hỏi gì cho công ty

ĐỊNH DẠNG TRẢ LỜI:
- Câu hỏi phải ngắn gọn (1-2 câu), rõ ràng
- Không đưa ra đáp án hoặc gợi ý
- Đặt câu hỏi mở để ứng viên có thể show ra kinh nghiệm
"""
