import inspect
from datetime import date
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
    assert "st.status(" in source


def test_output_filename_uses_mmdd_and_readable_spaces():
    filename = web._output_filename(
        date(2026, 8, 31),
        "예방의학",
        "오창모",
        "질병 및 사망, 건강수준의 측정",
    )

    assert filename == "0831 예방의학 오창모 질병 및 사망, 건강수준의 측정 수업동반노트.html"


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
