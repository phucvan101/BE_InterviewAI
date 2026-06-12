from app.feature.feature_up_cv.auth.services.score_feedback_service import (
    _parse_positive_id,
    _sanitize_score_overrides,
)


def test_sanitize_score_overrides_clamps_and_filters_values():
    result = _sanitize_score_overrides(
        {
            "experience_score": 55,
            "skills_score": 99,
            "education_score": -2,
            "career_objectives_score": "7.5",
            "company_fit_score": 8,
            "unknown_score": 10,
            "bad_numeric": "not-a-number",
        }
    )

    assert result == {
        "experience_score": 50.0,
        "skills_score": 30.0,
        "education_score": 0.0,
        "career_objectives_score": 7.5,
        "company_fit_score": 8.0,
    }


def test_parse_positive_id_rejects_invalid_values():
    assert _parse_positive_id("12", "cv_id") == 12

    for raw in ("0", "-1", "abc"):
        try:
            _parse_positive_id(raw, "cv_id")
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {raw!r}")
