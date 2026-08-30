from pathlib import Path

from prestudy.html_renderer import render_study_guide_html
from prestudy.models import (
    CitedItem,
    LectureFlowSection,
    LectureRequest,
    QuickReference,
    SourceDocument,
    SourceKind,
    StudyGuide,
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
