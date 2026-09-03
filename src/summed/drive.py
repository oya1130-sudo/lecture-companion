from __future__ import annotations

import json
import os
import shutil
import string
import uuid
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .files import MARKDOWN_FOLDER_NAME, safe_filename


FULL_DRIVE_SCOPE = ["https://www.googleapis.com/auth/drive"]
GMAIL_ACCOUNT = "oya1130@gmail.com"
KHU_ACCOUNT = "oya1130@khu.ac.kr"
OUTPUT_FOLDER_NAME = "summed"


def _mounted_my_drive_candidates() -> list[Path]:
    candidates = []
    for letter in string.ascii_uppercase:
        path = Path(f"{letter}:/내 드라이브")
        try:
            if path.is_dir():
                candidates.append(path)
        except OSError:
            continue
    return candidates


def _volume_label(path: Path) -> str:
    if os.name != "nt":
        return ""
    try:
        import ctypes

        label = ctypes.create_unicode_buffer(261)
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            f"{path.drive}\\",
            label,
            len(label),
            None,
            None,
            None,
            None,
            0,
        )
        return label.value if ok else ""
    except (AttributeError, OSError, ValueError):
        return ""


def default_mounted_output() -> Path | None:
    configured = os.environ.get("SUMMED_DRIVE_OUTPUT", "").strip()
    if configured:
        candidate = Path(configured).expanduser().resolve()
        return candidate if candidate.parent.is_dir() else None

    candidates = _mounted_my_drive_candidates()
    if not candidates:
        return None
    gmail = next(
        (
            candidate
            for candidate in candidates
            if GMAIL_ACCOUNT.casefold() in _volume_label(candidate).casefold()
        ),
        None,
    )
    existing = next(
        (candidate for candidate in candidates if (candidate / OUTPUT_FOLDER_NAME).is_dir()),
        None,
    )
    preferred_letter = next((candidate for candidate in candidates if candidate.drive == "G:"), None)
    return (gmail or existing or preferred_letter or candidates[0]) / OUTPUT_FOLDER_NAME


class MountedDrivePublisher:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root if root is not None else default_mounted_output()

    def publish(self, paths: list[Path], course: str) -> list[Path]:
        if self.root is None:
            raise FileNotFoundError("Gmail Google Drive가 이 PC에 연결되어 있지 않습니다.")
        target_root = self.root / safe_filename(course)
        target_root.mkdir(parents=True, exist_ok=True)
        published = []
        for source in paths:
            destination = (
                target_root / MARKDOWN_FOLDER_NAME
                if source.suffix.casefold() == ".md"
                else target_root
            )
            destination.mkdir(parents=True, exist_ok=True)
            target = destination / source.name
            temporary = destination / f".{source.name}.{uuid.uuid4().hex}.uploading"
            try:
                shutil.copy2(source, temporary)
                temporary.replace(target)
            finally:
                if temporary.exists():
                    temporary.unlink()
            if target.stat().st_size != source.stat().st_size:
                raise OSError(f"Drive 저장 검증에 실패했습니다: {target.name}")
            published.append(target)
        return published


