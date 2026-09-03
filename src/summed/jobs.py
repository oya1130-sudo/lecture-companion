from __future__ import annotations

import json
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Callable

from .drive import MountedDrivePublisher
from .models import JobEvent, JobRecord, SummaryRequest
from .service import SummedService


ServiceFactory = Callable[[], SummedService]


class JobManager:
    def __init__(
        self,
        root: Path,
        service_factory: ServiceFactory,
        publisher: MountedDrivePublisher,
        max_workers: int = 1,
    ) -> None:
        self.root = root
        self.service_factory = service_factory
        self.publisher = publisher
        self.root.mkdir(parents=True, exist_ok=True)
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="summed")
        self._lock = threading.RLock()
        self._records: dict[str, JobRecord] = {}
        self._load()

    def _record_path(self, job_id: str) -> Path:
        return self.root / job_id / "job.json"

    def _load(self) -> None:
        for path in self.root.glob("*/job.json"):
            try:
                record = JobRecord.model_validate_json(path.read_text(encoding="utf-8"))
                if record.status in {"대기", "생성 중", "Drive 저장 중"}:
                    interrupted_at = datetime.now()
                    message = "이전 실행이 종료되어 작업이 중단되었습니다. 다시 생성해 주세요."
                    record = record.model_copy(
                        update={
                            "status": "중단됨",
                            "error": message,
                            "status_changed_at": interrupted_at,
                            "finished_at": interrupted_at,
                            "messages": [*record.messages, message][-30:],
                            "events": [
                                *record.events,
                                JobEvent(
                                    message=message,
                                    status="중단됨",
                                    created_at=interrupted_at,
                                ),
                            ][-30:],
                        }
                    )
                    self._save(record)
                self._records[record.job_id] = record
            except (OSError, ValueError):
                continue

    def _save(self, record: JobRecord) -> None:
        path = self._record_path(record.job_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(
            json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        try:
            for attempt in range(6):
                try:
                    temporary.replace(path)
                    return
                except PermissionError:
                    if attempt == 5:
                        raise
                    time.sleep(0.05 * (2**attempt))
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def _change(self, job_id: str, **values) -> None:
        with self._lock:
            record = self._records[job_id].model_copy(update=values)
            self._records[job_id] = record
            self._save(record)

    def _message(self, job_id: str, message: str) -> None:
        with self._lock:
            record = self._records[job_id]
            messages = [*record.messages, message][-30:]
            events = [
                *record.events,
                JobEvent(message=message, status=record.status, created_at=datetime.now()),
            ][-30:]
            self._change(job_id, messages=messages, events=events)

    def _transition(self, job_id: str, status: str, message: str, **values) -> None:
        changed_at = values.get("finished_at") or values.get("started_at") or datetime.now()
        with self._lock:
            record = self._records[job_id]
            update = {
                **values,
                "status": status,
                "status_changed_at": changed_at,
                "messages": [*record.messages, message][-30:],
                "events": [
                    *record.events,
                    JobEvent(message=message, status=status, created_at=changed_at),
                ][-30:],
            }
            self._change(job_id, **update)

    def submit(self, request: SummaryRequest, model: str = "") -> str:
        job_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        label = f"{request.course} · {request.topic}"
        created_at = datetime.now()
        accepted_message = "작업을 접수했습니다. 실행 순서를 기다립니다."
        record = JobRecord(
            job_id=job_id,
            label=label,
            status="대기",
            messages=[accepted_message],
            markdown_path=Path(),
            html_path=Path(),
            created_at=created_at,
            status_changed_at=created_at,
            events=[
                JobEvent(message=accepted_message, status="대기", created_at=created_at)
            ],
        )
        with self._lock:
            self._records[job_id] = record
            self._save(record)
        self._executor.submit(self._run, job_id, request, model)
        return job_id

    def _run(self, job_id: str, request: SummaryRequest, model: str) -> None:
        try:
            started_at = datetime.now()
            self._transition(
                job_id,
                "생성 중",
                "자료 분석과 정리본 생성을 시작했습니다.",
                started_at=started_at,
            )
            _, markdown_path, html_path, _ = self.service_factory().create(
                request=request,
                job_root=self.root / job_id,
                model=model,
                progress=lambda message: self._message(job_id, message),
            )
            self._transition(
                job_id,
                "Drive 저장 중",
                "완성된 MD와 HTML을 Google Drive에 저장합니다.",
                markdown_path=markdown_path,
                html_path=html_path,
            )
            published = self.publisher.publish([markdown_path, html_path], request.course)
            finished_at = datetime.now()
            self._transition(
                job_id,
                "완료",
                "Gmail Google Drive의 summed 폴더에 저장했습니다.",
                drive_markdown_path=published[0],
                drive_html_path=published[1],
                finished_at=finished_at,
            )
        except Exception as exc:
            finished_at = datetime.now()
            self._transition(
                job_id,
                "실패",
                "작업이 실패했습니다. 아래 오류 내용을 확인해 주세요.",
                error=str(exc),
                finished_at=finished_at,
            )
            traceback_path = self.root / job_id / "error.log"
            traceback_path.write_text(traceback.format_exc(), encoding="utf-8")

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            record = self._records.get(job_id)
            return record.model_copy(deep=True) if record else None

    def publish_existing(self, job_id: str) -> JobRecord:
        with self._lock:
            record = self._records[job_id]
            if not (record.markdown_path.is_file() and record.html_path.is_file()):
                raise FileNotFoundError("게시할 MD 또는 HTML 결과 파일을 찾지 못했습니다.")
            course = record.html_path.parent.name
            self._transition(
                job_id,
                "Drive 저장 중",
                "기존 MD와 HTML을 Google Drive에 다시 저장합니다.",
                error="",
                finished_at=None,
            )

        try:
            published = self.publisher.publish(
                [record.markdown_path, record.html_path], course
            )
            finished_at = datetime.now()
            self._transition(
                job_id,
                "완료",
                "기존 결과를 Gmail Google Drive의 summed 폴더에 저장했습니다.",
                drive_markdown_path=published[0],
                drive_html_path=published[1],
                error="",
                finished_at=finished_at,
            )
        except Exception as exc:
            finished_at = datetime.now()
            self._transition(
                job_id,
                "실패",
                "Drive 재저장에 실패했습니다. 아래 오류 내용을 확인해 주세요.",
                error=str(exc),
                finished_at=finished_at,
            )
            raise
        return self.get(job_id)

    def all(self) -> list[JobRecord]:
        with self._lock:
            return sorted(
                (record.model_copy(deep=True) for record in self._records.values()),
                key=lambda item: item.created_at,
                reverse=True,
            )
