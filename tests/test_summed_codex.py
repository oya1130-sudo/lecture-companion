from summed.codex import configured_reasoning_effort, strict_schema
from summed.models import SummedNote


def test_reasoning_effort_defaults_are_tuned_by_work_type(monkeypatch):
    monkeypatch.delenv("SUMMED_NOTE_REASONING_EFFORT", raising=False)
    monkeypatch.delenv("SUMMED_PROFILE_REASONING_EFFORT", raising=False)

    assert configured_reasoning_effort("note") == "low"
    assert configured_reasoning_effort("profile") == "medium"


def test_invalid_reasoning_effort_falls_back(monkeypatch):
    monkeypatch.setenv("SUMMED_NOTE_REASONING_EFFORT", "turbo")

    assert configured_reasoning_effort("note") == "low"


def test_reasoning_effort_can_be_overridden(monkeypatch):
    monkeypatch.setenv("SUMMED_NOTE_REASONING_EFFORT", "HIGH")

    assert configured_reasoning_effort("note") == "high"


def test_structured_note_requires_quizzes_without_a_strict_question_count():
    schema = strict_schema(SummedNote)
    section_schema = schema["$defs"]["NoteSection"]

    assert "review_quiz" in section_schema["required"]
    assert section_schema["properties"]["review_quiz"]["minItems"] == 1
    assert "maxItems" not in section_schema["properties"]["review_quiz"]
