from __future__ import annotations

import os
from pathlib import Path


COURSE_DRIVE_FOLDERS = {
    "병리학": "01. 병리학",
    "약리학": "02. 약리학",
    "미생물학": "03. 미생물학",
    "예방의학": "04. 예방의학",
    "의동물학": "05. 의동물학",
}


def _default_root() -> Path:
    configured = os.environ.get("PRESTUDY_HOME", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / "Desktop" / "prestudy-pdf").resolve()


def _default_drive_output_root() -> Path | None:
    configured = os.environ.get("PRESTUDY_DRIVE_OUTPUT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()

    for drive_letter in ("H", "G"):
        my_drive = Path(f"{drive_letter}:/내 드라이브")
        if my_drive.is_dir():
            return my_drive / "수업 동반 노트"
    return None


def _default_drive_source_root(environment_name: str, folder_name: str) -> Path | None:
    configured = os.environ.get(environment_name, "").strip()
    if configured:
        path = Path(configured).expanduser().resolve()
        return path if path.is_dir() else None

    for drive_letter in ("H", "G"):
        shortcuts = Path(f"{drive_letter}:/.shortcut-targets-by-id")
        if not shortcuts.is_dir():
            continue
        try:
            for shortcut in shortcuts.iterdir():
                candidate = shortcut / folder_name
                if candidate.is_dir():
                    return candidate
        except OSError:
            continue
    return None


STORAGE_ROOT = _default_root()
DATA_ROOT = STORAGE_ROOT / "data"
GUIDES_ROOT = DATA_ROOT / "guides"
USER_GUIDES_CONFIG = DATA_ROOT / "user-guides.yaml"
OUTPUT_ROOT = STORAGE_ROOT / "output"
CACHE_ROOT = STORAGE_ROOT / ".prestudy-cache"
WORK_ROOT = STORAGE_ROOT / ".prestudy-work"
DOWNLOAD_ROOT = STORAGE_ROOT / "downloads"
DRIVE_OUTPUT_ROOT = _default_drive_output_root()
JOKCHEK_DRIVE_ROOT = _default_drive_source_root("PRESTUDY_JOKCHEK_ROOT", "2026 본과 1-2 족첵")
SUMMARY_DRIVE_ROOT = _default_drive_source_root("PRESTUDY_SUMMARY_ROOT", "써머리부")
