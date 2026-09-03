import time
from datetime import date
from pathlib import Path
from threading import Barrier

from summed.codex import configured_concurrency
from summed.drive import MountedDrivePublisher
from summed.jobs import JobManager
from summed.models import SummaryRequest


def test_concurrency_setting_defaults_and_clamps(monkeypatch):
    monkeypatch.delenv("SUMMED_CONCURRENCY", raising=False)
    monkeypatch.delenv("SUMMED_CODEX_CONCURRENCY", raising=False)
    assert configured_concurrency() == 3
    monkeypatch.setenv("SUMMED_CONCURRENCY", "99")
    assert configured_concurrency() == 4
    monkeypatch.setenv("SUMMED_CONCURRENCY", "broken")
    assert configured_concurrency() == 3


def test_job_manager_runs_multiple_jobs_at_the_same_time(tmp_path: Path):
    barrier = Barrier(2, timeout=3)

    class ConcurrentService:
        def create(self, request, job_root, model, progress):
            progress("동시 실행 지점 도착")
            barrier.wait()
            output = job_root / "output"
            output.mkdir(parents=True, exist_ok=True)
            markdown = output / f"{request.topic}.md"
            html = output / f"{request.topic}.html"
            markdown.write_text(request.topic, encoding="utf-8")
            html.write_text(request.topic, encoding="utf-8")
            return None, markdown, html, 0.25

    manager = JobManager(
        tmp_path / "jobs",
        lambda: ConcurrentService(),
        MountedDrivePublisher(tmp_path / "drive"),
        max_workers=2,
    )
    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")

    ids = []
    for topic in ("첫째", "둘째"):
        ids.append(
            manager.submit(
                SummaryRequest(
                    course="약리학",
                    professor="김교수",
                    topic=topic,
                    lecture_date=date(2026, 9, 2),
                    summary_path=source,
                    transcript_paths=[source],
                )
            )
        )

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if all(manager.get(job_id).status == "완료" for job_id in ids):
            break
        time.sleep(0.05)

    assert [manager.get(job_id).status for job_id in ids] == ["완료", "완료"]
    for job_id in ids:
        record = manager.get(job_id)
        assert record.started_at is not None
        assert record.finished_at is not None
        assert record.status_changed_at == record.events[-1].created_at
        assert [event.status for event in record.events][0:2] == ["대기", "생성 중"]
        assert record.events[-1].status == "완료"
        assert record.events[-1].message.endswith("저장했습니다.")


def test_job_state_write_retries_temporary_windows_lock(tmp_path: Path, monkeypatch):
    class InstantService:
        def create(self, request, job_root, model, progress):
            output = job_root / "output"
            output.mkdir(parents=True, exist_ok=True)
            markdown = output / "note.md"
            html = output / "note.html"
            markdown.write_text("done", encoding="utf-8")
            html.write_text("done", encoding="utf-8")
            return None, markdown, html, 0.25

    manager = JobManager(
        tmp_path / "jobs",
        lambda: InstantService(),
        MountedDrivePublisher(tmp_path / "drive"),
        max_workers=1,
    )
    original_replace = Path.replace
    attempts = 0

    def flaky_replace(self, target):
        nonlocal attempts
        if Path(target).name == "job.json" and attempts < 2:
            attempts += 1
            raise PermissionError("temporarily locked")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", flaky_replace)
    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")
    job_id = manager.submit(
        SummaryRequest(
            course="병리학",
            professor="김교수",
            topic="잠금 재시도",
            lecture_date=date(2026, 9, 2),
            summary_path=source,
            transcript_paths=[source],
        )
    )

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and manager.get(job_id).status != "완료":
        time.sleep(0.05)

    assert manager.get(job_id).status == "완료"
    assert attempts == 2


def test_failed_job_with_outputs_can_be_republished(tmp_path: Path):
    manager = JobManager(
        tmp_path / "jobs",
        lambda: None,
        MountedDrivePublisher(tmp_path / "drive"),
        max_workers=1,
    )
    course_output = tmp_path / "outputs" / "미생물학"
    course_output.mkdir(parents=True)
    markdown = course_output / "md" / "lecture summed.md"
    html = course_output / "lecture summed.html"
    markdown.parent.mkdir()
    markdown.write_text("note", encoding="utf-8")
    html.write_text("<p>note</p>", encoding="utf-8")

    from datetime import datetime
    from summed.models import JobRecord

    record = JobRecord(
        job_id="recover-me",
        label="미생물학 · 강의",
        status="실패",
        messages=[],
        markdown_path=markdown,
        html_path=html,
        error="temporary lock",
        created_at=datetime.now(),
    )
    manager._records[record.job_id] = record
    manager._save(record)

    recovered = manager.publish_existing(record.job_id)

    assert recovered.status == "완료"
    assert recovered.error == ""
    assert recovered.drive_markdown_path.read_text(encoding="utf-8") == "note"
    assert recovered.drive_markdown_path.parent.name == "md"
    assert recovered.drive_html_path.parent.name == "미생물학"
