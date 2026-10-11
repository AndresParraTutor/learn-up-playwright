from __future__ import annotations

import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from app.services import lesson_qa
from app.services.lesson_qa.backends import codex_cli


def _returning_stream(value: str):
    if False:
        yield ""
    return value


def _consume_return(iterator):
    chunks: list[str] = []
    while True:
        try:
            chunks.append(next(iterator))
        except StopIteration as stop:
            return chunks, stop.value


def test_ask_parses_streamed_answer() -> None:
    backend = SimpleNamespace(
        check_available=lambda: None,
        stream=lambda _prompt: _returning_stream(
            "Title: Una duda concreta\n\nUna respuesta respaldada."
        ),
    )

    events = list(
        lesson_qa.ask(
            "Contexto",
            "Pasaje",
            "Pregunta",
            allow_insufficient=True,
            backend=backend,
        )
    )

    assert events == [
        {
            "type": "result",
            "title": "Una duda concreta",
            "answer": "Una respuesta respaldada.",
        }
    ]


def test_ask_surfaces_insufficient_context() -> None:
    backend = SimpleNamespace(
        check_available=lambda: None,
        stream=lambda _prompt: _returning_stream(
            lesson_qa.INSUFFICIENT_CONTEXT_SENTINEL
        ),
    )

    events = list(
        lesson_qa.ask(
            "Contexto",
            "Pasaje",
            "Pregunta",
            allow_insufficient=True,
            backend=backend,
        )
    )

    assert events == [{"type": "insufficient"}]


def test_codex_cli_uses_ephemeral_read_only_execution(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(codex_cli.shutil, "which", lambda name: f"/fake/{name}")

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        event = {
            "type": "item.completed",
            "item": {
                "type": "agent_message",
                "text": "Title: Resultado\n\nRespuesta simulada.",
            },
        }
        return SimpleNamespace(
            stdout=json.dumps(event) + "\n", stderr="", returncode=0
        )

    monkeypatch.setattr(codex_cli.subprocess, "run", fake_run)

    chunks, answer = _consume_return(codex_cli.stream("prompt de prueba"))

    assert chunks == []
    assert answer == "Title: Resultado\n\nRespuesta simulada."
    assert captured["command"] == [
        "codex",
        "exec",
        "--json",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        "-",
    ]
    assert captured["kwargs"]["input"] == "prompt de prueba"


def test_codex_cli_reports_empty_failed_execution(monkeypatch) -> None:
    monkeypatch.setattr(codex_cli.shutil, "which", lambda name: f"/fake/{name}")
    monkeypatch.setattr(
        codex_cli.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            stdout="", stderr="fallo simulado", returncode=1
        ),
    )

    with pytest.raises(lesson_qa.LessonQAError, match="fallo simulado"):
        _consume_return(codex_cli.stream("prompt"))


@pytest.mark.parametrize("failed", [False, True])
def test_codex_cli_unicode_pipes_with_windows_default(monkeypatch, failed: bool) -> None:
    prompt = "Explicá cómo funciona la aserción: español 日本語 🧪"
    run = subprocess.run
    monkeypatch.setattr(codex_cli.shutil, "which", lambda name: f"/fake/{name}")
    monkeypatch.setattr(subprocess, "_text_encoding", lambda: "cp1252")
    child = (
        "import json, sys; "
        "prompt = sys.stdin.buffer.read().decode('utf-8'); "
        + (
            "sys.stderr.buffer.write(prompt.encode('utf-8')); sys.exit(1)"
            if failed
            else "sys.stdout.buffer.write(json.dumps({'type': 'item.completed', "
            "'item': {'type': 'agent_message', 'text': prompt}}, "
            "ensure_ascii=False).encode('utf-8'))"
        )
    )

    def run_child(_command, **kwargs):
        return run([sys.executable, "-c", child], **kwargs)

    monkeypatch.setattr(codex_cli.subprocess, "run", run_child)
    if failed:
        with pytest.raises(lesson_qa.LessonQAError, match=prompt):
            _consume_return(codex_cli.stream(prompt))
    else:
        chunks, answer = _consume_return(codex_cli.stream(prompt))
        assert chunks == []
        assert answer == prompt
