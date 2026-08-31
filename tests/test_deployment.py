from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_compose_is_private_single_instance_with_persistent_data():
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    app = compose["services"]["app"]

    assert app["ports"] == ["127.0.0.1:8501:8501"]
    assert app["environment"]["PRESTUDY_HOME"] == "/data"
    assert app["environment"]["CODEX_HOME"] == "/data/codex"
    assert app["volumes"] == ["lecture-data:/data"]
    assert compose["volumes"]["lecture-data"]["name"] == "lecture-companion-data"


def test_container_uses_non_root_user_and_separates_runtime_credentials():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "USER lecture" in dockerfile
    assert "PRESTUDY_HOME=/data" in dockerfile
    assert "CODEX_HOME=/data/codex" in dockerfile
    assert "CODEX_INSTALL_DIR=/usr/local/bin" in dockerfile
    assert "https://chatgpt.com/codex/install.sh" in dockerfile


def test_docker_context_excludes_secrets_and_user_data():
    ignored = {
        line.strip()
        for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }

    assert {".env", ".streamlit/secrets.toml", "credentials.json", "token.json", "*.pdf"} <= ignored


def test_oracle_free_profile_uses_conservative_concurrency():
    profile = (ROOT / ".env.oracle.example").read_text(encoding="utf-8")

    assert "PRESTUDY_JOB_WORKERS=2" in profile
    assert "PRESTUDY_SOURCE_WORKERS=2" in profile
    assert "PRESTUDY_CODEX_CONCURRENCY=1" in profile


def test_ci_builds_and_runs_container_on_native_arm64():
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    )
    matrix = workflow["jobs"]["docker"]["strategy"]["matrix"]["include"]

    assert {"arch": "arm64", "runner": "ubuntu-24.04-arm"} in matrix


def test_windows_launcher_reopens_or_starts_app_then_opens_browser():
    launcher = (ROOT / "run.ps1").read_text(encoding="utf-8")

    assert "if (Test-AppHealth -Attempts 4)" in launcher
    assert "UseShellExecute = $true" in launcher
    assert "Start-Process `\n    -FilePath $pythonCommand" in launcher
    assert "--server.headless', 'true'" in launcher
    assert "Start-Process -FilePath 'powershell.exe'" not in launcher
