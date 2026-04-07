# -*- coding: utf-8 -*-
"""
CV vs JD Matching Score Calculator
Analyzes CV against Job Description and returns:
- Matching score (0-100)
- Missing skills
- Detailed analysis
"""

import json
import os
import re
from typing import Dict, Any, List
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Gemini API
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
MODEL_NAME = os.getenv('MODEL_NAME', 'models/gemini-2.5-flash')

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file")

genai.configure(api_key=GEMINI_API_KEY)


def load_json_file(file_path: str) -> Dict[str, Any]:
    """Load JSON file safely"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {file_path}")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON format: {file_path}")


def build_matching_prompt(cv_data: Dict, jd_data: Dict) -> str:
    """
    Build a detailed prompt for Gemini to analyze CV-JD matching
    """
    
    cv_json = json.dumps(cv_data, ensure_ascii=False, indent=2)
    jd_json = json.dumps(jd_data, ensure_ascii=False, indent=2)
    
    prompt = f"""
Bạn là một chuyên gia tuyển dụng và phân tích CV. Hãy đánh giá mức độ phù hợp giữa CV ứng viên và mô tả công việc (JD).

## CV CỦA ỨNG VIÊN:
```json
{cv_json}
```

## MÔ TẢ CÔNG VIỆC (JD):
```json
{jd_json}
```

## HƯỚNG DẪN ĐÁNH GIÁ:

### 1. PHÂN TÍCH KỸ NĂNG (Skill Matching):
- So sánh từng kỹ năng yêu cầu trong JD với kinh nghiệm & kỹ năng có trong CV
- Ghi rõ:
  - Kỹ năng KHỚP (có trong CV)
  - Kỹ năng LIÊN QUAN (có nhưng khác tên gọi)
  - Kỹ năng THIẾU (không có trong CV)

### 2. PHÂN TÍCH KINH NGHIỆM:
- So sánh năm kinh nghiệm yêu cầu với năm kinh nghiệm của ứng viên
- Đánh giá mức độ phù hợp: Đủ / Chưa đủ / Vượt yêu cầu

### 3. PHÂN TÍCH VỊ TRÍ & ĐỊNH HƯỚNG NGHỀ NGHIỆP:
- Đánh giá ứng viên có định hướng phù hợp không
- Liệu kinh nghiệm trước đó có liên quan không

### 4. TIÊU CHÍ ĐÁNH GIÁ ĐIỂM:
- 85-100: Rất phù hợp (có hầu hết skills + kinh nghiệm đủ)
- 70-84: Khá phù hợp (có nhiều skills chính, kinh nghiệm tương đương)
- 60-69: Trung bình (có một số skills chính, kinh nghiệm thiếu)
- 50-59: Ít phù hợp (thiếu nhiều skills quan trọng)
- 0-49: Không phù hợp (thiếu hầu hết skills yêu cầu)

## RETURN FORMAT (STRICT JSON):
Hãy trả về CHÍNH XÁC dưới định dạng JSON sau không có bất cứ text nào khác:

{{
  "overall_score": <số từ 0-100>,
  "score_rationale": "<giải thích vì sao đạt điểm này (2-3 câu)>",
  "matched_skills": [
    "<danh sách kỹ năng CV đã có>",
    "..."
  ],
  "related_skills": [
    "<danh sách kỹ năng liên quan/tương tự>",
    "..."
  ],
  "missing_skills": [
    "<danh sách kỹ năng THIẾU trong CV>",
    "..."
  ],
  "experience_assessment": "<đánh giá kinh nghiệm: Đủ/Chưa đủ/Vượt>",
  "experience_detail": "<giải thích chi tiết về kinh nghiệm>",
  "main_strengths": [
    "<điểm mạnh chính 1>",
    "<điểm mạnh chính 2>",
    "..."
  ],
  "areas_for_development": [
    "<khu vực cần phát triển 1>",
    "<khu vực cần phát triển 2>",
    "..."
  ],
  "recommendation": "<khuyến nghị tổng quát cho ứng viên (2-3 câu)>"
}}

QUAN TRỌNG: 
- Chỉ trả về JSON, không có text khác
- Tất cả text phải là Tiếng Việt
- Điểm số phải là số nguyên từ 0-100
- Danh sách missing_skills là CRITICAL, phải liệt kê tất cả kỹ năng thiếu
"""
    
    return prompt


def parse_model_response(response_text: str) -> Dict[str, Any]:
    """
    Parse Gemini response and extract JSON
    """
    try:
        # Try to extract JSON from response
        # Handle case where model might add text before/after JSON
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        
        if not json_match:
            raise ValueError("No JSON found in response")
        
        json_str = json_match.group(0)
        result = json.loads(json_str)
        
        return result
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse model response as JSON: {str(e)}\nResponse: {response_text[:200]}")


def calculate_matching_score(cv_path: str, jd_path: str) -> Dict[str, Any]:
    """
    Main function to calculate CV-JD matching score
    
    Args:
        cv_path: Path to cv.json file
        jd_path: Path to jd.json file
    
    Returns:
        Dictionary containing:
        - overall_score: 0-100
        - matched_skills: List of skills candidate has
        - missing_skills: List of skills candidate lacks
        - All analysis details
    """
    
    print("📄 Loading CV and JD files...")
    
    # Load files
    cv_data = load_json_file(cv_path)
    jd_data = load_json_file(jd_path)
    
    print(f"✓ CV loaded: {cv_data.get('personal_info', {}).get('name', 'Unknown')}")
    print(f"✓ JD loaded: {jd_data.get('job_title', 'Unknown')}")
    
    # Build prompt
    prompt = build_matching_prompt(cv_data, jd_data)
    
    print("🤖 Calling Gemini model for analysis...")
    
    # Call Gemini API
    model = genai.GenerativeModel(MODEL_NAME)
    response = model.generate_content(prompt)
    
    print("✓ Received response from model")
    
    # Parse response
    analysis = parse_model_response(response.text)
    
    # Validate response structure
    required_fields = [
        'overall_score', 
        'matched_skills', 
        'missing_skills', 
        'experience_assessment'
    ]
    
    for field in required_fields:
        if field not in analysis:
            raise ValueError(f"Missing required field in response: {field}")
    
    # Add metadata
    analysis['cv_candidate'] = cv_data.get('personal_info', {}).get('name', 'Unknown')
    analysis['job_position'] = jd_data.get('job_title', 'Unknown')
    analysis['matched_at'] = __import__('datetime').datetime.now().isoformat()
    
    return analysis

# ═══════════════════════════════════════════════════════════════════════════
# CLI USAGE
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python score_matching.py <cv_path> <jd_path>")
        print("\nExample:")
        print("  python score_matching.py cv.json jd.json")
        sys.exit(1)
    
    cv_path = sys.argv[1]
    jd_path = sys.argv[2]
    
    try:
        result = calculate_matching_score(cv_path, jd_path)
        
        # Save result to JSON file
        output_path = "matching_result.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n✓ Result saved to: {output_path}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)
