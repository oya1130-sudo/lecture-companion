from prestudy.storage import discover_drive_source_roots


def test_drive_source_roots_are_discovered_at_call_time(monkeypatch, tmp_path):
    jokchek = tmp_path / "jokchek"
    lecture = tmp_path / "lecture"
    summary = tmp_path / "summary"
    jokchek.mkdir()
    lecture.mkdir()
    summary.mkdir()
    monkeypatch.setenv("PRESTUDY_JOKCHEK_ROOT", str(jokchek))
    monkeypatch.setenv("PRESTUDY_LECTURE_ROOT", str(lecture))
    monkeypatch.setenv("PRESTUDY_SUMMARY_ROOT", str(summary))

    assert discover_drive_source_roots() == (
        jokchek.resolve(),
        lecture.resolve(),
        summary.resolve(),
    )
