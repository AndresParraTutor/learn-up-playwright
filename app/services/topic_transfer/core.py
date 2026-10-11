from __future__ import annotations

import hashlib
import os
import shutil
import stat
import tempfile
import unicodedata
import uuid
import zipfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Iterator

import tomllib
import yaml
from yaml.events import AliasEvent, NodeEvent

from .faq import MergeResult, merge_topic_q_and_a
from .manifest import dump_manifest, load_manifest
from .types import (
    ALLOWED_SUFFIXES,
    ARCHIVE_FORMAT,
    IMPLEMENTATION_ID,
    MAX_ARCHIVE_BYTES,
    MAX_COMPRESSION_RATIO,
    MAX_ENTRIES,
    MAX_FILE_BYTES,
    MAX_TEXT_BYTES,
    MAX_TOTAL_BYTES,
    ExportReport,
    FileRecord,
    ImportReport,
    Manifest,
    TopicTransferError,
    TransferAdapter,
    TransferRoots,
    parse_app_version,
    parse_archive_version,
    validate_topic_slug,
)

_ABOUT_MEMBERS = {
    "about/ABOUT.md",
    "about/INTAKE.md",
    "about/SOURCES.md",
    "about/CHANGELOG.md",
}
_DANGEROUS_SUFFIXES = {
    ".7z",
    ".bat",
    ".bz2",
    ".cmd",
    ".dll",
    ".dylib",
    ".exe",
    ".gz",
    ".jar",
    ".js",
    ".msi",
    ".ps1",
    ".py",
    ".rar",
    ".sh",
    ".so",
    ".tar",
    ".tgz",
    ".xz",
    ".zip",
}
_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
_CHUNK_SIZE = 1024 * 1024


