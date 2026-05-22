import json
import re
from pathlib import Path
from typing import List

from app.feature.feature_up_cv.scoring.scoring_constants import _PROJECT_TECH_EQUIVALENTS
from app.feature.feature_up_cv.vector_search.embedding_service import get_embedding_service
from app.feature.feature_up_cv.scoring.ner_tech_extractor import get_ner_techs

# Embedding cache for canonical candidates
_CANONICAL_LIST = None
_CANONICAL_EMBS = None
_EMBED_THRESHOLD = 0.78


def _try_keys(tech: str) -> List[str]:
    """Return possible normalized keys from raw tech string."""
    if not isinstance(tech, str):
        return [""]
    s = tech.strip().lower()
    # variants: original, remove dots, remove spaces, remove dots+spaces
    variants = [s, s.replace('.', ''), s.replace(' ', ''), s.replace('.', '').replace(' ', '')]
    # also collapse multiple spaces
    variants.append(re.sub(r"\s+", "", s))
    # common normalization: node.js -> nodejs
    variants.append(s.replace('.', '').replace('-', ''))
    # keep unique
    seen = []
    for v in variants:
        if v and v not in seen:
            seen.append(v)
    return seen


def canonicalize_one(tech: str) -> str:
    """Map a single tech token to canonical token using _PROJECT_TECH_EQUIVALENTS."""
    keys = _try_keys(tech)
    for k in keys:
        if k in _PROJECT_TECH_EQUIVALENTS:
            vals = _PROJECT_TECH_EQUIVALENTS.get(k) or []
            if vals:
                return str(vals[0]).lower()
            else:
                return k
    # fallback: if exact raw lowercase exists as mapping key
    raw = (tech or "").strip().lower()
    if raw in _PROJECT_TECH_EQUIVALENTS:
        vals = _PROJECT_TECH_EQUIVALENTS.get(raw) or []
        return (str(vals[0]).lower() if vals else raw)
    # last-resort: simplified token (remove dots)
    simplified = raw.replace('.', '')

    # Embedding-based fallback: compare token against canonical keys/values
    try:
        best = _embedding_match(raw)
        if best:
            return best
    except Exception:
        pass

    return simplified


def _prepare_canonical_list():
    global _CANONICAL_LIST, _CANONICAL_EMBS
    if _CANONICAL_LIST is not None:
        return
    # build candidate list from mapping keys and mapped values
    candidates = set()
    for k, vals in _PROJECT_TECH_EQUIVALENTS.items():
        if k:
            candidates.add(k)
        for v in vals or []:
            if v:
                candidates.add(v.lower())
    _CANONICAL_LIST = sorted(candidates)
    # compute embeddings lazily when needed
    _CANONICAL_EMBS = None


def _embedding_match(token: str) -> str:
    """Return best canonical candidate by embedding similarity if above threshold."""
    global _CANONICAL_LIST, _CANONICAL_EMBS
    if not token or not token.strip():
        return ""
    _prepare_canonical_list()
    if not _CANONICAL_LIST:
        return ""
    es = get_embedding_service()
    # prepare canonical embeddings once
    if _CANONICAL_EMBS is None:
        texts = [t for t in _CANONICAL_LIST]
        try:
            prefixed = [t for t in texts]
            _CANONICAL_EMBS = es.encode_batch(prefixed, normalize=True)
        except Exception:
            _CANONICAL_EMBS = None
    try:
        t_emb = es.encode(token, normalize=True)
    except Exception:
        return ""
    if _CANONICAL_EMBS is None:
        return ""
    import numpy as _np
    sims = _CANONICAL_EMBS @ t_emb
    best_idx = int(_np.argmax(sims))
    best_sim = float(sims[best_idx])
    if best_sim >= _EMBED_THRESHOLD:
        return _CANONICAL_LIST[best_idx]
    return ""


def canonicalize_file(path: Path, inplace: bool = True) -> int:
    data = json.loads(path.read_text(encoding='utf-8'))
    projects = data.get('projects', [])
    changed = 0
    for proj in projects:
        # original list from parser
        techs = proj.get('technologies', []) or []
        # try NER extraction from description/text and merge
        ner_tokens = []
        try:
            desc = proj.get('description') or proj.get('text') or proj.get('summary') or ''
            ner_tokens = get_ner_techs(desc)
        except Exception:
            ner_tokens = []
        # expose ner results for debugging
        if ner_tokens:
            proj['technologies_ner'] = ner_tokens

        # merge existing techs with NER tokens (preserve order, uniqueness)
        combined = []
        for t in list(techs) + list(ner_tokens):
            if not isinstance(t, str):
                continue
            tt = t.strip()
            if tt and tt not in combined:
                combined.append(tt)

        canonical = []
        for t in combined:
            c = canonicalize_one(t)
            if c and c not in canonical:
                canonical.append(c)

        # store original if not present
        if 'technologies_original' not in proj:
            proj['technologies_original'] = techs

        # replace
        if canonical != techs:
            proj['technologies'] = canonical
            changed += 1

    if changed and inplace:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return changed


def run_on_parser_folder(folder: Path = None) -> None:
    if folder is None:
        folder = Path(__file__).resolve().parents[1] / 'storage' / 'parser_file'
    files = sorted(list(folder.glob('*.json')))
    total_changed = 0
    for p in files:
        try:
            changed = canonicalize_file(p)
            if changed:
                print(f'UPDATED {p.name}: {changed} projects changed')
            total_changed += changed
        except Exception as e:
            print(f'FAILED {p.name}: {e}')

    print(f'Done. Total projects changed: {total_changed}')


if __name__ == '__main__':
    run_on_parser_folder()
