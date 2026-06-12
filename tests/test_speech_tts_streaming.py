from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.dependencies import get_current_active_user as prod_get_current_active_user
from app.feature.speech.api.router import api_router as speech_router
from app.feature.speech.services.openai_speech_service import OpenAISpeechService


class FakeStreamingSpeechResponse:
    def __init__(self) -> None:
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        self.exited = True

    async def iter_bytes(self, chunk_size: int):
        assert chunk_size == OpenAISpeechService.speech_stream_chunk_size
        yield b"first-"
        yield b"second"


class FakeStreamingSpeechClient:
    def __init__(self, response: FakeStreamingSpeechResponse) -> None:
        self.response = response
        self.calls = []

    def create(self, **params):
        self.calls.append(params)
        return self.response


@pytest.mark.asyncio
async def test_create_speech_stream_uses_openai_streaming_response(monkeypatch):
    response = FakeStreamingSpeechResponse()
    streaming_client = FakeStreamingSpeechClient(response)
    fake_client = SimpleNamespace(
        audio=SimpleNamespace(
            speech=SimpleNamespace(
                with_streaming_response=SimpleNamespace(create=streaming_client.create),
            )
        )
    )

    monkeypatch.setattr(OpenAISpeechService, "_client", lambda self: fake_client)

    service = OpenAISpeechService()
    chunks = [
        chunk
        async for chunk in service.create_speech_stream(
            text="Xin chào",
            voice="alloy",
            response_format="mp3",
            instructions="Đọc tự nhiên",
        )
    ]

    assert chunks == [b"first-", b"second"]
    assert response.entered is True
    assert response.exited is True
    assert streaming_client.calls == [
        {
            "model": service.tts_model,
            "voice": "alloy",
            "input": "Xin chào",
            "response_format": "mp3",
            "instructions": "Đọc tự nhiên",
        }
    ]


@pytest.mark.asyncio
async def test_tts_endpoint_streams_audio(monkeypatch):
    async def fake_current_user():
        return SimpleNamespace(is_active=True, is_deleted=False)

    async def fake_audio_chunks(self, **kwargs):
        yield b"hello "
        yield b"audio"

    monkeypatch.setattr(OpenAISpeechService, "create_speech_stream", fake_audio_chunks)

    app = FastAPI()
    app.include_router(speech_router, prefix=settings.API_PREFIX)
    app.dependency_overrides[prod_get_current_active_user] = fake_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/speech/tts",
            json={"text": "Hello", "voice": "alloy", "response_format": "mp3"},
        )

    assert response.status_code == 200
    assert response.content == b"hello audio"
    assert response.headers["content-type"].startswith("audio/mpeg")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-speech-model"] == settings.OPENAI_TTS_MODEL
