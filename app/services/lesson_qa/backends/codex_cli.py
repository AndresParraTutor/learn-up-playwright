from __future__ import annotations

import json
import shutil
import subprocess
import tempfile

from app.constants import LESSON_QA_TIMEOUT_SECONDS
from app.services.lesson_qa import LessonQAError

name = "codex_cli"


def check_available() -> None:
    if shutil.which("codex") is None:
        raise LessonQAError(
            "No se encontró Codex CLI. Instalalo/autenticalo o configurá "
            "LEARNUP_LLM_BACKEND=agy_cli, claude_cli u openhands."
        )


def stream(prompt: str):
    check_available()
    command = [
        shutil.which("codex"),
        "exec",
        "--json",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        "-",
    ]
    try:
        with tempfile.TemporaryDirectory(prefix="learnup-codex-") as directory:
            result = subprocess.run(
                command,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=LESSON_QA_TIMEOUT_SECONDS,
                cwd=directory,
            )
    except subprocess.TimeoutExpired as exc:
        raise LessonQAError("Codex agotó el tiempo disponible para responder.") from exc
    answer = ""
    reported_error = ""
    for line in result.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        event_type = event.get("type")
        if event_type == "item.completed":
            item = event.get("item", {})
            if item.get("type") == "agent_message":
                answer = str(item.get("text", "")).strip()
        elif event_type in {"error", "turn.failed"}:
            reported_error = str(event.get("message") or event.get("error") or event)
    if not answer:
        details = reported_error or result.stderr.strip()
        if result.returncode != 0:
            details = details or f"código de salida {result.returncode}"
        raise LessonQAError(f"Codex no devolvió una respuesta: {details or 'salida vacía'}")
    if False:
        yield ""
    return answer
