from datetime import datetime
from pathlib import Path

from summed.models import JobRecord
from summed.web import _summary_run_state


def _record(
    *,
    status: str,
    course: str = "병리학",
    source_summary_path: Path | None = None,
    html_path: Path = Path(),
) -> JobRecord:
    return JobRecord(
        job_id=f"job-{status}",
        label=f"{course} · 세포손상",
        status=status,
        messages=[],
        markdown_path=Path(),
        html_path=html_path,
        course=course,
        source_summary_path=source_summary_path,
        created_at=datetime(2026, 9, 9, 12, 0),
    )


def test_summary_state_distinguishes_not_started_running_and_complete(tmp_path: Path):
    summary = tmp_path / "병리학 1주차 요약본.pdf"
    output_root = tmp_path / "outputs"

    assert _summary_run_state(summary, "병리학", [], output_root) == "not_started"
    assert (
        _summary_run_state(
            summary,
            "병리학",
            [_record(status="생성 중", source_summary_path=summary)],
            output_root,
        )
        == "in_progress"
    )
    assert (
        _summary_run_state(
            summary,
            "병리학",
            [_record(status="완료", source_summary_path=summary)],
            output_root,
        )
        == "complete"
    )


def test_failed_summary_shows_whether_only_drive_save_is_needed(tmp_path: Path):
    summary = tmp_path / "병리학 1주차 요약본.pdf"
    output_root = tmp_path / "outputs"
    failed = [_record(status="실패", source_summary_path=summary)]

    assert _summary_run_state(summary, "병리학", failed, output_root) == "retry"

    html = output_root / "병리학" / "병리학 1주차 summed.html"
    html.parent.mkdir(parents=True)
    html.write_text("done", encoding="utf-8")

    assert _summary_run_state(summary, "병리학", failed, output_root) == "drive_retry"


def test_existing_job_without_source_path_matches_output_name_and_course(tmp_path: Path):
    summary = tmp_path / "병리학 1주차 요약본.pdf"
    old_output = tmp_path / "old" / "병리학" / "병리학 1주차 summed.html"
    old_record = _record(status="완료", html_path=old_output)
    other_course = _record(
        status="생성 중",
        course="약리학",
        html_path=tmp_path / "old" / "약리학" / old_output.name,
    )

    assert (
        _summary_run_state(
            summary,
            "병리학",
            [other_course, old_record],
            tmp_path / "outputs",
        )
        == "complete"
    )


def test_output_name_fallback_survives_changed_drive_mount_path(tmp_path: Path):
    summary = tmp_path / "new-mount" / "병리학 1주차 요약본.pdf"
    record = _record(
        status="완료",
        source_summary_path=Path("G:/내 드라이브/병리학/병리학 1주차 요약본.pdf"),
        html_path=tmp_path / "outputs" / "병리학" / "병리학 1주차 summed.html",
    )

    assert (
        _summary_run_state(summary, "병리학", [record], tmp_path / "outputs")
        == "complete"
    )


def test_existing_local_html_counts_as_complete_without_job_history(tmp_path: Path):
    summary = tmp_path / "병리학 1주차 요약본.pdf"
    html = tmp_path / "outputs" / "병리학" / "병리학 1주차 summed.html"
    html.parent.mkdir(parents=True)
    html.write_text("done", encoding="utf-8")

    assert _summary_run_state(summary, "병리학", [], tmp_path / "outputs") == "complete"
