from __future__ import annotations

import os
import subprocess
import threading
import uuid
from datetime import date, datetime
from pathlib import Path

import streamlit as st

from .codex import CodexRunner, configured_concurrency, subscription_environment
from .drive import (
    GMAIL_ACCOUNT,
    KHU_ACCOUNT,
    DriveShortcutSetup,
    MountedDrivePublisher,
    default_mounted_output,
)
from .drive_sources import (
    DriveSourceRoots,
    discover_source_roots,
    drive_mount_diagnostic,
    infer_professor,
    infer_topic,
    list_course_sources,
    suggest_transcripts,
    transcript_upload_date,
    validate_drive_selection,
)
from .files import CURRENT_SUMMARY_EXTENSIONS, SUPPORTED_EXTENSIONS, TRANSCRIPT_EXTENSIONS, save_bytes
from .jobs import JobManager
from .models import JobRecord, ReferenceKind, SummaryRequest
from .references import ReferenceLibrary
from .service import SummedService
from .storage import COURSES, StoragePaths


@st.cache_resource
def _resources() -> tuple[StoragePaths, ReferenceLibrary, JobManager, DriveShortcutSetup]:
    paths = StoragePaths.discover().ensure()
    library = ReferenceLibrary(paths.references)
    model = os.environ.get("SUMMED_CODEX_MODEL", "").strip()
    runner_lock = threading.Lock()
    shared_runner: list[CodexRunner] = []

    def service_factory() -> SummedService:
        with runner_lock:
            if not shared_runner:
                shared_runner.append(CodexRunner(model=model))
        return SummedService(library, shared_runner[0], paths.outputs)

    manager = JobManager(
        paths.jobs,
        service_factory,
        MountedDrivePublisher(),
        max_workers=configured_concurrency(),
    )
    drive_setup = DriveShortcutSetup(paths.oauth / "oauth-client.json", paths.oauth / "tokens")
    return paths, library, manager, drive_setup


