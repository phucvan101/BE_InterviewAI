import json
import os
from pathlib import Path
from typing import List

import numpy as np

from app.feature.feature_up_cv.vector_search.embedding_service import get_embedding_service
from app.feature.feature_up_cv.scoring.cross_encoder_reranker import CrossEncoderReranker
from app.feature.feature_up_cv.scoring.ltr_trainer import LTRTrainer
from app.feature.feature_up_cv.scoring.hybrid_scoring import calculate_hybrid_score


def _normalize_list(items: List[str]) -> List[str]:
    return [s.strip().lower() for s in (items or []) if s]


def build_dataset(cv: dict, jd_files: List[Path]):
    es = get_embedding_service()
    ce = CrossEncoderReranker()

    X_rows = []
    y = []
    groups = []
    meta = []

    for jd_path in jd_files:
        jd = json.loads(jd_path.read_text(encoding='utf-8'))
        res = calculate_hybrid_score(cv, jd)
        labels = []
        exp_features = res.get('features', {}).get('experience', {}) or {}
        labels = exp_features.get('project_relevance_scores') or []

        jd_text = get_embedding_service().encode_structured_jd(jd)
        jd_skills = _normalize_list((jd.get('structured') or jd).get('skills_required') or jd.get('skills_required') or [])

        # per-project
        projects = cv.get('projects', [])
        groups.append(len(projects))
        for i, proj in enumerate(projects):
            proj_desc = proj.get('description', '')
            proj_techs = _normalize_list(proj.get('technologies') or [])
            # semantic sim
            v_jd = es.encode(jd_text)
            v_proj = es.encode(proj_desc)
            sem_sim = es.compute_similarity(v_jd, v_proj)
            # tech intersection
            tech_inter = len(set(jd_skills) & set(proj_techs))
            # skill overlap with CV overall
            cv_skills = _normalize_list(cv.get('skills') or [])
            skill_overlap = len(set(jd_skills) & set(cv_skills)) / max(1, len(jd_skills)) if jd_skills else 0.0
            desc_len = len((proj_desc or '').split())
            # cross-encoder
            try:
                ce_score = ce.score(jd_text, [proj_desc])[0]
            except Exception:
                ce_score = 0.0

            X_rows.append([sem_sim, tech_inter, skill_overlap, desc_len, ce_score])
            # label fallback
            label = labels[i] if i < len(labels) else sem_sim
            y.append(float(label))
            meta.append({
                'jd': jd_path.name,
                'project_index': i,
                'project_name': proj.get('name'),
                'sem_sim': sem_sim,
                'tech_inter': tech_inter,
                'ce_score': ce_score,
                'label': label,
            })

    X = np.array(X_rows, dtype=np.float32)
    y = np.array(y, dtype=np.float32)
    return X, y, groups, meta


def run_demo():
    base = Path(__file__).resolve().parents[1] / 'storage' / 'parser_file'
    cv_path = base / 'cv_20260520075822_7_8.json'
    jd_files = sorted(list(base.glob('jd_*.json')))
    cv = json.loads(cv_path.read_text(encoding='utf-8'))

    X, y, groups, meta = build_dataset(cv, jd_files)

    trainer = LTRTrainer()
    model = trainer.train(X, y, groups)

    ndcg = trainer.evaluate_ndcg(X, y, groups, k=2)

    out_dir = Path(__file__).resolve().parents[1] / 'models'
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / 'ltr_model.pkl'
    trainer.save(str(model_path))

    debug = {
        'model_path': str(model_path),
        'ndcg@2': ndcg,
        'meta': meta,
    }
    out_file = Path('debug_ltr_training.json')
    out_file.write_text(json.dumps(debug, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'WROTE: {out_file}  ndcg@2={ndcg:.4f}')


if __name__ == '__main__':
    run_demo()
