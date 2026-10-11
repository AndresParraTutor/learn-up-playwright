from __future__ import annotations

import re
import tomllib
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_topic_or_404
from app.db import get_session
from app.models import Domain, Lab, Lesson, Objective, Question
from app.schemas import AboutOut, ContentInfoOut, DomainOut, ObjectiveOut

router = APIRouter(prefix="/api", tags=["catalog"])
REPO_ROOT = Path(__file__).resolve().parents[2]
VERSION_RE = re.compile(r"[1-9]\d*\.\d*")


def _read_required(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise HTTPException(
            status_code=500, detail=f"No se pudo leer el documento requerido {path.name}."
        ) from exc
    if not value.strip():
        raise HTTPException(
            status_code=500, detail=f"El documento requerido {path.name} está vacío."
        )
    return value


@router.get("/t/{topic_slug}/domains", response_model=list[DomainOut])
def list_domains(
    topic_slug: str, session: Session = Depends(get_session)
) -> list[DomainOut]:
    topic = get_topic_or_404(topic_slug, session)
    domains = session.execute(
        select(Domain)
        .where(Domain.topic_id == topic.id)
        .options(selectinload(Domain.objectives))
        .order_by(Domain.code)
    ).scalars()
    return [
        DomainOut(
            id=domain.id,
            code=domain.code,
            name=domain.name,
            weight_pct=domain.weight_pct,
            objectives=[
                ObjectiveOut(
                    id=objective.id,
                    code=objective.code,
                    title=objective.title,
                    description=objective.description,
                )
                for objective in sorted(
                    domain.objectives, key=lambda value: value.code
                )
            ],
        )
        for domain in domains
    ]


@router.get("/t/{topic_slug}/content-info", response_model=ContentInfoOut)
def content_info(
    topic_slug: str, session: Session = Depends(get_session)
) -> ContentInfoOut:
    topic = get_topic_or_404(topic_slug, session)
    domain_count = session.scalar(
        select(func.count(Domain.id)).where(Domain.topic_id == topic.id)
    ) or 0
    objective_count = session.scalar(
        select(func.count(Objective.id))
        .join(Domain)
        .where(Domain.topic_id == topic.id)
    ) or 0
    lesson_count = session.scalar(
        select(func.count(Lesson.id))
        .join(Objective)
        .join(Domain)
        .where(Domain.topic_id == topic.id)
    ) or 0
    question_count = session.scalar(
        select(func.count(Question.id))
        .join(Objective)
        .join(Domain)
        .where(Domain.topic_id == topic.id)
    ) or 0
    lab_count = session.scalar(
        select(func.count(Lab.id))
        .join(Objective)
        .join(Domain)
        .where(Domain.topic_id == topic.id)
    ) or 0
    return ContentInfoOut(
        syllabus_version=topic.syllabus_version,
        domain_count=domain_count,
        objective_count=objective_count,
        lesson_count=lesson_count,
        question_count=question_count,
        lab_count=lab_count,
    )


@router.get("/t/{topic_slug}/about", response_model=AboutOut)
def about(topic_slug: str, session: Session = Depends(get_session)) -> AboutOut:
    get_topic_or_404(topic_slug, session)
    content_root = (REPO_ROOT / "content" / topic_slug).resolve()
    sources_root = (REPO_ROOT / "sources" / topic_slug).resolve()
    if content_root.parent != (REPO_ROOT / "content").resolve():
        raise HTTPException(status_code=400, detail="Ruta de tema inválida.")
    if sources_root.parent != (REPO_ROOT / "sources").resolve():
        raise HTTPException(status_code=400, detail="Ruta de fuentes inválida.")
    try:
        project = tomllib.loads(_read_required(REPO_ROOT / "pyproject.toml"))[
            "project"
        ]
        version = str(project["version"])
    except (KeyError, tomllib.TOMLDecodeError) as exc:
        raise HTTPException(
            status_code=500, detail="pyproject.toml no contiene una versión válida."
        ) from exc
    if VERSION_RE.fullmatch(version) is None:
        raise HTTPException(
            status_code=500, detail="La versión no cumple MAJOR.MINOR."
        )
    return AboutOut(
        app_version=version,
        app_markdown=_read_required(REPO_ROOT / "ABOUT.md"),
        intake_markdown="",
        sources_markdown=_read_required(sources_root / "SOURCES.md"),
        content_changes_markdown="",
    )
