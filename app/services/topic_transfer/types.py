from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

ARCHIVE_FORMAT = "1.0"
IMPLEMENTATION_ID = "learn-up-topic-transfer/1"
ALLOWED_SUFFIXES = frozenset({".md", ".yaml", ".mp4"})
MAX_ARCHIVE_BYTES = 1_073_741_824
MAX_ENTRIES = 4096
MAX_FILE_BYTES = 1_073_741_824
MAX_TOTAL_BYTES = 4_294_967_296
MAX_COMPRESSION_RATIO = 200
MAX_TEXT_BYTES = 16_777_216

_APP_VERSION_RE = re.compile(r"([1-9]\d*)\.(0|[1-9]\d*)\Z")
_ARCHIVE_VERSION_RE = re.compile(r"([1-9]\d*|0)\.(0|[1-9]\d*)\Z")
_SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class TopicTransferError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FileRecord:
    path: str
    size: int
    sha256: str

    @classmethod
    def from_mapping(cls, value: object) -> FileRecord:
        if not isinstance(value, dict) or set(value) != {"path", "size", "sha256"}:
            raise TopicTransferError(
                "Every manifest file entry must have path, size, and sha256"
            )
        path = value["path"]
        size = value["size"]
        sha256 = value["sha256"]
        if not isinstance(path, str) or not path:
            raise TopicTransferError("Manifest file path must be a non-empty string")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise TopicTransferError(f"Invalid declared size for {path!r}")
        if not isinstance(sha256, str) or _SHA256_RE.fullmatch(sha256) is None:
            raise TopicTransferError(f"Invalid SHA-256 for {path!r}")
        return cls(path=path, size=size, sha256=sha256)

    def as_mapping(self) -> dict[str, object]:
        return {"path": self.path, "size": self.size, "sha256": self.sha256}


@dataclass(frozen=True, slots=True)
class Manifest:
    archive_format: str
    implementation: str
    topic_slug: str
    topic_name: str
    source_app_version: str
    syllabus_version: str
    created_at: str
    files: tuple[FileRecord, ...]

    @classmethod
    def from_mapping(cls, value: object) -> Manifest:
        expected = {
            "archive_format",
            "implementation",
            "topic_slug",
            "topic_name",
            "source_app_version",
            "syllabus_version",
            "created_at",
            "files",
        }
        if not isinstance(value, dict) or set(value) != expected:
            raise TopicTransferError(
                "Manifest keys do not match the topic-transfer schema"
            )
        scalar_keys = expected - {"files"}
        for key in scalar_keys:
            if not isinstance(value[key], str) or not value[key]:
                raise TopicTransferError(f"Manifest {key} must be a non-empty string")
        files_value = value["files"]
        if not isinstance(files_value, list):
            raise TopicTransferError("Manifest files must be a list")
        files = tuple(FileRecord.from_mapping(item) for item in files_value)
        manifest = cls(
            archive_format=value["archive_format"],
            implementation=value["implementation"],
            topic_slug=value["topic_slug"],
            topic_name=value["topic_name"],
            source_app_version=value["source_app_version"],
            syllabus_version=value["syllabus_version"],
            created_at=value["created_at"],
            files=files,
        )
        manifest.validate()
        return manifest

    def validate(self) -> None:
        parse_archive_version(self.archive_format)
        parse_app_version(self.source_app_version)
        validate_topic_slug(self.topic_slug)
        if self.implementation != IMPLEMENTATION_ID:
            raise TopicTransferError(
                f"Unsupported topic-transfer implementation {self.implementation!r}"
            )
        if not self.topic_name.strip():
            raise TopicTransferError("Manifest topic_name cannot be blank")
        if not self.syllabus_version.strip():
            raise TopicTransferError("Manifest syllabus_version cannot be blank")
        if not self.created_at.endswith("Z") or "T" not in self.created_at:
            raise TopicTransferError(
                "Manifest created_at must be a UTC timestamp ending in Z"
            )
        paths = [record.path for record in self.files]
        if paths != sorted(paths):
            raise TopicTransferError("Manifest file inventory must be sorted by path")
        if len(paths) != len(set(paths)):
            raise TopicTransferError("Manifest contains duplicate file paths")

    def as_mapping(self) -> dict[str, object]:
        return {
            "archive_format": self.archive_format,
            "implementation": self.implementation,
            "topic_slug": self.topic_slug,
            "topic_name": self.topic_name,
            "source_app_version": self.source_app_version,
            "syllabus_version": self.syllabus_version,
            "created_at": self.created_at,
            "files": [record.as_mapping() for record in self.files],
        }


@dataclass(frozen=True, slots=True)
class TransferRoots:
    root: Path
    content: Path
    sources: Path
    media: Path
    about: Path
    pyproject: Path
    backups: Path

    @classmethod
    def from_repo(cls, root: Path) -> TransferRoots:
        resolved = root.resolve()
        return cls(
            root=resolved,
            content=resolved / "content",
            sources=resolved / "sources",
            media=resolved / "media",
            about=resolved / "ABOUT.md",
            pyproject=resolved / "pyproject.toml",
            backups=resolved / ".learnup-backups",
        )


@dataclass(slots=True)
class ExportReport:
    archive: str
    topic_slug: str
    archive_format: str
    source_app_version: str
    file_count: int
    total_bytes: int
    ignored: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ImportReport:
    topic_slug: str
    archive_format: str
    source_app_version: str
    destination_app_version: str
    mode: str
    status: str
    installed: list[str] = field(default_factory=list)
    replaced: list[str] = field(default_factory=list)
    merged_q_and_a: int = 0
    skipped_q_and_a: list[str] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)
    backup: str | None = None


class TransferAdapter(Protocol):
    def resolve_topic_name(self, topic_slug: str) -> str: ...

    def validate_staged_topic(self, staging_root: Path, topic_slug: str) -> None: ...

    def reseed_and_validate(self) -> None: ...


def parse_app_version(value: str) -> tuple[int, int]:
    match = _APP_VERSION_RE.fullmatch(value)
    if match is None:
        raise TopicTransferError(f"App version must be MAJOR.MINOR, got {value!r}")
    return int(match.group(1)), int(match.group(2))


def parse_archive_version(value: str) -> tuple[int, int]:
    match = _ARCHIVE_VERSION_RE.fullmatch(value)
    if match is None:
        raise TopicTransferError(f"Archive format must be MAJOR.MINOR, got {value!r}")
    return int(match.group(1)), int(match.group(2))


def validate_topic_slug(value: str) -> str:
    if _SLUG_RE.fullmatch(value) is None:
        raise TopicTransferError(f"Invalid topic slug {value!r}")
    return value
