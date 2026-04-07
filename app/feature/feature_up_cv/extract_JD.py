# -*- coding: utf-8 -*-
import os
import json
from dotenv import load_dotenv
from google import genai

# 1. Load .env
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-1.5-flash")

if not GEMINI_API_KEY:
    raise ValueError("Missing GEMINI_API_KEY in .env")

# 2. Init client
client = genai.Client(api_key=GEMINI_API_KEY)

# 3. Read JD file
with open("jd.txt", "r", encoding="utf-8") as f:
    jd_text = f.read()

# 4. Prompt (ép trả JSON sạch)
prompt = f"""
Extract structured information from the following Job Description.

Return ONLY valid JSON. No explanation.

Schema:
{{
  "job_title": "",
  "location": "",
  "years_of_experience": "",
  "skills": [],
  "responsibilities": []
}}

JD:
{jd_text}
"""

# 5. Call model
response = client.models.generate_content(
    model=MODEL_NAME,
    contents=prompt,
    config={"temperature": 0}
)

raw_output = response.text.strip()

# 6. Clean nếu model trả markdown ```json
if raw_output.startswith("```"):
    raw_output = raw_output.replace("```json", "").replace("```", "").strip()

# 7. Parse JSON
try:
    jd_json = json.loads(raw_output)
except json.JSONDecodeError:
    print("❌ JSON parse lỗi. Output thô:")
    print(raw_output)
    raise

# 8. Save file jd.json
with open("jd.json", "w", encoding="utf-8") as f:
    json.dump(jd_json, f, ensure_ascii=False, indent=2)

print("✅ Saved to jd.json")