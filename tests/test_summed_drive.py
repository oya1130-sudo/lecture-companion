from pathlib import Path

from summed.drive import MountedDrivePublisher, default_mounted_output
from summed import drive


def test_mounted_drive_publisher_copies_md_and_html(tmp_path: Path):
    source_root = tmp_path / "source"
    source_root.mkdir()
    markdown = source_root / "note.md"
    html = source_root / "note.html"
    markdown.write_text("markdown", encoding="utf-8")
    html.write_text("<html>note</html>", encoding="utf-8")

    published = MountedDrivePublisher(tmp_path / "drive" / "summed").publish(
        [markdown, html], "약리학"
    )

    assert [path.name for path in published] == ["note.md", "note.html"]
    assert published[0].read_text(encoding="utf-8") == "markdown"
    assert published[0].parent.name == "md"
    assert published[1].parent.name == "약리학"
    assert list((tmp_path / "drive" / "summed" / "약리학").glob("*.md")) == []


def test_output_mount_follows_gmail_volume_instead_of_fixed_letter(tmp_path: Path, monkeypatch):
    khu = tmp_path / "H" / "내 드라이브"
    gmail = tmp_path / "J" / "내 드라이브"
    khu.mkdir(parents=True)
    gmail.mkdir(parents=True)
    monkeypatch.delenv("SUMMED_DRIVE_OUTPUT", raising=False)
    monkeypatch.setattr(drive, "_mounted_my_drive_candidates", lambda: [khu, gmail])
    monkeypatch.setattr(
        drive,
        "_volume_label",
        lambda path: "oya1130@gmail.com - Google Drive" if path == gmail else "oya1130@khu.ac.kr - Google Drive",
    )

    assert default_mounted_output() == gmail / "summed"
