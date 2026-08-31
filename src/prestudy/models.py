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
    importance: int = Field(
        default=0,
        ge=0,
        le=3,
        description="기출 중요도. 일반 항목은 0, 기출 포인트는 1~3",
    )
    exam_years: list[str] = Field(
        default_factory=list,
        description="자료에서 명시적으로 확인된 기출 연도. 예: 22, 23",
    )


class StudyTable(BaseModel):
    title: str
    headers: list[str] = Field(description="강의록 원문 용어를 사용한 표 머리글")
    rows: list[list[str]] = Field(description="각 행의 셀. headers와 같은 열 수를 유지")
    citations: list[str] = Field(description="표 전체의 근거")


class CauseEffectFlow(BaseModel):
    title: str
    steps: list[str] = Field(description="원인부터 결과까지 강의록 용어로 쓴 순서형 단계")
    citations: list[str] = Field(description="흐름 전체의 근거")


class FinalChecklist(BaseModel):
    comparisons: list[CitedItem] = Field(default_factory=list)
    cause_and_effect: list[CitedItem] = Field(default_factory=list)
    traps: list[CitedItem] = Field(default_factory=list)


class LectureFlowSection(BaseModel):
    order: int
    source_range: str = Field(description="족첵/강의자료의 PDF 쪽 범위. 예: p.2–16")
    title: str
    ready_notes: list[CitedItem] = Field(description="학생이 따로 필기하지 않아도 되도록 완성된 핵심 노트")
    emphasis_signals: list[CitedItem] = Field(description="교수 강조 또는 출제 가능성이 근거로 확인되는 지점")
    listen_for: list[CitedItem] = Field(description="수업에서 말로 풀어줄 때 집중해서 들을 연결·해석 포인트")
    minimal_live_notes: list[str] = Field(description="PDF만으로 확정할 수 없어 수업 중 짧게 확인할 항목")
    tables: list[StudyTable] = Field(
        default_factory=list,
        description="비교·분류·공식 정리에 유용한 표",
    )
    cause_effect_flows: list[CauseEffectFlow] = Field(
        default_factory=list,
        description="원인에서 결과로 이어지는 기전 흐름",
    )
    trap_points: list[CitedItem] = Field(
        default_factory=list,
        description="오답을 유발하는 예외·반전·혼동 포인트",
    )


class QuickReference(BaseModel):
    title: str
    content: str
    use_when: str
    citations: list[str]


class StudyGuide(BaseModel):
    title: str
    subtitle: str
    exam_style_summary: str = Field(
        default="판단 자료 부족",
        description="학습가이드에 근거한 교수 출제 스타일과 노트 사용 전략",
    )
    how_to_use: list[str]
    lecture_flow: list[LectureFlowSection]
    quick_reference: list[QuickReference]
    professor_and_exam_signals: list[CitedItem]
    common_confusions: list[CitedItem]
    minimal_live_checklist: list[str]
    uncertainties: list[str]
    source_notes: list[str]
    final_checklist: FinalChecklist = Field(default_factory=FinalChecklist)
