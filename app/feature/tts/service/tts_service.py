# ...existing code...
import hashlib
from functools import lru_cache
import requests
from app.core.config import settings
from app.feature.tts.schema import TTSRequest

# Simple in-memory cache (use Redis in production)
_audio_cache: dict[str, bytes] = {}

def _cache_key(req: TTSRequest) -> str:
    raw = f"{req.text}|{req.voice_id}|{req.model_id}|{req.output_format}|{req.speed}"
    return hashlib.md5(raw.encode()).hexdigest()

def text_to_speech(req: TTSRequest) -> bytes:
    if not settings.FPT_API_KEY:
        raise RuntimeError("FPT_API_KEY not configured in settings or .env")

    key = _cache_key(req)
    if key in _audio_cache:
        return _audio_cache[key]

    url = settings.FPT_TTS_URL
    headers = {
        "api-key": settings.FPT_API_KEY,
        "voice": req.voice_id or settings.FPT_DEFAULT_VOICE,
        "speed": str(req.speed),
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
    }
    payload = req.text or ""

    resp = requests.post(url, data=payload.encode("utf-8"), headers=headers, timeout=30)
    if resp.status_code != 200:
        # surface error to caller (API response text may contain details)
        raise RuntimeError(f"FPT TTS error: status={resp.status_code}, body={resp.text}")

    audio = resp.content
    _audio_cache[key] = audio
    return audio

def get_available_voices() -> list[dict]:
    # FPT may not provide a public "list voices" endpoint; return default suggestion
    return [
        {"id": settings.FPT_DEFAULT_VOICE, "name": settings.FPT_DEFAULT_VOICE, "tier": "fpt", "default": True}
    ]

def _chunk_text(text: str, max_chars: int = 2400) -> list[str]:
    """Cắt text theo câu, tránh cắt giữa từ tiếng Việt/Anh."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    while len(text) > max_chars:
        for sep in [".", "!", "?", ",", " "]:
            idx = text.rfind(sep, 0, max_chars)
            if idx != -1:
                chunks.append(text[:idx + 1].strip())
                text = text[idx + 1:].strip()
                break
        else:
            chunks.append(text[:max_chars])
            text = text[max_chars:]
    if text:
        chunks.append(text)
    return chunks
# ...existing code...   