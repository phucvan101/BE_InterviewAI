import re
from pathlib import Path
from typing import List, Dict

try:
    import spacy
    from spacy.pipeline import EntityRuler
    _SPACY_AVAILABLE = True
except Exception:
    spacy = None
    EntityRuler = None
    _SPACY_AVAILABLE = False

import yaml

_NLP = None
_RULER_LOADED = False
_SYNONYMS_CACHE: Dict[str, List[str]] = {}


def _load_synonyms(yaml_path: Path) -> Dict[str, List[str]]:
    global _SYNONYMS_CACHE
    p = Path(yaml_path)
    if str(p) in _SYNONYMS_CACHE:
        return _SYNONYMS_CACHE[str(p)]
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    _SYNONYMS_CACHE[str(p)] = data
    return data


def _init_spacy_ruler(yaml_path: Path):
    """Initialize a spaCy blank pipeline and an EntityRuler built from the YAML synonyms.
    Falls back gracefully if spaCy is not available.
    """
    global _NLP, _RULER_LOADED
    if _RULER_LOADED:
        return
    syn = _load_synonyms(yaml_path)
    if not _SPACY_AVAILABLE:
        _RULER_LOADED = False
        return
    # use a blank English pipeline to avoid requiring large models
    _NLP = spacy.blank("en")
    # phrase_matcher_attr LOWER for case-insensitive matching
    try:
        ruler = _NLP.add_pipe("entity_ruler", config={"phrase_matcher_attr": "LOWER"})
    except Exception:
        ruler = _NLP.add_pipe("entity_ruler")

    patterns = []
    for canonical, variants in (syn or {}).items():
        # include canonical itself as pattern
        if canonical:
            patterns.append({"label": "TECH", "pattern": canonical})
        for v in variants or []:
            if v:
                patterns.append({"label": "TECH", "pattern": v})

    if patterns:
        ruler.add_patterns(patterns)
    _RULER_LOADED = True


def _regex_extract(text: str, yaml_path: Path) -> List[str]:
    syn = _load_synonyms(yaml_path)
    candidates = []
    for k, vals in (syn or {}).items():
        candidates.append(k)
        for v in vals or []:
            candidates.append(v)
    # sort by length desc to prefer longer matches first
    candidates = sorted(set([c for c in candidates if c and isinstance(c, str)]), key=lambda s: -len(s))
    found = []
    if not text:
        return found
    txt = text
    for cand in candidates:
        # word boundaries; allow punctuation next to token
        try:
            pat = re.compile(r"\b" + re.escape(cand) + r"\b", flags=re.IGNORECASE)
        except re.error:
            pat = re.compile(re.escape(cand), flags=re.IGNORECASE)
        if pat.search(txt):
            found.append(cand)
    return found


def get_ner_techs(text: str, yaml_path: str = None) -> List[str]:
    """Return a list of extracted technology spans (strings).

    Uses spaCy EntityRuler if available and initialized from `yaml_path` (defaults
    to the package's `skill_synonyms.yaml`). Falls back to regex phrase matching.
    """
    if not text:
        return []
    base = Path(__file__).resolve().parent
    default_yaml = base / "skill_synonyms.yaml"
    p = Path(yaml_path) if yaml_path else default_yaml
    # prefer spaCy ruler if possible
    try:
        if _SPACY_AVAILABLE and not _RULER_LOADED:
            _init_spacy_ruler(p)
        if _SPACY_AVAILABLE and _RULER_LOADED and _NLP is not None:
            doc = _NLP(text)
            res = []
            for ent in doc.ents:
                if ent.label_ == "TECH":
                    t = ent.text.strip()
                    if t and t not in res:
                        res.append(t)
            return res
    except Exception:
        # fall through to regex fallback
        pass
    # regex fallback
    try:
        return _regex_extract(text, p)
    except Exception:
        return []


if __name__ == '__main__':
    # small local test
    text = "Implemented object detection using YOLOv5, OpenCV and PyTorch in a real-time pipeline."
    print(get_ner_techs(text))
