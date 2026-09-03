from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path

from .files import copy_unique, safe_filename, sha256_file, write_extracted_text
from .models import ReferenceKind, ReferenceRecord


class ReferenceLibrary:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.raw_root = root / "raw"
        self.text_root = root / "text"
        self.index_path = root / "index.json"
        self.profile_root = root / "profiles"
        self._lock = threading.RLock()

    def records(self) -> list[ReferenceRecord]:
        with self._lock:
            if not self.index_path.is_file():
                return []
            try:
                data = json.loads(self.index_path.read_text(encoding="utf-8"))
                return [ReferenceRecord.model_validate(item) for item in data.get("records", [])]
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                return []

    def _save(self, records: list[ReferenceRecord]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "records": [item.model_dump(mode="json") for item in records],
        }
        temporary = self.index_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.index_path)

    def add(self, source: Path, kind: ReferenceKind, course: str) -> ReferenceRecord:
        digest = sha256_file(source)
        with self._lock:
            existing = self.records()
            for record in existing:
                if record.sha256 == digest and record.kind == kind and record.course == course:
                    return record
            record_id = uuid.uuid4().hex[:12]
            category = f"{kind.value}-{course}"
            stored = copy_unique(source, self.raw_root / safe_filename(category))
            text_path = self.text_root / safe_filename(category) / f"{record_id}-{stored.stem}.txt"
            write_extracted_text(stored, text_path)
            record = ReferenceRecord(
                id=record_id,
                kind=kind,
                course=course,
                original_name=source.name,
                source_path=stored.resolve(),
                text_path=text_path.resolve(),
                sha256=digest,
                added_at=datetime.now(),
            )
            existing.append(record)
            self._save(existing)
            return record

    def relevant(self, course: str) -> list[ReferenceRecord]:
        return [record for record in self.records() if record.course in {course, "공통"}]

    def fingerprint(self, course: str, model: str) -> str:
        values = [f"{item.id}:{item.sha256}:{item.kind.value}" for item in self.relevant(course)]
        import hashlib

        return hashlib.sha256((course + "|" + model + "|" + "|".join(sorted(values))).encode()).hexdigest()

    def profile_path(self, course: str, fingerprint: str) -> Path:
        return self.profile_root / safe_filename(course) / f"{fingerprint}.json"
