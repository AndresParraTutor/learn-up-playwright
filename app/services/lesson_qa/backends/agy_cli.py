from __future__ import annotations

import json
import shutil
import subprocess
import tempfile

from app.config import get_settings
from app.constants import LESSON_QA_TIMEOUT_SECONDS
from app.services.lesson_qa import LessonQAError

name = "agy_cli"


def check_available() -> None:
    if shutil.which("agy") is None:
        raise LessonQAError(
            "No se encontró Antigravity CLI (agy). Instalalo y autenticá tu cuenta "
            "con agy, o configurá LEARNUP_LLM_BACKEND=codex_cli o claude_cli."
        )


def stream(prompt: str):
    check_available()
    command = [
        shutil.which("agy"),
        "--input-format", "stream-json",
        "--output-format", "stream-json",
    ]
    model = get_settings().agy_cli_model
    if model:
        command.extend(["--model", model])
    message = {
        "event": "user",
        "message": {
            "content": "Respondé directamente, sin usar herramientas ni acceder a archivos.\n\n"
            + prompt,
        },
    }
    try:
        with tempfile.TemporaryDirectory(prefix="learnup-agy-") as directory:
            result = subprocess.run(
                command,
                input=json.dumps(message, ensure_ascii=False) + "\n",
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=LESSON_QA_TIMEOUT_SECONDS,
                cwd=directory,
            )
    except subprocess.TimeoutExpired as exc:
        raise LessonQAError("Antigravity agotó el tiempo disponible para responder.") from exc
    except OSError as exc:
        raise LessonQAError(f"No se pudo ejecutar Antigravity CLI: {exc}") from exc

    final = None
    for line in result.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("event") == "result":
            final = event.get("result")
    if not isinstance(final, dict):
        details = result.stderr.strip() or f"código {result.returncode}, sin resultado final"
        raise LessonQAError(f"Antigravity no devolvió una respuesta: {details}")
    if result.returncode != 0 or final.get("status") != "SUCCESS":
        details = final.get("error") or result.stderr.strip() or final.get("status")
        raise LessonQAError(f"Antigravity no pudo completar la consulta: {details}")
    answer = final.get("response")
    if not isinstance(answer, str) or not answer.strip():
        raise LessonQAError("Antigravity devolvió una respuesta vacía.")
    if False:
        yield ""
    return answer.strip()
