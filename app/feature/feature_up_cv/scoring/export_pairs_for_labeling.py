import csv
import json
from pathlib import Path
from typing import List

from app.feature.feature_up_cv.vector_search.embedding_service import get_embedding_service
from app.feature.feature_up_cv.scoring.cross_encoder_reranker import CrossEncoderReranker
from app.feature.feature_up_cv.scoring.hybrid_scoring import calculate_hybrid_score


def export_pairs(cv_path: Path, jd_dir: Path, out_csv: Path):
    es = get_embedding_service()
    ce = CrossEncoderReranker()

    cv = json.loads(cv_path.read_text(encoding='utf-8'))

    rows = []
    for jd_path in sorted(jd_dir.glob('jd_*.json')):
        jd = json.loads(jd_path.read_text(encoding='utf-8'))
        res = calculate_hybrid_score(cv, jd)
        exp_features = res.get('features', {}).get('experience', {}) or {}
        labels = exp_features.get('project_relevance_scores') or []

        jd_text = es.encode_structured_jd(jd)
        projects = cv.get('projects', [])
        for i, proj in enumerate(projects):
            proj_desc = proj.get('description', '')
            sem_sim = es.compute_similarity(es.encode(jd_text), es.encode(proj_desc))
            try:
                ce_score = ce.score(jd_text, [proj_desc])[0]
            except Exception:
                ce_score = 0.0
            current_label = labels[i] if i < len(labels) else sem_sim
            rows.append({
                'jd_file': jd_path.name,
                'project_index': i,
                'project_name': proj.get('name'),
                'project_description': proj_desc,
                'current_label': current_label,
                'sem_sim': sem_sim,
                'ce_score': ce_score,
            })

    # Write CSV
    with out_csv.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            for r in rows:
                writer.writerow(r)

    print(f'WROTE: {out_csv} rows={len(rows)}')


if __name__ == '__main__':
    base = Path(__file__).resolve().parents[1] / 'storage' / 'parser_file'
    cv_path = base / 'cv_20260520075822_7_8.json'
    out_csv = Path('label_candidates.csv')
    export_pairs(cv_path, base, out_csv)
