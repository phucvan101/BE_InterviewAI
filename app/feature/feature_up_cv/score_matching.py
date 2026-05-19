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
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MODEL_NAME = os.getenv('MODEL_NAME', 'models/gemini-2.5-flash')

from app.feature.feature_up_cv.gemini_client import generate_content


def load_json_file(file_path: str) -> Dict[str, Any]:
    """Load JSON file safely"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {file_path}")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON format: {file_path}")


def build_matching_prompt(cv_data: Dict, jd_data: Dict, company_data: Dict = None) -> str:
    """
    Build a detailed prompt for Gemini to analyze CV-JD matching
    """
    
    cv_json = json.dumps(cv_data, ensure_ascii=False, indent=2)
    jd_json = json.dumps(jd_data, ensure_ascii=False, indent=2)
    company_json = json.dumps(company_data, ensure_ascii=False, indent=2) if company_data else "Không có dữ liệu Company (Công ty). Điểm phần Company_fit_score sẽ là 0."
    
    # Prefer structured JD when available (for stability)
    jd_structured = jd_data.get("structured", None) if isinstance(jd_data, dict) else None
    jd_structured_json = (
        json.dumps(jd_structured, ensure_ascii=False, indent=2) if jd_structured else ""
    )

    prompt = f"""
Bạn là chuyên gia tuyển dụng + phân tích năng lực. Nhiệm vụ: đánh giá mức độ phù hợp giữa CV ứng viên, JD và mô tả công ty theo thang điểm 100.
Bạn sẽ dựa trên các tiêu chí sau và phân bổ điểm:
1) Kinh nghiệm làm việc (Tối đa 50 điểm): Sự phù hợp với JD, thành tích nổi bật, dự án cụ thể.
2) Kỹ năng (Tối đa 30 điểm): Các kỹ năng của ứng viên phù hợp với trong JD.
3) Học vấn & Bằng cấp (Tối đa 10 điểm): Chuyên ngành liên quan, chứng chỉ chuyên môn.
4) Mục tiêu nghề nghiệp (Tối đa 10 điểm): Mục tiêu nghề nghiệp trong CV phù hợp với JD và định hướng công ty.
5) Độ phù hợp công ty (Tối đa 10 điểm, KHÔNG tính vào tổng): CV phù hợp với thông tin và văn hoá công ty. Nếu KHÔNG CÓ dữ liệu công ty, điểm này bắt buộc là 0.

Ràng buộc bắt buộc:
- CHỈ trả về 1 JSON object, KHÔNG có text/markdown nào khác.
- KHÔNG giải thích dài dòng; chỉ điền vào các field theo schema.
- Điểm là số nguyên. `overall_score` = experience(50) + skills(30) + education(10) + career_objectives(10) = tối đa 100. KHÔNG bao gồm company_fit_score.
- `missing_skills` phải liệt kê đầy đủ kỹ năng quan trọng bị thiếu (ưu tiên skills_required).
- `matched_skills` chỉ liệt kê các kỹ năng thực sự có trong CV (dựa vào CV.skills / work_experience highlights).
- Nếu kỹ năng tương tự tên khác -> đưa vào `related_skills` (vd: "Postgres" ~ "PostgreSQL").
- Loại bỏ trùng lặp trong các list.
- Ngôn ngữ: Tiếng Việt (trừ keyword công nghệ).

Input:
CV_JSON:
{cv_json}

JD_JSON:
{jd_json}

JD_STRUCTURED (nếu có, dùng ưu tiên):
{jd_structured_json}

COMPANY_JSON:
{company_json}

Schema output:
{{
  "detailed_scores": {{
    "experience_score": 0,
    "skills_score": 0,
    "education_score": 0,
    "career_objectives_score": 0,
    "company_fit_score": 0
  }},
  "overall_score": 0,
  "score_rationale": "",
  "matched_skills": [],
  "related_skills": [],
  "missing_skills": [],
  "experience_assessment": "",
  "experience_detail": "",
  "main_strengths": [],
  "areas_for_development": [],
  "recommendation": "",
  "evidence": {{
    "cv_skills": [],
    "jd_skills_required": [],
    "jd_skills_preferred": []
  }}
}}

Few-shot (format reference only):
CV_EXAMPLE: {{"skills":["Python","FastAPI"]}}
JD_EXAMPLE: {{"structured":{{"skills_required":["Python","FastAPI","PostgreSQL"]}}}}
COMPANY_EXAMPLE: {{"company_name": "ABC Tech"}}
OUTPUT_EXAMPLE:
{{
  "detailed_scores": {{
    "experience_score": 40,
    "skills_score": 20,
    "education_score": 8,
    "career_objectives_score": 7,
    "company_fit_score": 8
  }},
  "overall_score": 75,
  "score_rationale":"Ứng viên có kỹ năng chính nhưng thiếu một kỹ năng quan trọng trong yêu cầu.",
  "matched_skills":["Python","FastAPI"],
  "related_skills":[],
  "missing_skills":["PostgreSQL"],
  "experience_assessment":"",
  "experience_detail":"",
  "main_strengths":["Nắm vững Python/FastAPI"],
  "areas_for_development":["Bổ sung PostgreSQL"],
  "recommendation":"Nên học và thực hành PostgreSQL để đáp ứng JD tốt hơn.",
  "evidence":{{"cv_skills":["Python","FastAPI"],"jd_skills_required":["Python","FastAPI","PostgreSQL"],"jd_skills_preferred":[]}}
}}

Self-check:
- Valid JSON only?
- Contains all required keys (bao gồm detailed_scores)?
- No text outside JSON?
- overall_score có bằng experience(50) + skills(30) + education(10) + career_objectives(10) không? KHÔNG bao gồm company_fit_score.
- career_objectives_score nằm trong detailed_scores chưa?
""".strip()
    
    return prompt


def parser_model_response(response_text: str) -> Dict[str, Any]:
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
    
    print("✅ CV and JD files loaded successfully")
    print(f"📊 CV data: {cv_data}")
    print(f"📊 JD data: {jd_data}")
    
    return calculate_matching_score_from_payload(cv_data, jd_data)


def calculate_matching_score_from_payload(cv_data: Dict[str, Any], jd_data: Dict[str, Any], company_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Main function: call Gemini matching using parsed CV/JD dictionaries.
    """
    # Build prompt
    prompt = build_matching_prompt(cv_data, jd_data, company_data)
    print("🤖 Calling Gemini model for analysis...")

    # Call Gemini model
    raw = generate_content(prompt=prompt, step="llm_match_score")
    print("✓ Received response from model")
    
    # Parse response
    analysis = parser_model_response(raw)
    
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
    analysis['job_position'] = (
        jd_data.get('job_title')
        or (jd_data.get("structured", {}) or {}).get("job_title")
        or 'Unknown'
    )
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
