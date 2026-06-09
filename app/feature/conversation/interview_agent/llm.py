# -*- coding: utf-8 -*-
import asyncio
from typing import Any, List, Optional

from langchain_core.language_models.llms import LLM
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.outputs import GenerationChunk

from app.feature.feature_up_cv.core.gemini_client import generate_content


class GeminiLangChainLLM(LLM):
    temperature: float = 0.7

    @property
    def _llm_type(self) -> str:
        return "gemini_custom"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        return generate_content(prompt=prompt, step="interview_agent")

    async def _agenerate(
        self,
        prompts: List[str],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> List[str]:
        results = []
        for p in prompts:
            result = generate_content(prompt=p, step="interview_agent")
            results.append(result)
        return results

    async def ainvoke(self, prompt: str) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._call, prompt)
