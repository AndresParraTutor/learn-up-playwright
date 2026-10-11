from __future__ import annotations

import json
import shutil
import subprocess
import threading

from app.config import get_settings
from app.constants import LESSON_QA_MAX_BUDGET_USD, LESSON_QA_TIMEOUT_SECONDS
from app.services.lesson_qa import LessonQAError

name = "claude_cli"


def check_available() -> None:
    if shutil.which("claude") is None:
        raise LessonQAError(
            "No se encontró Claude CLI. Instalalo/autenticalo o configurá "
            "LEARNUP_LLM_BACKEND=codex_cli u openhands."
        )


def stream(prompt: str):
    check_available()
    command = [
        "claude",
        "-p",
        "--output-format",
        "stream-json",
        "--include-partial-messages",
        "--verbose",
        "--tools",
        "",
        "--no-session-persistence",
        "--model",
        get_settings().claude_cli_model,
        "--max-budget-usd",
        str(LESSON_QA_MAX_BUDGET_USD),
    ]
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stderr: list[str] = []

    def write_prompt() -> None:
        assert process.stdin is not None
        try:
            process.stdin.write(prompt)
            process.stdin.close()
        except BrokenPipeError:
            pass

    def read_stderr() -> None:
        assert process.stderr is not None
        stderr.append(process.stderr.read())

    writer = threading.Thread(target=write_prompt, daemon=True)
    error_reader = threading.Thread(target=read_stderr, daemon=True)
    writer.start()
    error_reader.start()
    answer = ""
    assert process.stdout is not None
    for line in process.stdout:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "stream_event":
            delta = (
                event.get("event", {})
                .get("delta", {})
                .get("text")
            )
            if delta:
                yield str(delta)
        elif event.get("type") == "result":
            answer = str(event.get("result", "")).strip()
    try:
        return_code = process.wait(timeout=LESSON_QA_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        raise LessonQAError("Claude agotó el tiempo disponible para responder.") from exc
    writer.join(timeout=1)
    error_reader.join(timeout=1)
    if not answer:
        details = "".join(stderr).strip()
        raise LessonQAError(
            f"Claude no devolvió una respuesta: {details or f'código {return_code}'}"
        )
    return answer
