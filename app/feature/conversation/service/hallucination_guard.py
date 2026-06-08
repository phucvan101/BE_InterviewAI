# services/hallucination_guard.py
from sentence_transformers import SentenceTransformer, util
from app.feature.conversation.schema import AnalysisReportPayload
from app.feature.conversation.model.conversation import ConversationMessage


class HallucinationGuard:
    # Ngưỡng similarity tối thiểu — evidence phải "gần" transcript ít nhất mức này
    SIMILARITY_THRESHOLD = 0.35

    def __init__(self):
        self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    def evidence_similarity(
        self,
        evidence: str,
        transcript_chunks: list[str],
    ) -> float:
        if not evidence or not transcript_chunks:
            return 0.0
        evidence_embedding = self.model.encode(evidence, convert_to_tensor=True)
        chunk_embeddings = self.model.encode(transcript_chunks, convert_to_tensor=True)
        similarities = util.cos_sim(evidence_embedding, chunk_embeddings)[0]
        return similarities.max().item()

    def _build_transcript_chunks(self, messages: list[ConversationMessage]) -> list[str]:
        """Tách transcript thành chunks theo từng message để tăng độ chính xác"""
        return [
            m.content
            for m in messages
            if m.content and m.content.strip()
        ]

    def validate_evidence(
        self,
        payload: AnalysisReportPayload,
        messages: list[ConversationMessage],
    ) -> list[dict]:
        """
        Trả về list các warning với score cụ thể để dễ debug.
        [{"criterion": "technical", "score": 0.21, "evidence": "..."}]
        """
        transcript_chunks = self._build_transcript_chunks(messages)
        warnings = []

        if not transcript_chunks:
            return warnings

        criteria = [
            ("technical",         payload.scores.technical),
            ("communication",     payload.scores.communication),
            ("confidence",        payload.scores.confidence),
            ("soft_skills",       payload.scores.soft_skills),
            ("company_knowledge", payload.scores.company_knowledge),
        ]

        for criterion, score_item in criteria:
            # Bỏ qua company_knowledge nếu đã bị force về 0 bởi business rule
            if criterion == "company_knowledge" and score_item.score == 0:
                continue

            evidence = score_item.evidence or ""
            if not evidence.strip():
                warnings.append({
                    "criterion": criterion,
                    "score": 0.0,
                    "evidence": "",
                    "message": "Evidence trống",
                })
                continue

            sim_score = self.evidence_similarity(evidence, transcript_chunks)

            if sim_score < self.SIMILARITY_THRESHOLD:
                warnings.append({
                    "criterion": criterion,
                    "similarity": round(sim_score, 3),
                    "evidence": evidence[:120],  # Truncate để log gọn
                    "message": f"Evidence có thể không khớp transcript (similarity={sim_score:.2f})",
                })

        return warnings