class DriveShortcutSetup:
    def __init__(self, credentials_path: Path, token_root: Path) -> None:
        self.credentials_path = credentials_path
        self.token_root = token_root

    def save_client_credentials(self, data: bytes) -> Path:
        try:
            payload = json.loads(data.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("올바른 Google OAuth JSON 파일이 아닙니다.") from exc
        if not isinstance(payload, dict) or not ({"installed", "web"} & payload.keys()):
            raise ValueError("Google Cloud의 OAuth 클라이언트 JSON이 필요합니다.")
        self.credentials_path.parent.mkdir(parents=True, exist_ok=True)
        self.credentials_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.credentials_path

    def _token_path(self, expected_email: str) -> Path:
        return self.token_root / ("gmail-token.json" if expected_email == GMAIL_ACCOUNT else "khu-token.json")

    def _credentials(self, expected_email: str, interactive: bool) -> Credentials:
        token_path = self._token_path(expected_email)
        credentials = None
        if token_path.is_file():
            credentials = Credentials.from_authorized_user_file(str(token_path), FULL_DRIVE_SCOPE)
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        elif not credentials or not credentials.valid:
            if not interactive:
                raise RuntimeError(f"{expected_email} 계정 인증이 필요합니다.")
            if not self.credentials_path.is_file():
                raise FileNotFoundError("먼저 Google OAuth 클라이언트 JSON을 등록해 주세요.")
            flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), FULL_DRIVE_SCOPE)
            credentials = flow.run_local_server(
                port=0,
                open_browser=True,
                prompt="consent select_account",
                login_hint=expected_email,
                authorization_prompt_message=f"브라우저에서 {expected_email} 계정을 선택해 주세요.",
            )
        service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        profile = service.about().get(fields="user(emailAddress,displayName)").execute()["user"]
        if profile.get("emailAddress", "").casefold() != expected_email.casefold():
            if token_path.exists():
                token_path.unlink()
            raise RuntimeError(
                f"잘못된 계정으로 로그인했습니다: {profile.get('emailAddress', '알 수 없음')}. "
                f"{expected_email} 계정으로 다시 시도해 주세요."
            )
        self.token_root.mkdir(parents=True, exist_ok=True)
        token_path.write_text(credentials.to_json(), encoding="utf-8")
        return credentials

    def connect(self, expected_email: str) -> str:
        credentials = self._credentials(expected_email, interactive=True)
        service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        return service.about().get(fields="user(emailAddress)").execute()["user"]["emailAddress"]

    def connected(self, expected_email: str) -> bool:
        try:
            self._credentials(expected_email, interactive=False)
            return True
        except Exception:
            return False

    @staticmethod
    def _find_output_folder(service) -> dict | None:
        escaped = OUTPUT_FOLDER_NAME.replace("'", "\\'")
        result = service.files().list(
            q=(
                f"name = '{escaped}' and 'root' in parents and trashed = false "
                "and mimeType = 'application/vnd.google-apps.folder'"
            ),
            spaces="drive",
            fields="files(id,name,webViewLink)",
            pageSize=20,
        ).execute()
        return next(iter(result.get("files", [])), None)

    def create_folder_share_and_shortcut(self) -> dict[str, str]:
        gmail = build(
            "drive", "v3", credentials=self._credentials(GMAIL_ACCOUNT, interactive=False), cache_discovery=False
        )
        folder = self._find_output_folder(gmail)
        if folder is None:
            folder = gmail.files().create(
                body={"name": OUTPUT_FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder", "parents": ["root"]},
                fields="id,name,webViewLink",
            ).execute()
        permissions = gmail.permissions().list(fileId=folder["id"], fields="permissions(id,emailAddress,role)").execute()
        if not any(
            item.get("emailAddress", "").casefold() == KHU_ACCOUNT.casefold()
            for item in permissions.get("permissions", [])
        ):
            gmail.permissions().create(
                fileId=folder["id"],
                body={"type": "user", "role": "writer", "emailAddress": KHU_ACCOUNT},
                sendNotificationEmail=False,
                fields="id",
            ).execute()

        khu = build(
            "drive", "v3", credentials=self._credentials(KHU_ACCOUNT, interactive=False), cache_discovery=False
        )
        khu.files().get(fileId=folder["id"], fields="id,name").execute()
        result = khu.files().list(
            q=(
                "'root' in parents and trashed = false and "
                "mimeType = 'application/vnd.google-apps.shortcut' and name = 'summed'"
            ),
            spaces="drive",
            fields="files(id,name,webViewLink,shortcutDetails(targetId))",
            pageSize=20,
        ).execute()
        shortcut = next(
            (
                item
                for item in result.get("files", [])
                if item.get("shortcutDetails", {}).get("targetId") == folder["id"]
            ),
            None,
        )
        if shortcut is None:
            shortcut = khu.files().create(
                body={
                    "name": OUTPUT_FOLDER_NAME,
                    "mimeType": "application/vnd.google-apps.shortcut",
                    "parents": ["root"],
                    "shortcutDetails": {"targetId": folder["id"]},
                },
                fields="id,name,webViewLink,shortcutDetails(targetId)",
            ).execute()
        return {
            "folder_id": folder["id"],
            "folder_url": folder.get("webViewLink", f"https://drive.google.com/drive/folders/{folder['id']}"),
            "shortcut_id": shortcut["id"],
            "shortcut_url": shortcut.get("webViewLink", f"https://drive.google.com/open?id={shortcut['id']}"),
        }
