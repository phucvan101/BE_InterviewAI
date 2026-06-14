from typing import Optional
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from app.core.dependencies import get_current_active_user
from app.feature.auth.models.user import User
from app.feature.speech.schemas import SpeechToTextResponse, TextToSpeechRequest
from app.feature.speech.services.openai_speech_service import (
    OpenAISpeechService,
    SpeechServiceConfigurationError,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/stt",
    response_model=SpeechToTextResponse,
    summary="Chuyển giọng nói thành văn bản",
)
async def speech_to_text(
    file: UploadFile = File(..., description="File audio cần transcribe"),
    language: Optional[str] = Form(default=None, description="Mã ngôn ngữ tuỳ chọn, ví dụ: vi"),
    prompt: Optional[str] = Form(default=None, description="Ngữ cảnh tuỳ chọn cho transcription"),
    current_user: User = Depends(get_current_active_user),
) -> SpeechToTextResponse:
    del current_user
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File audio rỗng",
        )

    service = OpenAISpeechService()
    try:
        text = await service.transcribe(
            audio_bytes=audio_bytes,
            filename=file.filename or "audio.webm",
            content_type=file.content_type or "application/octet-stream",
            language=language,
            prompt=prompt,
        )
    except SpeechServiceConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("[speech_to_text] OpenAI transcription failed", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Lỗi khi chuyển giọng nói thành văn bản",
        ) from exc

    return SpeechToTextResponse(text=text, model=service.stt_model)


@router.post(
    "/tts",
    summary="Chuyển văn bản thành giọng nói",
)
async def text_to_speech(
    request: TextToSpeechRequest,
    current_user: User = Depends(get_current_active_user),
) -> StreamingResponse:
    del current_user
    service = OpenAISpeechService()
    try:
        audio_chunks = service.create_speech_stream(
            text=request.text,
            voice=request.voice,
            response_format=request.response_format,
            instructions=request.instructions,
        )
    except SpeechServiceConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("[text_to_speech] OpenAI speech generation failed", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Lỗi khi chuyển văn bản thành giọng nói",
        ) from exc

    media_type = request.media_type
    return StreamingResponse(
        audio_chunks,
        media_type=media_type,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'inline; filename="speech.{request.response_format}"',
            "X-Speech-Model": service.tts_model,
        },
    )
