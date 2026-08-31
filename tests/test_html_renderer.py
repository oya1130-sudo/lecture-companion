from pathlib import Path

from prestudy.html_renderer import render_study_guide_html
from prestudy.models import (
    CauseEffectFlow,
    CitedItem,
    FinalChecklist,
    LectureFlowSection,
    LectureRequest,
    QuickReference,
    SourceDocument,
    SourceKind,
    StudyGuide,
    StudyTable,
)


def _guide() -> StudyGuide:
    cited = CitedItem(content="분포용적과 반감기의 관계", citations=["[족첵파일.pdf p.12]"])
    return StudyGuide(
        title="약리학 수업 동반 노트",
        subtitle="강의록 옆에 두는 필기 대체 자료",
        how_to_use=["강의록 쪽수에 맞춰 펼친다."],
        lecture_flow=[
            LectureFlowSection(
                order=2,
                source_range="p.20–30",
                title="두 번째 범위",
                ready_notes=[cited],
                emphasis_signals=[cited],
                listen_for=[cited],
                minimal_live_notes=["올해 제외 범위:"],
            ),
            LectureFlowSection(
                order=1,
                source_range="p.1–19",
                title="첫 번째 범위",
                ready_notes=[cited],
                emphasis_signals=[cited],
                listen_for=[cited],
                minimal_live_notes=[],
            ),
        ],
        quick_reference=[
            QuickReference(title="Vd", content="Vd = Dose/C0", use_when="초기 농도 계산", citations=["[족첵파일.pdf p.12]"])
        ],
        professor_and_exam_signals=[cited],
        common_confusions=[cited],
        minimal_live_checklist=["올해 범위 변경만 확인"],
        uncertainties=["현재 강조점은 수업에서 확인"],
        source_notes=["족첵을 우선 사용"],
    )


def test_html_shows_source_files_on_cover_but_not_in_inline_citations(tmp_path: Path):
    output = tmp_path / "동반노트.html"
    lecture = LectureRequest(course="약리학", professor="김자은", topic="약동학")
    sources = [
        SourceDocument(path=tmp_path / "guide.pdf", kind=SourceKind.GUIDE),
        SourceDocument(path=tmp_path / "족첵파일.pdf", kind=SourceKind.JOKCHEK),
        SourceDocument(path=tmp_path / "summary.pdf", kind=SourceKind.SUMMARY),
    ]
    render_study_guide_html(_guide(), lecture, output, sources)
    text = output.read_text(encoding="utf-8")
    assert text.startswith("<!doctype html>")
    assert 'name="viewport"' in text
    assert "localStorage" in text
    assert "사용한 원본 자료" in text
    assert "guide.pdf" in text
    assert "summary.pdf" in text
    assert text.count("족첵파일.pdf") == 1
    hero_start = text.index('<section class="hero"')
    manifest_start = text.index('<div class="source-manifest"')
    hero_end = text.index("</section>", manifest_start)
    usage_start = text.index('<section class="usage"')
    assert hero_start < manifest_start < hero_end < usage_start
    assert "p.12" in text


def test_html_orders_flow_by_source_page(tmp_path: Path):
    output = tmp_path / "동반노트.html"
    lecture = LectureRequest(course="약리학", professor="김자은", topic="약동학")
    render_study_guide_html(_guide(), lecture, output)
    text = output.read_text(encoding="utf-8")
    assert text.index("첫 번째 범위") < text.index("두 번째 범위")


