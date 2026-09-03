from __future__ import annotations

import os
import re
import string
import threading
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path

from .files import CURRENT_SUMMARY_EXTENSIONS, TRANSCRIPT_EXTENSIONS


@dataclass(frozen=True)
class DriveSourceRoots:
    summaries: Path
    transcripts: Path


@dataclass(frozen=True)
class DriveFile:
    path: Path
    label: str
    modified_at: float
    uploaded_at: float = 0


_LAST_KNOWN_ROOTS: DriveSourceRoots | None = None
_LAST_KNOWN_LOCK = threading.Lock()


def _configured_path(name: str) -> Path | None:
    value = os.environ.get(name, "").strip()
    if not value:
        return None
    path = Path(value).expanduser().resolve()
    return path if path.is_dir() else None


def _mounted_shortcut_roots() -> list[Path]:
    roots = []
    for letter in string.ascii_uppercase:
        candidate = Path(f"{letter}:/.shortcut-targets-by-id")
        if candidate.is_dir():
            roots.append(candidate)
    return roots


def drive_mount_diagnostic() -> str:
    roots = _mounted_shortcut_roots()
    if not roots:
        return "Google Drive 마운트와 바로가기 폴더를 아직 찾지 못했습니다."
    letters = ", ".join(root.drive for root in roots)
    return f"Google Drive는 {letters}에 연결되어 있지만 이번 검색에서 00 학습자료 또는 녹음부 바로가기를 찾지 못했습니다."


def _remember_source_roots(roots: DriveSourceRoots) -> None:
    global _LAST_KNOWN_ROOTS
    with _LAST_KNOWN_LOCK:
        _LAST_KNOWN_ROOTS = roots


def _last_known_source_roots() -> DriveSourceRoots | None:
    with _LAST_KNOWN_LOCK:
        roots = _LAST_KNOWN_ROOTS
    if roots is None:
        return None
    try:
        return roots if roots.summaries.is_dir() and roots.transcripts.is_dir() else None
    except OSError:
        return None


def _find_directories(base: Path, target_name: str, max_depth: int = 5) -> list[Path]:
    matches = []
    pending: list[tuple[Path, int]] = [(base, 0)]
    while pending:
        folder, depth = pending.pop()
        if folder.name == target_name:
            matches.append(folder.resolve())
            continue
        if depth >= max_depth:
            continue
        try:
            children = [item for item in folder.iterdir() if item.is_dir()]
        except OSError:
            continue
        pending.extend((child, depth + 1) for child in children)
    return matches


def _latest_academic_folder(paths: list[Path]) -> Path | None:
    if not paths:
        return None

    def rank(path: Path) -> tuple[int, float]:
        years = [int(value) for value in re.findall(r"20\d{2}", str(path))]
        try:
            modified = path.stat().st_mtime
        except OSError:
            modified = 0
        return max(years, default=0), modified

    return max(paths, key=rank)


def _discover_source_roots_once() -> DriveSourceRoots | None:
    summaries = _configured_path("SUMMED_SUMMARY_ROOT")
    transcripts = _configured_path("SUMMED_TRANSCRIPT_ROOT")
    if summaries and transcripts:
        return DriveSourceRoots(summaries=summaries, transcripts=transcripts)

    transcript_candidates = []
    for shortcut_root in _mounted_shortcut_roots():
        if summaries is None:
            summary_candidates = _find_directories(shortcut_root, "00 학습자료", max_depth=2)
            summaries = next(iter(summary_candidates), None)
        if transcripts is None:
            transcript_candidates.extend(
                _find_directories(shortcut_root, "녹음부", max_depth=5)
            )
    transcripts = transcripts or _latest_academic_folder(transcript_candidates)
    if summaries and transcripts:
        return DriveSourceRoots(summaries=summaries, transcripts=transcripts)
    return None


def discover_source_roots(attempts: int = 3, retry_delay: float = 0.25) -> DriveSourceRoots | None:
    for attempt in range(max(1, attempts)):
        roots = _discover_source_roots_once()
        if roots is not None:
            _remember_source_roots(roots)
            return roots
        if attempt + 1 < attempts and retry_delay > 0:
            time.sleep(retry_delay)
    return _last_known_source_roots()


def _course_folder(root: Path, course: str) -> Path | None:
    try:
        folders = [item for item in root.iterdir() if item.is_dir()]
    except OSError:
        return None
    normalized_course = re.sub(r"\W", "", course).casefold()
    for folder in folders:
        normalized_name = re.sub(r"^\d+[.\s_-]*", "", folder.name)
        normalized_name = re.sub(r"\W", "", normalized_name).casefold()
        if normalized_name == normalized_course:
            return folder.resolve()
    return None


def _list_files(folder: Path | None, extensions: set[str]) -> list[DriveFile]:
    if folder is None:
        return []
    result = []
    try:
        candidates = folder.rglob("*")
        for path in candidates:
            try:
                if not path.is_file() or path.suffix.casefold() not in extensions:
                    continue
                stat = path.stat()
            except OSError:
                continue
            result.append(DriveFile(path.resolve(), path.name, stat.st_mtime, stat.st_ctime))
    except OSError:
        return []
    return sorted(result, key=lambda item: (item.modified_at, item.label.casefold()), reverse=True)


