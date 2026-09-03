from datetime import datetime
from pathlib import Path

import pytest

from summed.drive_sources import (
    DriveFile,
    DriveSourceRoots,
    infer_professor,
    infer_topic,
    list_course_sources,
    suggest_transcripts,
    transcript_upload_date,
    validate_drive_selection,
)
from summed import drive_sources


def _file(path: Path, text: str = "자료") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_course_folders_accept_numbered_transcript_folder_and_hide_raw_md_duplicate(tmp_path: Path):
    summary_root = tmp_path / "00 학습자료"
    transcript_root = tmp_path / "녹음부"
    pdf = _file(summary_root / "병리학" / "병리학 1주차(3) Inflammation 요약본.pdf")
    _file(summary_root / "병리학" / "병리학 1주차(3) Inflammation.summary.raw.md")
    transcript = _file(transcript_root / "1. 병리학" / "병리학_1주차(3-1)_이소민_inflammation(1).txt")

    summaries, transcripts = list_course_sources(
        DriveSourceRoots(summary_root, transcript_root), "병리학"
    )

    assert [item.path for item in summaries] == [pdf.resolve()]
    assert [item.path for item in transcripts] == [transcript.resolve()]


def test_transcript_suggestion_keeps_split_files_for_same_lecture(tmp_path: Path):
    summary = DriveFile(
        tmp_path / "병리학 1주차(3) Inflammation and repair 요약본.pdf",
        "병리학 1주차(3) Inflammation and repair 요약본.pdf",
        3,
    )
    related = [
        DriveFile(
            tmp_path / f"병리학_1주차(3-{part})_이소민_inflammation and repair({part}).txt",
            f"병리학_1주차(3-{part})_이소민_inflammation and repair({part}).txt",
            part,
        )
        for part in (1, 2)
    ]
    unrelated = DriveFile(
        tmp_path / "병리학_2주차(5-1)_김용준_Genetic disorders.txt",
        "병리학_2주차(5-1)_김용준_Genetic disorders.txt",
        4,
    )

    suggested = suggest_transcripts(summary, [unrelated, *related], "병리학")

    assert {item.label for item in suggested} == {item.label for item in related}
    assert infer_professor(related[0].label, "병리학") == "이소민"
    assert infer_topic(summary.label, "병리학") == "Inflammation and repair"


def test_drive_selection_rejects_paths_outside_expected_root(tmp_path: Path):
    root = tmp_path / "drive"
    inside = _file(root / "과목" / "요약.pdf")
    outside = _file(tmp_path / "outside.pdf")

    assert validate_drive_selection([inside], root) == [inside.resolve()]
    with pytest.raises(ValueError, match="Drive 폴더 밖"):
        validate_drive_selection([outside], root)


def test_discovery_chooses_latest_year_transcript_folder(tmp_path: Path, monkeypatch):
    shortcut_root = tmp_path / ".shortcut-targets-by-id"
    summaries = shortcut_root / "summary-id" / "00 학습자료"
    old = shortcut_root / "record-id" / "의학과" / "2022년" / "녹음부"
    latest = shortcut_root / "record-id" / "의학과" / "2026년" / "녹음부"
    summaries.mkdir(parents=True)
    old.mkdir(parents=True)
    latest.mkdir(parents=True)
    monkeypatch.delenv("SUMMED_SUMMARY_ROOT", raising=False)
    monkeypatch.delenv("SUMMED_TRANSCRIPT_ROOT", raising=False)
    monkeypatch.setattr(drive_sources, "_mounted_shortcut_roots", lambda: [shortcut_root])

    roots = drive_sources.discover_source_roots()

    assert roots is not None
    assert roots.transcripts == latest.resolve()


def test_discovery_retries_while_drive_shortcuts_wake_up(tmp_path: Path, monkeypatch):
    expected = DriveSourceRoots(tmp_path / "00 학습자료", tmp_path / "녹음부")
    calls = iter([None, expected])
    monkeypatch.setattr(drive_sources, "_discover_source_roots_once", lambda: next(calls))

    assert drive_sources.discover_source_roots(attempts=2, retry_delay=0) == expected


def test_discovery_reuses_last_known_roots_after_transient_scan_failure(tmp_path: Path, monkeypatch):
    expected = DriveSourceRoots(tmp_path / "00 학습자료", tmp_path / "녹음부")
    expected.summaries.mkdir()
    expected.transcripts.mkdir()
    monkeypatch.setattr(drive_sources, "_LAST_KNOWN_ROOTS", expected)
    monkeypatch.setattr(drive_sources, "_discover_source_roots_once", lambda: None)

    assert drive_sources.discover_source_roots(attempts=1, retry_delay=0) == expected


def test_lecture_date_uses_latest_selected_transcript_upload_timestamp(tmp_path: Path):
    first = DriveFile(
        tmp_path / "1.txt", "1.txt", modified_at=999,
        uploaded_at=datetime(2026, 8, 30, 10).timestamp(),
    )
    second = DriveFile(
        tmp_path / "2.txt", "2.txt", modified_at=1,
        uploaded_at=datetime(2026, 8, 31, 10).timestamp(),
    )

    assert transcript_upload_date([first, second]).isoformat() == "2026-08-31"
