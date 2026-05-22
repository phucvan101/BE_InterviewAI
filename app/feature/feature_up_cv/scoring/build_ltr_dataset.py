import csv
import json
from pathlib import Path
from typing import List, Optional

from app.feature.feature_up_cv.vector_search.embedding_service import get_embedding_service
from app.feature.feature_up_cv.scoring.cross_encoder_reranker import CrossEncoderReranker
from app.feature.feature_up_cv.scoring.hybrid_scoring import calculate_hybrid_score


def _normalize_list(items: List[str]) -> List[str]:
    return [s.strip().lower() for s in (items or []) if isinstance(s, str) and s.strip()]


def export_ltr_candidates(
    parser_folder: Optional[Path] = None,
    out_csv: Optional[Path] = None,
    max_cvs: Optional[int] = None,
    max_jds: Optional[int] = None,
):
    """Export candidate project pairs with features for LTR labeling.

    - Scans parser_file folder for `cv_*.json` and `jd_*.json` files.
    - For each CV and JD pair, writes one row per project with feature columns.
    """
    base = (
        Path(__file__).resolve().parents[1] / "storage" / "parser_file"
        if parser_folder is None
        else Path(parser_folder)
    )
    out_csv = Path(out_csv or "ltr_candidates.csv")

    cv_files = sorted(list(base.glob("cv_*.json")))
    jd_files = sorted(list(base.glob("jd_*.json")))

    if max_cvs:
        cv_files = cv_files[:max_cvs]
    if max_jds:
        jd_files = jd_files[:max_jds]

    es = get_embedding_service()
    ce = CrossEncoderReranker()

    rows = []
    for cv_path in cv_files:
        cv = json.loads(cv_path.read_text(encoding="utf-8"))
        projects = cv.get("projects", []) or []
        for jd_path in jd_files:
            jd = json.loads(jd_path.read_text(encoding="utf-8"))
            # hybrid scoring may provide per-project project_relevance_scores
            try:
                res = calculate_hybrid_score(cv, jd)
            except Exception:
                res = {}
            exp_features = (res.get("features", {}) or {}).get("experience", {}) or {}
            labels = exp_features.get("project_relevance_scores") or []

            jd_text = es.encode_structured_jd(jd)
            v_jd = es.encode(jd_text)

            jd_skills = _normalize_list((jd.get("structured") or jd).get("skills_required") or [])
            cv_skills = _normalize_list(cv.get("skills") or [])

            for i, proj in enumerate(projects):
                proj_desc = proj.get("description", "") or ""
                try:
                    v_proj = es.encode(proj_desc)
                    sem_sim = float(es.compute_similarity(v_jd, v_proj))
                except Exception:
                    sem_sim = 0.0

                try:
                    ce_score = ce.score(jd_text, [proj_desc])[0]
                except Exception:
                    ce_score = 0.0

                proj_techs = _normalize_list(proj.get("technologies") or [])
                tech_inter = len(set(jd_skills) & set(proj_techs))
                skill_overlap_cv = len(set(jd_skills) & set(cv_skills))
                desc_len = len((proj_desc or "").split())

                current_label = labels[i] if i < len(labels) else sem_sim

                rows.append({
                    "cv_file": cv_path.name,
                    "jd_file": jd_path.name,
                    "group_key": f"{cv_path.name}||{jd_path.name}",
                    "project_index": i,
                    "project_name": proj.get("name", ""),
                    "project_description": proj_desc,
                    "current_label": current_label,
                    "sem_sim": sem_sim,
                    "ce_score": ce_score,
                    "tech_inter": tech_inter,
                    "skill_overlap_cv": skill_overlap_cv,
                    "desc_len": desc_len,
                })

    # write CSV
    fieldnames = [
        "cv_file",
        "jd_file",
        "group_key",
        "project_index",
        "project_name",
        "project_description",
        "current_label",
        "sem_sim",
        "ce_score",
        "tech_inter",
        "skill_overlap_cv",
        "desc_len",
    ]

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print(f"WROTE: {out_csv} rows={len(rows)}")
    return out_csv


if __name__ == "__main__":
    export_ltr_candidates()
