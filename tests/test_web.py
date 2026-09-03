import inspect
from datetime import date, datetime
from pathlib import Path

import pytest
from prestudy import web


class FakeUpload:
    def __init__(self, name: str, payload: bytes) -> None:
        self.name = name
        self.payload = payload

    def getvalue(self) -> bytes:
        return self.payload


def test_running_job_does_not_use_invalid_indeterminate_progress_value():
    source = inspect.getsource(web._render_job_queue)

    assert "st.progress(None" not in source
    assert '@st.fragment(run_every="2s")' in source
    assert "이전 작업 내역" in source


def test_job_card_uses_status_and_deferred_download():
    source = inspect.getsource(web._render_job_card)
    progress_source = inspect.getsource(web._render_active_progress)

    assert "_render_active_progress(snapshot)" in source
    assert "st.status(" in progress_source
    assert "data=lambda" in source
    assert "사용한 자료" in source


def test_active_progress_uses_only_measurable_progress_bars():
    source = inspect.getsource(web._render_active_progress)

    assert "PDF 분석 {completed}/{snapshot.source_total}개 완료" in source
    assert "시간 제한 사용" in source
    assert "예상 완료율이 아니라" in source
    assert "단계 경과" in source
    assert "전체 경과" in source


def test_drive_sources_are_refreshed_dynamically():
    source = inspect.getsource(web.run)

    assert "drive_root_values = _drive_source_roots()" in source
    assert "Google Drive 다시 찾기" in source
    assert "JOKCHEK_DRIVE_ROOT" not in source


def test_upload_callback_keeps_first_selected_file(monkeypatch):
    upload = FakeUpload("summary.pdf", b"%PDF-summary")
    state = {"summary-0": [upload]}
    monkeypatch.setattr(web.st, "session_state", state)

    web._remember_uploads("summary-0", "pending-summary-0")

    assert state["pending-summary-0"] == [upload]


def test_elapsed_label_includes_live_seconds():
    started_at = datetime(2026, 9, 2, 9, 0, 0)

    assert web._elapsed_label(started_at, datetime(2026, 9, 2, 9, 0, 7)) == "7초"
    assert web._elapsed_label(started_at, datetime(2026, 9, 2, 9, 2, 13)) == "2분 13초"


def test_output_filename_uses_mmdd_and_readable_spaces():
    filename = web._output_filename(
        date(2026, 8, 31),
        "예방의학",
        "오창모",
        "질병 및 사망, 건강수준의 측정",
    )

    assert filename == "0831 예방의학 오창모 질병 및 사망, 건강수준의 측정 수업동반노트.html"


def test_web_uses_jokchek_metadata_without_manual_professor_or_topic_fields():
    source = inspect.getsource(web.run)

    assert 'text_input("교수"' not in source
    assert 'text_input("강의 주제"' not in source
    assert "infer_jokchek_metadata" in source
    assert "선배 써머리와 학습가이드의 교수명·제목은 자동 인식에 사용하지 않습니다." in source
    assert "SourceKind.LECTURE" in source
    assert "페이지 기준 · 선택한 강의자료" in source


def test_drive_pdf_options_only_scan_selected_course(tmp_path: Path):
    pharmacology = tmp_path / "2. 약리학" / "week1"
    pathology = tmp_path / "1. 병리학"
    pharmacology.mkdir(parents=True)
    pathology.mkdir()
    selected = pharmacology / "약동학.pdf"
    selected.write_bytes(b"%PDF-test")
    (pathology / "세포손상.pdf").write_bytes(b"%PDF-test")
    (pharmacology / "메모.txt").write_text("not pdf", encoding="utf-8")

    options = web._drive_pdf_options(str(tmp_path), "약리학")

    assert options == [str(selected)]


def test_drive_selection_cannot_escape_configured_root(tmp_path: Path):
    root = tmp_path / "drive"
    root.mkdir()
    inside = root / "lecture.pdf"
    outside = tmp_path / "outside.pdf"
    inside.write_bytes(b"%PDF-inside")
    outside.write_bytes(b"%PDF-outside")

    assert web._validated_drive_paths([str(inside)], root) == [inside.resolve()]
    with pytest.raises(ValueError, match="허용된 Drive 폴더 밖"):
        web._validated_drive_paths([str(outside)], root)


def test_persisted_guides_are_copied_and_configured(tmp_path: Path):
    guides_root = tmp_path / "data" / "guides"
    config_path = tmp_path / "data" / "user-guides.yaml"
    uploads = [
        FakeUpload("guide-1.pdf", b"%PDF-one"),
        FakeUpload("guide-2.pdf", b"%PDF-two"),
    ]

    saved = web._persist_guides(uploads, guides_root, config_path)

    assert [path.name for path in saved] == ["guide-1.pdf", "guide-2.pdf"]
    assert (guides_root / "guide-1.pdf").read_bytes() == b"%PDF-one"
    configured = config_path.read_text(encoding="utf-8")
    assert "guide-1.pdf" in configured
    assert "guide-2.pdf" in configured


def test_cloud_deployment_helpers(monkeypatch):
    monkeypatch.setenv("PRESTUDY_DEPLOYMENT_MODE", " CLOUD ")
    monkeypatch.setenv("PRESTUDY_PUBLIC_URL", "https://lecture.example.ts.net/")

    assert web._is_cloud_deployment() is True
    assert web._public_url() == "https://lecture.example.ts.net"
