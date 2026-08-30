from __future__ import annotations

import os
import shutil
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .ai import CodexStudyEngine
from .models import LectureRequest, SourceDocument
from .service import StudyGuideService
from .storage import COURSE_DRIVE_FOLDERS, DRIVE_OUTPUT_ROOT


@dataclass
class JobSnapshot:
    job_id: str
    label: str
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
    created_at: datetime = field(default_factory=datetime.now)
    finished_at: datetime | None = None
    status: str = "queued"
    messages: list[str] = field(default_factory=list)
    drive_path: Path | None = None
    drive_error: str = ""
    error: str = ""
    lock: threading.RLock = field(default_factory=threading.RLock)

    def log(self, message: str) -> None:
        with self.lock:
            self.messages.append(message)
            self.messages = self.messages[-30:]

    def snapshot(self) -> JobSnapshot:
        with self.lock:
            return JobSnapshot(
                job_id=self.job_id,
                label=self.label,
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
    ) -> None:
        workers = max(1, max_workers or int(os.environ.get("PRESTUDY_JOB_WORKERS", "3")))
        self.executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="lecture-job")
        self.jobs: dict[str, _Job] = {}
        self.lock = threading.RLock()
        self.drive_lock = threading.RLock()
        self.max_workers = workers
        self.drive_output_root = Path(drive_output_root) if drive_output_root is not None else None

    def new_id(self) -> str:
        return uuid.uuid4().hex[:12]

    def submit(
        self,
        job_id: str,
        lecture: LectureRequest,
        sources: list[SourceDocument],
        output_path: Path,
        model: str = "",
    ) -> JobSnapshot:
        job = _Job(job_id=job_id, label=f"{lecture.course} · {lecture.topic}", output_path=output_path)
        with self.lock:
            self.jobs[job_id] = job
        self.executor.submit(self._run, job, lecture, sources, model)
        return job.snapshot()

    def _run(
        self,
        job: _Job,
        lecture: LectureRequest,
        sources: list[SourceDocument],
        model: str,
    ) -> None:
        with job.lock:
            job.status = "running"
        job.log("작업 시작")
        try:
            engine = CodexStudyEngine(model=model)
            service = StudyGuideService(engine)
            service.create(lecture, sources, job.output_path, job.log)
            self._save_to_drive(job, lecture.course)
            with job.lock:
                job.status = "complete"
                job.finished_at = datetime.now()
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
