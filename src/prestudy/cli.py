from __future__ import annotations

import argparse
import os
from pathlib import Path

import yaml

from .ai import CodexStudyEngine
from .drive import GoogleDriveReader
from .models import LectureRequest, SourceDocument, SourceKind, SummaryReliability
from .service import StudyGuideService
from .storage import DOWNLOAD_ROOT, OUTPUT_ROOT, STORAGE_ROOT


def slug(text: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in text).strip("_")


def local_pdfs(values: list[str] | None) -> list[Path]:
    paths = [Path(value).expanduser() for value in (values or [])]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("다음 로컬 PDF를 찾을 수 없습니다:\n" + "\n".join(missing))
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Google Drive 자료로 수업 동반 노트를 일괄 생성합니다.")
    parser.add_argument("--config", type=Path, default=STORAGE_ROOT / "config.yaml")
    parser.add_argument("--credentials", type=Path, default=STORAGE_ROOT / "credentials.json")
    parser.add_argument("--token", type=Path, default=STORAGE_ROOT / "token.json")
    args = parser.parse_args()

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    model = config.get("model", os.environ.get("PRESTUDY_CODEX_MODEL", ""))
    configured_output = Path(config.get("output_dir", "output"))
    output_dir = configured_output if configured_output.is_absolute() else STORAGE_ROOT / configured_output
    reader = GoogleDriveReader(args.credentials, args.token)
    engine = CodexStudyEngine(model=model)
    service = StudyGuideService(engine)

    if config.get("common_guides"):
        common_paths = local_pdfs(config["common_guides"])
    else:
        print("공통 학습가이드 다운로드 중")
        common_paths = reader.download_pdfs(
            config["common_guides_folder"],
            DOWNLOAD_ROOT / "common",
            config.get("common_guides_match", ""),
        )
    for raw in config["lectures"]:
        lecture = LectureRequest(
            course=raw["course"],
            professor=raw["professor"],
            topic=raw["topic"],
            lecture_date=str(raw.get("lecture_date", "")),
            summary_reliability=SummaryReliability(raw.get("summary_reliability", "unknown")),
        )
        key = slug(f"{lecture.lecture_date}_{lecture.course}_{lecture.topic}")
        lecture_dir = DOWNLOAD_ROOT / key
        if raw.get("jokchek_files"):
            jokchek = local_pdfs(raw["jokchek_files"])
        else:
            jokchek = reader.download_pdfs(
                raw["jokchek_folder"],
                lecture_dir / "jokchek",
                raw.get("jokchek_match", ""),
            )
        if raw.get("summary_files"):
            summaries = local_pdfs(raw["summary_files"])
        elif raw.get("summary_folder"):
            summaries = reader.download_pdfs(
                raw["summary_folder"],
                lecture_dir / "summaries",
                raw.get("summary_match", ""),
            )
        else:
            summaries = []
        if not jokchek:
            raise FileNotFoundError(f"{lecture.course}: 조건에 맞는 족첵 PDF가 없습니다.")
        sources = [SourceDocument(path=p, kind=SourceKind.GUIDE) for p in common_paths]
        sources.extend(SourceDocument(path=p, kind=SourceKind.JOKCHEK) for p in jokchek)
        sources.extend(SourceDocument(path=p, kind=SourceKind.SUMMARY) for p in summaries)
        output = output_dir / f"{key}_수업동반노트.html"
        service.create(lecture, sources, output, print)


if __name__ == "__main__":
    main()
