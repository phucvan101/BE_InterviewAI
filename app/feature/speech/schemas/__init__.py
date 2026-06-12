from typing import Literal

from pydantic import BaseModel, Field


SpeechAudioFormat = Literal["mp3", "opus", "aac", "flac", "wav", "pcm"]


class SpeechToTextResponse(BaseModel):
    text: str = Field(..., description="Nội dung transcription")
    model: str = Field(..., description="Model STT đã dùng")


class TextToSpeechRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4096, description="Văn bản cần đọc")
    voice: str = Field(default="alloy", min_length=1, description="Voice OpenAI TTS")
    response_format: SpeechAudioFormat = Field(default="mp3", description="Định dạng audio trả về")
    instructions: str | None = Field(
        default=None,
        max_length=1024,
        description="Hướng dẫn phong cách giọng đọc tuỳ chọn",
    )

    @property
    def media_type(self) -> str:
        return {
            "mp3": "audio/mpeg",
            "opus": "audio/opus",
            "aac": "audio/aac",
            "flac": "audio/flac",
            "wav": "audio/wav",
            "pcm": "audio/L16",
        }[self.response_format]
