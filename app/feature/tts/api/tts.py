import io
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, Response
from app.feature.tts.schema import TTSRequest
from app.feature.tts.service import text_to_speech
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/tts", tags=["TTS"])

@router.post(
    "/generate",
    summary="Chuyển text sang audio (Việt + Anh xen lẫn)",
    response_class=Response,
    responses={200: {"content": {"audio/mpeg": {}}}},
)
def generate_tts(req: TTSRequest, _=Depends(get_current_user)):
    try:
        audio_bytes = text_to_speech(req)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ElevenLabs error: {str(e)}")

    return StreamingResponse(
        io.BytesIO(audio_bytes),
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": "inline; filename=speech.mp3",
            "Cache-Control": "public, max-age=86400",
        },
    )

@router.get("/voices", summary="Danh sách premade voices miễn phí tối ưu cho tiếng Việt")
def list_free_voices(_=Depends(get_current_user)):
    """
    Chỉ liệt kê ElevenLabs PREMADE voices (miễn phí qua API).
    Library voices (vd: Rachel) yêu cầu gói trả phí — sẽ bị lỗi 402.
    Dùng GET /voices/available để xem đúng danh sách voice khả dụng với API key của bạn.
    """
    return {
        "note": "Đây là premade voices — dùng được trên free tier. Rachel là library voice (trả phí).",
        "recommended_for_vietnamese": [
            {
                "id": "EXAVITQu4vr4xnSDxMaL",
                "name": "Sarah",
                "gender": "Nữ",
                "note": "⭐ Default — premade voice, giọng rõ, hỗ trợ multilingual tốt",
                "tier": "free",
                "default": True,
            },
            {
                "id": "N2lVS1w4EtoT3dr4eOWO",
                "name": "Callum",
                "gender": "Nam",
                "note": "Premade voice, phát âm Việt khá tốt",
                "tier": "free",
                "default": False,
            },
            {
                "id": "JBFqnCBsd6RMkjVDRZzb",
                "name": "George",
                "gender": "Nam",
                "note": "Premade voice, giọng trầm, phù hợp đọc văn bản dài",
                "tier": "free",
                "default": False,
            },
            {
                "id": "onwK4e9ZLuTAKqWW03F9",
                "name": "Daniel",
                "gender": "Nam",
                "note": "Premade voice, giọng tin tức, rõ ràng",
                "tier": "free",
                "default": False,
            },
            {
                "id": "pFZP5JQG7iQjIQuC4Bku",
                "name": "Lily",
                "gender": "Nữ",
                "note": "Premade voice, giọng trẻ, tự nhiên",
                "tier": "free",
                "default": False,
            },
        ],
        "model_recommendation": {
            "best_quality": "eleven_multilingual_v2 — chất lượng cao nhất cho tiếng Việt",
            "balanced": "eleven_turbo_v2_5 — cân bằng tốc độ và chất lượng",
            "lowest_latency": "eleven_flash_v2_5 — dùng khi cần real-time",
        },
        "vietnamese_tuning_tips": {
            "stability": 0.75,
            "similarity_boost": 0.85,
            "style": 0.05,
            "speed": "0.85–0.95 giúp phát âm rõ thanh điệu hơn tốc độ 1.0",
        },
    }


@router.get("/voices/available", summary="Fetch danh sách voice thực tế từ tài khoản ElevenLabs")
def list_available_voices(_=Depends(get_current_user)):
    """
    Gọi ElevenLabs API để lấy đúng danh sách voices khả dụng với API key hiện tại.
    Dùng endpoint này để biết chính xác voice nào dùng được trước khi gọi /generate.
    """
    from app.feature.tts.service import get_available_voices
    try:
        voices = get_available_voices()
        return {"voices": voices, "total": len(voices)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ElevenLabs error: {str(e)}")