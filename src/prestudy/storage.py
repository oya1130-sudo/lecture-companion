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
        direct = Path(f"{drive_letter}:/내 드라이브") / folder_name
        try:
            if direct.is_dir():
                return direct
        except OSError:
            pass

        shortcuts = Path(f"{drive_letter}:/.shortcut-targets-by-id")
        try:
            shortcut_entries = list(shortcuts.iterdir()) if shortcuts.is_dir() else []
        except OSError:
            continue
        for shortcut in shortcut_entries:
            candidate = shortcut / folder_name
            try:
                if candidate.is_dir():
                    return candidate
            except OSError:
                # One unavailable Drive shortcut must not abort the whole scan.
                pass
    return None


def _default_lecture_source_root() -> Path | None:
    configured = os.environ.get("PRESTUDY_LECTURE_ROOT", "").strip()
    if configured:
        path = Path(configured).expanduser().resolve()
        return path if path.is_dir() else None

    relative_paths = (
        Path("의학과 1-2") / "2026년" / "학습부",
        Path("2026년") / "학습부",
    )
    for drive_letter in ("H", "G"):
        direct = Path(f"{drive_letter}:/내 드라이브")
        for relative in relative_paths:
            candidate = direct / relative
            if candidate.is_dir():
                return candidate

        shortcuts = Path(f"{drive_letter}:/.shortcut-targets-by-id")
        try:
            shortcut_entries = list(shortcuts.iterdir()) if shortcuts.is_dir() else []
        except OSError:
            continue
        for shortcut in shortcut_entries:
            for relative in relative_paths:
                candidate = shortcut / relative
                try:
                    if candidate.is_dir():
                        return candidate
                except OSError:
                    # Shared-drive shortcuts may be temporarily offline independently.
                    pass
    return None


def discover_drive_source_roots() -> tuple[Path | None, Path | None, Path | None]:
    """Re-scan Drive mounts instead of relying on import-time availability."""
    return (
        _default_drive_source_root("PRESTUDY_JOKCHEK_ROOT", "2026 본과 1-2 족첵"),
        _default_lecture_source_root(),
        _default_drive_source_root("PRESTUDY_SUMMARY_ROOT", "써머리부"),
    )


STORAGE_ROOT = _default_root()
DATA_ROOT = STORAGE_ROOT / "data"
GUIDES_ROOT = DATA_ROOT / "guides"
USER_GUIDES_CONFIG = DATA_ROOT / "user-guides.yaml"
OUTPUT_ROOT = STORAGE_ROOT / "output"
CACHE_ROOT = STORAGE_ROOT / ".prestudy-cache"
WORK_ROOT = STORAGE_ROOT / ".prestudy-work"
DOWNLOAD_ROOT = STORAGE_ROOT / "downloads"
JOB_STATE_PATH = STORAGE_ROOT / "jobs.json"
DRIVE_OUTPUT_ROOT = _default_drive_output_root()
JOKCHEK_DRIVE_ROOT = _default_drive_source_root("PRESTUDY_JOKCHEK_ROOT", "2026 본과 1-2 족첵")
LECTURE_DRIVE_ROOT = _default_lecture_source_root()
SUMMARY_DRIVE_ROOT = _default_drive_source_root("PRESTUDY_SUMMARY_ROOT", "써머리부")
