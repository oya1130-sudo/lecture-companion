from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from .ai import CodexStudyEngine
from .cache import DigestCache, GuideCache
from .html_renderer import render_study_guide_html
from .models import LectureRequest, SourceDigest, SourceDocument, SourceKind, StudyGuide
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
            source_workers or int(os.environ.get("PRESTUDY_SOURCE_WORKERS", "2")),
        )

    @staticmethod
    def _apply_page_basis(
        guide: StudyGuide,
        lecture: LectureRequest,
        sources: list[SourceDocument],
    ) -> StudyGuide:
        if any(source.kind == SourceKind.LECTURE for source in sources):
            guide.title = f"{lecture.topic} 수업 동반 노트"
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
        if not sources:
            raise ValueError("분석할 PDF가 없습니다.")
        digests: list[SourceDigest | None] = [None] * len(sources)
        source_keys: list[str] = []
        missing: list[tuple[int, SourceDocument, str]] = []
        for index, source in enumerate(sources, start=1):
            cache_context = None if source.kind.value == "학습가이드" else lecture
            key = self.cache.key(source, self.engine.model, cache_context)
            source_keys.append(key)
            cached = self.cache.get(key)
            if cached is not None:
                progress(f"[{index}/{len(sources)}] 캐시 사용: {source.path.name}")
                digests[index - 1] = cached
                continue
            missing.append((index - 1, source, key))

        def analyze(item: tuple[int, SourceDocument, str]) -> tuple[int, SourceDigest]:
            position, source, key = item
            progress(f"[{position + 1}/{len(sources)}] 병렬 분석 시작: {source.path.name}")
            digest = self.engine.analyze_source(source, lecture, progress)
            self.cache.put(key, digest)
            return position, digest

        if missing:
            workers = min(self.source_workers, len(missing))
            progress(f"미분석 자료 {len(missing)}개를 최대 {workers}개씩 병렬 처리")
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="source-analysis") as executor:
                futures = [executor.submit(analyze, item) for item in missing]
                for future in as_completed(futures):
                    position, digest = future.result()
                    digests[position] = digest

        complete_digests = [item for item in digests if item is not None]
        if len(complete_digests) != len(sources):
            raise RuntimeError("일부 자료 분석 결과가 누락되었습니다.")

        guide_key = self.guide_cache.key(lecture, self.engine.model, source_keys)
        cached_guide = self.guide_cache.get(guide_key)
        if cached_guide is not None:
            progress("완성 노트 캐시 사용 — AI 재호출 없이 출력")
            cached_guide = self._apply_page_basis(cached_guide, lecture, sources)
            self._render(cached_guide, lecture, sources, output_path, progress)
            progress(f"완료: {output_path.name}")
            return cached_guide

        progress("강의 흐름별 수업 동반 노트 구성 중")
        guide = self.engine.synthesize(lecture, complete_digests)
        guide = self._apply_page_basis(guide, lecture, sources)
        self.guide_cache.put(guide_key, guide)
        self._render(guide, lecture, sources, output_path, progress)
        progress(f"완료: {output_path.name}")
        return guide
