from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.config import LLMBackend, Settings
from app.services import lesson_qa
from app.services.lesson_qa.backends import agy_cli, get_backend


@pytest.fixture
def cli(monkeypatch):
    monkeypatch.setattr(agy_cli.shutil, "which", lambda _name: "/fake/agy")
    monkeypatch.setattr(
        agy_cli, "get_settings", lambda: SimpleNamespace(agy_cli_model=None)
    )
    return agy_cli


def ask():
    return list(lesson_qa.ask(
        "Material de prueba", "Un pasaje", "¿Qué significa?",
        allow_insufficient=True, backend=agy_cli,
    ))


def result_event(response="Title: Una pregunta\n\nUna respuesta.", status="SUCCESS", **extra):
    return json.dumps({
        "event": "result",
        "result": {"status": status, "response": response, **extra},
    }, ensure_ascii=False)


def test_default_and_explicit_backend_selection(monkeypatch):
    monkeypatch.delenv("LEARNUP_LLM_BACKEND", raising=False)
    assert Settings(_env_file=None).llm_backend == LLMBackend.AGY_CLI
    assert get_backend("agy_cli") is agy_cli
    for name in ("codex_cli", "claude_cli", "openhands"):
        assert Settings(_env_file=None, llm_backend=name).llm_backend.value == name
    with pytest.raises(lesson_qa.LessonQAError, match="desconocido"):
        get_backend("missing_cli")


def test_agy_sends_unicode_context_on_stdin_in_temporary_directory(cli, monkeypatch):
    captured = {}
    monkeypatch.setattr(cli, "get_settings", lambda: SimpleNamespace(agy_cli_model="test-model"))

    def run(command, **kwargs):
        captured.update(command=command, kwargs=kwargs)
        assert Path(kwargs["cwd"]).is_dir()
        return SimpleNamespace(
            stdout='{"event":"init"}\n' + result_event() + '\n',
            stderr="", returncode=0,
        )

    monkeypatch.setattr(cli.subprocess, "run", run)
    assert ask() == [{"type": "result", "title": "Una pregunta", "answer": "Una respuesta."}]
    assert captured["command"] == [
        "/fake/agy", "--input-format", "stream-json", "--output-format", "stream-json",
        "--model", "test-model",
    ]
    kwargs = captured["kwargs"]
    message = json.loads(kwargs["input"])
    assert message["event"] == "user"
    assert "¿Qué significa?" in message["message"]["content"]
    assert "Material de prueba" in message["message"]["content"]
    assert kwargs["encoding"] == "utf-8"
    assert kwargs["timeout"] == cli.LESSON_QA_TIMEOUT_SECONDS
    assert not Path(kwargs["cwd"]).exists()


@pytest.mark.parametrize(("stdout", "stderr", "code", "match"), [
    (result_event(status="ERROR", error="authentication required"), "", 1, "authentication required"),
    (result_event(status="WAITING"), "", 0, "WAITING"),
    (result_event(), "fallo del proceso", 1, "fallo del proceso"),
    (result_event(response=""), "", 0, "vacía"),
    ('{"event":"result","result":null}', "", 0, "sin resultado final"),
    ('ruido\n[]\n', "sin sesión", 1, "sin sesión"),
    ('{"event":"step_update","step_update":{"text_delta":"parcial"}}', "", 0, "sin resultado final"),
])
def test_agy_rejects_incomplete_or_failed_output(cli, monkeypatch, stdout, stderr, code, match):
    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **k: SimpleNamespace(
        stdout=stdout, stderr=stderr, returncode=code,
    ))
    with pytest.raises(lesson_qa.LessonQAError, match=match):
        ask()


def test_agy_preserves_insufficient_context(cli, monkeypatch):
    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **k: SimpleNamespace(
        stdout=result_event(response="INSUFFICIENT_CONTEXT"), stderr="", returncode=0,
    ))
    assert ask() == [{"type": "insufficient"}]


def test_agy_reports_missing_executable(cli, monkeypatch):
    monkeypatch.setattr(cli.shutil, "which", lambda _name: None)
    with pytest.raises(lesson_qa.LessonQAError, match="No se encontró Antigravity"):
        ask()


@pytest.mark.parametrize("error", [subprocess.TimeoutExpired("agy", 180), OSError("no ejecutable")])
def test_agy_reports_execution_errors(cli, monkeypatch, error):
    def run(*args, **kwargs):
        raise error
    monkeypatch.setattr(cli.subprocess, "run", run)
    with pytest.raises(lesson_qa.LessonQAError):
        ask()


def test_agy_utf8_subprocess_roundtrip(cli, monkeypatch):
    run = subprocess.run
    monkeypatch.setattr(subprocess, "_text_encoding", lambda: "cp1252")
    child = (
        "import json, sys; "
        "message = json.loads(sys.stdin.buffer.read().decode('utf-8')); "
        "assert '¿Qué significa?' in message['message']['content']; "
        "sys.stdout.buffer.write(json.dumps({'event': 'result', 'result': "
        "{'status': 'SUCCESS', 'response': 'Title: Español 日本語 🧪\\n\\nRespuesta válida.'}}, "
        "ensure_ascii=False).encode('utf-8'))"
    )
    monkeypatch.setattr(cli.subprocess, "run", lambda command, **kwargs: run(
        [sys.executable, "-c", child], **kwargs,
    ))
    assert ask()[0]["title"] == "Español 日本語 🧪"
