from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


_JOKCHEK_FILENAME = re.compile(
    r"^(?P<course>.+?)_"
    r"(?P<week>\d+주차\([^)]+\))_"
    r"(?P<professor>[^_]+)_"
    r"(?P<title>.+)_"
    r"(?P<author>[^_]+)$"
)


class JokchekMetadataError(ValueError):
    pass


@dataclass(frozen=True)
class LectureMetadata:
    professor: str
    topic: str


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _identity(value: str) -> str:
    return re.sub(r"[\s_-]+", "", value).casefold()


def infer_jokchek_metadata(
    filenames: Iterable[str | Path],
    expected_course: str = "",
) -> LectureMetadata:
    parsed: list[tuple[str, str, str]] = []
    invalid: list[str] = []

    for value in filenames:
        filename = Path(value).name
        match = _JOKCHEK_FILENAME.match(Path(filename).stem)
        if match is None:
            invalid.append(filename)
            continue
        course = _clean(match.group("course"))
        professor = _clean(match.group("professor"))
        topic = _clean(match.group("title"))
        if not professor or not topic:
            invalid.append(filename)
            continue
        parsed.append((course, professor, topic))

    if invalid:
        names = ", ".join(invalid)
        raise JokchekMetadataError(
            "족첵 파일명에서 교수명과 수업 제목을 찾지 못했습니다. "
            "'과목_주차(차시)_교수명_수업제목_작성자.pdf' 형식인지 확인해 주세요: "
            f"{names}"
        )
    if not parsed:
        raise JokchekMetadataError("교수명과 수업 제목을 확인할 족첵 PDF가 없습니다.")

    if expected_course:
        mismatched = sorted({course for course, _, _ in parsed if _identity(course) != _identity(expected_course)})
        if mismatched:
            raise JokchekMetadataError(
                f"선택한 과목은 {expected_course}이지만 족첵 파일명에는 "
                f"{', '.join(mismatched)}으로 표시되어 있습니다."
            )

    professors: dict[str, str] = {}
    for _, professor, _ in parsed:
        professors.setdefault(_identity(professor), professor)
    if len(professors) != 1:
        raise JokchekMetadataError(
            "선택한 족첵들의 교수명이 서로 다릅니다. 같은 교수의 한 강의 자료만 선택해 주세요: "
            + ", ".join(professors.values())
        )

    topics: dict[str, str] = {}
    for _, _, topic in parsed:
        topics.setdefault(_identity(topic), topic)

    return LectureMetadata(
        professor=next(iter(professors.values())),
        topic=" / ".join(topics.values()),
    )
