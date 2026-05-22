import json
from pathlib import Path
from typing import Dict, Any

import numpy as np

from app.feature.feature_up_cv.scoring.ltr_demo import build_dataset
from app.feature.feature_up_cv.scoring.ltr_trainer import LTRTrainer


def simple_grid_search(cv_path: Path, jd_dir: Path, param_grid: Dict[str, Any]):
    X, y, groups, meta = build_dataset(json.loads(cv_path.read_text(encoding='utf-8')), sorted(list(jd_dir.glob('jd_*.json'))))

    best = {'ndcg': -1.0, 'params': None}
    results = []
    trainer = LTRTrainer()
    # Flatten grid (simple product)
    import itertools
    keys = list(param_grid.keys())
    values = [param_grid[k] for k in keys]
    for combo in itertools.product(*values):
        params = dict(zip(keys, combo))
        try:
            trainer.train(X, y, groups, params=params)
            ndcg = trainer.evaluate_ndcg(X, y, groups, k=2)
        except Exception:
            ndcg = 0.0
        results.append({'params': params, 'ndcg': float(ndcg)})
        if ndcg > best['ndcg']:
            best['ndcg'] = float(ndcg)
            best['params'] = params

    out = {'best': best, 'results': results}
    Path('debug_ltr_tuning.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print('WROTE: debug_ltr_tuning.json')


if __name__ == '__main__':
    base = Path(__file__).resolve().parents[1] / 'storage' / 'parser_file'
    cv_path = base / 'cv_20260520075822_7_8.json'
    param_grid = {
        'n_estimators': [50, 100],
        'learning_rate': [0.05, 0.1],
        'num_leaves': [31, 63],
    }
    simple_grid_search(cv_path, base, param_grid)
