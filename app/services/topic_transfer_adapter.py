from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.content.seed import seed_all
from app.content.validate import validate_repo, validate_topic_tree
from app.db import SessionLocal
from app.models import Topic


class AppTransferAdapter:
    def resolve_topic_name(self, topic_slug: str) -> str:
        with SessionLocal() as session:
            topic = session.execute(
                select(Topic).where(Topic.slug == topic_slug)
            ).scalar_one_or_none()
            if topic is None:
                raise ValueError(f"Tema inexistente: {topic_slug}")
            return topic.name

    def validate_staged_topic(self, staging_root: Path, topic_slug: str) -> None:
        validate_topic_tree(staging_root, topic_slug)

    def reseed_and_validate(self) -> None:
        seed_all()
        validate_repo()


_ADAPTER = AppTransferAdapter()


def get_adapter() -> AppTransferAdapter:
    return _ADAPTER
