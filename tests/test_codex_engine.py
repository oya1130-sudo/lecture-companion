import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, Field

from prestudy.ai import CodexExecutionError, CodexStudyEngine, _strict_schema
from prestudy.models import LectureRequest, StudyGuide


class MiniResult(BaseModel):
    status: str


class DefaultedResult(BaseModel):
    status: str
    importance: int = 0
    tags: list[str] = Field(default_factory=list)


def test_strict_schema_disallows_extra_properties():
    schema = _strict_schema(MiniResult)
    assert schema["additionalProperties"] is False


def test_strict_schema_requires_defaulted_fields_and_removes_defaults():
    schema = _strict_schema(DefaultedResult)

    assert schema["required"] == ["status", "importance", "tags"]
    assert "default" not in schema["properties"]["importance"]


def test_study_guide_schema_requires_every_property_recursively():
    def assert_strict(value):
        if isinstance(value, dict):
            assert "default" not in value
            if value.get("type") == "object":
                assert value["required"] == list(value.get("properties", {}))
            for child in value.values():
                assert_strict(child)
        elif isinstance(value, list):
            for child in value:
                assert_strict(child)

    assert_strict(_strict_schema(StudyGuide))


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
    config_index = exec_command.index("--config") + 1
    assert exec_command[config_index] == 'model_reasoning_effort="low"'
    for environment in environments:
        assert "OPENAI_API_KEY" not in environment
        assert "CODEX_API_KEY" not in environment
        assert "CODEX_ACCESS_TOKEN" not in environment

    assert commands[-1][-1] == "-"


def test_codex_engine_accepts_reasoning_effort_override(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("prestudy.ai.shutil.which", lambda _: "codex")
    monkeypatch.setattr(
        "prestudy.ai.subprocess.run",
        lambda command, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="Logged in using ChatGPT\n",
            stderr="",
        ),
    )

    engine = CodexStudyEngine(work_root=tmp_path, reasoning_effort="medium")

    assert engine.reasoning_effort == "medium"


def test_codex_engine_uses_bounded_default_timeouts(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("prestudy.ai.shutil.which", lambda _: "codex")
    monkeypatch.setattr(
        "prestudy.ai.subprocess.run",
        lambda command, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="Logged in using ChatGPT\n",
            stderr="",
        ),
    )

    engine = CodexStudyEngine(work_root=tmp_path)

    assert engine.timeout_seconds == 600
    assert engine.synthesis_timeout_seconds == 600


def test_codex_engine_falls_back_after_default_model_timeout(
    monkeypatch,
    tmp_path: Path,
):
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        if command[1:3] == ["login", "status"]:
            return SimpleNamespace(returncode=0, stdout="Logged in using ChatGPT\n", stderr="")
        if "--model" not in command:
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        output_index = command.index("--output-last-message") + 1
        Path(command[output_index]).write_text(json.dumps({"status": "ok"}), encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("prestudy.ai.shutil.which", lambda _: "codex")
    monkeypatch.setattr("prestudy.ai.subprocess.run", fake_run)
    engine = CodexStudyEngine(work_root=tmp_path, timeout_seconds=1)
    messages = []

    result = engine._run_structured("return ok", MiniResult, progress=messages.append)

    assert result.status == "ok"
    assert any("제한을 초과하여 gpt-5.6-luna로 자동 전환" in message for message in messages)
    assert commands[-1][commands[-1].index("--model") + 1] == "gpt-5.6-luna"


def test_default_synthesis_prefers_fast_model_with_ten_minute_limit(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setattr("prestudy.ai.shutil.which", lambda _: "codex")
    monkeypatch.setattr(
        "prestudy.ai.subprocess.run",
        lambda command, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="Logged in using ChatGPT\n",
            stderr="",
        ),
    )
    engine = CodexStudyEngine(work_root=tmp_path)
    captured = {}
    sentinel = object()

    def fake_structured(prompt, output_model, **kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(engine, "_run_structured", fake_structured)
    lecture = LectureRequest(course="미생물학", professor="안현종", topic="Enterococcus")

    result = engine.synthesize(lecture, [])

    assert result is sentinel
    assert captured["preferred_model"] == "gpt-5.6-luna"
    assert captured["timeout_seconds"] == 600


def test_codex_engine_falls_back_when_default_model_is_at_capacity(
    monkeypatch,
    tmp_path: Path,
):
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        if command[1:3] == ["login", "status"]:
            return SimpleNamespace(returncode=0, stdout="Logged in using ChatGPT\n", stderr="")
        if "--model" not in command:
            return SimpleNamespace(
                returncode=1,
                stdout="",
                stderr="ERROR: Selected model is at capacity. Please try a different model.",
            )
        output_index = command.index("--output-last-message") + 1
        Path(command[output_index]).write_text(json.dumps({"status": "ok"}), encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("prestudy.ai.shutil.which", lambda _: "codex")
    monkeypatch.setattr("prestudy.ai.subprocess.run", fake_run)
    engine = CodexStudyEngine(work_root=tmp_path)

    result = engine._run_structured("return ok", MiniResult)

    assert result.status == "ok"
    fallback_command = commands[-1]
    model_index = fallback_command.index("--model") + 1
    assert fallback_command[model_index] == "gpt-5.6-luna"


def test_codex_engine_rejects_api_key_login(monkeypatch, tmp_path: Path):
    def fake_run(command, **kwargs):
        return SimpleNamespace(returncode=0, stdout="Logged in using API key\n", stderr="")

    monkeypatch.setattr("prestudy.ai.shutil.which", lambda _: "codex")
    monkeypatch.setattr("prestudy.ai.subprocess.run", fake_run)
    with pytest.raises(CodexExecutionError, match="ChatGPT 구독 로그인"):
        CodexStudyEngine(work_root=tmp_path)
