from __future__ import annotations

import sys
from pathlib import Path

import pytest

try:
    from app.services.topic_transfer import (
        ARCHIVE_FORMAT,
        IMPLEMENTATION_ID,
        Manifest,
        TopicTransferError,
        dump_manifest,
        load_manifest,
    )
    from app.services.topic_transfer.types import FileRecord
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from topic_transfer import (
        ARCHIVE_FORMAT,
        IMPLEMENTATION_ID,
        Manifest,
        TopicTransferError,
        dump_manifest,
        load_manifest,
    )
    from topic_transfer.types import FileRecord


def sample_manifest() -> Manifest:
    return Manifest(
        archive_format="1.0",
        implementation="learn-up-topic-transfer/1",
        topic_slug="sample-topic",
        topic_name="Sample Topic",
        source_app_version="1.0",
        syllabus_version="v1",
        created_at="2026-08-08T12:00:00Z",
        files=(FileRecord("about/ABOUT.md", 3, "0" * 64),),
    )


def test_protocol_identity_and_format_are_pinned() -> None:
    assert ARCHIVE_FORMAT == "1.0"
    assert IMPLEMENTATION_ID == "learn-up-topic-transfer/1"


def test_manifest_serialization_is_canonical_and_round_trips() -> None:
    first = dump_manifest(sample_manifest())
    second = dump_manifest(sample_manifest())
    assert first == second
    assert load_manifest(first) == sample_manifest()


def test_manifest_rejects_yaml_aliases() -> None:
    aliased = dump_manifest(sample_manifest()).replace(
        b"archive_format: '1.0'", b"archive_format: &version '1.0'"
    )
    with pytest.raises(TopicTransferError, match="anchors"):
        load_manifest(aliased)
