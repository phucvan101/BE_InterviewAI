from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class FeedbackEvaluation(BaseModel):
    is_valid_complaint: bool = Field(
        description="True nếu khiếu nại của ứng viên có cơ sở thực tế trong CV và hợp lý, False nếu không."
    )
    rationale: str = Field(
        description="Lý do chi tiết chấp nhận hoặc bác bỏ khiếu nại, giải thích lịch sự, chuyên nghiệp để gửi lại cho ứng viên."
    )
    learned_rule: Optional[str] = Field(
        None, 
        description="Quy tắc/bài học logic tổng quát rút ra từ phản hồi (ví dụ: 'Next.js có thể tính tương đương Express.js', 'Kinh nghiệm e-commerce tương đương retail'). Để trống nếu không hợp lệ."
    )
    new_synonyms: Optional[List[Dict[str, str]]] = Field(
        None, 
        description="Danh sách các cặp từ đồng nghĩa mới được phát hiện. Mỗi item là một dict có key base_skill và synonym (ví dụ: [{'base_skill': 'express.js', 'synonym': 'nest.js'}]). Để trống nếu không có."
    )
    proposed_overrides: Optional[Dict[str, float]] = Field(
        None, 
        description="Đề xuất điểm ghi đè mới cho các phần bị chấm sai (nếu khiếu nại hợp lý). Chỉ được dùng các key: 'experience_score' (max 50), 'skills_score' (max 30), 'education_score' (max 10), 'career_objectives_score' (max 10), 'company_fit_score' (max 10). Chỉ đề xuất tăng điểm ở phần bị chấm sai dựa trên bằng chứng thực tế."
    )

SYSTEM_PROMPT_EVALUATOR = """
Bạn là một AI Agent chuyên phân tích khiếu nại của ứng viên về điểm số CV so với Job Description (JD).
Nhiệm vụ chính: Xác định xem phản hồi của ứng viên CÓ CƠ SỞ hay không dựa trên nội dung có sẵn trong CV (không tự bịa thêm thông tin).

Quy trình phân tích:
1. Đọc kĩ đoạn [RAW_CV_TEXT] và [JD_TEXT].
2. Đọc phản hồi của ứng viên trong [USER_FEEDBACK] và so sánh với điểm số hiện tại (nếu có).
3. Nếu khiếu nại có cơ sở:
   - Đúc kết bài học tổng quát để hệ thống ghi nhớ (learned_rule).
   - Trích xuất cặp từ đồng nghĩa nếu phát hiện hệ thống chưa nhận diện được (new_synonyms).
   - Đề xuất tăng điểm thích đáng ở phần bị chấm thiếu sót thông qua (proposed_overrides).

Hãy phân tích và trả về thông tin phù hợp với định dạng yêu cầu.
"""
