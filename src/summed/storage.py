from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


COURSES = ("미생물학", "병리학", "약리학", "예방의학", "의동물학")


@dataclass(frozen=True)
class StoragePaths:
    root: Path
    references: Path
    jobs: Path
    outputs: Path
    oauth: Path

    @classmethod
    def discover(cls) -> "StoragePaths":
        configured = os.environ.get("SUMMED_HOME", "").strip()
        root = Path(configured).expanduser() if configured else Path.home() / ".summed"
        root = root.resolve()
        return cls(
            root=root,
            references=root / "references",
            jobs=root / "jobs",
            outputs=root / "outputs",
            oauth=root / "oauth",
        )

    def ensure(self) -> "StoragePaths":
        for path in (self.root, self.references, self.jobs, self.outputs, self.oauth):
            path.mkdir(parents=True, exist_ok=True)
        return self
