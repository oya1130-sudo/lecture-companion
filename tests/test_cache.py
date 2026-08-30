from pathlib import Path

from prestudy.cache import DigestCache, GuideCache
from prestudy.models import LectureRequest, SourceDigest, SourceDocument, SourceKind, StudyGuide


def digest() -> SourceDigest:
    return SourceDigest(
        source_file="guide.pdf",
        source_kind="학습가이드",
        relevance="관련 있음",
        scope=["약리학"],
        facts=[],
        study_advice=[],
        exam_patterns=[],
        key_concepts=[],
        questions_found=[],
        conflicts_or_limits=[],
    )


def guide() -> StudyGuide:
    return StudyGuide(
        title="약동학 수업 동반 노트",
        subtitle="테스트",
        how_to_use=[],
        lecture_flow=[],
        quick_reference=[],
        professor_and_exam_signals=[],
        common_confusions=[],
        minimal_live_checklist=[],
        uncertainties=[],
        source_notes=[],
    )


def test_cache_round_trip(tmp_path: Path):
    pdf = tmp_path / "guide.pdf"
    pdf.write_bytes(b"%PDF-example")
    source = SourceDocument(path=pdf, kind=SourceKind.GUIDE)
    cache = DigestCache(tmp_path / "cache")
    lecture = LectureRequest(course="약리학", professor="김자은", topic="약동학")
    key = cache.key(source, "test-model", lecture)
    cache.put(key, digest())
    assert cache.get(key) == digest()


def test_cache_key_changes_by_lecture(tmp_path: Path):
    pdf = tmp_path / "guide.pdf"
    pdf.write_bytes(b"%PDF-example")
    source = SourceDocument(path=pdf, kind=SourceKind.GUIDE)
    cache = DigestCache(tmp_path / "cache")
    first = LectureRequest(course="약리학", professor="김자은", topic="약동학")
    second = LectureRequest(course="병리학", professor="김용준", topic="세포 손상")
    assert cache.key(source, "model", first) != cache.key(source, "model", second)


def test_guide_cache_round_trip_and_key_changes(tmp_path: Path):
    cache = GuideCache(tmp_path / "cache")
    lecture = LectureRequest(course="약리학", professor="김자은", topic="약동학")
    first_key = cache.key(lecture, "model", ["source-a", "source-b"])
    second_key = cache.key(lecture, "model", ["source-a", "source-c"])

    cache.put(first_key, guide())

    assert cache.get(first_key) == guide()
    assert first_key != second_key
