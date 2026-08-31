from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable

from pydantic import BaseModel
from pypdf import PdfReader

from .models import LectureRequest, SourceDigest, SourceDocument, SourceKind, StudyGuide
from .prompts import digest_prompt, synthesis_prompt
from .storage import WORK_ROOT


Progress = Callable[[str], None]
_CODEX_CONCURRENCY = max(1, int(os.environ.get("PRESTUDY_CODEX_CONCURRENCY", "3")))
_CODEX_SLOTS = threading.BoundedSemaphore(_CODEX_CONCURRENCY)
_REASONING_EFFORTS = {"low", "medium", "high", "xhigh"}
_CAPACITY_RETRIES = max(1, int(os.environ.get("PRESTUDY_CAPACITY_RETRIES", "3")))
_CAPACITY_FALLBACK_MODEL = os.environ.get(
    "PRESTUDY_CAPACITY_FALLBACK_MODEL",
    "gpt-5.6-luna",
).strip()


def _subscription_env() -> dict[str, str]:
    environment = os.environ.copy()
    for name in ("OPENAI_API_KEY", "CODEX_API_KEY", "CODEX_ACCESS_TOKEN"):
        environment.pop(name, None)
    return environment


class FileValidationError(ValueError):
    pass


class CodexExecutionError(RuntimeError):
    pass


def _is_capacity_error(details: str) -> bool:
    normalized = details.casefold()
    return "selected model is at capacity" in normalized or "model is at capacity" in normalized


def validate_pdf(path: Path) -> None:
    if not path.is_file():
        raise FileValidationError(f"파일을 찾을 수 없습니다: {path}")
    if path.suffix.lower() != ".pdf":
        raise FileValidationError(f"PDF만 사용할 수 있습니다: {path.name}")
    with path.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise FileValidationError(f"올바른 PDF가 아닙니다: {path.name}")


def _strict_schema(model: type[BaseModel]) -> dict:
    schema = model.model_json_schema()

    def visit(value) -> None:
        if isinstance(value, dict):
            if value.get("type") == "object":
                value.setdefault("additionalProperties", False)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(schema)
    return schema


