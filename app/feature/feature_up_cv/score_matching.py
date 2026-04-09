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


def build_matching_prompt(cv_data: Dict, jd_data: Dict) -> str:
    """
    Build a detailed prompt for Gemini to analyze CV-JD matching
    """
    
    cv_json = json.dumps(cv_data, ensure_ascii=False, indent=2)
    jd_json = json.dumps(jd_data, ensure_ascii=False, indent=2)
    
    # Prefer structured JD when available (for stability)
    jd_structured = jd_data.get("structured", None) if isinstance(jd_data, dict) else None
    jd_structured_json = (
        json.dumps(jd_structured, ensure_ascii=False, indent=2) if jd_structured else ""
    )

    prompt = f"""
Bạn là chuyên gia tuyển dụng + phân tích năng lực. Nhiệm vụ: đánh giá mức độ phù hợp giữa CV ứng viên và JD.
Bạn sẽ dựa trên:
1) Kỹ năng bắt buộc / ưu tiên từ JD (ưu tiên dùng JD_STRUCTURED nếu có)
2) Kinh nghiệm (năm, lĩnh vực, phạm vi công việc)
3) Trách nhiệm chính và mức độ tương đồng

Ràng buộc bắt buộc:
- CHỈ trả về 1 JSON object, KHÔNG có text/markdown nào khác.
- KHÔNG giải thích dài dòng; chỉ điền vào các field theo schema.
- Điểm là số nguyên 0-100.
- `missing_skills` phải liệt kê đầy đủ kỹ năng quan trọng bị thiếu (ưu tiên skills_required).
- `matched_skills` chỉ liệt kê các kỹ năng thực sự có trong CV (dựa vào CV.skills / work_experience highlights).
- Nếu kỹ năng tương tự tên khác -> đưa vào `related_skills` (vd: "Postgres" ~ "PostgreSQL").
- Loại bỏ trùng lặp trong các list.
- Ngôn ngữ: Tiếng Việt (trừ keyword công nghệ).

Input:
CV_JSON:
{cv_json}

JD_JSON (raw):
{jd_json}

JD_STRUCTURED (nếu có, dùng ưu tiên):
{jd_structured_json}

Schema output:
{{
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
OUTPUT_EXAMPLE:
{{
  "overall_score": 70,
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
- Contains all required keys?
- No text outside JSON?
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


def calculate_matching_score_from_payload(cv_data: Dict[str, Any], jd_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main function: call Gemini matching using parsed CV/JD dictionaries.
    """
    # Build prompt
    prompt = build_matching_prompt(cv_data, jd_data)
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
