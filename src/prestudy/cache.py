from __future__ import annotations

import hashlib
import json
import threading
import uuid
from pathlib import Path

from .models import LectureRequest, SourceDigest, SourceDocument, StudyGuide
from .prompts import PROMPT_VERSION, SYNTHESIS_VERSION
from .storage import CACHE_ROOT


_CACHE_LOCK = threading.RLock()


def _atomic_write(path: Path, payload: str) -> None:
    temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)


class DigestCache:
    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root is not None else CACHE_ROOT
        self.root.mkdir(parents=True, exist_ok=True)

    def key(
        self,
        source: SourceDocument,
        model: str,
        lecture: LectureRequest | None = None,
    ) -> str:
        digest = hashlib.sha256()
        with source.path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(source.kind.value.encode("utf-8"))
        digest.update(model.encode("utf-8"))
        digest.update(PROMPT_VERSION.encode("utf-8"))
        if lecture is not None:
            digest.update(lecture.model_dump_json().encode("utf-8"))
        return digest.hexdigest()

    def get(self, key: str) -> SourceDigest | None:
        path = self.root / f"{key}.json"
        with _CACHE_LOCK:
            if not path.exists():
                return None
            return SourceDigest.model_validate_json(path.read_text(encoding="utf-8"))

    def put(self, key: str, value: SourceDigest) -> None:
        path = self.root / f"{key}.json"
        payload = json.dumps(value.model_dump(mode="json"), ensure_ascii=False, indent=2)
        with _CACHE_LOCK:
            _atomic_write(path, payload)


class GuideCache:
    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root is not None else CACHE_ROOT
        self.root.mkdir(parents=True, exist_ok=True)

    def key(self, lecture: LectureRequest, model: str, source_keys: list[str]) -> str:
        digest = hashlib.sha256()
        digest.update(lecture.model_dump_json().encode("utf-8"))
        digest.update(model.encode("utf-8"))
        digest.update(SYNTHESIS_VERSION.encode("utf-8"))
        for source_key in source_keys:
            digest.update(source_key.encode("ascii"))
        return digest.hexdigest()

    def get(self, key: str) -> StudyGuide | None:
        path = self.root / f"guide-{key}.json"
        with _CACHE_LOCK:
            if not path.exists():
                return None
            return StudyGuide.model_validate_json(path.read_text(encoding="utf-8"))

    def put(self, key: str, value: StudyGuide) -> None:
        path = self.root / f"guide-{key}.json"
        payload = json.dumps(value.model_dump(mode="json"), ensure_ascii=False, indent=2)
        with _CACHE_LOCK:
            _atomic_write(path, payload)
