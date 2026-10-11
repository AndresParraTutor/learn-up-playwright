from __future__ import annotations

import random

from app.models import Choice, Question
from app.schemas import ChoiceOut, ChoiceReviewOut


def shuffled_choices(question: Question, attempt_id: int) -> list[Choice]:
    choices = list(question.choices)
    random.Random(f"{attempt_id}:{question.id}").shuffle(choices)
    return choices


def grade_question(question: Question, selected_choice_ids: list[int]) -> bool:
    valid_ids = {choice.id for choice in question.choices}
    selected = set(selected_choice_ids)
    if not selected.issubset(valid_ids):
        raise ValueError("Una opción seleccionada no pertenece a la pregunta.")
    correct = {choice.id for choice in question.choices if choice.is_correct}
    return selected == correct


def prompt_choices(question: Question, attempt_id: int) -> list[ChoiceOut]:
    return [
        ChoiceOut(id=choice.id, position=index, text_markdown=choice.text_markdown)
        for index, choice in enumerate(shuffled_choices(question, attempt_id))
    ]


def review_choices(question: Question, attempt_id: int) -> list[ChoiceReviewOut]:
    return [
        ChoiceReviewOut(
            id=choice.id,
            position=index,
            text_markdown=choice.text_markdown,
            is_correct=choice.is_correct,
            explanation_markdown=choice.distractor_explanation_markdown,
        )
        for index, choice in enumerate(shuffled_choices(question, attempt_id))
    ]
