from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from .models import CitedItem, SourceDocument, SourceKind, StudyGuide


_CITATION = re.compile(
    r"\[(?P<filename>.+?)\s+p\.\s*(?P<start>\d+)"
    r"(?:\s*[–-]\s*(?P<end>\d+))?[^]]*]",
    flags=re.IGNORECASE,
)


def citation_page_ranges(
    citations: Iterable[str],
    allowed_filenames: set[str] | None = None,
) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for citation in citations:
        for match in _CITATION.finditer(citation):
            filename = match.group("filename").strip()
            if allowed_filenames is not None and filename not in allowed_filenames:
                continue
            start = int(match.group("start"))
            end = int(match.group("end") or start)
            page_range = (min(start, end), max(start, end))
            if page_range not in ranges:
                ranges.append(page_range)
    return ranges


def citation_page_labels(
    citations: Iterable[str],
    allowed_filenames: set[str] | None = None,
) -> list[str]:
    return [
        f"p.{start}" if start == end else f"p.{start}–{end}"
        for start, end in citation_page_ranges(citations, allowed_filenames)
    ]


def page_basis_filenames(sources: Sequence[SourceDocument]) -> tuple[set[str], SourceKind]:
    lecture_files = {
        source.path.name for source in sources if source.kind == SourceKind.LECTURE
    }
    if lecture_files:
        return lecture_files, SourceKind.LECTURE
    return (
        {source.path.name for source in sources if source.kind == SourceKind.JOKCHEK},
        SourceKind.JOKCHEK,
    )


def _section_citations(items: Iterable[CitedItem]) -> list[str]:
    return [citation for item in items for citation in item.citations]


def align_lecture_flow_to_material(
    guide: StudyGuide,
    sources: Sequence[SourceDocument],
) -> StudyGuide:
    lecture_files = {
        source.path.name for source in sources if source.kind == SourceKind.LECTURE
    }
    if not lecture_files:
        return guide

    for section in guide.lecture_flow:
        citations = _section_citations(
            [*section.ready_notes, *section.emphasis_signals, *section.listen_for]
        )
        ranges = citation_page_ranges(citations, lecture_files)
        if not ranges:
            section.source_range = "강의자료 쪽수 확인 필요"
            continue
        first_page = min(start for start, _ in ranges)
        last_page = max(end for _, end in ranges)
        section.source_range = (
            f"p.{first_page}"
            if first_page == last_page
            else f"p.{first_page}–{last_page}"
        )
    return guide
