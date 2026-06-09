# -*- coding: utf-8 -*-
import logging
from typing import Optional

from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


class ContextRetrieverTool(BaseTool):
    name: str = "context_retriever"
    description: str = (
        "Truy xuất phần liên quan trong Job Description hoặc CV. "
        "Input: query (từ khóa cần tìm), source (jd|cv|both, mặc định both)"
    )

    def __init__(self, jd_text: str = "", cv_text: str = ""):
        super().__init__()
        self._jd_text = jd_text
        self._cv_text = cv_text

    def _run(self, query: str, source: str = "both") -> str:
        if not query.strip():
            return "Query rỗng."

        results = []

        if source in ("jd", "both") and self._jd_text:
            jd_match = self._find_relevant_section(self._jd_text, query)
            if jd_match:
                results.append(f"[JD]\n{jd_match}")

        if source in ("cv", "both") and self._cv_text:
            cv_match = self._find_relevant_section(self._cv_text, query)
            if cv_match:
                results.append(f"[CV]\n{cv_match}")

        if not results:
            return f"Không tìm thấy nội dung liên quan đến '{query}'"

        return "\n\n".join(results)

    def _find_relevant_section(self, text: str, query: str) -> Optional[str]:
        query_lower = query.lower()
        lines = text.split("\n")

        for i, line in enumerate(lines):
            if query_lower in line.lower():
                start = max(0, i - 1)
                end = min(len(lines), i + 4)
                return "\n".join(lines[start:end])

        words = query_lower.split()
        if len(words) >= 2:
            for i, line in enumerate(lines):
                if all(w in line.lower() for w in words):
                    start = max(0, i - 1)
                    end = min(len(lines), i + 4)
                    return "\n".join(lines[start:end])

        return None
