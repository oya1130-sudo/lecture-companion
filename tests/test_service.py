from __future__ import annotations

import threading
import time
from pathlib import Path

from prestudy.cache import DigestCache, GuideCache
from prestudy.models import (
    LectureRequest,
    SourceDigest,
    SourceDocument,
    SourceKind,
    StudyGuide,
)
from prestudy.service import StudyGuideService


def _digest(source: SourceDocument) -> SourceDigest:
    return SourceDigest(
        source_file=source.path.name,
        source_kind=source.kind.value,
        relevance="관련 있음",
        scope=["테스트"],
        facts=[],
        study_advice=[],
        exam_patterns=[],
        key_concepts=[],
        questions_found=[],
        conflicts_or_limits=[],
    )


def _guide() -> StudyGuide:
    return StudyGuide(
        title="수업 동반 노트",
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


class FakeEngine:
    model = "test-model"

    def __init__(self) -> None:
        self.synthesis_count = 0
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def analyze_source(self, source, lecture, progress):
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        time.sleep(0.05)
        with self.lock:
            self.active -= 1
        return _digest(source)

    def synthesize(self, lecture, digests):
        self.synthesis_count += 1
        return _guide()


def test_sources_run_in_parallel_and_finished_guide_is_reused(tmp_path: Path, monkeypatch):
    sources = []
    for index in range(3):
        path = tmp_path / f"source-{index}.pdf"
        path.write_bytes(f"%PDF-{index}".encode())
        sources.append(SourceDocument(path=path, kind=SourceKind.JOKCHEK))

    rendered = []

    def fake_render(guide, lecture, output_path, source_documents):
        output_path.write_text("<html>done</html>", encoding="utf-8")
        rendered.append((output_path, source_documents))

    monkeypatch.setattr("prestudy.service.render_study_guide_html", fake_render)
    engine = FakeEngine()
    cache_root = tmp_path / "cache"
    service = StudyGuideService(
        engine,
        cache=DigestCache(cache_root),
        guide_cache=GuideCache(cache_root),
        source_workers=3,
    )
    lecture = LectureRequest(course="약리학", professor="김자은", topic="약동학")

    service.create(lecture, sources, tmp_path / "first.html")
    service.create(lecture, sources, tmp_path / "second.html")

    assert engine.max_active >= 2
    assert engine.synthesis_count == 1
    assert len(rendered) == 2
    assert rendered[0][1] == sources
    assert (tmp_path / "second.html").is_file()
