from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from .ai import CodexStudyEngine
from .models import LectureRequest, SourceDocument
from .service import StudyGuideService
from .storage import COURSE_DRIVE_FOLDERS, DRIVE_OUTPUT_ROOT


_STATE_LOCKS_GUARD = threading.Lock()
_STATE_LOCKS: dict[str, threading.RLock] = {}


def _shared_state_lock(path: Path | None) -> threading.RLock:
    if path is None:
        return threading.RLock()
    key = str(path.resolve()).casefold()
    with _STATE_LOCKS_GUARD:
        return _STATE_LOCKS.setdefault(key, threading.RLock())


@dataclass(frozen=True)
class JobSource:
    kind: str
    filename: str


@dataclass
class JobSnapshot:
    job_id: str
    label: str
    course: str
    professor: str
    topic: str
    lecture_date: str
    source_files: list[JobSource]
    status: str
    messages: list[str]
    output_path: Path
    drive_path: Path | None
    drive_error: str
    error: str
    created_at: datetime
    finished_at: datetime | None


@dataclass
class _Job:
    job_id: str
    label: str
    output_path: Path
    course: str = ""
    professor: str = ""
    topic: str = ""
    lecture_date: str = ""
    source_files: list[JobSource] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    finished_at: datetime | None = None
    status: str = "queued"
    messages: list[str] = field(default_factory=list)
    drive_path: Path | None = None
    drive_error: str = ""
    error: str = ""
    lock: threading.RLock = field(default_factory=threading.RLock)
    on_change: Callable[[], None] | None = field(default=None, repr=False, compare=False)

    def log(self, message: str) -> None:
        with self.lock:
            self.messages.append(message)
            self.messages = self.messages[-30:]
        if self.on_change is not None:
            self.on_change()

    def snapshot(self) -> JobSnapshot:
        with self.lock:
            return JobSnapshot(
                job_id=self.job_id,
                label=self.label,
                course=self.course,
                professor=self.professor,
                topic=self.topic,
                lecture_date=self.lecture_date,
                source_files=list(self.source_files),
                status=self.status,
                messages=list(self.messages),
                output_path=self.output_path,
                drive_path=self.drive_path,
                drive_error=self.drive_error,
                error=self.error,
                created_at=self.created_at,
                finished_at=self.finished_at,
            )


