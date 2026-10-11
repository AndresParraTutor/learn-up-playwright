from __future__ import annotations

import math
import random

from app.models import LabCheck


class LabCheckError(ValueError):
    pass


_RELATIVE_DESCRIPTIONS = {
    "number_positive": "Debe ser un número positivo.",
    "number_less_than_previous": "Debe ser menor que tu respuesta anterior.",
    "number_greater_than_previous": "Debe ser mayor que tu respuesta anterior.",
}


def check_hint_available(check: LabCheck) -> bool:
    value = (check.expected_value or "").strip().lower()
    return value not in {"yes", "no", "sí", "si"}


def build_check_answer(check: LabCheck) -> str:
    if check.kind in _RELATIVE_DESCRIPTIONS:
        return _RELATIVE_DESCRIPTIONS[check.kind]
    value = (check.expected_value or "").strip()
    if not value:
        raise LabCheckError("El autocontrol no tiene un valor esperado.")
    return value


def _numeric_hint(value: float) -> str:
    magnitude = 1 if value == 0 else 10 ** math.floor(math.log10(abs(value)))
    increment = magnitude / 10 if magnitude >= 10 else magnitude
    delta = increment * random.randint(1, 9)
    if random.random() < 0.5:
        lower = value - delta
        if value > 0:
            lower = max(0, lower)
        return f"Más de {lower:g}."
    return f"Menos de {value + delta:g}."


def build_check_hint(check: LabCheck) -> str:
    if not check_hint_available(check):
        raise LabCheckError("Este autocontrol de sí/no no ofrece pista.")
    if check.kind in _RELATIVE_DESCRIPTIONS:
        return _RELATIVE_DESCRIPTIONS[check.kind]
    value = build_check_answer(check)
    try:
        return _numeric_hint(float(value))
    except ValueError:
        words = value.split()
        if random.random() < 0.5:
            return " ".join(f"{word[0].lower()}..." for word in words if word)
        return " ".join("." * len(word) for word in words)


def check_answer(
    check: LabCheck, answer: str, previous_answer: str | None = None
) -> bool:
    actual = answer.strip()
    expected = (check.expected_value or "").strip()
    if check.kind == "contains":
        if not check.case_sensitive:
            actual, expected = actual.casefold(), expected.casefold()
        return expected in actual
    if check.kind == "exact":
        if not check.case_sensitive:
            actual, expected = actual.casefold(), expected.casefold()
        return actual == expected
    try:
        number = float(actual)
    except ValueError:
        return False
    if check.kind == "number_positive":
        return number > 0
    if previous_answer is None:
        return False
    try:
        previous = float(previous_answer.strip())
    except ValueError:
        return False
    if check.kind == "number_less_than_previous":
        return number < previous
    if check.kind == "number_greater_than_previous":
        return number > previous
    raise LabCheckError(f"Tipo de autocontrol desconocido: {check.kind}")
