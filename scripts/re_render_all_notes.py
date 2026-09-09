from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root and src to sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from summed.backfill_quizzes import _request_and_sources, _storage_paths, discover_artifacts
from summed.models import SummedNote
from summed.renderer import render_html


def re_render_all():
    paths = _storage_paths()
    artifacts = discover_artifacts(paths)
    print(f"Found {len(artifacts)} artifacts to re-render.")

    google_drive_root = Path("G:/내 드라이브/summed")
    re_rendered_count = 0

    for artifact in artifacts:
        # 1. Locate best result.json (quiz-backfill preferred, then generation)
        res_path = artifact.source_job / "quiz-backfill" / "result.json"
        if not res_path.exists():
            res_path = artifact.source_job / "generation" / "result.json"

        if not res_path.exists():
            print(f"[SKIP] No result.json found for {artifact.html_path.name}")
            continue

        data = json.loads(res_path.read_text(encoding="utf-8"))
        note = SummedNote.model_validate(data)

        # 2. Locate corresponding markdown file for metadata
        markdown_path = artifact.html_path.with_suffix(".md")
        if not markdown_path.exists():
            # Check inside job.json
            job_record = json.loads((artifact.source_job / "job.json").read_text(encoding="utf-8"))
            if "markdown_path" in job_record and Path(job_record["markdown_path"]).exists():
                markdown_path = Path(job_record["markdown_path"])

        request, sources = _request_and_sources(artifact, markdown_path)

        # 3. Special handling for 병리학 1주차(A) which has the customized rich matrix/pipeline visualization
        if "병리학 1주차(A)" in artifact.html_path.name:
            import subprocess
            v2_gen = Path(r"C:\Users\oya11\.gemini\antigravity\brain\334c1273-e627-4152-8eea-e2758c9e43b9\scratch\generate_v2_enhanced.py")
            if v2_gen.exists():
                subprocess.run([sys.executable, "-X", "utf8", str(v2_gen)], check=True)
                print(f"[OK] Preserved rich matrix/pipeline version: {artifact.html_path.name}")
                re_rendered_count += 1
                continue

        # 3. Render HTML to local output path
        render_html(note, request, sources, artifact.html_path)
        print(f"[OK] Re-rendered: {artifact.html_path.name} ({artifact.html_path.stat().st_size:,} bytes)")
        re_rendered_count += 1

        # 4. Sync to Google Drive
        course_name = artifact.html_path.parent.name
        drive_dest = google_drive_root / course_name / artifact.html_path.name
        if google_drive_root.is_dir():
            drive_dest.parent.mkdir(parents=True, exist_ok=True)
            drive_dest.write_text(artifact.html_path.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"     -> Synced to Google Drive: {drive_dest}")

    print(f"\nAll done! Successfully re-rendered {re_rendered_count} files with high-scanability card design.")


if __name__ == "__main__":
    re_render_all()