class JobManager:
    def __init__(
        self,
        max_workers: int | None = None,
        drive_output_root: Path | str | None = DRIVE_OUTPUT_ROOT,
        state_path: Path | str | None = None,
        history_output_root: Path | str | None = None,
    ) -> None:
        workers = max(1, max_workers or int(os.environ.get("PRESTUDY_JOB_WORKERS", "3")))
        self.executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="lecture-job")
        self.jobs: dict[str, _Job] = {}
        self.lock = threading.RLock()
        self.drive_lock = threading.RLock()
        self.max_workers = workers
        self.drive_output_root = Path(drive_output_root) if drive_output_root is not None else None
        self.state_path = Path(state_path) if state_path is not None else None
        self.state_lock = _shared_state_lock(self.state_path)
        self.state_error = ""
        self.history_output_root = Path(history_output_root) if history_output_root is not None else None
        self._load_state()
        self._backfill_history()

    @staticmethod
    def _serialize(snapshot: JobSnapshot) -> dict:
        return {
            "job_id": snapshot.job_id,
            "label": snapshot.label,
            "course": snapshot.course,
            "professor": snapshot.professor,
            "topic": snapshot.topic,
            "lecture_date": snapshot.lecture_date,
            "source_files": [
                {"kind": source.kind, "filename": source.filename}
                for source in snapshot.source_files
            ],
            "status": snapshot.status,
            "messages": snapshot.messages,
            "output_path": str(snapshot.output_path),
            "drive_path": str(snapshot.drive_path) if snapshot.drive_path is not None else None,
            "drive_error": snapshot.drive_error,
            "error": snapshot.error,
            "created_at": snapshot.created_at.isoformat(),
            "finished_at": snapshot.finished_at.isoformat() if snapshot.finished_at is not None else None,
        }

    def _save_state(self) -> None:
        if self.state_path is None:
            return
        with self.state_lock:
            with self.lock:
                jobs = list(self.jobs.values())
            snapshots = [job.snapshot() for job in jobs]
            serialized = [self._serialize(item) for item in snapshots]
            merged_jobs: dict[str, dict] = {}
            if self.state_path.is_file():
                try:
                    existing = json.loads(self.state_path.read_text(encoding="utf-8"))
                    merged_jobs = {
                        str(item["job_id"]): item
                        for item in existing.get("jobs", [])
                        if isinstance(item, dict) and item.get("job_id")
                    }
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    merged_jobs = {}
            merged_jobs.update({str(item["job_id"]): item for item in serialized})
            payload = json.dumps(
                {"version": 2, "jobs": list(merged_jobs.values())},
                ensure_ascii=False,
                indent=2,
            )
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.state_path.with_name(
                f".{self.state_path.name}.{uuid.uuid4().hex}.tmp"
            )
            try:
                temporary.write_text(payload, encoding="utf-8")
                last_error: OSError | None = None
                for attempt in range(8):
                    try:
                        os.replace(temporary, self.state_path)
                        self.state_error = ""
                        return
                    except PermissionError as exc:
                        last_error = exc
                        time.sleep(0.05 * (attempt + 1))
                self.state_error = (
                    "작업 이력을 잠시 저장하지 못했습니다. 생성 작업은 계속되며 "
                    f"다음 상태 변경 때 다시 시도합니다: {last_error}"
                )
            except OSError as exc:
                self.state_error = (
                    "작업 이력을 잠시 저장하지 못했습니다. 생성 작업은 계속되며 "
                    f"다음 상태 변경 때 다시 시도합니다: {exc}"
                )
            finally:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def _load_state(self) -> None:
        if self.state_path is None or not self.state_path.is_file():
            return
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            for item in data.get("jobs", []):
                status = str(item["status"])
                messages = [str(value) for value in item.get("messages", [])][-30:]
                error = str(item.get("error", ""))
                finished_at = (
                    datetime.fromisoformat(item["finished_at"])
                    if item.get("finished_at")
                    else None
                )
                if status in {"queued", "running"}:
                    status = "failed"
                    error = "서버가 재시작되어 작업이 중단되었습니다. 다시 제출해 주세요."
                    messages.append(error)
                    finished_at = datetime.now()
                source_files = [
                    JobSource(
                        kind=str(value.get("kind", "자료")),
                        filename=str(value.get("filename", "")),
                    )
                    for value in item.get("source_files", [])
                    if isinstance(value, dict) and value.get("filename")
                ]
                job = _Job(
                    job_id=str(item["job_id"]),
                    label=str(item["label"]),
                    course=str(item.get("course", "")),
                    professor=str(item.get("professor", "")),
                    topic=str(item.get("topic", "")),
                    lecture_date=str(item.get("lecture_date", "")),
                    source_files=source_files,
                    status=status,
                    messages=messages,
                    output_path=Path(item["output_path"]),
                    drive_path=Path(item["drive_path"]) if item.get("drive_path") else None,
                    drive_error=str(item.get("drive_error", "")),
                    error=error,
                    created_at=datetime.fromisoformat(item["created_at"]),
                    finished_at=finished_at,
                    on_change=self._save_state,
                )
                self.jobs[job.job_id] = job
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            # A damaged history file must not prevent the app from starting.
            self.jobs = {}
            return
        self._save_state()

    @staticmethod
    def _history_label(path: Path) -> str:
        label = path.stem
        for suffix in (" 수업동반노트", "_수업동반노트"):
            if label.endswith(suffix):
                label = label[: -len(suffix)]
                break
        return label.replace("_", " ").strip() or path.name

    @staticmethod
    def _history_course(path: Path) -> str:
        parent_names = {parent.name for parent in path.parents}
        for course, folder in COURSE_DRIVE_FOLDERS.items():
            if course in path.name or folder in parent_names:
                return course
        return ""

    @staticmethod
    def _html_files(root: Path | None, recursive: bool = False) -> list[Path]:
        if root is None or not root.is_dir():
            return []
        try:
            candidates = root.rglob("*.html") if recursive else root.glob("*.html")
            return [path for path in candidates if path.is_file()]
        except OSError:
            return []

    def _history_job(self, path: Path, drive_path: Path | None = None) -> _Job:
        modified_at = datetime.fromtimestamp(path.stat().st_mtime)
        identifier = hashlib.sha1(str(path.resolve()).casefold().encode("utf-8")).hexdigest()[:12]
        return _Job(
            job_id=f"history-{identifier}",
            label=self._history_label(path),
            course=self._history_course(path),
            topic=self._history_label(path),
            status="complete",
            messages=["기존 완성 HTML에서 불러온 작업 내역"],
            output_path=path,
            drive_path=drive_path,
            created_at=modified_at,
            finished_at=modified_at,
            on_change=self._save_state,
        )

    def _backfill_history(self) -> None:
        local_files = self._html_files(self.history_output_root)
        drive_files = self._html_files(self.drive_output_root, recursive=True)
        changed = False

        with self.lock:
            jobs_by_filename = {job.output_path.name: job for job in self.jobs.values()}
            for path in sorted(local_files, key=lambda item: item.stat().st_mtime):
                if path.name in jobs_by_filename:
                    continue
                job = self._history_job(path)
                self.jobs[job.job_id] = job
                jobs_by_filename[path.name] = job
                changed = True

            for path in sorted(drive_files, key=lambda item: item.stat().st_mtime):
                existing = jobs_by_filename.get(path.name)
                if existing is not None:
                    with existing.lock:
                        if existing.drive_path is None:
                            existing.drive_path = path
                            changed = True
                    continue
                job = self._history_job(path, drive_path=path)
                self.jobs[job.job_id] = job
                jobs_by_filename[path.name] = job
                changed = True

        if changed:
            self._save_state()

    def new_id(self) -> str:
        return uuid.uuid4().hex[:12]

    def submit(
        self,
        job_id: str,
        lecture: LectureRequest,
        sources: list[SourceDocument],
        output_path: Path,
        model: str = "",
        reasoning_effort: str = "low",
    ) -> JobSnapshot:
        job = _Job(
            job_id=job_id,
            label=f"{lecture.course} · {lecture.topic}",
            course=lecture.course,
            professor=lecture.professor,
            topic=lecture.topic,
            lecture_date=lecture.lecture_date,
            source_files=[
                JobSource(kind=source.kind.value, filename=source.path.name)
                for source in sources
            ],
            output_path=output_path,
            on_change=self._save_state,
        )
        with self.lock:
            self.jobs[job_id] = job
        self._save_state()
        self.executor.submit(
            self._run,
            job,
            lecture,
            sources,
            model,
            reasoning_effort,
        )
        return job.snapshot()

    def _run(
        self,
        job: _Job,
        lecture: LectureRequest,
        sources: list[SourceDocument],
        model: str,
        reasoning_effort: str,
    ) -> None:
        with job.lock:
            job.status = "running"
        job.log("작업 시작")
        try:
            engine = CodexStudyEngine(
                model=model,
                reasoning_effort=reasoning_effort,
            )
            service = StudyGuideService(engine)
            service.create(lecture, sources, job.output_path, job.log)
            self._save_to_drive(job, lecture.course)
            with job.lock:
                job.status = "complete"
                job.finished_at = datetime.now()
            self._save_state()
        except Exception as exc:
            with job.lock:
                job.status = "failed"
                job.error = str(exc)
                job.finished_at = datetime.now()
            job.log(f"실패: {exc}")

    def _save_to_drive(self, job: _Job, course: str) -> None:
        if self.drive_output_root is None:
            with job.lock:
                job.drive_error = "Google Drive의 ‘내 드라이브’를 찾지 못했습니다."
            job.log("Drive 자동 저장 건너뜀 — 로컬 HTML은 정상 저장됨")
            return

        try:
            folder_name = COURSE_DRIVE_FOLDERS.get(course, "99. 기타")
            target_root = self.drive_output_root / folder_name
            with self.drive_lock:
                target_root.mkdir(parents=True, exist_ok=True)
                target = target_root / job.output_path.name
                number = 2
                while target.exists():
                    target = target_root / f"{job.output_path.stem} ({number}){job.output_path.suffix}"
                    number += 1
                temporary = target_root / f"{target.name}.{uuid.uuid4().hex}.uploading"
                try:
                    shutil.copy2(job.output_path, temporary)
                    temporary.replace(target)
                finally:
                    if temporary.is_file():
                        temporary.unlink()
            if target.stat().st_size != job.output_path.stat().st_size:
                raise OSError("저장된 Drive 파일의 크기가 원본과 다릅니다.")
            with job.lock:
                job.drive_path = target
            job.log(f"Google Drive 자동 저장 완료: {target}")
        except Exception as exc:
            with job.lock:
                job.drive_error = str(exc)
            job.log(f"Drive 자동 저장 실패 — 로컬 HTML은 정상 저장됨: {exc}")

    def snapshots(self) -> list[JobSnapshot]:
        with self.lock:
            jobs = list(self.jobs.values())
        return sorted((job.snapshot() for job in jobs), key=lambda item: item.created_at, reverse=True)
