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
