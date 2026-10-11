from __future__ import annotations

import importlib.util
import os
import queue
import threading
import time

from app.config import get_settings
from app.constants import LESSON_QA_TIMEOUT_SECONDS
from app.services.lesson_qa import LessonQAError

os.environ.setdefault("OPENHANDS_SUPPRESS_BANNER", "1")
os.environ.setdefault("LOG_AUTO_CONFIG", "false")

name = "openhands"


def check_available() -> None:
    if importlib.util.find_spec("openhands.sdk") is None:
        raise LessonQAError(
            "OpenHands no está instalado. Ejecutá uv sync --group openhands o configurá "
            "LEARNUP_LLM_BACKEND=codex_cli/claude_cli."
        )
    if not get_settings().llm_api_key:
        raise LessonQAError(
            "LEARNUP_LLM_API_KEY es obligatorio para OpenHands; para un modelo local "
            "usá un marcador como local-llm."
        )


def stream(prompt: str):
    check_available()
    from openhands.sdk import LLM, Message, TextContent

    settings = get_settings()
    chunks: queue.Queue[object] = queue.Queue()
    sentinel = object()
    errors: list[BaseException] = []
    final: list[str] = []

    def on_token(chunk) -> None:
        try:
            text = chunk.choices[0].delta.content
        except (AttributeError, IndexError):
            text = ""
        if text:
            chunks.put(str(text))

    def worker() -> None:
        try:
            llm = LLM(
                usage_id="learn-up-faq",
                model=settings.llm_model,
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                timeout=LESSON_QA_TIMEOUT_SECONDS,
            )
            response = llm.completion(
                [Message(role="user", content=[TextContent(text=prompt)])],
                on_token=on_token,
                stream=True,
            )
            text = getattr(response, "content", None)
            if isinstance(text, str):
                final.append(text)
        except BaseException as exc:
            errors.append(exc)
        finally:
            chunks.put(sentinel)

    threading.Thread(target=worker, daemon=True).start()
    deadline = time.monotonic() + LESSON_QA_TIMEOUT_SECONDS
    received: list[str] = []
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise LessonQAError("OpenHands agotó el tiempo disponible para responder.")
        try:
            item = chunks.get(timeout=remaining)
        except queue.Empty as exc:
            raise LessonQAError("OpenHands agotó el tiempo disponible para responder.") from exc
        if item is sentinel:
            break
        text = str(item)
        received.append(text)
        yield text
    if errors:
        raise LessonQAError(f"OpenHands no pudo responder: {errors[0]}") from errors[0]
    answer = (final[-1] if final else "".join(received)).strip()
    if not answer:
        raise LessonQAError("OpenHands devolvió una respuesta vacía.")
    return answer
