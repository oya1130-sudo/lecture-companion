import json
from datetime import date
from pathlib import Path

from summed.models import (
    CourseReferenceProfile,
    NoteSection,
    ReferenceKind,
    ReviewQuestion,
    SummedNote,
    SummaryRequest,
)
from summed.references import ReferenceLibrary
from summed.service import SummedService


LONG_TEXT = ("포도알균의 병독성, 독소, 임상 양상과 치료 원칙을 구분한다. " * 80).strip()


class FakeRunner:
    def __init__(self):
        self.profile_calls = 0
        self.note_calls = []

    def build_reference_profile(self, course, manifest, workdir, progress):
        self.profile_calls += 1
        assert "족보" in manifest
        return CourseReferenceProfile(
            course=course,
            current_professors=["김교수"],
            key_topics=[],
            exam_patterns=["기전 연결"],
            study_advice=[],
            professor_rules=[],
            timetable_context=[],
            uncertainties=[],
        )

    def create_note(self, **kwargs):
        self.note_calls.append(kwargs)
        return SummedNote(
            title="포도알균",
            subtitle="시험 대비",
            overview=["독소 구분"],
            sections=[
                NoteSection(
                    title="핵심",
                    core_points=["병독성"],
                    exam_focus=[],
                    transcript_additions=[],
                    review_quiz=[ReviewQuestion(question="핵심 병독성은?", answer="독소")],
                )
            ],
            tables=[],
            rapid_review=["독소"],
            likely_confusions=[],
            caveats=[],
        )


def test_service_caches_reference_profile_and_generates_both_formats(tmp_path: Path):
    library = ReferenceLibrary(tmp_path / "references")
    reference = tmp_path / "족보.txt"
    reference.write_text(LONG_TEXT, encoding="utf-8")
    library.add(reference, ReferenceKind.EXAM, "미생물학")
    summary = tmp_path / "요약.md"
    transcript = tmp_path / "전사.txt"
    summary.write_text(LONG_TEXT, encoding="utf-8")
    transcript.write_text(LONG_TEXT, encoding="utf-8")
    request = SummaryRequest(
        course="미생물학",
        professor="김교수",
        topic="포도알균",
        lecture_date=date(2026, 9, 2),
        summary_path=summary,
        transcript_paths=[transcript],
    )
    runner = FakeRunner()
    service = SummedService(library, runner, tmp_path / "output")

    _, markdown, html, _ = service.create(request, tmp_path / "job-1", model="test")
    service.create(request, tmp_path / "job-2", model="test")

    assert markdown.is_file()
    assert html.is_file()
    assert markdown.name == "요약 summed.md"
    assert markdown.parent.name == "md"
    assert markdown.parent.parent.name == "미생물학"
    assert html.name == "요약 summed.html"
    assert html.parent.name == "미생물학"
    assert runner.profile_calls == 1
    assert len(runner.note_calls) == 2
    assert runner.note_calls[0]["target_min"] == round(len(LONG_TEXT.replace(" ", "")) * 0.20)
    profile_files = list((tmp_path / "references" / "profiles").rglob("*.json"))
    assert len(profile_files) == 1
    assert json.loads(profile_files[0].read_text(encoding="utf-8"))["course"] == "미생물학"
