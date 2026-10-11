from __future__ import annotations

from importlib import import_module
from types import ModuleType

from app.config import LLMBackend, get_settings
from app.services.lesson_qa import LessonQAError


def get_backend(name: str | None = None) -> ModuleType:
    configured = name or get_settings().llm_backend.value
    try:
        backend = LLMBackend(configured)
    except ValueError as exc:
        raise LessonQAError(f"Backend LLM desconocido: {configured}") from exc
    return import_module(f"app.services.lesson_qa.backends.{backend.value}")
