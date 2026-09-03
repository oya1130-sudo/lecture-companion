from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_this_project_has_a_dedicated_summed_entrypoint_and_port():
    summed_entry = (ROOT / "app.py").read_text(encoding="utf-8")
    runner = (ROOT / "run-program.ps1").read_text(encoding="utf-8")

    assert "from summed.web import run" in summed_entry
    assert "$port = 8502" in runner
    assert "$port = 8501" not in runner
    assert "SUMMED_SUMMARY_ROOT" in runner
    assert "SUMMED_TRANSCRIPT_ROOT" in runner
    assert "CreateShortcut" in runner


def test_windows_launchers_target_summed_runner():
    default_launcher = (ROOT / "start-app.cmd").read_text(encoding="utf-8")
    summed_launcher = (ROOT / "start-summed.cmd").read_text(encoding="utf-8")

    assert "run.ps1" in default_launcher
    assert "run-summed.ps1" in summed_launcher