def list_course_sources(roots: DriveSourceRoots, course: str) -> tuple[list[DriveFile], list[DriveFile]]:
    summary_folder = _course_folder(roots.summaries, course)
    transcript_folder = _course_folder(roots.transcripts, course)
    summaries = _list_files(summary_folder, CURRENT_SUMMARY_EXTENSIONS)
    # When a PDF and its extracted Markdown coexist, show the PDF as the canonical choice.
    pdf_keys = {_summary_key(item.path.name) for item in summaries if item.path.suffix.casefold() == ".pdf"}
    summaries = [
        item
        for item in summaries
        if item.path.suffix.casefold() == ".pdf" or _summary_key(item.path.name) not in pdf_keys
    ]
    transcripts = _list_files(transcript_folder, TRANSCRIPT_EXTENSIONS)
    return summaries, transcripts


def _summary_key(name: str) -> str:
    value = Path(name).stem.casefold()
    value = re.sub(r"\.summary\.raw$", "", value)
    value = re.sub(r"\s*요약본$", "", value)
    return re.sub(r"\W", "", value)


def _week_and_slot(name: str) -> tuple[str, str]:
    normalized = unicodedata.normalize("NFKC", name)
    week_match = re.search(r"(\d+)\s*주차", normalized)
    slot_match = re.search(r"\(([^)]+)\)", normalized)
    return (
        week_match.group(1) if week_match else "",
        slot_match.group(1).strip().casefold() if slot_match else "",
    )


def _content_text(name: str, course: str) -> str:
    value = unicodedata.normalize("NFKC", Path(name).stem).casefold()
    value = value.replace(".summary.raw", "")
    value = re.sub(re.escape(course.casefold()), " ", value)
    value = re.sub(r"\d+\s*주차", " ", value)
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"요약본|영상보강|영상", " ", value)
    value = re.sub(r"[_\-]+", " ", value)
    return " ".join(value.split())


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[가-힣]{2,}|[a-z]{3,}|\d+", value.casefold())
        if token not in {"요약본", "강의", "week"}
    }


def transcript_match_score(summary_name: str, transcript_name: str, course: str) -> float:
    summary_week, summary_slot = _week_and_slot(summary_name)
    transcript_week, transcript_slot = _week_and_slot(transcript_name)
    score = 0.0
    if summary_week and summary_week == transcript_week:
        score += 35
    if summary_slot and transcript_slot:
        if summary_slot == transcript_slot:
            score += 55
        elif transcript_slot.startswith(summary_slot + "-") or summary_slot.startswith(transcript_slot + "-"):
            score += 50

    summary_content = _content_text(summary_name, course)
    transcript_content = _content_text(transcript_name, course)
    summary_tokens = _tokens(summary_content)
    transcript_tokens = _tokens(transcript_content)
    if summary_tokens and transcript_tokens:
        score += 60 * len(summary_tokens & transcript_tokens) / len(summary_tokens | transcript_tokens)
    score += 20 * SequenceMatcher(None, summary_content, transcript_content).ratio()
    return score


def suggest_transcripts(
    summary: DriveFile, transcripts: list[DriveFile], course: str, limit: int = 8
) -> list[DriveFile]:
    ranked = sorted(
        ((transcript_match_score(summary.label, item.label, course), item) for item in transcripts),
        key=lambda pair: (pair[0], pair[1].modified_at),
        reverse=True,
    )
    if not ranked or ranked[0][0] < 25:
        return []
    cutoff = max(45, ranked[0][0] * 0.72)
    return [item for score, item in ranked if score >= cutoff][:limit]


def infer_topic(summary_name: str, course: str) -> str:
    value = Path(summary_name).stem
    value = re.sub(r"\.summary\.raw$", "", value, flags=re.IGNORECASE)
    value = re.sub(rf"^\s*{re.escape(course)}\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"^\d+\s*주차\s*\([^)]*\)\s*", "", value)
    value = re.sub(r"\s*요약본$", "", value)
    return value.strip() or Path(summary_name).stem


def infer_professor(transcript_name: str, course: str) -> str:
    stem = Path(transcript_name).stem
    parts = stem.split("_")
    if len(parts) >= 4 and parts[0].strip() == course:
        return parts[2].strip()
    return ""


def transcript_upload_date(transcripts: list[DriveFile]) -> date:
    if not transcripts:
        return date.today()
    timestamp = max(item.uploaded_at or item.modified_at for item in transcripts)
    try:
        return datetime.fromtimestamp(timestamp).date()
    except (OSError, OverflowError, ValueError):
        return date.today()


def validate_drive_selection(paths: list[Path], allowed_root: Path) -> list[Path]:
    root = allowed_root.resolve()
    validated = []
    for path in paths:
        resolved = path.resolve()
        if not resolved.is_file() or not resolved.is_relative_to(root):
            raise ValueError(f"허용된 Drive 폴더 밖의 파일은 선택할 수 없습니다: {path.name}")
        validated.append(resolved)
    return validated
