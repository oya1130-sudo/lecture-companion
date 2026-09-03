import pytest

from summed.backfill_quizzes import merge_review_quizzes
from summed.models import QuizBackfillResult, ReviewQuestion, SectionReviewQuiz


def _legacy_note() -> dict:
    return {
        "title": "기존 정리본",
        "subtitle": "본문 보존",
        "overview": ["개요"],
        "sections": [
            {
                "title": "첫 소단원",
                "core_points": ["A"],
                "exam_focus": ["B"],
                "transcript_additions": [],
            },
            {
                "title": "둘째 소단원",
                "core_points": ["C"],
                "exam_focus": [],
                "transcript_additions": ["D"],
            },
        ],
        "tables": [],
        "rapid_review": [],
        "likely_confusions": [],
        "caveats": [],
    }


def test_merge_adds_quizzes_without_changing_existing_content():
    legacy = _legacy_note()
    quizzes = QuizBackfillResult(
        sections=[
            SectionReviewQuiz(
                section_number=1,
                review_quiz=[ReviewQuestion(question="A는?", answer="A")],
            ),
            SectionReviewQuiz(
                section_number=2,
                review_quiz=[ReviewQuestion(question="C는?", answer="C")],
            ),
        ]
    )

    enriched = merge_review_quizzes(legacy, quizzes)

    assert enriched.sections[0].review_quiz[0].question == "A는?"
    assert enriched.sections[1].review_quiz[0].answer == "C"
    assert legacy["sections"][0].get("review_quiz") is None
    assert enriched.model_dump(exclude={"sections"}) == {
        key: value for key, value in legacy.items() if key != "sections"
    }


def test_merge_rejects_missing_or_duplicate_section_numbers():
    duplicate = QuizBackfillResult(
        sections=[
            SectionReviewQuiz(
                section_number=1,
                review_quiz=[ReviewQuestion(question="A는?", answer="A")],
            ),
            SectionReviewQuiz(
                section_number=1,
                review_quiz=[ReviewQuestion(question="B는?", answer="B")],
            ),
        ]
    )

    with pytest.raises(ValueError, match="소단원 번호"):
        merge_review_quizzes(_legacy_note(), duplicate)
