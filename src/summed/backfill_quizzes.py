from __future__ import annotations

import argparse
import copy
import html
import json
import os
import re
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .codex import CodexRunner, configured_concurrency
from .drive import MountedDrivePublisher
from .files import MARKDOWN_FOLDER_NAME
from .models import QuizBackfillResult, SummedNote, SummaryRequest
from .renderer import render_html, render_markdown
from .storage import StoragePaths


@dataclass(frozen=True)
class Artifact:
    html_path: Path
    records: tuple[Path, ...]
    source_job: Path


def merge_review_quizzes(note_payload: dict, quizzes: QuizBackfillResult) -> SummedNote:
    sections = note_payload.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError("소단원이 없는 기존 정리본입니다.")
    expected = set(range(1, len(sections) + 1))
    by_number = {item.section_number: item.review_quiz for item in quizzes.sections}
    if len(by_number) != len(quizzes.sections) or set(by_number) != expected:
        raise ValueError(
            f"퀴즈 소단원 번호가 일치하지 않습니다: expected={sorted(expected)}, actual={sorted(by_number)}"
        )
    enriched = copy.deepcopy(note_payload)
    for number, section in enumerate(enriched["sections"], 1):
        section["review_quiz"] = [item.model_dump() for item in by_number[number]]
    return SummedNote.model_validate(enriched)


def _has_complete_quizzes(note_payload: dict) -> bool:
    sections = note_payload.get("sections", [])
    return bool(sections) and all(section.get("review_quiz") for section in sections)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _storage_paths() -> StoragePaths:
    if os.environ.get("SUMMED_HOME", "").strip():
        return StoragePaths.discover().ensure()
    project_home = Path(__file__).resolve().parents[2] / ".summed-data"
    if project_home.is_dir():
        return StoragePaths(
            root=project_home,
            references=project_home / "references",
            jobs=project_home / "jobs",
            outputs=project_home / "outputs",
            oauth=project_home / "oauth",
        ).ensure()
    return StoragePaths.discover().ensure()


def _metadata(markdown: str, key: str) -> str:
    match = re.search(rf"^- {re.escape(key)}:\s*(.+?)\s*$", markdown, flags=re.MULTILINE)
    if not match:
        raise ValueError(f"기존 Markdown에서 {key} 정보를 찾지 못했습니다.")
    return match.group(1)


def _source_names(document: str) -> list[str]:
    block = re.search(
        r'<details class="sources">.*?<ul>(.*?)</ul>.*?</details>',
        document,
        flags=re.DOTALL,
    )
    if not block:
        return []
    return [
        html.unescape(re.sub(r"<[^>]+>", "", value)).strip()
        for value in re.findall(r"<li>(.*?)</li>", block.group(1), flags=re.DOTALL)
    ]


def _request_and_sources(artifact: Artifact, markdown_path: Path) -> tuple[SummaryRequest, list[str]]:
    markdown = markdown_path.read_text(encoding="utf-8")
    html_document = artifact.html_path.read_text(encoding="utf-8")
    sources = _source_names(html_document)
    if not sources:
        sources = [markdown_path.name]
    request = SummaryRequest(
        course=artifact.html_path.parent.name,
        professor=_metadata(markdown, "교수"),
        topic=_metadata(markdown, "주제"),
        lecture_date=date.fromisoformat(_metadata(markdown, "강의일")),
        summary_path=Path(sources[0]),
        transcript_paths=[Path(value) for value in sources[1:]],
    )
    return request, sources


def discover_artifacts(paths: StoragePaths) -> list[Artifact]:
    grouped: dict[str, list[tuple[Path, dict]]] = {}
    for record_path in paths.jobs.glob("*/job.json"):
        try:
            record = _read_json(record_path)
            html_path = Path(record.get("html_path", ""))
        except (OSError, ValueError, TypeError):
            continue
        result_path = record_path.parent / "generation" / "result.json"
        if record.get("status") != "완료" or not html_path.is_file() or not result_path.is_file():
            continue
        grouped.setdefault(str(html_path.resolve()), []).append((record_path, record))

    artifacts = []
    for records in grouped.values():
        source_record_path, _ = max(
            records,
            key=lambda item: item[1].get("finished_at") or item[1].get("created_at") or "",
        )
        artifacts.append(
            Artifact(
                html_path=Path(records[0][1]["html_path"]),
                records=tuple(item[0] for item in records),
                source_job=source_record_path.parent,
            )
        )
    return sorted(artifacts, key=lambda item: str(item.html_path))


def _section_inputs(note_payload: dict) -> list[dict]:
    return [
        {
            "section_number": number,
            "title": section.get("title", ""),
            "core_points": section.get("core_points", []),
            "exam_focus": section.get("exam_focus", []),
            "transcript_additions": section.get("transcript_additions", []),
        }
        for number, section in enumerate(note_payload["sections"], 1)
    ]


def _existing_markdown(artifact: Artifact) -> Path:
    for record_path in artifact.records:
        path = Path(_read_json(record_path).get("markdown_path", ""))
        if path.is_file():
            return path
    nested = artifact.html_path.parent / MARKDOWN_FOLDER_NAME / f"{artifact.html_path.stem}.md"
    if nested.is_file():
        return nested
    raise FileNotFoundError(f"기존 Markdown을 찾지 못했습니다: {artifact.html_path.name}")


