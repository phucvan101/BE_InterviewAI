from app.feature.conversation.schema import AnalysisReportPayload, ScoreCriterion


class ScoreAnomalyDetector:
    """Phát hiện bất thường trong điểm AI, chỉ dùng để cảnh báo."""

    MAX_OVERALL_DEVIATION = 10
    HIGH_SCORE_THRESHOLD = 80
    MIN_WORDS_FOR_HIGH_SCORE = 10
    MIN_SIMILARITY_FOR_HIGH_SCORE = 0.35

    def validate(
        self,
        payload: AnalysisReportPayload,
        evidence_similarities: dict[str, float] | None = None,
    ) -> list[dict]:
        warnings: list[dict] = []
        score_items = self._score_items(payload)
        scores = [item.score for _, item in score_items]
        avg_score = sum(scores) / len(scores)
        deviation = abs(payload.overall_score - avg_score)

        if deviation > self.MAX_OVERALL_DEVIATION:
            warnings.append(
                {
                    "type": "overall_score_deviation",
                    "severity": "warning",
                    "overall_score": payload.overall_score,
                    "average_score": round(avg_score, 1),
                    "deviation": round(deviation, 1),
                    "message": (
                        f"overall_score={payload.overall_score} lệch khỏi "
                        f"avg={avg_score:.1f} (deviation={deviation:.1f})"
                    ),
                }
            )

        for criterion, item in score_items:
            evidence = (item.evidence or "").strip()
            word_count = len(evidence.split())

            if (
                item.score >= self.HIGH_SCORE_THRESHOLD
                and word_count < self.MIN_WORDS_FOR_HIGH_SCORE
            ):
                warnings.append(
                    {
                        "type": "high_score_short_evidence",
                        "severity": "warning",
                        "criterion": criterion,
                        "score": item.score,
                        "word_count": word_count,
                        "message": (
                            f"{criterion}: điểm cao ({item.score}) nhưng "
                            f"evidence quá ngắn ({word_count} từ)"
                        ),
                    }
                )

            if evidence_similarities and criterion in evidence_similarities:
                similarity = evidence_similarities[criterion]
                if (
                    item.score >= self.HIGH_SCORE_THRESHOLD
                    and similarity < self.MIN_SIMILARITY_FOR_HIGH_SCORE
                ):
                    warnings.append(
                        {
                            "type": "high_score_low_similarity",
                            "severity": "warning",
                            "criterion": criterion,
                            "score": item.score,
                            "similarity": round(similarity, 3),
                            "message": (
                                f"{criterion}: điểm cao ({item.score}) nhưng "
                                f"evidence ít liên quan transcript "
                                f"(similarity={similarity:.2f})"
                            ),
                        }
                    )

        return warnings

    def _score_items(
        self,
        payload: AnalysisReportPayload,
    ) -> list[tuple[str, ScoreCriterion]]:
        return [
            ("technical", payload.scores.technical),
            ("communication", payload.scores.communication),
            ("confidence", payload.scores.confidence),
            ("soft_skills", payload.scores.soft_skills),
            ("company_knowledge", payload.scores.company_knowledge),
        ]


# ScoreAnomalyDetector, trả warning dạng dict gồm type, severity, criterion, score, message. Detector hiện bắt 3 case:

# overall_score lệch khỏi trung bình điểm thành phần quá 10.
# Điểm cao >=80 nhưng evidence dưới 10 từ.
# Điểm cao >=80 nhưng similarity evidence/transcript dưới 0.35, đồng bộ nhẹ hơn cho tiếng Việt.
