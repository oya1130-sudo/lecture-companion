from pathlib import Path

import pytest

from summed.files import (
    SourceFileError,
    extract_text,
    preferred_summary_text_source,
    safe_filename,
    summed_output_stem,
)


def test_html_extraction_ignores_images_and_active_content(tmp_path: Path):
    source = tmp_path / "lecture.html"
    source.write_text(
        "<h1>세균학 핵심</h1><p>포도알균의 병독성과 감염 경로를 자세히 설명한다. "
        "시험에서는 독소와 임상 양상의 연결을 구분해야 한다. "
        "응고효소와 용혈 양상, 항생제 내성 기전을 함께 비교하고 임상 사례에 적용한다.</p>"
        "<img alt='이미지 안의 정답' src='x'><script>비밀 정답</script>",
        encoding="utf-8",
    )

    text = extract_text(source)

    assert "세균학 핵심" in text
    assert "이미지 안의 정답" not in text
    assert "비밀 정답" not in text


def test_short_or_image_only_source_is_rejected(tmp_path: Path):
    source = tmp_path / "empty.html"
    source.write_text("<img src='scan.png'>", encoding="utf-8")

    with pytest.raises(SourceFileError, match="텍스트를 충분히"):
        extract_text(source)


def test_safe_filename_removes_path_and_windows_metacharacters():
    assert safe_filename("../12:강의?.md") == "12_강의_.md"


def test_output_name_replaces_only_last_summary_marker():
    assert (
        summed_output_stem("병리학 요약본 비교 2주차 요약본.pdf")
        == "병리학 요약본 비교 2주차 summed"
    )
    assert summed_output_stem("약리학 1주차.summary.raw.md") == "약리학 1주차 summed"


def test_pdf_prefers_existing_raw_markdown_companion(tmp_path: Path):
    pdf = tmp_path / "약리학 1주차(1) 약리학 서론 요약본.pdf"
    raw = tmp_path / "약리학 1주차(1) 약리학 서론.summary.raw.md"
    pdf.write_bytes(b"%PDF-placeholder")
    raw.write_text("빠른 텍스트판", encoding="utf-8")

    assert preferred_summary_text_source(pdf) == raw
