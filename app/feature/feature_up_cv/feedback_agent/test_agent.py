import asyncio
from unittest.mock import MagicMock
import sys
import os

# Ensure the root directory is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from app.feature.feature_up_cv.auth.schemas.score_feedback import FeedbackRequest

# 1.5 Mock DB models to avoid Python 3.9 syntax errors in cv_profile.py
sys.modules['app.feature.feature_up_cv.auth.models.cv_profile'] = MagicMock()
sys.modules['app.feature.feature_up_cv.auth.models.job_description'] = MagicMock()
sys.modules['app.feature.feature_up_cv.auth.schemas.cv_profile'] = MagicMock()
sys.modules['app.feature.feature_up_cv.auth.schemas.job_description'] = MagicMock()
sys.modules['app.feature.feature_up_cv.auth.services.cv_profile_service'] = MagicMock()
sys.modules['app.feature.feature_up_cv.auth.services.job_description_service'] = MagicMock()

from app.feature.feature_up_cv.auth.services.score_feedback_service import handle_feedback
from app.feature.feature_up_cv.feedback_agent.memory_faiss import agent_memory
from app.feature.feature_up_cv.feedback_agent.synonym_manager import synonym_manager

# 1. Định nghĩa mock data
FAKE_CV_TEXT = """
Họ tên: Nguyễn Văn A
Vị trí: Lập trình viên Backend
Kinh nghiệm:
- 2024-nay: Phát triển hệ thống e-commerce dùng Nest.js và Prisma.
- Kỹ năng: Nest.js, Prisma, MySQL, TypeScript.
"""

FAKE_JD_TEXT = """
Vị trí: Backend Engineer (Node.js)
Yêu cầu bắt buộc:
- Có kinh nghiệm làm việc với Node.js, Express.js.
- Thành thạo TypeORM hoặc Sequelize.
- Khả năng thiết kế database tốt.
"""

USER_FEEDBACK = """
Hệ thống chấm tôi điểm kỹ năng thấp vì cho rằng tôi thiếu Express.js và TypeORM. 
Tuy nhiên tôi đang dùng Nest.js (là một framework cao cấp của Node.js mạnh hơn cả Express) 
và Prisma (là ORM hiện đại tốt hơn TypeORM). Xin hãy cập nhật lại kiến thức cho hệ thống!
"""

async def run_test():
    print("🚀 Bắt đầu test Agent Feedback...\n")
    
    # 2. Mock AsyncSession và các hàm gọi DB
    mock_db = MagicMock()
    
    # Patch trực tiếp các hàm fetch data trong module score_feedback_service
    import app.feature.feature_up_cv.auth.services.score_feedback_service as svc
    svc._get_cv_text = MagicMock(return_value=asyncio.Future())
    svc._get_cv_text.return_value.set_result(FAKE_CV_TEXT)
    
    svc._get_jd_text = MagicMock(return_value=asyncio.Future())
    svc._get_jd_text.return_value.set_result(FAKE_JD_TEXT)

    request = FeedbackRequest(
        cv_id="1",
        jd_id="1",
        feedback_text=USER_FEEDBACK
    )
    
    print("📝 Input Feedback:", USER_FEEDBACK.strip())
    # 2.5 Mock Gemini response to bypass 503 Server High Demand
    import app.feature.feature_up_cv.auth.services.score_feedback_service as svc
    svc.generate_content = MagicMock(return_value='''{
        "is_valid_complaint": true,
        "rationale": "Ứng viên dùng Nest.js và Prisma, đây là các công nghệ bậc cao tương đương và thậm chí tốt hơn Express.js và TypeORM.",
        "learned_rule": "Nest.js tương đương Express.js và cao cấp hơn; Prisma tương đương TypeORM.",
        "new_synonyms": [
            {"base_skill": "express.js", "synonym": "nest.js"},
            {"base_skill": "typeorm", "synonym": "prisma"}
        ]
    }''')
    
    print("\n⏳ Đang gọi Gemini phân tích...")
    
    # 3. Chạy hàm handle_feedback
    response = await handle_feedback(request, mock_db)
    
    print("\n✅ Kết quả từ Agent:")
    print(f"- is_valid_complaint: {response.success and response.is_overridden == False}")
    print(f"- rationale: {response.rationale}")
    print(f"- learned_rule: {response.learned_rule}")
    
    print("\n🔍 Kiểm tra dữ liệu được học:")
    # Kiểm tra Rules FAISS
    rules = agent_memory.get_relevant_rules(query="Nest.js and Prisma", top_k=2, threshold=0.0)
    print(f"- FAISS Rules hiện tại liên quan tới 'Nest.js': {rules}")
    
    # Kiểm tra file YAML xem có Nest.js hoặc Prisma chưa
    with open(synonym_manager.yaml_path, 'r', encoding='utf-8') as f:
        yaml_content = f.read()
        if 'nest' in yaml_content.lower() or 'prisma' in yaml_content.lower():
            print("- YAML đã được tự động thêm từ khoá mới!")
        else:
            print("- YAML chưa có từ khoá mới (tuỳ thuộc vào response của Gemini).")

if __name__ == "__main__":
    asyncio.run(run_test())
