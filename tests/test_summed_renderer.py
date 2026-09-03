from datetime import date
from pathlib import Path

from summed.models import NoteSection, NoteTable, ReviewQuestion, SummedNote, SummaryRequest
from summed.renderer import render_html, render_markdown


def _note() -> SummedNote:
    return SummedNote(
        title="세균 <핵심>",
        subtitle="시험용 압축",
        overview=["독소 ![금지](image.png) 구분"],
        sections=[
            NoteSection(
                title="병독성",
                core_points=["<script>alert(1)</script>은 텍스트"],
                exam_focus=["기전 연결"],
                transcript_additions=["교수 강조"],
                review_quiz=[
                    ReviewQuestion(
                        question="핵심 병독성 인자는 <무엇>인가?",
                        answer="독소와 부착 인자를 구분한다.",
                    )
                ],
            )
        ],
        tables=[
            NoteTable(
                title="비교",
                columns=["항목", "특징"],
                rows=[["A", "B"]],
                why_useful="구분에 유용",
            )
        ],
        rapid_review=["A → B"],
        likely_confusions=["C와 D"],
        caveats=[],
    )


def _request(tmp_path: Path) -> SummaryRequest:
    return SummaryRequest(
        course="미생물학",
        professor="김교수",
        topic="세균",
        lecture_date=date(2026, 9, 2),
        summary_path=tmp_path / "요약.md",
        transcript_paths=[tmp_path / "전사.txt"],
    )


def test_renderers_remove_images_and_escape_html(tmp_path: Path):
    markdown = tmp_path / "note.md"
    html = tmp_path / "note.html"
    request = _request(tmp_path)

    render_markdown(_note(), request, ["요약.md", "전사.txt"], markdown)
    render_html(_note(), request, ["요약.md", "전사.txt"], html)

    md_text = markdown.read_text(encoding="utf-8")
    html_text = html.read_text(encoding="utf-8")
    assert "![" not in md_text
    assert "<img" not in html_text.casefold()
    assert "<script>alert(1)</script>은 텍스트" not in html_text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;은 텍스트" in html_text
    assert "<table>" in html_text
    assert "### 소단원 복습 퀴즈" in md_text
    assert "<summary>정답 보기</summary>" in md_text
    assert '<details class="quiz-item">' in html_text
    assert "핵심 병독성 인자는 &lt;무엇&gt;인가?" in html_text
    assert "독소와 부착 인자를 구분한다." in html_text
