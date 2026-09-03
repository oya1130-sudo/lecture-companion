from __future__ import annotations

import json
import shutil
import threading
from pathlib import Path
from typing import Callable

from .codex import CodexRunner
from .files import (
    MARKDOWN_FOLDER_NAME,
    meaningful_length,
    preferred_summary_text_source,
    safe_filename,
    summed_output_stem,
    write_extracted_text,
)
from .models import CourseReferenceProfile, SummaryRequest, SummedNote
from .references import ReferenceLibrary
from .renderer import render_html, render_markdown


Progress = Callable[[str], None]
_PROFILE_LOCKS: dict[str, threading.Lock] = {}
_PROFILE_LOCKS_GUARD = threading.Lock()


def _profile_lock(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _PROFILE_LOCKS_GUARD:
        return _PROFILE_LOCKS.setdefault(key, threading.Lock())


class SummedService:
    def __init__(self, library: ReferenceLibrary, runner: CodexRunner, output_root: Path) -> None:
        self.library = library
        self.runner = runner
        self.output_root = output_root

    @staticmethod
    def _write_json(path: Path, value) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(value.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(path)

    def _reference_profile(
        self, course: str, model: str, workdir: Path, progress: Progress
    ) -> CourseReferenceProfile:
        records = self.library.relevant(course)
        if not records:
            progress("등록된 관련 참고자료가 없어 현재 수업 자료만으로 정리합니다.")
            return CourseReferenceProfile(
                course=course,
                current_professors=[],
                key_topics=[],
                exam_patterns=[],
                study_advice=[],
                professor_rules=[],
                timetable_context=[],
                uncertainties=["등록된 족보·학습가이드·시간표가 없습니다."],
            )

        fingerprint = self.library.fingerprint(course, model)
        cache_path = self.library.profile_path(course, fingerprint)
        if cache_path.is_file():
            try:
                profile = CourseReferenceProfile.model_validate_json(cache_path.read_text(encoding="utf-8"))
                progress("과목 참고자료 분석 캐시를 사용합니다.")
                return profile
            except (OSError, ValueError):
                pass

        progress("과목 참고자료 분석 캐시와 실행 순서를 확인합니다.")
        with _profile_lock(cache_path):
            if cache_path.is_file():
                try:
                    profile = CourseReferenceProfile.model_validate_json(
                        cache_path.read_text(encoding="utf-8")
                    )
                    progress("다른 작업이 완성한 과목 참고자료 분석 캐시를 사용합니다.")
                    return profile
                except (OSError, ValueError):
                    pass

            profile_work = workdir / "profile"
            reference_folder = profile_work / "references"
            reference_folder.mkdir(parents=True, exist_ok=True)
            manifest_lines = []
            for number, record in enumerate(records, 1):
                filename = f"{number:02d}-{safe_filename(record.kind.value)}-{safe_filename(record.original_name)}.txt"
                destination = reference_folder / filename
                shutil.copy2(record.text_path, destination)
                manifest_lines.append(
                    f"- {filename}: {record.kind.value}, 대상={record.course}, 원본={record.original_name}"
                )

            progress(f"{course} 참고자료 {len(records)}개에서 출제 경향을 분석합니다.")
            profile = self.runner.build_reference_profile(
                course,
                "\n".join(manifest_lines),
                profile_work,
                lambda message: progress(f"참고자료 분석: {message}"),
            )
            self._write_json(cache_path, profile)
            return profile

    def create(
        self,
        request: SummaryRequest,
        job_root: Path,
        model: str = "",
        progress: Progress = lambda _: None,
    ) -> tuple[SummedNote, Path, Path, float]:
        generation = job_root / "generation"
        current = generation / "current"
        current.mkdir(parents=True, exist_ok=True)

        summary_source = preferred_summary_text_source(request.summary_path)
        if summary_source != request.summary_path:
            progress("요약본과 함께 저장된 텍스트판을 사용해 PDF 추출 시간을 줄입니다.")
        else:
            progress("요약본에서 텍스트를 추출합니다. PDF 이미지는 읽지 않습니다.")
        summary_text_path = current / f"요약본-{safe_filename(request.summary_path.stem)}.txt"
        write_extracted_text(summary_source, summary_text_path)
        summary_text = summary_text_path.read_text(encoding="utf-8")

        transcript_names: list[str] = []
        progress(f"전사본 {len(request.transcript_paths)}개에서 텍스트를 추출합니다.")
        for number, source in enumerate(request.transcript_paths, 1):
            name = f"전사본-{number:02d}-{safe_filename(source.stem)}.txt"
            write_extracted_text(source, current / name)
            transcript_names.append(name)

        profile = self._reference_profile(request.course, model, generation, progress)
        self._write_json(generation / "reference-profile.json", profile)

        source_length = meaningful_length(summary_text)
        target_min = max(100, round(source_length * 0.20))
        target_max = max(target_min + 50, round(source_length * 0.30))
        progress(f"요약본의 약 20~30% 분량({target_min:,}~{target_max:,}자)을 목표로 정리합니다.")
        note = self.runner.create_note(
            course=request.course,
            professor=request.professor,
            topic=request.topic,
            lecture_date=request.lecture_date.isoformat(),
            target_min=target_min,
            target_max=target_max,
            summary_filename=summary_text_path.name,
            transcript_filenames=transcript_names,
            workdir=generation,
            progress=lambda message: progress(f"정리본 생성: {message}"),
        )

        progress("정리 결과를 검증하고 MD·HTML 파일로 변환합니다.")
        basename = summed_output_stem(request.summary_path.name)
        output_folder = self.output_root / safe_filename(request.course)
        markdown_path = output_folder / MARKDOWN_FOLDER_NAME / f"{basename}.md"
        html_path = output_folder / f"{basename}.html"
        source_names = [request.summary_path.name, *(item.name for item in request.transcript_paths)]
        render_markdown(note, request, source_names, markdown_path)
        render_html(note, request, source_names, html_path)
        rendered_length = meaningful_length(markdown_path.read_text(encoding="utf-8"))
        ratio = rendered_length / source_length if source_length else 0.0
        progress(f"MD와 HTML을 만들었습니다. 요약본 대비 약 {ratio:.0%} 분량입니다.")
        return note, markdown_path, html_path, ratio
