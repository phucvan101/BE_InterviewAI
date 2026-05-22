import json
from typing import List

import numpy as np
import joblib

from sklearn.metrics import ndcg_score


class LTRTrainer:
    def __init__(self, model=None):
        self.model = model

    def train(self, X: np.ndarray, y: np.ndarray, groups: List[int], params: dict = None):
        """
        Train an LTR model.

        If LightGBM is available, uses LGBMRanker with default params that can be
        overridden via `params` dict. If LightGBM is not available, falls back
        to a RandomForestRegressor for demonstration purposes.
        """
        try:
            import lightgbm as lgb
            base_params = {"objective": "lambdarank", "n_estimators": 200, "learning_rate": 0.05}
            if params:
                base_params.update(params)
            model = lgb.LGBMRanker(**base_params)
            model.fit(X, y, group=groups)
            self.model = model
            return model
        except Exception:
            from sklearn.ensemble import RandomForestRegressor
            rf = RandomForestRegressor(n_estimators=100)
            rf.fit(X, y)
            self.model = rf
            return rf

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.model.predict(X)

    def save(self, path: str):
        joblib.dump(self.model, path)

    def evaluate_ndcg(self, X: np.ndarray, y: np.ndarray, groups: List[int], k: int = 5) -> float:
        idx = 0
        scores = []
        preds = []
        trues = []
        for g in groups:
            Xg = X[idx: idx + g]
            yg = y[idx: idx + g]
            pg = self.predict(Xg)
            # sklearn's ndcg_score expects arrays shaped (1, n_items)
            try:
                s = ndcg_score([yg], [pg], k=k)
            except Exception:
                s = 0.0
            scores.append(s)
            idx += g
        return float(np.mean(scores)) if scores else 0.0
