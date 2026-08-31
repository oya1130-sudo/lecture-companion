from __future__ import annotations

import os
import re
import socket
from datetime import date
from pathlib import Path

import streamlit as st
import yaml

from .ai import CodexStudyEngine
from .jobs import JobManager, JobSnapshot
from .models import LectureRequest, SourceDocument, SourceKind, SummaryReliability
from .storage import (
    COURSE_DRIVE_FOLDERS,
    DRIVE_OUTPUT_ROOT,
    GUIDES_ROOT,
    JOB_STATE_PATH,
    JOKCHEK_DRIVE_ROOT,
    OUTPUT_ROOT,
    STORAGE_ROOT,
    SUMMARY_DRIVE_ROOT,
    USER_GUIDES_CONFIG,
    WORK_ROOT,
)


RELIABILITY_LABELS = {
    "일부 변경됨 (권장)": SummaryReliability.PARTIAL,
    "교수·내용 동일": SummaryReliability.SAME,
    "많이 변경됨": SummaryReliability.CHANGED,
    "잘 모름": SummaryReliability.UNKNOWN,
}

CODEX_CONCURRENCY = max(1, int(os.environ.get("PRESTUDY_CODEX_CONCURRENCY", "2")))


@st.cache_resource
def _job_manager(config_version: str = "persistent-history-v2") -> JobManager:
    # Bump config_version when shared worker construction changes so a hot
    # reload cannot keep an older JobManager instance alive.
    return JobManager(state_path=JOB_STATE_PATH, history_output_root=OUTPUT_ROOT)


@st.cache_data(ttl="5m", max_entries=4, show_spinner=False)
def _login_status(model: str) -> str:
    return CodexStudyEngine(model=model).login_status()


@st.cache_data(ttl="10m", max_entries=2, show_spinner=False)
def _local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        sock.close()


def _is_cloud_deployment() -> bool:
    return os.environ.get("PRESTUDY_DEPLOYMENT_MODE", "").strip().casefold() == "cloud"


def _public_url() -> str:
    return os.environ.get("PRESTUDY_PUBLIC_URL", "").strip().rstrip("/")


def _save_uploads(files, folder: Path) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for file in files or []:
        path = folder / Path(file.name).name
        path.write_bytes(file.getvalue())
        paths.append(path)
    return paths


