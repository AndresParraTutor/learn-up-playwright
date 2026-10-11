from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Topic, User


def get_topic_or_404(topic_slug: str, session: Session) -> Topic:
    topic = session.execute(
        select(Topic).where(Topic.slug == topic_slug)
    ).scalar_one_or_none()
    if topic is None:
        raise HTTPException(status_code=404, detail="Tema inexistente.")
    return topic


def get_default_user(session: Session) -> User:
    user = session.execute(
        select(User).where(User.display_name == "Estudiante")
    ).scalar_one_or_none()
    if user is not None:
        return user
    user = User(display_name="Estudiante")
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        user = session.execute(
            select(User).where(User.display_name == "Estudiante")
        ).scalar_one()
    return user
