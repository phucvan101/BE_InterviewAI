from pydantic import BaseModel, Field
from typing import Literal
from app.core.config import settings

class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2500)  # free tier limit
    # Rachel (21m00Tcm4TlvDq8ikWAM) hỗ trợ tiếng Việt tốt nhất trong free voices
    voice_id: str = Field(default_factory=lambda: settings.DEFAULT_VOICE_ID)
    model_id: Literal[
        "eleven_multilingual_v2",  # chất lượng cao nhất, tốt nhất cho tiếng Việt
        "eleven_turbo_v2_5",       # nhanh hơn, cũng hỗ trợ Việt tốt
        "eleven_flash_v2_5",       # latency thấp nhất, dùng khi cần real-time
    ] = "eleven_multilingual_v2"
    output_format: Literal[
        "mp3_44100_128",   # chất lượng tốt nhất free tier
        "mp3_22050_32",    # nhẹ hơn, tải nhanh hơn
    ] = "mp3_44100_128"
    # Tiếng Việt có thanh điệu → nên dùng 0.85-0.95 để phát âm rõ hơn
    speed: float = Field(default=0.9, ge=0.5, le=1.2)