def export_topic(
    roots: TransferRoots,
    adapter: TransferAdapter,
    topic_slug: str,
    output: Path,
    *,
    overwrite: bool = False,
    created_at: str | None = None,
) -> ExportReport:
    _validate_transfer_roots(roots)
    slug = validate_topic_slug(topic_slug)
    if not output.name.endswith(".learnup.zip"):
        raise TopicTransferError("Export path must end in .learnup.zip")
    if output.exists() and not overwrite:
        raise TopicTransferError(f"Refusing to overwrite existing archive {output}")
    topic_name = adapter.resolve_topic_name(slug)
    if not isinstance(topic_name, str) or not topic_name.strip():
        raise TopicTransferError("Topic adapter returned an invalid topic name")
    app_version = _read_app_version(roots.pyproject)
    files, ignored = _collect_export_files(roots, slug)
    syllabus = _load_yaml_file(roots.content / slug / "syllabus.yaml")
    if not isinstance(syllabus, dict):
        raise TopicTransferError("syllabus.yaml must be a mapping")
    if syllabus.get("topic_slug") != slug:
        raise TopicTransferError(
            "syllabus.yaml topic_slug does not match the requested topic"
        )
    if syllabus.get("topic_name") != topic_name:
        raise TopicTransferError(
            "Topic catalog name does not match syllabus.yaml topic_name"
        )
    syllabus_version = syllabus.get("syllabus_version")
    if not isinstance(syllabus_version, str) or not syllabus_version:
        raise TopicTransferError("syllabus.yaml is missing syllabus_version")
    adapter.validate_staged_topic(roots.root, slug)

    records: list[FileRecord] = []
    for archive_path, source in sorted(files.items()):
        _validate_allowed_file(source, archive_path, slug)
        size, digest = _hash_file(source)
        records.append(FileRecord(archive_path, size, digest))
    timestamp = created_at or datetime.now(UTC).replace(
        microsecond=0
    ).isoformat().replace("+00:00", "Z")
    _parse_created_at(timestamp)
    manifest = Manifest(
        archive_format=ARCHIVE_FORMAT,
        implementation=IMPLEMENTATION_ID,
        topic_slug=slug,
        topic_name=topic_name,
        source_app_version=app_version,
        syllabus_version=syllabus_version,
        created_at=timestamp,
        files=tuple(records),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output.with_name(f".{output.name}.{uuid.uuid4().hex}.tmp")
    try:
        with zipfile.ZipFile(
            temporary_output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6
        ) as archive:
            _write_zip_bytes(archive, "manifest.yaml", dump_manifest(manifest))
            for record in records:
                size, digest = _write_zip_file(archive, record.path, files[record.path])
                if size != record.size or digest != record.sha256:
                    raise TopicTransferError(
                        f"File changed while archiving: {files[record.path]}"
                    )
        os.replace(temporary_output, output)
    except BaseException:
        temporary_output.unlink(missing_ok=True)
        raise
    return ExportReport(
        archive=str(output),
        topic_slug=slug,
        archive_format=ARCHIVE_FORMAT,
        source_app_version=app_version,
        file_count=len(records),
        total_bytes=sum(record.size for record in records),
        ignored=ignored,
    )


def inspect_topic_archive(
    archive_path: Path,
    roots: TransferRoots,
    adapter: TransferAdapter,
) -> ImportReport:
    return import_topic(archive_path, roots, adapter, confirm=False)


def import_topic(
    archive_path: Path,
    roots: TransferRoots,
    adapter: TransferAdapter,
    *,
    confirm: bool,
) -> ImportReport:
    _validate_transfer_roots(roots)
    if not archive_path.name.endswith(".learnup.zip"):
        raise TopicTransferError("Import path must end in .learnup.zip")
    destination_version = _read_app_version(roots.pyproject)
    archive_digest = _sha256_path(archive_path)
    try:
        with _validated_staging(archive_path, destination_version) as staged:
            manifest, staging_root, ignored = staged
            slug = manifest.topic_slug
            topic_path = roots.content / slug
            mode = "update" if topic_path.exists() else "new"
            if not topic_path.exists() and (
                (roots.sources / slug).exists() or (roots.media / slug).exists()
            ):
                raise TopicTransferError(
                    f"Destination has partial paths for {slug!r} but no content topic"
                )
            _materialize_staged_sources(staging_root, manifest)
            merge_result = MergeResult(merged=0, skipped=[])
            if mode == "update":
                if topic_path.is_symlink() or not topic_path.is_dir():
                    raise TopicTransferError(
                        f"Existing topic path is not a regular directory: {topic_path}"
                    )
                _assert_tree_has_no_symlinks(topic_path)
                merge_result = merge_topic_q_and_a(
                    topic_path, staging_root / "content" / slug
                )
            _append_import_provenance(
                staging_root / "content" / slug / "CHANGELOG.md",
                manifest,
                archive_digest,
            )
            adapter.validate_staged_topic(staging_root, slug)
            destinations = _destination_paths(roots, slug)
            report = ImportReport(
                topic_slug=slug,
                archive_format=manifest.archive_format,
                source_app_version=manifest.source_app_version,
                destination_app_version=destination_version,
                mode=mode,
                status="validated" if not confirm else "installing",
                installed=destinations,
                replaced=[path for path in destinations if Path(path).exists()]
                if mode == "update"
                else [],
                merged_q_and_a=merge_result.merged,
                skipped_q_and_a=merge_result.skipped,
                ignored=ignored,
            )
            if not confirm:
                return report
            _install_staged_topic(roots, adapter, staging_root, report)
            report.status = "installed"
            return report
    except zipfile.BadZipFile as exc:
        raise TopicTransferError("File is not a valid ZIP archive") from exc


@contextmanager
def _validated_staging(
    archive_path: Path, destination_version: str
) -> Iterator[tuple[Manifest, Path, list[str]]]:
    if not archive_path.is_file() or archive_path.is_symlink():
        raise TopicTransferError(f"Archive is not a regular file: {archive_path}")
    archive_size = archive_path.stat().st_size
    if archive_size > MAX_ARCHIVE_BYTES:
        raise TopicTransferError("Archive exceeds the maximum compressed size")
    with tempfile.TemporaryDirectory(prefix="learnup-topic-import-") as temporary:
        staging_root = Path(temporary)
        with zipfile.ZipFile(archive_path, "r") as archive:
            infos, ignored = _inspect_zip_structure(archive)
            manifest_info = infos.get("manifest.yaml")
            if manifest_info is None:
                raise TopicTransferError("Archive is missing manifest.yaml")
            if manifest_info.file_size > MAX_TEXT_BYTES:
                raise TopicTransferError("manifest.yaml exceeds the text size limit")
            manifest = load_manifest(
                _read_member_bounded(archive, manifest_info, MAX_TEXT_BYTES)
            )
            _check_compatibility(manifest, destination_version)
            inventory = {record.path: record for record in manifest.files}
            expected_names = set(inventory) | {"manifest.yaml"}
            actual_allowed = {
                name
                for name, info in infos.items()
                if not info.is_dir()
                and (name == "manifest.yaml" or Path(name).suffix in ALLOWED_SUFFIXES)
            }
            if actual_allowed != expected_names:
                missing = sorted(expected_names - actual_allowed)
                extra = sorted(actual_allowed - expected_names)
                raise TopicTransferError(
                    f"Archive inventory mismatch; missing={missing}, extra={extra}"
                )
            _validate_required_inventory(manifest)
            for record in manifest.files:
                info = infos[record.path]
                if info.file_size != record.size:
                    raise TopicTransferError(
                        f"Declared size mismatch for {record.path}"
                    )
                target = staging_root.joinpath(*PurePosixPath(record.path).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                digest, written = _copy_member(archive, info, target)
                if written != record.size or digest != record.sha256:
                    raise TopicTransferError(f"Checksum mismatch for {record.path}")
                _validate_allowed_file(target, record.path, manifest.topic_slug)
            _validate_about_snapshots(staging_root, manifest.topic_slug)
        yield manifest, staging_root, ignored


def _collect_export_files(
    roots: TransferRoots, slug: str
) -> tuple[dict[str, Path], list[str]]:
    topic_content = roots.content / slug
    topic_sources = roots.sources / slug
    if topic_content.is_symlink() or not topic_content.is_dir():
        raise TopicTransferError(
            f"Topic content directory does not exist: {topic_content}"
        )
    required = {
        "about/ABOUT.md": roots.about,
        "about/INTAKE.md": topic_sources / "INTAKE.md",
        "about/SOURCES.md": topic_sources / "SOURCES.md",
        "about/CHANGELOG.md": topic_content / "CHANGELOG.md",
    }
    files: dict[str, Path] = {}
    ignored: list[str] = []
    for archive_path, source in required.items():
        _require_regular_file(source)
        files[archive_path] = source
    for source in sorted(topic_sources.rglob("*")):
        if source.is_symlink():
            raise TopicTransferError(f"Refusing to export symlink {source}")
        if source.is_file() and source.name not in {"INTAKE.md", "SOURCES.md"}:
            ignored.append(
                f"sources/{slug}/{source.relative_to(topic_sources).as_posix()}"
            )
    for source in sorted(topic_content.rglob("*")):
        if source.is_symlink():
            raise TopicTransferError(f"Refusing to export symlink {source}")
        if source.is_dir():
            continue
        if not source.is_file():
            raise TopicTransferError(f"Refusing to export non-regular file {source}")
        archive_path = f"content/{slug}/{source.relative_to(topic_content).as_posix()}"
        if source.suffix.lower() not in ALLOWED_SUFFIXES:
            ignored.append(archive_path)
            continue
        files[archive_path] = source
    topic_media = roots.media / slug
    if topic_media.exists():
        if topic_media.is_symlink() or not topic_media.is_dir():
            raise TopicTransferError(
                f"Topic media path is not a regular directory: {topic_media}"
            )
        for source in sorted(topic_media.iterdir()):
            if source.is_symlink():
                raise TopicTransferError(f"Refusing to export symlink {source}")
            archive_path = f"media/{slug}/{source.name}"
            if not source.is_file():
                raise TopicTransferError(
                    f"Refusing to export non-regular media entry {source}"
                )
            if source.suffix.lower() != ".mp4":
                ignored.append(archive_path)
                continue
            files[archive_path] = source
    required_content = {f"content/{slug}/syllabus.yaml", f"content/{slug}/CHANGELOG.md"}
    missing = sorted(required_content - set(files))
    if missing:
        raise TopicTransferError(f"Topic is missing required content files: {missing}")
    return files, ignored


def _inspect_zip_structure(
    archive: zipfile.ZipFile,
) -> tuple[dict[str, zipfile.ZipInfo], list[str]]:
    infos_list = archive.infolist()
    if len(infos_list) > MAX_ENTRIES:
        raise TopicTransferError("Archive contains too many entries")
    infos: dict[str, zipfile.ZipInfo] = {}
    casefolded: set[str] = set()
    ignored: list[str] = []
    total = 0
    for info in infos_list:
        name = _normalize_member_name(info.filename, allow_directory=info.is_dir())
        folded = name.casefold()
        if name in infos or folded in casefolded:
            raise TopicTransferError(
                f"Archive contains a duplicate or case-colliding path: {name}"
            )
        infos[name] = info
        casefolded.add(folded)
        _validate_zip_file_type(info, name)
        if info.is_dir():
            continue
        if info.flag_bits & 0x1:
            raise TopicTransferError(f"Encrypted ZIP member is not supported: {name}")
        if info.file_size < 0 or info.compress_size < 0:
            raise TopicTransferError(f"ZIP member has an invalid size: {name}")
        if info.file_size > MAX_FILE_BYTES:
            raise TopicTransferError(f"ZIP member exceeds the per-file limit: {name}")
        total += info.file_size
        if total > MAX_TOTAL_BYTES:
            raise TopicTransferError(
                "Archive exceeds the total uncompressed-size limit"
            )
        if info.file_size and info.compress_size == 0:
            raise TopicTransferError(
                f"ZIP member has an invalid compression ratio: {name}"
            )
        if (
            info.file_size > 1024 * 1024
            and info.file_size / max(info.compress_size, 1) > MAX_COMPRESSION_RATIO
        ):
            raise TopicTransferError(
                f"ZIP member exceeds the compression-ratio limit: {name}"
            )
        suffix = Path(name).suffix.lower()
        if suffix in _DANGEROUS_SUFFIXES:
            raise TopicTransferError(
                f"Executable or nested archive member is forbidden: {name}"
            )
        if name != "manifest.yaml" and suffix not in ALLOWED_SUFFIXES:
            if name.startswith(("about/", "content/", "media/")):
                raise TopicTransferError(
                    f"Unsupported file in a protected archive path: {name}"
                )
            ignored.append(name)
    return infos, ignored


def _normalize_member_name(value: str, *, allow_directory: bool) -> str:
    if not value or "\x00" in value or "\\" in value:
        raise TopicTransferError(f"Unsafe ZIP member path: {value!r}")
    if unicodedata.normalize("NFC", value) != value:
        raise TopicTransferError(f"ZIP member path is not NFC-normalized: {value!r}")
    if value.startswith("/") or value.startswith("//"):
        raise TopicTransferError(f"Absolute ZIP member path is forbidden: {value!r}")
    raw = value[:-1] if allow_directory and value.endswith("/") else value
    path = PurePosixPath(raw)
    raw_parts = raw.split("/")
    if (
        not raw
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in raw_parts)
    ):
        raise TopicTransferError(f"Unsafe ZIP member path: {value!r}")
    if len(path.parts[0]) == 2 and path.parts[0][1] == ":":
        raise TopicTransferError(
            f"Drive-qualified ZIP member path is forbidden: {value!r}"
        )
    return raw


def _validate_zip_file_type(info: zipfile.ZipInfo, name: str) -> None:
    mode = info.external_attr >> 16
    if mode == 0:
        return
    kind = stat.S_IFMT(mode)
    if info.is_dir() and kind in {0, stat.S_IFDIR}:
        return
    if not info.is_dir() and kind in {0, stat.S_IFREG}:
        return
    raise TopicTransferError(f"ZIP member is not a regular file or directory: {name}")


def _validate_required_inventory(manifest: Manifest) -> None:
    _parse_created_at(manifest.created_at)
    supported_major, supported_minor = parse_archive_version(ARCHIVE_FORMAT)
    incoming_major, incoming_minor = parse_archive_version(manifest.archive_format)
    if incoming_major != supported_major or incoming_minor > supported_minor:
        raise TopicTransferError(
            f"Unsupported archive format {manifest.archive_format}; this app supports {ARCHIVE_FORMAT}"
        )
    required = _ABOUT_MEMBERS | {
        f"content/{manifest.topic_slug}/syllabus.yaml",
        f"content/{manifest.topic_slug}/CHANGELOG.md",
    }
    paths = {record.path for record in manifest.files}
    missing = sorted(required - paths)
    if missing:
        raise TopicTransferError(f"Archive is missing required files: {missing}")
    for record in manifest.files:
        normalized = _normalize_member_name(record.path, allow_directory=False)
        if normalized != record.path:
            raise TopicTransferError(
                f"Manifest contains a non-canonical path: {record.path}"
            )
        _validate_logical_member_path(record.path, manifest.topic_slug)
    lesson_stems = {
        PurePosixPath(path).stem
        for path in paths
        if path.startswith(f"content/{manifest.topic_slug}/lessons/")
        and path.endswith(".md")
    }
    media_stems = {
        PurePosixPath(path).stem
        for path in paths
        if path.startswith(f"media/{manifest.topic_slug}/") and path.endswith(".mp4")
    }
    unknown_media = sorted(media_stems - lesson_stems)
    if unknown_media:
        raise TopicTransferError(
            f"Media files have no matching lesson slug: {unknown_media}"
        )


def _validate_logical_member_path(archive_path: str, slug: str) -> None:
    path = PurePosixPath(archive_path)
    suffix = path.suffix
    if suffix not in ALLOWED_SUFFIXES:
        raise TopicTransferError(
            f"Manifest inventories an unsupported file: {archive_path}"
        )
    if archive_path in _ABOUT_MEMBERS:
        return
    content_prefix = ("content", slug)
    media_prefix = ("media", slug)
    if path.parts[:2] == content_prefix:
        relative = path.parts[2:]
        if not relative:
            raise TopicTransferError(f"Invalid content member path: {archive_path}")
        if suffix == ".md" and (
            relative == ("CHANGELOG.md",)
            or (len(relative) == 3 and relative[0] == "lessons")
            or (len(relative) == 3 and relative[:2] == ("strategy", "lessons"))
        ):
            return
        if suffix == ".yaml" and (
            relative == ("syllabus.yaml",)
            or (len(relative) == 2 and relative[0] in {"questions", "mocks"})
            or (len(relative) == 3 and relative[0] == "labs")
            or relative == ("strategy", "questions.yaml")
        ):
            return
        raise TopicTransferError(f"Unexpected topic content path: {archive_path}")
    if path.parts[:2] == media_prefix and len(path.parts) == 3 and suffix == ".mp4":
        return
    raise TopicTransferError(
        f"Archive member is outside the declared topic roots: {archive_path}"
    )


def _validate_allowed_file(path: Path, archive_path: str, slug: str) -> None:
    _require_regular_file(path)
    _validate_logical_member_path(archive_path, slug)
    suffix = path.suffix.lower()
    if suffix == ".md":
        _validate_markdown(path, archive_path)
    elif suffix == ".yaml":
        _load_yaml_file(path)
    elif suffix == ".mp4":
        _validate_mp4(path, archive_path)
    else:
        raise TopicTransferError(f"Unsupported file suffix: {archive_path}")


def _validate_markdown(path: Path, archive_path: str) -> None:
    if path.stat().st_size > MAX_TEXT_BYTES:
        raise TopicTransferError(
            f"Markdown file exceeds the text size limit: {archive_path}"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise TopicTransferError(
            f"Markdown file is not valid UTF-8: {archive_path}"
        ) from exc
    if "\x00" in text or not text.strip():
        raise TopicTransferError(
            f"Markdown file is empty or contains NUL: {archive_path}"
        )
    if archive_path.startswith("about/") or archive_path.endswith("/CHANGELOG.md"):
        if not text.lstrip().startswith("#"):
            raise TopicTransferError(
                f"Markdown document is missing its heading: {archive_path}"
            )
    elif not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise TopicTransferError(
            f"Content Markdown is missing YAML frontmatter: {archive_path}"
        )


def _load_yaml_file(path: Path) -> object:
    if path.stat().st_size > MAX_TEXT_BYTES:
        raise TopicTransferError(f"YAML file exceeds the text size limit: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise TopicTransferError(f"YAML file is not valid UTF-8: {path}") from exc
    if "\x00" in text or not text.strip():
        raise TopicTransferError(f"YAML file is empty or contains NUL: {path}")
    try:
        for event in yaml.parse(text):
            if isinstance(event, AliasEvent):
                raise TopicTransferError(f"YAML aliases are forbidden: {path}")
            if isinstance(event, NodeEvent) and event.anchor is not None:
                raise TopicTransferError(f"YAML anchors are forbidden: {path}")
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise TopicTransferError(f"Malformed YAML file: {path}") from exc


def _validate_mp4(path: Path, archive_path: str) -> None:
    with path.open("rb") as stream:
        data = stream.read(4096)
    offset = 0
    found_ftyp = False
    while offset + 8 <= len(data):
        box_size = int.from_bytes(data[offset : offset + 4], "big")
        box_type = data[offset + 4 : offset + 8]
        header_size = 8
        if box_size == 1:
            if offset + 16 > len(data):
                break
            box_size = int.from_bytes(data[offset + 8 : offset + 16], "big")
            header_size = 16
        if box_size == 0:
            box_size = path.stat().st_size - offset
        if box_size < header_size or offset + box_size > path.stat().st_size:
            raise TopicTransferError(f"Invalid MP4 box structure: {archive_path}")
        if box_type == b"ftyp":
            if box_size < header_size + 8 or offset + header_size + 8 > len(data):
                raise TopicTransferError(f"Invalid MP4 ftyp box: {archive_path}")
            major_brand = data[offset + header_size : offset + header_size + 4]
            if not all(32 <= byte <= 126 for byte in major_brand):
                raise TopicTransferError(f"Invalid MP4 major brand: {archive_path}")
            found_ftyp = True
            break
        offset += box_size
        if offset >= 4096:
            break
    if not found_ftyp:
        raise TopicTransferError(f"File is not a recognized MP4: {archive_path}")


def _validate_about_snapshots(staging_root: Path, slug: str) -> None:
    snapshot = staging_root / "about" / "CHANGELOG.md"
    canonical = staging_root / "content" / slug / "CHANGELOG.md"
    if snapshot.read_bytes() != canonical.read_bytes():
        raise TopicTransferError(
            f"About snapshot does not match canonical topic file: {canonical}"
        )


def _destination_paths(roots: TransferRoots, slug: str) -> list[str]:
    return [
        str(roots.content / slug),
        str(roots.media / slug),
        str(roots.sources / slug / "INTAKE.md"),
        str(roots.sources / slug / "SOURCES.md"),
    ]


def _materialize_staged_sources(staging_root: Path, manifest: Manifest) -> None:
    destination = staging_root / "sources" / manifest.topic_slug
    destination.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(staging_root / "about" / "INTAKE.md", destination / "INTAKE.md")
    shutil.copyfile(staging_root / "about" / "SOURCES.md", destination / "SOURCES.md")


def _append_import_provenance(
    path: Path, manifest: Manifest, archive_sha256: str
) -> None:
    text = path.read_text(encoding="utf-8").rstrip()
    entry = (
        f"\n\n## Imported {datetime.now().date().isoformat()}\n\n"
        f"- Source app version: `{manifest.source_app_version}`\n"
        f"- Archive format: `{manifest.archive_format}`\n"
        f"- Source topic: `{manifest.topic_slug}` (`{manifest.syllabus_version}`)\n"
        f"- Archive created: `{manifest.created_at}`\n"
        f"- Archive SHA-256: `{archive_sha256}`\n"
    )
    path.write_text(text + entry, encoding="utf-8", newline="\n")


def _install_staged_topic(
    roots: TransferRoots,
    adapter: TransferAdapter,
    staging_root: Path,
    report: ImportReport,
) -> None:
    slug = report.topic_slug
    live_content = roots.content / slug
    live_media = roots.media / slug
    live_sources = roots.sources / slug
    staged_content = staging_root / "content" / slug
    staged_media = staging_root / "media" / slug
    staged_sources = staging_root / "sources" / slug
    roots.root.mkdir(parents=True, exist_ok=True)
    install_workspace = Path(
        tempfile.mkdtemp(prefix=".learnup-install-", dir=roots.root)
    )
    backup: Path | None = None
    source_existed = {
        name: (live_sources / name).exists() for name in ("INTAKE.md", "SOURCES.md")
    }
    if live_sources.is_symlink() or live_media.is_symlink():
        raise TopicTransferError("Live topic source/media path cannot be a symlink")
    for name, existed in source_existed.items():
        source_file = live_sources / name
        if existed and (source_file.is_symlink() or not source_file.is_file()):
            raise TopicTransferError(
                f"Live About source is not a regular file: {source_file}"
            )
    try:
        prepared_content = install_workspace / "content"
        prepared_media = install_workspace / "media"
        prepared_sources = install_workspace / "sources"
        shutil.copytree(staged_content, prepared_content)
        if staged_media.exists():
            shutil.copytree(staged_media, prepared_media)
        else:
            prepared_media.mkdir()
        shutil.copytree(staged_sources, prepared_sources)
        if report.mode == "update":
            timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
            backup = roots.backups / f"{slug}-{timestamp}"
            backup.mkdir(parents=True, exist_ok=False)
            if live_content.exists():
                shutil.move(str(live_content), backup / "content")
            if live_media.exists():
                shutil.move(str(live_media), backup / "media")
            backup_sources = backup / "sources"
            backup_sources.mkdir()
            for name, existed in source_existed.items():
                if existed:
                    shutil.copy2(live_sources / name, backup_sources / name)
            report.backup = str(backup)
        roots.content.mkdir(parents=True, exist_ok=True)
        roots.media.mkdir(parents=True, exist_ok=True)
        live_sources.mkdir(parents=True, exist_ok=True)
        os.replace(prepared_content, live_content)
        os.replace(prepared_media, live_media)
        for name in ("INTAKE.md", "SOURCES.md"):
            os.replace(prepared_sources / name, live_sources / name)
        adapter.reseed_and_validate()
    except BaseException as install_error:
        rollback_error = _rollback_install(
            roots, adapter, slug, report.mode, backup, source_existed
        )
        if rollback_error is not None:
            raise TopicTransferError(
                f"Import failed ({install_error}); rollback also failed ({rollback_error})"
            ) from rollback_error
        raise
    finally:
        shutil.rmtree(install_workspace, ignore_errors=True)


def _rollback_install(
    roots: TransferRoots,
    adapter: TransferAdapter,
    slug: str,
    mode: str,
    backup: Path | None,
    source_existed: dict[str, bool],
) -> BaseException | None:
    try:
        live_content = roots.content / slug
        live_media = roots.media / slug
        live_sources = roots.sources / slug
        if live_content.exists():
            shutil.rmtree(live_content)
        if live_media.exists():
            shutil.rmtree(live_media)
        for name in ("INTAKE.md", "SOURCES.md"):
            (live_sources / name).unlink(missing_ok=True)
        if mode == "update":
            if backup is None:
                raise TopicTransferError("Update rollback has no backup")
            if (backup / "content").exists():
                shutil.copytree(backup / "content", live_content)
            if (backup / "media").exists():
                shutil.copytree(backup / "media", live_media)
            for name, existed in source_existed.items():
                if existed:
                    shutil.copy2(backup / "sources" / name, live_sources / name)
        if live_sources.exists() and not any(live_sources.iterdir()):
            live_sources.rmdir()
        adapter.reseed_and_validate()
    except BaseException as exc:
        return exc
    return None


def _check_compatibility(manifest: Manifest, destination_version: str) -> None:
    supported_format = parse_archive_version(ARCHIVE_FORMAT)
    incoming_format = parse_archive_version(manifest.archive_format)
    if (
        incoming_format[0] != supported_format[0]
        or incoming_format[1] > supported_format[1]
    ):
        raise TopicTransferError(
            f"Archive format {manifest.archive_format} is incompatible with supported {ARCHIVE_FORMAT}"
        )
    incoming_app = parse_app_version(manifest.source_app_version)
    destination_app = parse_app_version(destination_version)
    if incoming_app[0] != destination_app[0]:
        raise TopicTransferError(
            f"App major versions are incompatible: source {manifest.source_app_version}, "
            f"destination {destination_version}"
        )
    if incoming_app[1] > destination_app[1]:
        raise TopicTransferError(
            f"Topic requires app {manifest.source_app_version}; upgrade destination {destination_version}"
        )


def _read_app_version(pyproject: Path) -> str:
    _require_regular_file(pyproject)
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise TopicTransferError(f"Cannot read app version from {pyproject}") from exc
    project = data.get("project")
    if not isinstance(project, dict) or not isinstance(project.get("version"), str):
        raise TopicTransferError(f"Missing project.version in {pyproject}")
    version = project["version"]
    parse_app_version(version)
    return version


def _parse_created_at(value: str) -> datetime:
    if not value.endswith("Z"):
        raise TopicTransferError("created_at must end in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise TopicTransferError(
            "created_at is not a valid ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo != UTC:
        raise TopicTransferError("created_at must be UTC")
    return parsed


def _hash_file(path: Path) -> tuple[int, str]:
    before = path.stat()
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(_CHUNK_SIZE), b""):
            size += len(chunk)
            digest.update(chunk)
    after = path.stat()
    if (
        size != before.st_size
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
    ):
        raise TopicTransferError(f"File changed while being exported: {path}")
    return size, digest.hexdigest()


def _sha256_path(path: Path) -> str:
    return _hash_file(path)[1]


def _write_zip_bytes(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, _ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    archive.writestr(info, data)


def _write_zip_file(
    archive: zipfile.ZipFile, name: str, source: Path
) -> tuple[int, str]:
    info = zipfile.ZipInfo(name, _ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    digest = hashlib.sha256()
    size = 0
    with source.open("rb") as input_stream, archive.open(info, "w") as output_stream:
        while True:
            chunk = input_stream.read(_CHUNK_SIZE)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
            output_stream.write(chunk)
    return size, digest.hexdigest()


def _read_member_bounded(
    archive: zipfile.ZipFile, info: zipfile.ZipInfo, limit: int
) -> bytes:
    with archive.open(info, "r") as stream:
        data = stream.read(limit + 1)
        if len(data) > limit or stream.read(1):
            raise TopicTransferError(
                f"ZIP member exceeds its read limit: {info.filename}"
            )
    if len(data) != info.file_size:
        raise TopicTransferError(
            f"ZIP member size changed while reading: {info.filename}"
        )
    return data


def _copy_member(
    archive: zipfile.ZipFile, info: zipfile.ZipInfo, target: Path
) -> tuple[str, int]:
    digest = hashlib.sha256()
    written = 0
    with archive.open(info, "r") as source, target.open("xb") as destination:
        while True:
            chunk = source.read(_CHUNK_SIZE)
            if not chunk:
                break
            written += len(chunk)
            if written > info.file_size or written > MAX_FILE_BYTES:
                raise TopicTransferError(
                    f"ZIP member exceeded its declared size: {info.filename}"
                )
            digest.update(chunk)
            destination.write(chunk)
    return digest.hexdigest(), written


def _require_regular_file(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise TopicTransferError(f"Required path is not a regular file: {path}")


def _validate_transfer_roots(roots: TransferRoots) -> None:
    if not roots.root.is_dir():
        raise TopicTransferError(f"Repository root is not a directory: {roots.root}")
    for path in (roots.content, roots.sources, roots.media, roots.backups):
        if path.is_symlink():
            raise TopicTransferError(f"Topic-transfer root cannot be a symlink: {path}")
        try:
            path.resolve(strict=False).relative_to(roots.root)
        except ValueError as exc:
            raise TopicTransferError(
                f"Topic-transfer root escapes the repository: {path}"
            ) from exc


def _assert_tree_has_no_symlinks(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_symlink():
            raise TopicTransferError(f"Existing topic contains a symlink: {path}")
