from pathlib import Path

from prestudy.models import (
    CitedItem,
    LectureFlowSection,
    SourceDocument,
    SourceKind,
    StudyGuide,
)
from prestudy.page_basis import (
    align_lecture_flow_to_material,
    citation_page_labels,
    page_basis_filenames,
)


def _guide() -> StudyGuide:
    lecture_cited = CitedItem(
        content="강의자료 근거",
        citations=["[강의자료.pdf p.7-9]", "[족첵.pdf p.101]"],
    )
    jokchek_only = CitedItem(content="족보 근거", citations=["[족첵.pdf p.102]"])
    return StudyGuide(
        title="원래 제목",
        subtitle="테스트",
        how_to_use=[],
        lecture_flow=[
            LectureFlowSection(
                order=1,
                source_range="p.101–102",
                title="강의자료 연결 구간",
                ready_notes=[lecture_cited],
                emphasis_signals=[],
                listen_for=[],
                minimal_live_notes=[],
            ),
            LectureFlowSection(
                order=2,
                source_range="p.103",
                title="족첵만 있는 구간",
                ready_notes=[jokchek_only],
                emphasis_signals=[],
                listen_for=[],
                minimal_live_notes=[],
            ),
        ],
        quick_reference=[],
        professor_and_exam_signals=[],
        common_confusions=[],
        minimal_live_checklist=[],
        uncertainties=[],
        source_notes=[],
    )


def test_lecture_material_replaces_jokchek_as_page_basis(tmp_path: Path):
    sources = [
        SourceDocument(path=tmp_path / "강의자료.pdf", kind=SourceKind.LECTURE),
        SourceDocument(path=tmp_path / "족첵.pdf", kind=SourceKind.JOKCHEK),
    ]

    filenames, kind = page_basis_filenames(sources)
    guide = align_lecture_flow_to_material(_guide(), sources)

    assert kind == SourceKind.LECTURE
    assert filenames == {"강의자료.pdf"}
    assert guide.lecture_flow[0].source_range == "p.7–9"
    assert guide.lecture_flow[1].source_range == "강의자료 쪽수 확인 필요"
    assert citation_page_labels(
        ["[강의자료.pdf p.7-9]", "[족첵.pdf p.101]"],
        filenames,
    ) == ["p.7–9"]


def test_jokchek_remains_page_basis_without_lecture_material(tmp_path: Path):
    sources = [SourceDocument(path=tmp_path / "족첵.pdf", kind=SourceKind.JOKCHEK)]

    filenames, kind = page_basis_filenames(sources)
    guide = align_lecture_flow_to_material(_guide(), sources)

    assert kind == SourceKind.JOKCHEK
    assert filenames == {"족첵.pdf"}
    assert guide.lecture_flow[0].source_range == "p.101–102"
