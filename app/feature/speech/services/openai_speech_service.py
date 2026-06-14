from typing import Optional
import inspect
from collections.abc import AsyncIterator
from io import BytesIO

from app.core.config import settings


class SpeechServiceConfigurationError(RuntimeError):
    pass


class OpenAISpeechService:
    speech_stream_chunk_size = 64 * 1024

    def __init__(self) -> None:
        self.stt_model = settings.OPENAI_STT_MODEL
        self.tts_model = settings.OPENAI_TTS_MODEL

    def _client(self):
        if not settings.OPENAI_API_KEY:
            raise SpeechServiceConfigurationError("Thiếu OPENAI_API_KEY")

        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise SpeechServiceConfigurationError(
                "Chưa cài dependency openai; hãy chạy `pip install -r requirements.txt`"
            ) from exc

        return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def transcribe(
        self,
        *,
        audio_bytes: bytes,
        filename: str,
        content_type: str,
        language: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> str:
        client = self._client()
        audio_file = (filename, BytesIO(audio_bytes), content_type)
        params = {
            "model": self.stt_model,
            "file": audio_file,
            "response_format": "json",
        }
        if language:
            params["language"] = language
        if prompt:
            params["prompt"] = prompt

        transcription = await client.audio.transcriptions.create(**params)
        text = getattr(transcription, "text", None)
        if text is None and isinstance(transcription, dict):
            text = transcription.get("text")
        return (text or "").strip()

    async def create_speech(
        self,
        *,
        text: str,
        voice: str,
        response_format: str,
        instructions: Optional[str] = None,
    ) -> bytes:
        client = self._client()
        params = {
            "model": self.tts_model,
            "voice": voice,
            "input": text,
            "response_format": response_format,
        }
        if instructions:
            params["instructions"] = instructions

        response = await client.audio.speech.create(**params)
        return await self._read_response_bytes(response)

    def create_speech_stream(
        self,
        *,
        text: str,
        voice: str,
        response_format: str,
        instructions: str | None = None,
    ) -> AsyncIterator[bytes]:
        client = self._client()
        params = {
            "model": self.tts_model,
            "voice": voice,
            "input": text,
            "response_format": response_format,
        }
        if instructions:
            params["instructions"] = instructions

        return self._stream_speech_response(client, params)

    async def _stream_speech_response(self, client, params: dict) -> AsyncIterator[bytes]:
        streaming_response = getattr(client.audio.speech, "with_streaming_response", None)
        if streaming_response is not None:
            async with streaming_response.create(**params) as response:
                async for chunk in self._iter_response_chunks(response):
                    yield chunk
            return

        response = await client.audio.speech.create(**params)
        async for chunk in self._iter_response_chunks(response):
            yield chunk

    async def _iter_response_chunks(self, response) -> AsyncIterator[bytes]:
        if isinstance(response, bytes):
            yield response
            return

        if hasattr(response, "iter_bytes"):
            chunks = response.iter_bytes(chunk_size=self.speech_stream_chunk_size)
            if inspect.isasyncgen(chunks) or hasattr(chunks, "__aiter__"):
                async for chunk in chunks:
                    if chunk:
                        yield chunk
            else:
                for chunk in chunks:
                    if chunk:
                        yield chunk
            return

        data = await self._read_response_bytes(response)
        if data:
            yield data

    async def _read_response_bytes(self, response) -> bytes:
        if isinstance(response, bytes):
            return response

        if hasattr(response, "aread"):
            data = response.aread()
            if inspect.isawaitable(data):
                return await data
            return data

        if hasattr(response, "read"):
            data = response.read()
            if inspect.isawaitable(data):
                return await data
            return data

        content = getattr(response, "content", None)
        if content is not None:
            return content

        raise TypeError("Unsupported OpenAI speech response type")