def _safe_name(value: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", value).strip() or "강의"


def _output_filename(lecture_date: date, course: str, professor: str, topic: str) -> str:
    return (
        f"{lecture_date:%m%d} {_safe_name(course)} {_safe_name(professor)} "
        f"{_safe_name(topic)} 수업동반노트.html"
    )


def _available_output_path(filename: str, manager: JobManager) -> Path:
    reserved = {snapshot.output_path for snapshot in manager.snapshots()}
    candidate = OUTPUT_ROOT / filename
    number = 2
    while candidate.exists() or candidate in reserved:
        candidate = OUTPUT_ROOT / f"{Path(filename).stem} ({number}){Path(filename).suffix}"
        number += 1
    return candidate


@st.cache_data(ttl="2m", max_entries=20, show_spinner=False)
def _drive_pdf_options(root_value: str, course: str) -> list[str]:
    root = Path(root_value)
    if not root.is_dir() or not course:
        return []
    try:
        course_folders = [
            path
            for path in root.iterdir()
            if path.is_dir() and course.casefold() in path.name.casefold()
        ]
        pdfs = [
            str(path)
            for folder in course_folders
            for path in folder.rglob("*")
            if path.is_file() and path.suffix.casefold() == ".pdf"
        ]
    except OSError:
        return []
    return sorted(pdfs, key=lambda value: Path(value).name.casefold(), reverse=True)


def _drive_option_label(value: str) -> str:
    path = Path(value)
    return f"{path.name} · {path.parent.name}"


def _validated_drive_paths(values: list[str], root: Path | None) -> list[Path]:
    if not values:
        return []
    if root is None:
        raise ValueError("Google Drive 자료 폴더를 찾지 못했습니다.")
    root_resolved = root.resolve()
    paths = []
    for value in values:
        path = Path(value).resolve()
        try:
            path.relative_to(root_resolved)
        except ValueError as exc:
            raise ValueError(f"허용된 Drive 폴더 밖의 파일입니다: {path.name}") from exc
        if not path.is_file() or path.suffix.casefold() != ".pdf":
            raise ValueError(f"Drive PDF를 찾을 수 없습니다: {path.name}")
        paths.append(path)
    return paths


def _upload_summary(label: str, files) -> None:
    if not files:
        return
    total_mb = sum(len(file.getvalue()) for file in files) / (1024 * 1024)
    names = ", ".join(file.name for file in files)
    st.success(f"{label} {len(files)}개 업로드 완료 · {total_mb:.1f}MB")
    st.caption(names)


def _persist_guides(
    files,
    guides_root: Path = GUIDES_ROOT,
    config_path: Path = USER_GUIDES_CONFIG,
) -> list[Path]:
    if not files:
        raise ValueError("저장할 학습가이드 PDF를 선택해 주세요.")
    guides_root.mkdir(parents=True, exist_ok=True)
    saved = []
    for file in files:
        filename = Path(file.name).name
        if Path(filename).suffix.casefold() != ".pdf":
            raise ValueError(f"PDF만 학습가이드로 저장할 수 있습니다: {filename}")
        destination = guides_root / filename
        destination.write_bytes(file.getvalue())
        saved.append(destination.resolve())

    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = yaml.safe_dump(
        {"common_guides": [str(path) for path in saved]},
        allow_unicode=True,
        sort_keys=False,
    )
    temporary = config_path.with_suffix(f"{config_path.suffix}.tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(config_path)
    return saved


def _configured_guides() -> tuple[list[Path], Path]:
    configured = os.environ.get("PRESTUDY_GUIDES_CONFIG", "").strip()
    candidates = []
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.extend([USER_GUIDES_CONFIG, STORAGE_ROOT / "default-guides.yaml"])
    for config_path in candidates:
        if not config_path.is_file():
            continue
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        paths = [Path(value).expanduser() for value in data.get("common_guides", [])]
        existing = [path for path in paths if path.is_file()]
        if existing:
            return existing, config_path
    return [], USER_GUIDES_CONFIG


def _render_job_card(snapshot: JobSnapshot) -> None:
    with st.container(border=True):
        header = st.container(horizontal=True, vertical_alignment="center")
        with header:
            st.markdown(f"**{snapshot.label}**")
            if snapshot.status == "queued":
                st.badge("대기", color="gray")
            elif snapshot.status == "running":
                st.badge("생성 중", color="blue")
            elif snapshot.status == "complete":
                st.badge("완료", color="green")
            else:
                st.badge("실패", color="red")

        details = [snapshot.created_at.strftime("등록 %Y-%m-%d %H:%M")]
        if snapshot.professor:
            details.append(snapshot.professor)
        if snapshot.lecture_date:
            details.append(f"강의일 {snapshot.lecture_date}")
        if snapshot.finished_at is not None:
            details.append(snapshot.finished_at.strftime("완료 %m-%d %H:%M"))
        st.caption(" · ".join(details))

        if snapshot.status == "running":
            st.status(
                snapshot.messages[-1] if snapshot.messages else "작업 시작 중",
                state="running",
                expanded=False,
                type="compact",
            )
        elif snapshot.status == "queued":
            st.caption("실행 슬롯을 기다리고 있습니다.")
        elif snapshot.status == "failed":
            st.error(snapshot.error or "작업이 실패했습니다.")
        elif snapshot.output_path.is_file():
            if snapshot.drive_path is not None:
                st.success(f"Google Drive 저장 완료 · {snapshot.drive_path}")
            elif snapshot.drive_error:
                st.warning(
                    f"Google Drive 저장 실패 · {snapshot.drive_error}\n\n"
                    "로컬 HTML은 정상적으로 완성됐습니다."
                )
            output_path = snapshot.output_path
            st.download_button(
                "HTML 다운로드",
                data=lambda path=output_path: path.read_bytes(),
                file_name=output_path.name,
                mime="text/html",
                key=f"download-{snapshot.job_id}",
                width="stretch",
                on_click="ignore",
                icon=":material/download:",
            )
        elif snapshot.status == "complete":
            st.warning("완성 HTML 파일을 찾지 못했습니다.")

        if snapshot.source_files:
            with st.expander(f"사용한 자료 · {len(snapshot.source_files)}개"):
                grouped_sources: dict[str, list[str]] = {}
                for source in snapshot.source_files:
                    grouped_sources.setdefault(source.kind, []).append(source.filename)
                for kind, filenames in grouped_sources.items():
                    st.markdown(f"**{kind}**")
                    for filename in filenames:
                        st.caption(f"• {filename}")

        if snapshot.messages:
            with st.expander("진행 기록"):
                st.code("\n".join(snapshot.messages[-12:]), language=None)


@st.fragment(run_every="2s")
def _render_job_queue() -> None:
    manager = _job_manager()
    snapshots = manager.snapshots()
    active = [snapshot for snapshot in snapshots if snapshot.status in {"queued", "running"}]
    history = [snapshot for snapshot in snapshots if snapshot.status not in {"queued", "running"}]

    st.subheader("작업 큐")
    st.caption(
        f"진행 중 {len(active)}개 · 이전 작업 {len(history)}개 · "
        f"최대 {manager.max_workers}개 병렬 처리 · Codex 동시 호출 {CODEX_CONCURRENCY}개"
    )

    st.markdown("#### 진행 중인 작업")
    if active:
        for snapshot in active:
            _render_job_card(snapshot)
    else:
        st.info("현재 진행 중인 작업이 없습니다.")

    st.markdown(f"#### 이전 작업 내역 · {len(history)}개")
    st.caption("앱을 재시작해도 보존되며, 기존 output과 Google Drive의 HTML도 자동으로 불러옵니다.")
    if history:
        for snapshot in history:
            _render_job_card(snapshot)
    else:
        st.info("아직 완료되거나 실패한 작업이 없습니다.")


def run() -> None:
    st.set_page_config(page_title="수업 동반 노트", page_icon="📚", layout="wide")
    st.title("수업 동반 노트 만들기")
    st.caption("한 작업이 생성되는 동안 다음 강의를 계속 제출할 수 있습니다.")

    if "upload_batch" not in st.session_state:
        st.session_state.upload_batch = 0
    if flash_message := st.session_state.pop("upload_flash", ""):
        st.success(flash_message)

    guide_paths, guide_config = _configured_guides()
    manager = _job_manager()
    cloud_deployment = _is_cloud_deployment()

    with st.sidebar:
        st.header("접속과 실행 상태")
        if len(guide_paths) == 3:
            st.success("학습가이드 3개 자동 연결됨")
        elif guide_paths:
            st.warning(f"학습가이드 {len(guide_paths)}개만 확인됨")
        else:
            st.error("기본 학습가이드를 찾지 못함")
        if cloud_deployment:
            st.success("클라우드 서버에서 실행 중")
            if public_url := _public_url():
                st.info(f"태블릿과 다른 기기에서 접속\n\n{public_url}")
            else:
                st.info("Tailscale Serve 주소를 설정하면 태블릿 접속 주소가 여기에 표시됩니다.")
            st.caption("서버와 비공개 네트워크가 실행 중이면 노트북을 꺼도 작업이 계속됩니다.")
        else:
            network_url = f"http://{_local_ip()}:8501"
            st.info(f"같은 Wi-Fi 기기에서 접속\n\n{network_url}")
            st.caption("메인 노트북이 켜져 있고 프로그램 창이 실행 중이어야 합니다. Windows 방화벽 창이 뜨면 개인 네트워크를 허용하세요.")
        st.caption(f"HTML 저장 위치\n{OUTPUT_ROOT}")
        if DRIVE_OUTPUT_ROOT is not None:
            st.success("Google Drive 자동 저장 켜짐")
            st.caption(f"Drive 저장 위치\n{DRIVE_OUTPUT_ROOT}")
        else:
            if cloud_deployment:
                st.caption("Google Drive가 서버에 연결되지 않아 완성본은 영구 디스크에 저장됩니다.")
            else:
                st.warning("Google Drive 자동 저장 폴더를 찾지 못했습니다.")

        model = ""
        with st.expander("고급 설정"):
            model = st.text_input(
                "Codex 모델",
                value=os.environ.get("PRESTUDY_CODEX_MODEL", ""),
                help="비워두면 현재 Codex 기본 모델을 사용합니다.",
                key="codex-model",
            )
            st.caption(f"가이드 설정: {guide_config}")
            if st.button("ChatGPT 로그인 상태 확인"):
                try:
                    st.success(_login_status(model))
                except Exception as exc:
                    st.error(str(exc))

    with st.expander("기본 학습가이드 확인·교체", expanded=not guide_paths):
        if guide_paths:
            st.write("아래 세 파일은 자동으로 사용됩니다. 평소에는 다시 선택하지 않아도 됩니다.")
            for path in guide_paths:
                st.code(str(path), language=None)
        replacement_guides = st.file_uploader(
            "학습가이드 PDF 등록 또는 이번 작업에서만 교체",
            type=["pdf"],
            accept_multiple_files=True,
            key="replacement-guides",
        )
        if st.button(
            "선택한 파일을 기본 학습가이드로 저장",
            disabled=not replacement_guides,
            width="stretch",
        ):
            try:
                saved_guides = _persist_guides(replacement_guides)
                st.session_state.upload_flash = f"기본 학습가이드 {len(saved_guides)}개를 저장했습니다."
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    st.subheader("새 강의 작업 추가")
    upload_batch = st.session_state.upload_batch
    course = st.selectbox(
        "과목",
        list(COURSE_DRIVE_FOLDERS),
        index=None,
        placeholder="과목 선택",
        key="course-selection",
    )
    drive_available = JOKCHEK_DRIVE_ROOT is not None
    source_mode = st.segmented_control(
        "자료 가져오기",
        ["Google Drive에서 선택", "기기에서 업로드"],
        default="Google Drive에서 선택" if drive_available else "기기에서 업로드",
        required=True,
        width="stretch",
        key="source-mode",
    )

    jokchek_uploads = []
    summary_uploads = []
    drive_jokchek_values: list[str] = []
    drive_summary_values: list[str] = []
    if source_mode == "Google Drive에서 선택":
        if not drive_available:
            st.error("서버에서 족첵 Google Drive 폴더를 찾지 못했습니다. 기기 업로드를 사용해 주세요.")
        elif not course:
            st.info("과목을 선택하면 Google Drive의 족첵과 선배 써머리 목록이 나타납니다.")
        else:
            jokchek_options = _drive_pdf_options(str(JOKCHEK_DRIVE_ROOT), course)
            summary_options = (
                _drive_pdf_options(str(SUMMARY_DRIVE_ROOT), course)
                if SUMMARY_DRIVE_ROOT is not None
                else []
            )
            st.caption(
                f"서버의 Google Drive에서 {course} 족첵 {len(jokchek_options)}개, "
                f"써머리 {len(summary_options)}개를 찾았습니다. 파일명 일부를 입력해 검색할 수 있습니다."
            )
            left, right = st.columns(2)
            with left:
                drive_jokchek_values = st.multiselect(
                    "족첵 PDF",
                    jokchek_options,
                    format_func=_drive_option_label,
                    placeholder="족첵 파일 검색·선택",
                    key=f"drive-jokchek-{upload_batch}-{course}",
                )
            with right:
                drive_summary_values = st.multiselect(
                    "선배 써머리 PDF (선택)",
                    summary_options,
                    format_func=_drive_option_label,
                    placeholder="써머리 파일 검색·선택",
                    key=f"drive-summary-{upload_batch}-{course}",
                )
    else:
        st.caption("Drive 목록에 없는 자료만 태블릿이나 노트북에서 직접 업로드하세요.")
        left, right = st.columns(2)
        with left:
            jokchek_uploads = st.file_uploader(
                "족첵 PDF",
                type=["pdf", "application/pdf"],
                accept_multiple_files=True,
                max_upload_size=500,
                key=f"jokchek-{upload_batch}",
            )
            _upload_summary("족첵", jokchek_uploads)
        with right:
            summary_uploads = st.file_uploader(
                "선배 써머리 PDF (선택)",
                type=["pdf", "application/pdf"],
                accept_multiple_files=True,
                max_upload_size=500,
                key=f"summary-{upload_batch}",
            )
            _upload_summary("선배 써머리", summary_uploads)

    with st.form("lecture-job-form", clear_on_submit=True):
        col1, col2 = st.columns([1, 1.6])
        professor = col1.text_input("교수", placeholder="예: 김자은")
        topic = col2.text_input("강의 주제", placeholder="예: Pharmacokinetics 2 & metabolism")
        col4, col5 = st.columns(2)
        lecture_date = col4.date_input("강의일")
        reliability_label = col5.selectbox("선배 써머리 일치도", list(RELIABILITY_LABELS))
        submitted = st.form_submit_button("작업 큐에 추가", type="primary", width="stretch")

    if submitted:
        selected_jokchek = drive_jokchek_values if source_mode == "Google Drive에서 선택" else jokchek_uploads
        if not selected_jokchek:
            st.error("족첵 PDF를 한 개 이상 선택해 주세요.")
        elif not course or not professor.strip() or not topic.strip():
            st.error("과목, 교수, 강의 주제를 입력해 주세요.")
        elif not guide_paths and not replacement_guides:
            st.error("기본 학습가이드가 없습니다. 교체 영역에 학습가이드 PDF를 넣어 주세요.")
        else:
            job_id = manager.new_id()
            job_root = WORK_ROOT / "jobs" / job_id
            selected_guides = _save_uploads(replacement_guides, job_root / "guides") if replacement_guides else guide_paths
            if source_mode == "Google Drive에서 선택":
                try:
                    jokchek_paths = _validated_drive_paths(drive_jokchek_values, JOKCHEK_DRIVE_ROOT)
                    summary_paths = _validated_drive_paths(drive_summary_values, SUMMARY_DRIVE_ROOT)
                except ValueError as exc:
                    st.error(str(exc))
                    st.stop()
            else:
                jokchek_paths = _save_uploads(jokchek_uploads, job_root / "jokchek")
                summary_paths = _save_uploads(summary_uploads, job_root / "summaries")
            lecture = LectureRequest(
                course=course,
                professor=professor.strip(),
                topic=topic.strip(),
                lecture_date=str(lecture_date),
                summary_reliability=RELIABILITY_LABELS[reliability_label],
            )
            sources = [SourceDocument(path=path, kind=SourceKind.GUIDE) for path in selected_guides]
            sources.extend(SourceDocument(path=path, kind=SourceKind.JOKCHEK) for path in jokchek_paths)
            sources.extend(SourceDocument(path=path, kind=SourceKind.SUMMARY) for path in summary_paths)
            filename = _output_filename(lecture_date, course, professor, topic)
            OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
            output_path = _available_output_path(filename, manager)
            snapshot = manager.submit(job_id, lecture, sources, output_path, model=model)
            st.session_state.upload_batch += 1
            st.session_state.upload_flash = (
                f"{snapshot.label} 작업을 큐에 추가했습니다. 바로 다음 강의를 제출할 수 있습니다."
            )
            st.rerun()

    _render_job_queue()
