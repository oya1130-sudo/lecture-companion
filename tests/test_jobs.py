from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import prestudy.jobs as jobs_module
from prestudy.jobs import JobManager
from prestudy.models import LectureRequest, SourceDocument, SourceKind


class FakeEngine:
    def __init__(self, model="") -> None:
        self.model = model


class FakeService:
    active = 0
    max_active = 0
    lock = threading.Lock()

    def __init__(self, engine) -> None:
        self.engine = engine

    def create(self, lecture, sources, output_path, progress):
        with self.lock:
            type(self).active += 1
            type(self).max_active = max(type(self).max_active, type(self).active)
        progress("테스트 생성 중")
        time.sleep(0.05)
        output_path.write_text("<html>done</html>", encoding="utf-8")
        with self.lock:
            type(self).active -= 1


def test_job_manager_runs_multiple_jobs_without_blocking(tmp_path: Path, monkeypatch):
    FakeService.active = 0
    FakeService.max_active = 0
    monkeypatch.setattr(jobs_module, "CodexStudyEngine", FakeEngine)
    monkeypatch.setattr(jobs_module, "StudyGuideService", FakeService)
    drive_root = tmp_path / "drive"
    manager = JobManager(max_workers=2, drive_output_root=drive_root)
    lecture = LectureRequest(course="약리학", professor="김자은", topic="약동학")

    manager.submit("job-a", lecture, [], tmp_path / "a.html")
    manager.submit("job-b", lecture, [], tmp_path / "b.html")

    deadline = time.monotonic() + 2
    snapshots = manager.snapshots()
    while time.monotonic() < deadline and any(item.status != "complete" for item in snapshots):
        time.sleep(0.01)
        snapshots = manager.snapshots()
    manager.executor.shutdown(wait=True)

    assert {item.status for item in snapshots} == {"complete"}
    assert FakeService.max_active == 2
    assert (tmp_path / "a.html").is_file()
    assert (tmp_path / "b.html").is_file()
    assert (drive_root / "02. 약리학" / "a.html").is_file()
    assert (drive_root / "02. 약리학" / "b.html").is_file()
    assert all(item.drive_path is not None for item in snapshots)


def test_drive_failure_keeps_local_result_complete(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(jobs_module, "CodexStudyEngine", FakeEngine)
    monkeypatch.setattr(jobs_module, "StudyGuideService", FakeService)
    blocked_drive_path = tmp_path / "not-a-folder"
    blocked_drive_path.write_text("blocked", encoding="utf-8")
    manager = JobManager(max_workers=1, drive_output_root=blocked_drive_path)
    lecture = LectureRequest(course="약리학", professor="김자은", topic="약동학")
    local_output = tmp_path / "local.html"

    manager.submit("job-local", lecture, [], local_output)

    deadline = time.monotonic() + 2
    snapshot = manager.snapshots()[0]
    while time.monotonic() < deadline and snapshot.status != "complete":
        time.sleep(0.01)
        snapshot = manager.snapshots()[0]
    manager.executor.shutdown(wait=True)

    assert snapshot.status == "complete"
    assert local_output.is_file()
    assert snapshot.drive_path is None
    assert snapshot.drive_error


def test_job_history_survives_manager_restart(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(jobs_module, "CodexStudyEngine", FakeEngine)
    monkeypatch.setattr(jobs_module, "StudyGuideService", FakeService)
    state_path = tmp_path / "jobs.json"
    manager = JobManager(max_workers=1, drive_output_root=None, state_path=state_path)
    lecture = LectureRequest(course="약리학", professor="김자은", topic="약동학")
    output_path = tmp_path / "persisted.html"
    source_path = tmp_path / "족첵.pdf"
    source_path.write_bytes(b"%PDF-test")
    sources = [SourceDocument(path=source_path, kind=SourceKind.JOKCHEK)]

    manager.submit("job-persisted", lecture, sources, output_path)
    deadline = time.monotonic() + 2
    snapshot = manager.snapshots()[0]
    while time.monotonic() < deadline and snapshot.status != "complete":
        time.sleep(0.01)
        snapshot = manager.snapshots()[0]
    manager.executor.shutdown(wait=True)

    restored = JobManager(max_workers=1, drive_output_root=None, state_path=state_path)
    restored_snapshot = restored.snapshots()[0]
    restored.executor.shutdown(wait=True)

    assert restored_snapshot.status == "complete"
    assert restored_snapshot.output_path == output_path
    assert restored_snapshot.professor == "김자은"
    assert restored_snapshot.source_files[0].filename == "족첵.pdf"
    assert state_path.is_file()


def test_existing_output_and_drive_files_are_added_to_history(tmp_path: Path):
    output_root = tmp_path / "output"
    drive_root = tmp_path / "drive"
    drive_course_root = drive_root / "02. 약리학"
    output_root.mkdir()
    drive_course_root.mkdir(parents=True)
    filename = "0831 약리학 김자은 약동학 수업동반노트.html"
    local_output = output_root / filename
    drive_output = drive_course_root / filename
    drive_only = drive_course_root / "0830 약리학 김자은 약물대사 수업동반노트.html"
    local_output.write_text("<html>local</html>", encoding="utf-8")
    drive_output.write_text("<html>drive</html>", encoding="utf-8")
    drive_only.write_text("<html>drive only</html>", encoding="utf-8")

    manager = JobManager(
        max_workers=1,
        drive_output_root=drive_root,
        state_path=tmp_path / "jobs.json",
        history_output_root=output_root,
    )
    snapshots = manager.snapshots()
    manager.executor.shutdown(wait=True)

    assert len(snapshots) == 2
    local_snapshot = next(item for item in snapshots if item.output_path == local_output)
    drive_snapshot = next(item for item in snapshots if item.output_path == drive_only)
    assert local_snapshot.status == "complete"
    assert local_snapshot.course == "약리학"
    assert local_snapshot.drive_path == drive_output
    assert drive_snapshot.drive_path == drive_only


def test_running_job_is_marked_failed_after_restart(tmp_path: Path):
    state_path = tmp_path / "jobs.json"
    state_path.write_text(
        json.dumps(
            {
                "version": 1,
                "jobs": [
                    {
                        "job_id": "interrupted",
                        "label": "약리학 · 약동학",
                        "status": "running",
                        "messages": ["작업 시작"],
                        "output_path": str(tmp_path / "interrupted.html"),
                        "drive_path": None,
                        "drive_error": "",
                        "error": "",
                        "created_at": "2026-08-30T10:00:00",
                        "finished_at": None,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    manager = JobManager(max_workers=1, drive_output_root=None, state_path=state_path)
    snapshot = manager.snapshots()[0]
    manager.executor.shutdown(wait=True)

    assert snapshot.status == "failed"
    assert "서버가 재시작" in snapshot.error