def _backup(artifact: Artifact, markdown_path: Path, backup_root: Path) -> None:
    target = backup_root / artifact.html_path.parent.name / artifact.html_path.stem
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(artifact.html_path, target / artifact.html_path.name)
    shutil.copy2(markdown_path, target / markdown_path.name)
    for record_path in artifact.records:
        record_target = target / record_path.parent.name
        record_target.mkdir(exist_ok=True)
        shutil.copy2(record_path, record_target / "job.json")
        result_path = record_path.parent / "generation" / "result.json"
        if result_path.is_file():
            shutil.copy2(result_path, record_target / "result.json")


def _update_records(artifact: Artifact, markdown_path: Path, published: list[Path]) -> None:
    for record_path in artifact.records:
        record = _read_json(record_path)
        record["markdown_path"] = str(markdown_path)
        record["html_path"] = str(artifact.html_path)
        record["drive_markdown_path"] = str(published[0])
        record["drive_html_path"] = str(published[1])
        messages = record.setdefault("messages", [])
        message = "기존 정리본의 모든 소단원에 복습 퀴즈를 추가했습니다."
        if message not in messages:
            messages.append(message)
        _write_json_atomic(record_path, record)


def backfill_artifact(
    artifact: Artifact,
    runner: CodexRunner,
    publisher: MountedDrivePublisher,
    backup_root: Path,
    report,
) -> tuple[str, int, bool]:
    result_path = artifact.source_job / "generation" / "result.json"
    note_payload = _read_json(result_path)
    markdown_source = _existing_markdown(artifact)
    _backup(artifact, markdown_source, backup_root)

    reused = _has_complete_quizzes(note_payload)
    if reused:
        note = SummedNote.model_validate(note_payload)
    else:
        report(f"{artifact.html_path.name}: 퀴즈 생성 중")
        quizzes = runner.create_review_quizzes(
            course=artifact.html_path.parent.name,
            title=str(note_payload.get("title", artifact.html_path.stem)),
            sections=_section_inputs(note_payload),
            workdir=artifact.source_job / "generation" / "quiz-backfill",
            progress=lambda message: report(f"{artifact.html_path.name}: {message}"),
        )
        note = merge_review_quizzes(note_payload, quizzes)

    request, sources = _request_and_sources(artifact, markdown_source)
    markdown_target = artifact.html_path.parent / MARKDOWN_FOLDER_NAME / f"{artifact.html_path.stem}.md"
    markdown_target.parent.mkdir(parents=True, exist_ok=True)
    markdown_temp = markdown_target.with_suffix(".quiz.tmp.md")
    html_temp = artifact.html_path.with_suffix(".quiz.tmp.html")
    render_markdown(note, request, sources, markdown_temp)
    render_html(note, request, sources, html_temp)

    markdown_temp.replace(markdown_target)
    html_temp.replace(artifact.html_path)
    _write_json_atomic(result_path, note.model_dump(mode="json"))
    published = publisher.publish([markdown_target, artifact.html_path], request.course)
    _update_records(artifact, markdown_target, published)
    if markdown_source != markdown_target and markdown_source.is_file():
        markdown_source.unlink()
    report(f"{artifact.html_path.name}: 완료")
    return artifact.html_path.name, len(note.sections), reused


def run_backfill(max_workers: int | None = None) -> int:
    paths = _storage_paths()
    artifacts = discover_artifacts(paths)
    if not artifacts:
        print("보강할 완성본이 없습니다.", flush=True)
        return 0
    active = []
    for record_path in paths.jobs.glob("*/job.json"):
        record = _read_json(record_path)
        if record.get("status") in {"대기", "생성 중", "Drive 저장 중"}:
            active.append(record_path.parent.name)
    if active:
        raise RuntimeError(f"진행 중인 작업이 있어 보강을 시작하지 않습니다: {', '.join(active)}")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = paths.root / "backups" / f"quiz-backfill-{stamp}"
    backup_root.mkdir(parents=True, exist_ok=False)
    runner = CodexRunner(model=os.environ.get("SUMMED_CODEX_MODEL", ""))
    publisher = MountedDrivePublisher()
    workers = max(1, min(max_workers or configured_concurrency(), 4))
    print(f"대상 {len(artifacts)}개, 동시 작업 {workers}개, 백업 {backup_root}", flush=True)
    lock = threading.Lock()

    def report(message: str) -> None:
        with lock:
            print(message, flush=True)

    failures = []
    completed = 0
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="quiz-backfill") as executor:
        futures = {
            executor.submit(backfill_artifact, artifact, runner, publisher, backup_root, report): artifact
            for artifact in artifacts
        }
        for future in as_completed(futures):
            try:
                future.result()
                completed += 1
                report(f"진행률: {completed}/{len(artifacts)}")
            except Exception as exc:
                failures.append((futures[future].html_path.name, str(exc)))
                report(f"실패: {futures[future].html_path.name}: {exc}")

    if failures:
        failure_path = backup_root / "failures.json"
        _write_json_atomic(
            failure_path,
            {"completed": completed, "failures": [{"file": name, "error": error} for name, error in failures]},
        )
        print(f"{completed}개 완료, {len(failures)}개 실패: {failure_path}", flush=True)
        return 1
    print(f"완료: {completed}개 정리본에 복습 퀴즈를 추가했습니다.", flush=True)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="기존 summed 정리본에 소단원 복습 퀴즈를 추가합니다.")
    parser.add_argument("--workers", type=int, default=None, help="동시 처리 수(기본: summed 설정값)")
    args = parser.parse_args()
    raise SystemExit(run_backfill(args.workers))


if __name__ == "__main__":
    main()
