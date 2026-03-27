import json
import hashlib
import os
import re
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# =====================
# Load model
# =====================
model = SentenceTransformer("all-MiniLM-L6-v2")

# =====================
# Embedding Cache
# =====================
CACHE_FILE = "embedding_cache.json"

if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        EMBEDDING_CACHE = json.load(f)
else:
    EMBEDDING_CACHE = {}


def save_cache():
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(EMBEDDING_CACHE, f)


def hash_text(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def embed(texts):
    """
    Batch embedding + cache
    """
    results = []
    to_encode = []
    keys = []

    # check cache
    for t in texts:
        key = hash_text(t)

        if key in EMBEDDING_CACHE:
            results.append(np.array(EMBEDDING_CACHE[key]))
        else:
            to_encode.append(t)
            keys.append(key)
            results.append(None)

    # encode missing
    if to_encode:
        new_vecs = model.encode(to_encode, normalize_embeddings=True)

        idx = 0
        for i in range(len(results)):
            if results[i] is None:
                vec = new_vecs[idx]
                EMBEDDING_CACHE[keys[idx]] = vec.tolist()
                results[i] = vec
                idx += 1

    return np.array(results)


# =====================
# Normalization
# =====================
NORMALIZE_MAP = {
    "postgresql": "sql",
    "mysql": "sql",
    "restful api": "rest api",
    "nodejs": "node.js"
}


def normalize_text(text):
    return str(text).lower().strip()


def normalize_skill(skill):
    skill = normalize_text(skill)
    return NORMALIZE_MAP.get(skill, skill)


# =====================
# Utils
# =====================
def parse_years(value):
    if value is None:
        return 0

    if isinstance(value, (int, float)):
        return float(value)

    value = str(value).lower().strip()

    match = re.search(r"\d+(\.\d+)?", value)
    if match:
        return float(match.group())

    return 0


# =====================
# JD Preprocessing
# =====================
def preprocess_jd(jd_json):
    skills = [normalize_skill(s) for s in jd_json.get("skills", [])]

    responsibilities = []
    for r in jd_json.get("responsibilities", []):
        r = normalize_text(r)

        parts = re.split(r",| and | & ", r)
        responsibilities.extend([p.strip() for p in parts if p.strip()])

    return {
        "skills": skills,
        "responsibilities": responsibilities,
        "years_of_experience": parse_years(
            jd_json.get("years_of_experience", 0)
        )
    }


# =====================
# CV Processing
# =====================
def build_cv_chunks(cv_json):
    chunks = []

    # skills
    for skill in cv_json.get("skills", []):
        chunks.append(normalize_skill(skill))

    # work experience
    for exp in cv_json.get("work_experience", []):
        if isinstance(exp, dict):
            if exp.get("job_title"):
                chunks.append(normalize_text(exp["job_title"]))

            if exp.get("description"):
                chunks.append(normalize_text(exp["description"]))

            for r in exp.get("responsibilities", []):
                chunks.append(normalize_text(r))

        elif isinstance(exp, str):
            chunks.append(normalize_text(exp))

    return list(set([c for c in chunks if len(c) > 2]))


# =====================
# Matching
# =====================
def semantic_match(requirements, cv_chunks):
    if not requirements or not cv_chunks:
        return []

    req_emb = embed(requirements)
    cv_emb = embed(cv_chunks)

    sim_matrix = cosine_similarity(req_emb, cv_emb)

    results = []
    cv_set = set(cv_chunks)

    for i, req in enumerate(requirements):
        best_idx = sim_matrix[i].argmax()
        best_score = sim_matrix[i][best_idx]

        # boost exact match
        if req in cv_set:
            best_score = max(best_score, 0.9)

        results.append({
            "requirement": req,
            "score": float(round(best_score, 3)),
            "matched_with": cv_chunks[best_idx]
        })

    return results


# =====================
# Scoring
# =====================
def score_group(matches, weight):
    if not matches:
        return 0

    score = 0
    for m in matches:
        if m["score"] >= 0.75:
            score += 1
        elif m["score"] >= 0.6:
            score += 0.5

    return (score / len(matches)) * weight


def score_experience(cv_json, jd_years):
    total_years = 0

    for exp in cv_json.get("work_experience", []):
        if isinstance(exp, dict):
            total_years += parse_years(exp.get("years", 0))

    if jd_years <= 0:
        return 0

    ratio = total_years / jd_years

    if ratio >= 1:
        return 20
    elif ratio >= 0.7:
        return 15
    elif ratio >= 0.5:
        return 10
    else:
        return 5


# =====================
# Main
# =====================
def evaluate(cv_json, jd_json):
    jd = preprocess_jd(jd_json)
    cv_chunks = build_cv_chunks(cv_json)

    skill_matches = semantic_match(jd["skills"], cv_chunks)
    resp_matches = semantic_match(jd["responsibilities"], cv_chunks)

    skill_score = score_group(skill_matches, 40)
    resp_score = score_group(resp_matches, 40)
    exp_score = score_experience(cv_json, jd["years_of_experience"])

    total_score = skill_score + resp_score + exp_score

    missing_skills = [
        m["requirement"] for m in skill_matches if m["score"] < 0.6
    ]

    strengths = [
        m["requirement"] for m in skill_matches if m["score"] >= 0.75
    ]

    return {
        "total_score": round(total_score, 2),
        "breakdown": {
            "skills": round(skill_score, 2),
            "responsibilities": round(resp_score, 2),
            "experience": exp_score
        },
        "strengths": strengths,
        "missing_skills": missing_skills,
        "matches": {
            "skills": skill_matches,
            "responsibilities": resp_matches
        }
    }


# =====================
# Run
# =====================
if __name__ == "__main__":
    with open("jd.json", "r", encoding="utf-8") as f:
        jd_json = json.load(f)

    with open("cv.json", "r", encoding="utf-8") as f:
        cv_json = json.load(f)

    result = evaluate(cv_json, jd_json)

    print(json.dumps(result, indent=2, ensure_ascii=False))

    save_cache()