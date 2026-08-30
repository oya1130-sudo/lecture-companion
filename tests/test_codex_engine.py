import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from prestudy.ai import CodexExecutionError, CodexStudyEngine, _strict_schema


class MiniResult(BaseModel):
    status: str


def test_strict_schema_disallows_extra_properties():
    schema = _strict_schema(MiniResult)
    assert schema["additionalProperties"] is False


def test_codex_engine_uses_subscription_and_structured_output(monkeypatch, tmp_path: Path):
    commands = []
    environments = []

    def fake_run(command, **kwargs):
        commands.append(command)
        environments.append(kwargs.get("env", {}))
        if command[1:3] == ["login", "status"]:
            return SimpleNamespace(returncode=0, stdout="Logged in using ChatGPT\n", stderr="")
        output_index = command.index("--output-last-message") + 1
        Path(command[output_index]).write_text(json.dumps({"status": "ok"}), encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("prestudy.ai.shutil.which", lambda _: "codex")
    monkeypatch.setattr("prestudy.ai.subprocess.run", fake_run)
    engine = CodexStudyEngine(work_root=tmp_path)
    result = engine._run_structured("return ok", MiniResult)

    assert result.status == "ok"
    exec_command = commands[-1]
    assert exec_command[-1] == "-"
    assert environments
    assert "--ignore-user-config" not in exec_command
    assert "--ignore-rules" not in exec_command
    assert exec_command[exec_command.index("--sandbox") + 1] == "workspace-write"
    for environment in environments:
        assert "OPENAI_API_KEY" not in environment
        assert "CODEX_API_KEY" not in environment
        assert "CODEX_ACCESS_TOKEN" not in environment

    assert commands[-1][-1] == "-"


def test_codex_engine_rejects_api_key_login(monkeypatch, tmp_path: Path):
    def fake_run(command, **kwargs):
        return SimpleNamespace(returncode=0, stdout="Logged in using API key\n", stderr="")

    monkeypatch.setattr("prestudy.ai.shutil.which", lambda _: "codex")
    monkeypatch.setattr("prestudy.ai.subprocess.run", fake_run)
    with pytest.raises(CodexExecutionError, match="ChatGPT 구독 로그인"):
        CodexStudyEngine(work_root=tmp_path)