class CodexStudyEngine:
    """ChatGPT 계정으로 로그인된 Codex CLI를 사용하는 분석 엔진."""

    def __init__(
        self,
        model: str = "",
        executable: str = "codex",
        work_root: Path | str | None = None,
        timeout_seconds: int = 3600,
        reasoning_effort: str | None = None,
    ) -> None:
        resolved = shutil.which(executable)
        if not resolved:
            raise FileNotFoundError("Codex CLI를 찾을 수 없습니다. 먼저 Codex를 설치해 주세요.")
        self.executable = resolved
        self.codex_model = model.strip()
        self.model = f"codex-subscription:{self.codex_model or 'default'}"
        selected_effort = (
            reasoning_effort or os.environ.get("PRESTUDY_REASONING_EFFORT", "low")
        ).strip().lower()
        if selected_effort not in _REASONING_EFFORTS:
            raise ValueError(
                "Codex 추론 강도는 low, medium, high, xhigh 중 하나여야 합니다."
            )
        self.reasoning_effort = selected_effort
        self.work_root = Path(work_root).resolve() if work_root is not None else WORK_ROOT
        self.work_root.mkdir(parents=True, exist_ok=True)
        self.timeout_seconds = timeout_seconds
        self.check_subscription_login()

    def login_status(self) -> str:
        result = subprocess.run(
            [self.executable, "login", "status"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
            env=_subscription_env(),
        )
        return (result.stdout + result.stderr).strip()

    def check_subscription_login(self) -> None:
        status = self.login_status()
        if "ChatGPT" not in status:
            raise CodexExecutionError(
                "ChatGPT 구독 로그인이 필요합니다. 터미널에서 `codex logout` 후 "
                "`codex login`을 실행해 ChatGPT 계정으로 로그인해 주세요. "
                f"현재 상태: {status or '로그인 안 됨'}"
            )

    def _run_structured(
        self,
        prompt: str,
        output_model: type[BaseModel],
        files: list[Path] | None = None,
        progress: Progress = lambda _: None,
    ):
        # Codex may leave rendered PDF previews with restrictive Windows ACLs.
        # Keep each isolated run directory instead of letting TemporaryDirectory
        # discard a completed analysis while trying to clean those previews.
        with tempfile.TemporaryDirectory(
            prefix="run-",
            dir=self.work_root,
            delete=False,
        ) as temporary:
            root = Path(temporary)
            copied_names: list[str] = []
            extracted_names: list[str] = []
            for index, source in enumerate(files or [], 1):
                destination = root / f"{index:02d}_{source.name}"
                shutil.copy2(source, destination)
                copied_names.append(destination.name)
                try:
                    reader = PdfReader(str(destination))
                    page_text = []
                    for page_number, page in enumerate(reader.pages, 1):
                        page_text.append(f"\n===== PDF p.{page_number} =====\n{page.extract_text() or ''}")
                    extracted = destination.with_suffix(".extracted.txt")
                    extracted.write_text("".join(page_text), encoding="utf-8")
                    extracted_names.append(extracted.name)
                except Exception:
                    # Scanned or malformed PDFs remain available for visual inspection.
                    pass

            schema_path = root / "output-schema.json"
            result_path = root / "result.json"
            schema_path.write_text(
                json.dumps(_strict_schema(output_model), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            file_context = ""
            if copied_names:
                file_context = (
                    "\n\n분석할 로컬 PDF: "
                    + ", ".join(copied_names)
                    + ("\n페이지별 텍스트 추출본: " + ", ".join(extracted_names) if extracted_names else "")
                    + f"\nPDF 도구는 현재 Python 실행 파일 `{sys.executable}`에서 사용할 수 있다. "
                    "먼저 페이지별 텍스트 추출본을 사용하고, 글자가 깨지거나 표·그림·색 표시가 중요한 페이지만 "
                    "PyMuPDF(fitz)로 해당 페이지를 이미지로 렌더링해 시각적으로 확인하라. "
                    "관련 페이지를 건너뛰지 말고 PDF 뷰어 기준 페이지 번호를 보존하라."
                )

            base_command = [
                self.executable,
                "exec",
                "--ephemeral",
                "--sandbox",
                "workspace-write",
                "--skip-git-repo-check",
                "--color",
                "never",
                "--config",
                f'model_reasoning_effort="{self.reasoning_effort}"',
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(result_path),
                "--cd",
                str(root),
            ]
            model_candidates = [self.codex_model]
            if (
                _CAPACITY_FALLBACK_MODEL
                and _CAPACITY_FALLBACK_MODEL not in model_candidates
            ):
                model_candidates.append(_CAPACITY_FALLBACK_MODEL)

            last_capacity_details = ""
            for model_index, candidate_model in enumerate(model_candidates):
                attempts = 1 if model_index < len(model_candidates) - 1 else _CAPACITY_RETRIES
                for attempt in range(attempts):
                    command = list(base_command)
                    if candidate_model:
                        command.extend(["--model", candidate_model])
                    # Read the prompt from stdin so large multi-source synthesis
                    # payloads do not exceed Windows' command-line length limit.
                    command.append("-")
                    result_path.unlink(missing_ok=True)

                    progress(
                        f"Codex 실행 슬롯 대기 중 (최대 {_CODEX_CONCURRENCY}개 병렬)"
                    )
                    try:
                        with _CODEX_SLOTS:
                            progress(
                                "ChatGPT 구독 사용량으로 Codex 분석 실행 중 "
                                f"(모델: {candidate_model or '기본값'}, "
                                f"추론 강도: {self.reasoning_effort})"
                            )
                            result = subprocess.run(
                                command,
                                input=prompt + file_context,
                                capture_output=True,
                                text=True,
                                encoding="utf-8",
                                errors="replace",
                                timeout=self.timeout_seconds,
                                check=False,
                                env=_subscription_env(),
                            )
                    except subprocess.TimeoutExpired as exc:
                        raise CodexExecutionError(
                            f"Codex 분석이 {self.timeout_seconds // 60}분 제한을 초과했습니다."
                        ) from exc

                    if result.returncode == 0:
                        if not result_path.exists():
                            raise CodexExecutionError(
                                "Codex가 구조화된 결과 파일을 만들지 않았습니다."
                            )
                        try:
                            return output_model.model_validate_json(
                                result_path.read_text(encoding="utf-8")
                            )
                        except Exception as exc:
                            raise CodexExecutionError(
                                f"Codex 결과 JSON을 읽지 못했습니다: {exc}"
                            ) from exc

                    details = (result.stderr or result.stdout)[-5000:]
                    if not _is_capacity_error(details):
                        raise CodexExecutionError(f"Codex 분석 실패:\n{details}")
                    last_capacity_details = details

                    if model_index < len(model_candidates) - 1:
                        progress(
                            f"현재 모델이 혼잡하여 {_CAPACITY_FALLBACK_MODEL}로 자동 전환"
                        )
                        break
                    if attempt < attempts - 1:
                        delay = 3 * (attempt + 1)
                        progress(
                            "대체 모델도 혼잡합니다. "
                            f"{delay}초 후 자동 재시도 ({attempt + 2}/{attempts})"
                        )
                        time.sleep(delay)

            raise CodexExecutionError(
                "Codex 모델이 현재 혼잡합니다. 기본 모델과 대체 모델로 "
                f"자동 재시도했지만 연결되지 않았습니다. 잠시 후 다시 시도해 주세요.\n"
                f"{last_capacity_details[-500:]}"
            )

    def analyze_source(
        self,
        source: SourceDocument,
        lecture: LectureRequest,
        progress: Progress = lambda _: None,
    ) -> SourceDigest:
        validate_pdf(source.path)
        progress(f"{source.path.name} 로컬 분석 준비 중")
        result = self._run_structured(
            digest_prompt(source.kind, lecture, source.path.name),
            SourceDigest,
            files=[source.path],
            progress=progress,
        )
        result.source_file = source.path.name
        result.source_kind = source.kind.value
        return result

    def synthesize(
        self,
        lecture: LectureRequest,
        digests: list[SourceDigest],
        progress: Progress = lambda _: None,
    ) -> StudyGuide:
        payload = json.dumps(
            [item.model_dump(mode="json") for item in digests],
            ensure_ascii=False,
        )
        return self._run_structured(
            synthesis_prompt(
                lecture,
                payload,
                has_lecture_material=any(
                    item.source_kind == SourceKind.LECTURE.value for item in digests
                ),
            ),
            StudyGuide,
            progress=progress,
        )
