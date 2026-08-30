from __future__ import annotations

import io
import re
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def folder_id(value: str) -> str:
    value = value.strip()
    match = re.search(r"/folders/([A-Za-z0-9_-]+)", value)
    return match.group(1) if match else value


def safe_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip() or "document.pdf"


class GoogleDriveReader:
    def __init__(self, credentials_path: Path, token_path: Path) -> None:
        self.credentials_path = credentials_path
        self.token_path = token_path

    def _credentials(self):
        credentials = None
        if self.token_path.exists():
            credentials = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        elif not credentials or not credentials.valid:
            if not self.credentials_path.exists():
                raise FileNotFoundError(f"Google OAuth 파일이 없습니다: {self.credentials_path}")
            flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), SCOPES)
            credentials = flow.run_local_server(port=0)
        self.token_path.write_text(credentials.to_json(), encoding="utf-8")
        return credentials

    def download_pdfs(
        self,
        drive_folder: str,
        destination: Path,
        name_contains: str = "",
    ) -> list[Path]:
        service = build("drive", "v3", credentials=self._credentials(), cache_discovery=False)
        destination.mkdir(parents=True, exist_ok=True)
        query = (
            f"'{folder_id(drive_folder)}' in parents and trashed = false "
            "and mimeType = 'application/pdf'"
        )
        files: list[dict] = []
        page_token = None
        while True:
            result = service.files().list(
                q=query,
                spaces="drive",
                fields="nextPageToken, files(id, name, modifiedTime)",
                orderBy="name",
                pageToken=page_token,
            ).execute()
            files.extend(result.get("files", []))
            page_token = result.get("nextPageToken")
            if not page_token:
                break

        if name_contains.strip():
            needle = name_contains.strip().casefold()
            files = [item for item in files if needle in item["name"].casefold()]

        paths = []
        for item in files:
            path = destination / safe_filename(item["name"])
            request = service.files().get_media(fileId=item["id"])
            with path.open("wb") as stream:
                downloader = MediaIoBaseDownload(stream, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
            paths.append(path)
        return paths
