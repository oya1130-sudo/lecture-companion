from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class ReferenceKind(str, Enum):
    EXAM = "족보"
    GUIDE = "학습가이드"
    TIMETABLE = "시간표"


class ReferenceRecord(BaseModel):
    id: str
    kind: ReferenceKind
    course: str
    original_name: str
    source_path: Path
    text_path: Path
    sha256: str
    added_at: datetime


class WeightedTopic(BaseModel):
    topic: str
    importance: str = Field(description="high, medium, low 중 하나")
    reason: str


class ProfessorRule(BaseModel):
    professor: str
    rule: str
    effect: str = Field(description="족보 중요도를 유지 또는 낮추는 이유")


class CourseReferenceProfile(BaseModel):
    course: str
    current_professors: list[str]
    key_topics: list[WeightedTopic]
    exam_patterns: list[str]
    study_advice: list[str]
    professor_rules: list[ProfessorRule]
    timetable_context: list[str]
    uncertainties: list[str]


class NoteTable(BaseModel):
    title: str
    columns: list[str]
    rows: list[list[str]]
    why_useful: str

    @field_validator("rows")
    @classmethod
    def limit_table_size(cls, value: list[list[str]]) -> list[list[str]]:
        return value[:20]


class ReviewQuestion(BaseModel):
    question: str = Field(description="소단원의 핵심 내용을 회상하게 하는 간단한 문제")
    answer: str = Field(description="자료에 근거한 짧고 명확한 정답")


class SectionReviewQuiz(BaseModel):
    section_number: int = Field(ge=1, description="1부터 시작하는 소단원 순서")
    review_quiz: list[ReviewQuestion] = Field(
        min_length=1,
        description="해당 소단원의 주요 내용을 빠짐없이 복습하는 문항",
    )


class QuizBackfillResult(BaseModel):
    sections: list[SectionReviewQuiz]


class NoteSection(BaseModel):
    title: str
    core_points: list[str]
    exam_focus: list[str]
    transcript_additions: list[str]
    review_quiz: list[ReviewQuestion] = Field(
        min_length=1,
        description="소단원 주요 내용을 빠짐없이 복습하는 문항. 보통 3~5개지만 내용 범위에 따라 조절",
    )


class SummedNote(BaseModel):
    title: str
    subtitle: str
    overview: list[str]
    sections: list[NoteSection]
    tables: list[NoteTable]
    rapid_review: list[str]
    likely_confusions: list[str]
    caveats: list[str]


class SummaryRequest(BaseModel):
    course: str
    professor: str
    topic: str
    lecture_date: date
    summary_path: Path
    transcript_paths: list[Path]


class JobEvent(BaseModel):
    message: str
    status: str
    created_at: datetime


class JobRecord(BaseModel):
    job_id: str
    label: str
    status: str
    messages: list[str]
    markdown_path: Path
    html_path: Path
    drive_markdown_path: Path | None = None
    drive_html_path: Path | None = None
    error: str = ""
    created_at: datetime
    started_at: datetime | None = None
    status_changed_at: datetime | None = None
    finished_at: datetime | None = None
    events: list[JobEvent] = Field(default_factory=list)