def test_html_displays_only_lecture_material_pages_when_selected(tmp_path: Path):
    output = tmp_path / "강의자료기준.html"
    lecture = LectureRequest(course="약리학", professor="김자은", topic="약동학")
    guide = _guide()
    mixed_citations = ["[족첵파일.pdf p.99]", "[강의자료.pdf p.5]"]
    for section in guide.lecture_flow:
        for item in [*section.ready_notes, *section.emphasis_signals, *section.listen_for]:
            item.citations = mixed_citations
    guide.lecture_flow[0].tables = [
        StudyTable(
            title="강의자료 비교표",
            headers=["A", "B"],
            rows=[["1", "2"]],
            citations=["[족첵파일.pdf p.98]", "[강의자료.pdf p.6]"],
        )
    ]
    guide.lecture_flow[0].cause_effect_flows = [
        CauseEffectFlow(
            title="강의자료 흐름",
            steps=["원인", "결과"],
            citations=["[족첵파일.pdf p.97]", "[강의자료.pdf p.7]"],
        )
    ]
    guide.lecture_flow[0].trap_points = [
        CitedItem(
            content="강의자료 함정",
            citations=["[족첵파일.pdf p.96]", "[강의자료.pdf p.8]"],
        )
    ]
    guide.final_checklist = FinalChecklist(traps=guide.lecture_flow[0].trap_points)
    sources = [
        SourceDocument(path=tmp_path / "강의자료.pdf", kind=SourceKind.LECTURE),
        SourceDocument(path=tmp_path / "족첵파일.pdf", kind=SourceKind.JOKCHEK),
    ]

    render_study_guide_html(guide, lecture, output, sources)
    text = output.read_text(encoding="utf-8")

    assert "페이지 기준 · 강의자료" in text
    assert "강의자료.pdf" in text
    assert "p.5" in text
    assert "p.6" in text and "p.7" in text and "p.8" in text
    assert "p.99" not in text
    assert "p.98" not in text and "p.97" not in text and "p.96" not in text


def test_html_uses_exam_focused_companion_note_layout(tmp_path: Path):
    output = tmp_path / "새스타일.html"
    lecture = LectureRequest(
        course="병리학",
        professor="이소민",
        topic="Hemodynamic Disorders(2)",
        lecture_date="2026-08-31",
    )
    guide = _guide()
    exam_point = CitedItem(
        content="반감기 계산은 반복 출제됨",
        citations=["[족첵파일.pdf p.12]"],
        importance=3,
        exam_years=["22", "23"],
    )
    unknown_year_point = CitedItem(
        content="연도 표기가 없는 기출 표시",
        citations=["[족첵파일.pdf p.13]"],
        importance=2,
    )
    section = guide.lecture_flow[0]
    section.emphasis_signals = [exam_point, unknown_year_point]
    section.tables = [
        StudyTable(
            title="A vs B",
            headers=["항목", "A", "B"],
            rows=[["제거", "linear", "nonlinear"]],
            citations=["[족첵파일.pdf p.12]"],
        )
    ]
    section.cause_effect_flows = [
        CauseEffectFlow(
            title="Dose 증가의 결과",
            steps=["Dose 증가", "C0 증가", "AUC 증가"],
            citations=["[족첵파일.pdf p.12]"],
        )
    ]
    section.trap_points = [
        CitedItem(
            content="clearance와 elimination rate를 혼동하지 않는다.",
            citations=["[족첵파일.pdf p.12]"],
        )
    ]
    guide.exam_style_summary = "짤족 근거 있음 · 문제 패턴과 정답 근거 중심"
    guide.final_checklist = FinalChecklist(
        comparisons=[exam_point],
        cause_and_effect=[exam_point],
        traps=section.trap_points,
    )

    render_study_guide_html(guide, lecture, output)
    text = output.read_text(encoding="utf-8")

    assert "<title>0831 병리학 이소민 Hemodynamic Disorders(2)</title>" in text
    assert "<h1>0831 병리학 이소민 Hemodynamic Disorders(2)</h1>" in text
    assert text.index("수업 로드맵") < text.index('id="flow-1"')
    assert "짤족 근거 있음" in text
    assert "⭐⭐⭐" in text
    assert "22년, 23년 기출" in text
    assert "기출 연도 확인 불가" in text
    assert '<table>' in text and "linear" in text
    assert "Dose 증가의 결과" in text and "mechanism-arrow" in text
    assert 'blockquote class="trap-point' in text
    assert "최종 체크리스트" in text
    assert "Cause &amp; Effect" in text
