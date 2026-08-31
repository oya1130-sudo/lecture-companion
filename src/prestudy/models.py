from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class SourceKind(str, Enum):
    GUIDE = "학습가이드"
    LECTURE = "강의자료"
    JOKCHEK = "족첵"
    SUMMARY = "선배 써머리"


class SummaryReliability(str, Enum):
    SAME = "same"
    PARTIAL = "partial"
    CHANGED = "changed"
    UNKNOWN = "unknown"


class SourceDocument(BaseModel):
    path: Path
    kind: SourceKind


class LectureRequest(BaseModel):
    course: str
    professor: str
    topic: str
    lecture_date: str = ""
    summary_reliability: SummaryReliability = SummaryReliability.UNKNOWN


class Evidence(BaseModel):
    statement: str = Field(description="자료에서 확인한 사실 또는 조언")
    page: int | None = Field(description="PDF의 1부터 시작하는 쪽 번호. 알 수 없으면 null")
    confidence: str = Field(description="high, medium, low 중 하나")


class SourceDigest(BaseModel):
    source_file: str
    source_kind: str
    relevance: str = Field(description="현재 강의와의 관련성 및 시대/교수 변경 여부")
    scope: list[str]
    facts: list[Evidence]
    study_advice: list[Evidence]
    exam_patterns: list[Evidence]
    key_concepts: list[Evidence]
    questions_found: list[Evidence]
    conflicts_or_limits: list[str]


class CitedItem(BaseModel):
    content: str
    citations: list[str] = Field(description="[파일명 p.쪽] 형태의 근거")


class LectureFlowSection(BaseModel):
    order: int
    source_range: str = Field(description="족첵/강의자료의 PDF 쪽 범위. 예: p.2–16")
    title: str
    ready_notes: list[CitedItem] = Field(description="학생이 따로 필기하지 않아도 되도록 완성된 핵심 노트")
    emphasis_signals: list[CitedItem] = Field(description="교수 강조 또는 출제 가능성이 근거로 확인되는 지점")
    listen_for: list[CitedItem] = Field(description="수업에서 말로 풀어줄 때 집중해서 들을 연결·해석 포인트")
    minimal_live_notes: list[str] = Field(description="PDF만으로 확정할 수 없어 수업 중 짧게 확인할 항목")


class QuickReference(BaseModel):
    title: str
    content: str
    use_when: str
    citations: list[str]


class StudyGuide(BaseModel):
    title: str
    subtitle: str
    how_to_use: list[str]
    lecture_flow: list[LectureFlowSection]
    quick_reference: list[QuickReference]
    professor_and_exam_signals: list[CitedItem]
    common_confusions: list[CitedItem]
    minimal_live_checklist: list[str]
    uncertainties: list[str]
    source_notes: list[str]
