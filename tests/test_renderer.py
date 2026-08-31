from pathlib import Path

from pypdf import PdfReader

from prestudy.models import (
    CitedItem,
    CoreNote,
    LectureRequest,
    LectureFlowSection,
    QuickReference,
    StudyGuide,
)
from prestudy.pdf_renderer import _citation_pages, render_study_guide


def sample_guide() -> StudyGuide:
    cited = CitedItem(content="분포용적과 반감기의 관계를 확인한다.", citations=["[써머리.pdf p.1]"])
    core_note = CoreNote(
        heading="분포용적과 반감기",
        kind="기전",
        takeaway="분포용적과 반감기는 clearance를 통해 연결된다.",
        details=["t1/2 = 0.693 × Vd / CL"],
        citations=["[써머리.pdf p.1]"],
    )
    return StudyGuide(
        title="약리학 예습",
        subtitle="약동학 2 및 약물대사",
        how_to_use=["강의록 쪽수에 맞춰 펼친다."],
        lecture_flow=[LectureFlowSection(
            order=1,
            source_range="p.1–10",
            title="분포용적",
            ready_notes=[core_note],
            emphasis_signals=[cited],
            listen_for=[cited],
            minimal_live_notes=["올해 제외 범위:"],
        )],
        quick_reference=[QuickReference(title="Vd", content="Vd = Dose/C0", use_when="초기 농도 계산", citations=["[써머리.pdf p.1]"])],
        professor_and_exam_signals=[cited],
        common_confusions=[cited],
        minimal_live_checklist=["올해 범위 변경만 적는다."],
        uncertainties=["현재 강조점은 수업에서 재확인"],
        source_notes=["써머리는 보조 근거로 사용"],
    )


def test_render_creates_pdf(tmp_path: Path):
    output = tmp_path / "수업동반노트.pdf"
    lecture = LectureRequest(course="약리학", professor="김자은", topic="약동학 2")
    render_study_guide(sample_guide(), lecture, output)
    assert output.read_bytes().startswith(b"%PDF-")
    assert output.stat().st_size > 1000
    text = "\n".join(page.extract_text() or "" for page in PdfReader(str(output)).pages)
    assert "써머리.pdf" not in text
    assert "p.1" in text


def test_citation_pages_removes_filenames_and_deduplicates():
    citations = ["[족첵.pdf p.8]", "[써머리.pdf p.8]", "[족첵.pdf p.12-14]"]
    assert _citation_pages(citations) == "p.8 · p.12–14"
