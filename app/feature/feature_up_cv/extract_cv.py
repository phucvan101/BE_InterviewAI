import fitz
import string
import os
import json
import re
import time
from dotenv import load_dotenv
from google import genai

# ================= LOAD ENV =================
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME")  # Thay đổi trong .env

client = genai.Client(api_key=GEMINI_API_KEY)

# ================= CONFIG =================
INPUT_FOLDER = r"C:\Users\pc\Documents\code\DATN\BE\BE_InterviewAI\app\feature\feature_up_cv\cv_test"
OUTPUT_FOLDER = r"C:\Users\pc\Documents\code\DATN\BE\BE_InterviewAI\app\feature\feature_up_cv\cv_output"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ================= PDF CLASSIFY =================
def analyze_text_quality(text):
    if not text:
        return 0
    valid_chars = sum(c in string.printable for c in text)
    return valid_chars / len(text)

def classify_pdf(file_path, text_threshold=50, quality_threshold=0.7):
    doc = fitz.open(file_path)
    total_text_length = 0
    total_images = 0
    image_pages = 0

    for page in doc:
        text = page.get_text().strip()
        images = page.get_images()
        if text:
            total_text_length += len(text)
        if images:
            total_images += len(images)
            image_pages += 1

    sample_text = "".join(page.get_text() for page in doc[:3])
    quality = analyze_text_quality(sample_text)

    if total_text_length > text_threshold:
        if quality < quality_threshold:
            return "garbage_text"
        if image_pages > 0:
            return "hybrid"
        return "text"
    else:
        if total_images > 0:
            return "image"

    return "unknown"

# ================= EXTRACT TEXT =================
def extract_text(pdf_path):
    doc = fitz.open(pdf_path)
    return "\n".join(page.get_text().strip() for page in doc)

# ================= PROMPT =================
def build_prompt(cv_text):
    return f"""
You are an AI that extracts structured data from CVs.

Return ONLY valid JSON.
No explanation, no markdown, no ```.

If extraction fails, return empty JSON: {{}}

JSON schema:
{{
  "personal_info": {{
    "name": "",
    "dob": "",
    "gender": "",
    "phone": "",
    "email": "",
    "address": ""
  }},
  "objective": "",
  "education": [],
  "work_experience": [],
  "skills": []
}}

CV TEXT:
{cv_text[:3000]}
"""  # giới hạn 3000 chars để giảm token free tier

# ================= CALL GEMINI =================
def call_llm(prompt, max_retry=5, wait_sec=10):
    for attempt in range(1, max_retry + 1):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt
            )
            if not response.text:
                raise Exception("Empty response")
            return response.text
        except Exception as e:
            print(f" Gemini error (attempt {attempt}): {e}")
            time.sleep(wait_sec)
    raise Exception("Gemini API failed after retries")

# ================= JSON UTILS =================
def extract_first_json(text):
    stack = 0
    start = None
    for i, c in enumerate(text):
        if c == "{":
            if stack == 0:
                start = i
            stack += 1
        elif c == "}":
            stack -= 1
            if stack == 0:
                return text[start:i+1]
    return None

def validate_json(data):
    required = ["personal_info", "education", "work_experience", "skills"]
    return isinstance(data, dict) and all(k in data for k in required)

def fallback():
    return {
        "personal_info": {"name":"","dob":"","gender":"","phone":"","email":"","address":""},
        "objective": "",
        "education": [],
        "work_experience": [],
        "skills": []
    }

def robust_parse(text, max_retry=3):
    for i in range(max_retry):
        print(f"   LLM attempt {i+1}...")
        prompt = build_prompt(text)
        raw = call_llm(prompt)
        json_text = extract_first_json(raw)
        if not json_text:
            continue
        try:
            parsed = json.loads(json_text)
            if validate_json(parsed):
                return parsed
        except:
            pass
    return fallback()

# ================= PROCESS 1 FILE =================
def process_cv(file_path):
    file_name = os.path.basename(file_path)
    print(f"\n Processing: {file_name}")

    start_time = time.time()
    try:
        pdf_type = classify_pdf(file_path)
        if pdf_type == "image":
            print("   Skipped (image-based)")
            return
        print(f"   Type: {pdf_type}")
        text = extract_text(file_path)
        result = robust_parse(text)

        output_name = os.path.splitext(file_name)[0] + ".json"
        output_path = os.path.join(OUTPUT_FOLDER, output_name)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4, ensure_ascii=False)

        print(f"   Saved: {output_name}")
        print(f"   Time: {time.time() - start_time:.2f}s")
    except Exception as e:
        print(f"   Error: {e}")

# ================= PROCESS ALL =================
def process_all_cvs():
    files = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith(".pdf")]
    print(f" Found {len(files)} CV files\n")
    for file in files:
        file_path = os.path.join(INPUT_FOLDER, file)
        process_cv(file_path)
    print("\n DONE ALL")

# ================= RUN =================
if __name__ == "__main__":
    process_all_cvs()