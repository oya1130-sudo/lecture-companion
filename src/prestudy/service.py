from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from .ai import CodexStudyEngine
from .cache import DigestCache, GuideCache
from .html_renderer import render_study_guide_html
from .models import LectureRequest, SourceDigest, SourceDocument, SourceKind, StudyGuide
from .naming import companion_title
from .page_basis import align_lecture_flow_to_material
from .pdf_renderer import render_study_guide


Progress = Callable[[str], None]


class StudyGuideService:
    def __init__(
        self,
        engine: CodexStudyEngine,
        cache: DigestCache | None = None,
        guide_cache: GuideCache | None = None,
        source_workers: int | None = None,
    ) -> None:
        self.engine = engine
        self.cache = cache or DigestCache()
        self.guide_cache = guide_cache or GuideCache(self.cache.root)
        self.source_workers = max(
            1,
            source_workers or int(os.environ.get("PRESTUDY_SOURCE_WORKERS", "3")),
        )

    @staticmethod
    def _elapsed(started_at: float) -> str:
        seconds = max(0, round(time.monotonic() - started_at))
        minutes, remainder = divmod(seconds, 60)
        return f"{minutes}분 {remainder}초" if minutes else f"{remainder}초"

    @staticmethod
    def _apply_page_basis(
        guide: StudyGuide,
        lecture: LectureRequest,
        sources: list[SourceDocument],
    ) -> StudyGuide:
        guide.title = companion_title(
            lecture.lecture_date,
            lecture.course,
            lecture.professor,
            lecture.topic,
        )
        return align_lecture_flow_to_material(guide, sources)

    def _render(
        self,
        guide: StudyGuide,
        lecture: LectureRequest,
        sources: list[SourceDocument],
        output_path: Path,
        progress: Progress,
    ) -> None:
        suffix = output_path.suffix.lower()
        if suffix == ".html":
            progress("태블릿용 HTML 구성 중")
            render_study_guide_html(guide, lecture, output_path, sources)
        elif suffix == ".pdf":
            progress("PDF 렌더링 중")
            render_study_guide(guide, lecture, output_path)
        else:
            raise ValueError("출력 파일은 .html 또는 .pdf여야 합니다.")

    def create(
        self,
        lecture: LectureRequest,
        sources: list[SourceDocument],
        output_path: Path,
        progress: Progress = lambda _: None,
    ) -> StudyGuide:
        total_started_at = time.monotonic()
        if not sources:
            raise ValueError("분석할 PDF가 없습니다.")
        source_keys: list[str] = []
        for source in sources:
            cache_context = None if source.kind == SourceKind.GUIDE else lecture
            key = self.cache.key(source, self.engine.model, cache_context)
            source_keys.append(key)

        guide_key = self.guide_cache.key(lecture, self.engine.model, source_keys)
        cached_guide = self.guide_cache.get(guide_key)
        if cached_guide is not None:
            progress("완성 노트 캐시 사용 — AI 재호출 없이 출력")
            cached_guide = self._apply_page_basis(cached_guide, lecture, sources)
            self._render(cached_guide, lecture, sources, output_path, progress)
            progress(f"완료 · 총 {self._elapsed(total_started_at)}: {output_path.name}")
            return cached_guide

        guide_digests: list[SourceDigest | None] = [None] * len(sources)
        missing_guides: list[tuple[int, SourceDocument, str]] = []
        direct_sources: list[SourceDocument] = []
        for index, (source, key) in enumerate(zip(sources, source_keys), start=1):
            if source.kind != SourceKind.GUIDE:
                direct_sources.append(source)
                progress(f"[{index}/{len(sources)}] 원문 직접 사용: {source.path.name}")
                continue
            cached = self.cache.get(key)
            if cached is not None:
                progress(f"[{index}/{len(sources)}] 캐시 사용: {source.path.name}")
                guide_digests[index - 1] = cached
                continue
            missing_guides.append((index - 1, source, key))

        def analyze_guide(
            item: tuple[int, SourceDocument, str],
        ) -> tuple[int, SourceDigest]:
            position, source, key = item
            source_started_at = time.monotonic()
            progress(
                f"[{position + 1}/{len(sources)}] 학습가이드 최초 분석 시작: "
                f"{source.path.name}"
            )
            digest = self.engine.analyze_source(source, lecture, progress)
            self.cache.put(key, digest)
            progress(
                f"[{position + 1}/{len(sources)}] 분석 완료 "
                f"({self._elapsed(source_started_at)}): {source.path.name}"
            )
            return position, digest

        if missing_guides:
            workers = min(self.source_workers, len(missing_guides))
            progress(
                f"처음 보는 학습가이드 {len(missing_guides)}개를 "
                f"최대 {workers}개씩 한 번만 분석"
            )
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="source-analysis") as executor:
                futures = [executor.submit(analyze_guide, item) for item in missing_guides]
                for future in as_completed(futures):
                    position, digest = future.result()
                    guide_digests[position] = digest

        progress(f"자료 준비 단계 완료 · 누적 {self._elapsed(total_started_at)}")

        complete_guide_digests = [item for item in guide_digests if item is not None]
        if not direct_sources:
            raise ValueError("족첵 또는 강의자료처럼 이번 수업의 원문 자료가 필요합니다.")

        progress(
            "빠른 생성 · 족첵과 써머리를 별도 분석하지 않고 "
            "한 번에 수업 동반 노트 구성 중"
        )
        synthesis_started_at = time.monotonic()
        guide = self.engine.synthesize_direct(
            lecture,
            complete_guide_digests,
            direct_sources,
            progress=progress,
        )
        progress(f"최종 노트 합성 완료 · {self._elapsed(synthesis_started_at)}")
        guide = self._apply_page_basis(guide, lecture, sources)
        self.guide_cache.put(guide_key, guide)
        self._render(guide, lecture, sources, output_path, progress)
        progress(f"완료 · 총 {self._elapsed(total_started_at)}: {output_path.name}")
        return guide
