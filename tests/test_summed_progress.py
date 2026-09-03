from datetime import datetime, timedelta
from pathlib import Path

from summed.models import JobEvent, JobRecord
from summed.web import _format_duration, _job_timing


def test_duration_format_is_compact_and_readable():
    assert _format_duration(None) == "—"
    assert _format_duration(9.9) == "9초"
    assert _format_duration(125) == "2분 05초"
    assert _format_duration(3_725) == "1:02:05"


def test_job_timing_separates_queue_run_and_current_activity():
    created = datetime(2026, 9, 3, 10, 0, 0)
    started = created + timedelta(seconds=7)
    activity = started + timedelta(seconds=20)
    record = JobRecord(
        job_id="timed-job",
        label="병리학 · 세포손상",
        status="생성 중",
        messages=["Codex 사용량으로 분석 중"],
        markdown_path=Path(),
        html_path=Path(),
        created_at=created,
        started_at=started,
        status_changed_at=started,
        events=[
            JobEvent(
                message="Codex 사용량으로 분석 중",
                status="생성 중",
                created_at=activity,
            )
        ],
    )

    timing = _job_timing(record, now=created + timedelta(seconds=57))

    assert timing == {"total": 57, "queued": 7, "running": 50, "current": 30}


def test_old_job_record_without_timing_events_remains_compatible():
    created = datetime(2026, 9, 3, 10, 0, 0)
    record = JobRecord.model_validate(
        {
            "job_id": "old-job",
            "label": "약리학 · 약동학",
            "status": "완료",
            "messages": ["완료했습니다."],
            "markdown_path": "",
            "html_path": "",
            "created_at": created.isoformat(),
            "finished_at": (created + timedelta(seconds=90)).isoformat(),
        }
    )

    assert record.events == []
    assert record.started_at is None
    assert _job_timing(record, now=created + timedelta(hours=1))["total"] == 90