@st.cache_data(ttl="30s", max_entries=1, show_spinner=False)
def _codex_status() -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["codex", "login", "status"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
            env=subscription_environment(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    message = (result.stdout + result.stderr).strip()
    return result.returncode == 0 and "ChatGPT" in message, message


def _save_uploads(paths: StoragePaths, summary, transcripts) -> tuple[Path, list[Path]]:
    staging = paths.root / "uploads" / uuid.uuid4().hex
    summary_path = save_bytes(summary.getvalue(), summary.name, staging)
    transcript_paths = [save_bytes(item.getvalue(), item.name, staging) for item in transcripts]
    return summary_path, transcript_paths


@st.cache_data(ttl="30s", max_entries=20, show_spinner=False)
def _cached_course_sources(
    summary_root: str, transcript_root: str, course: str
):
    return list_course_sources(
        DriveSourceRoots(Path(summary_root), Path(transcript_root)), course
    )


@st.cache_data(ttl="15s", max_entries=1, show_spinner=False)
def _cached_source_roots() -> DriveSourceRoots | None:
    return discover_source_roots()


def _submit_request(manager: JobManager, request: SummaryRequest) -> None:
    job_id = manager.submit(request, os.environ.get("SUMMED_CODEX_MODEL", ""))
    st.session_state["selected_job"] = job_id
    st.success("생성을 시작했습니다. ‘결과’ 탭에서 진행 상황을 볼 수 있습니다.", icon=":material/check:")


_TERMINAL_JOB_STATUSES = {"완료", "실패", "중단됨"}


def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    total_seconds = max(0, int(seconds))
    days, remainder = divmod(total_seconds, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes, secs = divmod(remainder, 60)
    if days:
        return f"{days}일 {hours:02d}:{minutes:02d}:{secs:02d}"
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    if minutes:
        return f"{minutes}분 {secs:02d}초"
    return f"{secs}초"


def _seconds_between(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return max(0.0, (end - start).total_seconds())


def _job_timing(record: JobRecord, now: datetime | None = None) -> dict[str, float | None]:
    current_time = now or datetime.now()
    end_time = record.finished_at or current_time
    current_started_at = (
        record.events[-1].created_at
        if record.events
        else record.status_changed_at or record.started_at or record.created_at
    )
    return {
        "total": _seconds_between(record.created_at, end_time),
        "queued": _seconds_between(record.created_at, record.started_at),
        "running": _seconds_between(record.started_at, end_time),
        "current": (
            None
            if record.status in _TERMINAL_JOB_STATUSES
            else _seconds_between(current_started_at, current_time)
        ),
    }


def _new_note_tab(paths: StoragePaths, manager: JobManager) -> None:
    st.subheader("새 정리본", anchor=False)
    st.caption("Drive에서 수업을 고르면 대응 전사본을 자동 추천합니다. 직접 업로드도 계속 사용할 수 있습니다.")
    controls = st.container(horizontal=True, vertical_alignment="bottom")
    with controls:
        source_mode = st.segmented_control(
            "자료 선택 방식", ["Drive에서 선택", "직접 업로드"], default="Drive에서 선택",
            key="source-mode", persist_state="session"
        )
        course = st.selectbox("과목", COURSES, key="note-course", persist_state="session")

    if source_mode == "Drive에서 선택":
        roots = _cached_source_roots()
        if roots is None:
            st.error(drive_mount_diagnostic())
            st.caption("Drive가 막 시작된 경우 바로가기 폴더가 나타나는 데 잠시 걸릴 수 있습니다.")
            if st.button("Google Drive 다시 검색", icon=":material/refresh:"):
                _cached_source_roots.clear()
                _cached_course_sources.clear()
                st.rerun()
            return
        refresh_row = st.container(horizontal=True, vertical_alignment="center")
        with refresh_row:
            st.caption("최근에 수정된 요약본부터 표시합니다.")
            if st.button("Drive 목록 새로고침", icon=":material/refresh:"):
                _cached_source_roots.clear()
                _cached_course_sources.clear()
                st.rerun()
        summaries, transcripts = _cached_course_sources(
            str(roots.summaries), str(roots.transcripts), course
        )
        if not summaries:
            st.warning(f"00 학습자료의 {course} 폴더에서 요약본을 찾지 못했습니다.")
            return
        summary_by_path = {str(item.path): item for item in summaries}
        selected_summary_path = st.selectbox(
            "수업 요약본",
            list(summary_by_path),
            format_func=lambda value: summary_by_path[value].label,
            key=f"drive-summary-{course}",
        )
        selected_summary = summary_by_path[selected_summary_path]
        transcript_by_path = {str(item.path): item for item in transcripts}
        suggested = suggest_transcripts(selected_summary, transcripts, course)
        suggestion_paths = [str(item.path) for item in suggested]
        selection_key = f"drive-transcripts-{course}-{abs(hash(selected_summary_path))}"
        selected_transcript_paths = st.multiselect(
            "전사본",
            list(transcript_by_path),
            default=suggestion_paths,
            format_func=lambda value: transcript_by_path[value].label,
            key=selection_key,
            help="파일명의 주차·차시·주제를 기준으로 자동 선택했습니다. 필요하면 추가하거나 빼세요.",
        )
        if suggested:
            st.caption(f"관련성이 높은 전사본 {len(suggested)}개를 자동 선택했습니다.")
        elif transcripts:
            st.warning("자동으로 확신할 만한 전사본을 찾지 못했습니다. 전사본을 직접 선택해 주세요.")
        else:
            st.warning(f"녹음부의 {course} 폴더에서 전사본을 찾지 못했습니다.")

        inferred_professor = ""
        selected_transcript_files = [
            transcript_by_path[value] for value in selected_transcript_paths
        ]
        if selected_transcript_paths:
            inferred_professor = infer_professor(
                transcript_by_path[selected_transcript_paths[0]].label, course
            )
        inferred_date = transcript_upload_date(selected_transcript_files)
        form_identity = abs(hash((selected_summary_path, tuple(selected_transcript_paths))))
        with st.form(f"create-drive-note-{course}-{form_identity}"):
            left, right = st.columns(2)
            with left:
                professor = st.text_input("담당 교수", value=inferred_professor, placeholder="예: 홍길동")
                lecture_date = st.date_input(
                    "강의일",
                    value=inferred_date,
                    help="선택한 전사본 중 가장 늦게 Drive에 업로드된 파일의 날짜입니다.",
                )
            with right:
                topic = st.text_input("강의 주제", value=infer_topic(selected_summary.label, course))
                st.text_input("선택 위치", value="KHU Drive · 00 학습자료 / 녹음부", disabled=True)
            submitted = st.form_submit_button(
                "선택한 자료로 정리본 만들기", type="primary", icon=":material/auto_awesome:"
            )
        if submitted:
            problems = []
            if not professor.strip():
                problems.append("담당 교수를 입력해 주세요.")
            if not topic.strip():
                problems.append("강의 주제를 입력해 주세요.")
            if not selected_transcript_paths:
                problems.append("전사본을 한 개 이상 선택해 주세요.")
            if problems:
                for problem in problems:
                    st.error(problem)
                return
            try:
                summary_path = validate_drive_selection([Path(selected_summary_path)], roots.summaries)[0]
                transcript_paths = validate_drive_selection(
                    [Path(value) for value in selected_transcript_paths], roots.transcripts
                )
            except ValueError as exc:
                st.error(str(exc))
                return
            _submit_request(
                manager,
                SummaryRequest(
                    course=course,
                    professor=professor.strip(),
                    topic=topic.strip(),
                    lecture_date=lecture_date,
                    summary_path=summary_path,
                    transcript_paths=transcript_paths,
                ),
            )
        return

    with st.form("create-upload-note", clear_on_submit=False):
        left, right = st.columns(2)
        with left:
            professor = st.text_input("담당 교수", placeholder="예: 홍길동 교수")
            lecture_date = st.date_input("강의일", value=date.today())
        with right:
            topic = st.text_input("강의 주제", placeholder="예: Staphylococcus")
        summary = st.file_uploader(
            "수업 요약본",
            type=sorted(extension.lstrip(".") for extension in CURRENT_SUMMARY_EXTENSIONS),
            accept_multiple_files=False,
            help="PDF는 글자만 추출하며 이미지와 스캔 그림은 사용하지 않습니다.",
        )
        transcripts = st.file_uploader(
            "수업 전사본",
            type=sorted(extension.lstrip(".") for extension in TRANSCRIPT_EXTENSIONS),
            accept_multiple_files=True,
            help="한 강의가 여러 전사 파일로 나뉘었다면 모두 선택하세요.",
        )
        submitted = st.form_submit_button(
            "정리본 만들기", type="primary", icon=":material/auto_awesome:"
        )
    if submitted:
        problems = []
        if not professor.strip():
            problems.append("담당 교수를 입력해 주세요.")
        if not topic.strip():
            problems.append("강의 주제를 입력해 주세요.")
        if summary is None:
            problems.append("수업 요약본을 올려 주세요.")
        if not transcripts:
            problems.append("전사본을 한 개 이상 올려 주세요.")
        if problems:
            for problem in problems:
                st.error(problem)
            return
        summary_path, transcript_paths = _save_uploads(paths, summary, transcripts)
        _submit_request(
            manager,
            SummaryRequest(
                course=course,
                professor=professor.strip(),
                topic=topic.strip(),
                lecture_date=lecture_date,
                summary_path=summary_path,
                transcript_paths=transcript_paths,
            ),
        )


def _references_tab(paths: StoragePaths, library: ReferenceLibrary) -> None:
    st.subheader("기본 참고자료", anchor=False)
    st.caption("족보·학습가이드·시간표는 과목별 출제 경향과 중요도 판단에만 씁니다.")
    with st.form("add-references", clear_on_submit=True):
        left, right = st.columns(2)
        with left:
            kind_label = st.segmented_control(
                "자료 종류", [item.value for item in ReferenceKind], default=ReferenceKind.EXAM.value
            )
        with right:
            course = st.selectbox("적용 과목", ("공통", *COURSES), key="reference-course")
        uploads = st.file_uploader(
            "참고자료 파일",
            type=sorted(extension.lstrip(".") for extension in SUPPORTED_EXTENSIONS),
            accept_multiple_files=True,
            help="PDF·TXT·MD·HTML·DOCX·CSV·XLSX를 지원합니다. 이미지로만 된 PDF는 제외됩니다.",
        )
        add = st.form_submit_button("참고자료 등록", icon=":material/library_add:")

    if add:
        if not uploads:
            st.error("등록할 파일을 선택해 주세요.")
        else:
            staging = paths.root / "reference-uploads" / uuid.uuid4().hex
            added = 0
            for upload in uploads:
                try:
                    source = save_bytes(upload.getvalue(), upload.name, staging)
                    library.add(source, ReferenceKind(kind_label), course)
                    added += 1
                except Exception as exc:
                    st.error(f"{upload.name}: {exc}")
            if added:
                st.success(f"참고자료 {added}개를 등록했습니다. 다음 생성 때 과목 프로필을 갱신합니다.")

    records = library.records()
    if not records:
        st.info("아직 등록된 참고자료가 없습니다.", icon=":material/info:")
        return
    st.markdown("#### 등록된 자료")
    st.dataframe(
        [
            {
                "종류": record.kind.value,
                "과목": record.course,
                "파일": record.original_name,
                "등록 시각": record.added_at.strftime("%Y-%m-%d %H:%M"),
            }
            for record in reversed(records)
        ],
        width="stretch",
        hide_index=True,
    )
    st.caption("같은 과목의 자료 구성이 바뀔 때만 출제 경향 프로필을 다시 분석합니다.")


def _job_result(record, manager: JobManager | None = None) -> None:
    st.markdown(f"#### {record.label}")
    now = datetime.now()
    timing = _job_timing(record, now=now)
    terminal = record.status in _TERMINAL_JOB_STATUSES
    state = "complete" if record.status == "완료" else "error" if terminal else "running"
    latest_message = (
        record.events[-1].message
        if record.events
        else record.messages[-1]
        if record.messages
        else "기록된 진행 사항이 없습니다."
    )
    if terminal:
        status_label = f"{record.status} · 총 {_format_duration(timing['total'])}"
    else:
        status_label = (
            f"{record.status} · 현재 활동 {_format_duration(timing['current'])} 경과"
        )

    with st.status(status_label, state=state, expanded=not terminal):
        st.markdown(f"**현재 사항:** {latest_message}")
        if record.events:
            st.caption("최근 기록부터 표시합니다. ‘소요’는 다음 사항으로 넘어갈 때까지의 시간입니다.")
            for index in range(len(record.events) - 1, -1, -1):
                event = record.events[index]
                since_created = _seconds_between(record.created_at, event.created_at)
                next_event_at = (
                    record.events[index + 1].created_at
                    if index + 1 < len(record.events)
                    else None
                )
                if next_event_at is not None:
                    duration = f"소요 {_format_duration(_seconds_between(event.created_at, next_event_at))}"
                elif not terminal:
                    duration = f"진행 {_format_duration(_seconds_between(event.created_at, now))}"
                else:
                    duration = "종료"
                st.caption(
                    f"{event.created_at:%H:%M:%S} · +{_format_duration(since_created)} · "
                    f"{duration} · {event.status} · {event.message}"
                )
        elif record.messages:
            st.caption("이전 버전에서 만든 작업은 진행 시각 없이 메시지만 표시됩니다.")
            for message in reversed(record.messages):
                st.caption(message)

    with st.container(horizontal=True):
        st.metric(
            "전체 소요" if terminal else "전체 경과",
            _format_duration(timing["total"]),
            icon=":material/schedule:",
            border=True,
        )
        st.metric(
            "대기 시간",
            _format_duration(timing["queued"]),
            icon=":material/hourglass_top:",
            border=True,
        )
        st.metric(
            "실행 소요" if terminal else "실행 경과",
            _format_duration(timing["running"]),
            icon=":material/timer:",
            border=True,
        )
    st.caption(
        f"접수 {record.created_at:%Y-%m-%d %H:%M:%S}"
        + (f" · 완료 {record.finished_at:%Y-%m-%d %H:%M:%S}" if record.finished_at else "")
    )
    if record.error:
        st.error(record.error)

    markdown_ready = record.markdown_path.is_file()
    html_ready = record.html_path.is_file()
    if (
        manager is not None
        and record.status in {"실패", "중단됨"}
        and markdown_ready
        and html_ready
        and st.button("기존 결과를 Drive에 다시 저장", key=f"republish-{record.job_id}")
    ):
        try:
            manager.publish_existing(record.job_id)
            st.success("Drive 저장을 완료했습니다.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if markdown_ready or html_ready:
        buttons = st.columns(2)
        if markdown_ready:
            buttons[0].download_button(
                "MD 받기",
                data=record.markdown_path.read_bytes(),
                file_name=record.markdown_path.name,
                mime="text/markdown",
                icon=":material/download:",
                width="stretch",
            )
        if html_ready:
            buttons[1].download_button(
                "HTML 받기",
                data=record.html_path.read_bytes(),
                file_name=record.html_path.name,
                mime="text/html",
                icon=":material/download:",
                width="stretch",
            )
            with st.expander("HTML 미리보기", expanded=record.status == "완료"):
                st.iframe(record.html_path, height=760)
    if record.drive_html_path:
        st.caption(f"Drive 저장 위치: {record.drive_html_path.parent}")


def _results_tab(manager: JobManager) -> None:
    st.subheader("결과", anchor=False)
    records = manager.all()
    if not records:
        st.info("아직 생성 작업이 없습니다.", icon=":material/inbox:")
        return
    ids = [record.job_id for record in records]
    selected = st.session_state.get("selected_job")
    index = ids.index(selected) if selected in ids else 0
    selected_id = st.selectbox(
        "작업 선택",
        ids,
        index=index,
        format_func=lambda value: next(
            f"{item.label} · {item.status}" for item in records if item.job_id == value
        ),
    )
    st.session_state["selected_job"] = selected_id

    selected_record = manager.get(selected_id)
    auto_refresh = bool(
        selected_record and selected_record.status not in _TERMINAL_JOB_STATUSES
    )
    if auto_refresh:
        st.caption("진행 시간과 사항은 2초마다 자동으로 갱신됩니다.")

    @st.fragment(run_every="2s" if auto_refresh else None)
    def live_result(job_id: str) -> None:
        record = manager.get(job_id)
        if record:
            _job_result(record, manager)
            if auto_refresh and record.status in _TERMINAL_JOB_STATUSES:
                st.rerun()

    live_result(selected_id)


def _settings_tab(paths: StoragePaths, setup: DriveShortcutSetup) -> None:
    st.subheader("연결 설정", anchor=False)
    output = default_mounted_output()
    if output and output.parent.is_dir():
        st.success(f"결과 저장 폴더 연결됨: {output}", icon=":material/cloud_done:")
    else:
        st.warning(
            "Gmail Google Drive 데스크톱 폴더를 찾지 못했습니다. "
            "Google Drive for desktop에서 oya1130@gmail.com 계정을 연결하거나 "
            "SUMMED_DRIVE_OUTPUT 환경변수를 지정해 주세요.",
            icon=":material/cloud_off:",
        )

    st.markdown("#### KHU 드라이브 바로가기 (최초 1회)")
    st.caption(
        "Google은 계정별 승인을 요구하므로 OAuth 데스크톱 클라이언트 JSON 등록과 두 번의 로그인이 필요합니다. "
        "인증 파일과 토큰은 이 PC에만 저장됩니다."
    )
    client = st.file_uploader("Google OAuth 클라이언트 JSON", type=["json"], key="oauth-client")
    if st.button("OAuth JSON 저장", disabled=client is None, icon=":material/key:"):
        try:
            setup.save_client_credentials(client.getvalue())
            st.success("OAuth 클라이언트 정보를 저장했습니다.")
        except Exception as exc:
            st.error(str(exc))

    left, right = st.columns(2)
    gmail_connected = setup.connected(GMAIL_ACCOUNT)
    khu_connected = setup.connected(KHU_ACCOUNT)
    with left:
        st.write(f"{'✅' if gmail_connected else '⬜'} {GMAIL_ACCOUNT}")
        if st.button("Gmail 계정 연결", disabled=gmail_connected, icon=":material/login:"):
            try:
                setup.connect(GMAIL_ACCOUNT)
                st.success("Gmail 계정을 연결했습니다.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    with right:
        st.write(f"{'✅' if khu_connected else '⬜'} {KHU_ACCOUNT}")
        if st.button("KHU 계정 연결", disabled=khu_connected, icon=":material/login:"):
            try:
                setup.connect(KHU_ACCOUNT)
                st.success("KHU 계정을 연결했습니다.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    if st.button(
        "폴더 공유 및 바로가기 만들기",
        type="primary",
        disabled=not (gmail_connected and khu_connected),
        icon=":material/add_to_drive:",
    ):
        try:
            result = setup.create_folder_share_and_shortcut()
            st.success("Gmail의 summed 폴더를 KHU 계정과 공유하고 내 드라이브 바로가기를 만들었습니다.")
            st.link_button("Gmail 결과 폴더 열기", result["folder_url"], icon=":material/open_in_new:")
        except Exception as exc:
            st.error(str(exc))

    with st.expander("고급 정보"):
        st.code(f"데이터 폴더: {paths.root}\nCodex 모델: {os.environ.get('SUMMED_CODEX_MODEL') or '로그인 계정 기본값'}")


def run() -> None:
    st.set_page_config(
        page_title="summed · 의학 강의 정리",
        page_icon=":material/summarize:",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    paths, library, manager, setup = _resources()
    codex_ok, codex_message = _codex_status()

    with st.sidebar:
        st.title("summed")
        st.caption("족보의 방향성, 수업 자료의 사실성")
        if codex_ok:
            st.success("ChatGPT 구독 로그인", icon=":material/verified_user:")
        else:
            st.error("Codex 로그인이 필요합니다", icon=":material/account_circle:")
            st.code("codex login")
            if codex_message:
                st.caption(codex_message)
        output = default_mounted_output()
        if output and output.parent.is_dir():
            st.info("Gmail Drive 저장 준비됨", icon=":material/cloud_done:")
        st.caption(f"동시 생성: 최대 {configured_concurrency()}개")
        st.divider()
        st.caption("이미지는 입력·출력에서 제외합니다. 결과 분량은 요약본의 20~30%를 목표로 합니다.")

    st.title("강의 정리본 만들기", anchor=False)
    st.caption("파일을 직접 올리고, Codex 구독 사용량으로 과목별 핵심과 출제 포인트를 압축합니다.")
    new_tab, references_tab, results_tab, settings_tab = st.tabs(
        ["새 정리본", "기본 참고자료", "결과", "설정"],
        key="main-tabs",
        on_change="rerun",
    )
    if new_tab.open:
        with new_tab:
            _new_note_tab(paths, manager)
    if references_tab.open:
        with references_tab:
            _references_tab(paths, library)
    if results_tab.open:
        with results_tab:
            _results_tab(manager)
    if settings_tab.open:
        with settings_tab:
            _settings_tab(paths, setup)
