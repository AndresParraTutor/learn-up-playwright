from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from yaml.events import AliasEvent, NodeEvent

from .types import TopicTransferError

FAQ_SECTION_MARKER = "\n## FAQ\n"
_ENTRY_RE = re.compile(
    r"^### (?P<question>[^\n]+)\n"
    r"(?:<!-- selected: (?P<selected>[^\n]*?) -->\n)?"
    r"\n(?P<answer>.*?)(?=^### |\Z)",
    re.MULTILINE | re.DOTALL,
)


@dataclass(frozen=True, slots=True)
class FaqEntry:
    question: str
    selected_text: str | None
    answer: str

    def dedupe_key(self) -> tuple[str, str, str]:
        return (
            _collapse(self.question),
            _collapse(self.selected_text or ""),
            _collapse(self.answer),
        )


@dataclass(slots=True)
class MergeResult:
    merged: int
    skipped: list[str]


def merge_topic_q_and_a(existing_topic: Path, staged_topic: Path) -> MergeResult:
    merged = 0
    skipped: list[str] = []
    incoming_paths = {
        path.relative_to(staged_topic)
        for path in staged_topic.rglob("*")
        if path.is_file() and _is_q_and_a_file(path.relative_to(staged_topic))
    }
    local_paths = {
        path.relative_to(existing_topic)
        for path in existing_topic.rglob("*")
        if path.is_file() and _is_q_and_a_file(path.relative_to(existing_topic))
    }

    for relative in sorted(incoming_paths):
        incoming = staged_topic / relative
        local = existing_topic / relative
        if not local.exists():
            _validate_q_and_a_file(incoming, relative)
            continue
        if relative.suffix == ".md":
            count, reason = _merge_markdown(local, incoming, relative)
        else:
            count, reason = _merge_lab_yaml(local, incoming, relative)
        merged += count
        if reason is not None:
            skipped.append(reason)

    for relative in sorted(local_paths - incoming_paths):
        entries = _read_entries(existing_topic / relative, relative)
        if entries:
            skipped.append(
                f"{relative.as_posix()}: target is absent from incoming topic"
            )

    return MergeResult(merged=merged, skipped=skipped)


def _is_q_and_a_file(relative: Path) -> bool:
    parts = relative.parts
    if relative.suffix == ".md":
        return (len(parts) == 3 and parts[0] == "lessons") or (
            len(parts) == 3 and parts[:2] == ("strategy", "lessons")
        )
    return relative.suffix == ".yaml" and len(parts) == 3 and parts[0] == "labs"


def _validate_q_and_a_file(path: Path, relative: Path) -> None:
    _read_entries(path, relative)


def _read_entries(path: Path, relative: Path) -> list[FaqEntry]:
    if relative.suffix == ".md":
        text = _read_text(path)
        _, entries = parse_markdown_faq(text, relative.as_posix())
        return entries
    data = _load_yaml(path)
    _, entries = _lab_identity_and_entries(data, relative)
    return entries


def _merge_markdown(
    local: Path, incoming: Path, relative: Path
) -> tuple[int, str | None]:
    local_text = _read_text(local)
    incoming_text = _read_text(incoming)
    local_identity = _markdown_identity(local_text, relative)
    incoming_identity = _markdown_identity(incoming_text, relative)
    _, local_entries = parse_markdown_faq(local_text, relative.as_posix())
    base, incoming_entries = parse_markdown_faq(incoming_text, relative.as_posix())
    if local_identity != incoming_identity:
        reason = None
        if local_entries:
            reason = f"{relative.as_posix()}: stable content identity changed"
        return 0, reason
    entries, count = _merge_entries(incoming_entries, local_entries)
    incoming.write_text(
        render_markdown_faq(base, entries), encoding="utf-8", newline="\n"
    )
    return count, None


def _merge_lab_yaml(
    local: Path, incoming: Path, relative: Path
) -> tuple[int, str | None]:
    local_data = _load_yaml(local)
    incoming_data = _load_yaml(incoming)
    local_identity, local_entries = _lab_identity_and_entries(local_data, relative)
    incoming_identity, incoming_entries = _lab_identity_and_entries(
        incoming_data, relative
    )
    if local_identity != incoming_identity:
        reason = None
        if local_entries:
            reason = f"{relative.as_posix()}: stable content identity changed"
        return 0, reason
    entries, count = _merge_entries(incoming_entries, local_entries)
    incoming_data["faq"] = [_entry_as_yaml(entry) for entry in entries]
    text = yaml.safe_dump(
        incoming_data,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=1000,
    )
    incoming.write_text(text, encoding="utf-8", newline="\n")
    return count, None


def parse_markdown_faq(text: str, label: str) -> tuple[str, list[FaqEntry]]:
    if FAQ_SECTION_MARKER not in text:
        return text.rstrip() + "\n", []
    base, block = text.split(FAQ_SECTION_MARKER, 1)
    if FAQ_SECTION_MARKER in block:
        raise TopicTransferError(f"{label} contains more than one FAQ section")
    entries: list[FaqEntry] = []
    position = 0
    for match in _ENTRY_RE.finditer(block):
        if block[position : match.start()].strip():
            raise TopicTransferError(f"{label} has malformed FAQ content")
        question = match.group("question").strip()
        selected = match.group("selected")
        answer = match.group("answer").strip()
        if not question or not answer:
            raise TopicTransferError(f"{label} has an empty FAQ question or answer")
        if selected is not None:
            selected = selected.strip() or None
        entries.append(
            FaqEntry(question=question, selected_text=selected, answer=answer)
        )
        position = match.end()
    if block[position:].strip() or (block.strip() and not entries):
        raise TopicTransferError(f"{label} has malformed FAQ content")
    return base.rstrip() + "\n", entries


def render_markdown_faq(base: str, entries: list[FaqEntry]) -> str:
    clean_base = base.rstrip()
    if not entries:
        return clean_base + "\n"
    rendered: list[str] = []
    for entry in entries:
        section = f"### {entry.question}\n"
        if entry.selected_text is not None:
            if "\n" in entry.selected_text or "-->" in entry.selected_text:
                raise TopicTransferError(
                    "FAQ selected text cannot contain a newline or '-->'"
                )
            section += f"<!-- selected: {entry.selected_text} -->\n"
        rendered.append(f"{section}\n{entry.answer.strip()}")
    return f"{clean_base}{FAQ_SECTION_MARKER}\n" + "\n\n".join(rendered) + "\n"


def _markdown_identity(text: str, relative: Path) -> tuple[str, str, str]:
    if not text.startswith("---\n"):
        raise TopicTransferError(f"{relative.as_posix()} is missing YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise TopicTransferError(
            f"{relative.as_posix()} has malformed YAML frontmatter"
        )
    frontmatter = _load_yaml_text(text[4:end], relative.as_posix())
    if not isinstance(frontmatter, dict):
        raise TopicTransferError(f"{relative.as_posix()} frontmatter must be a mapping")
    if relative.parts[0] == "lessons":
        key = frontmatter.get("objective")
        kind = "lesson"
    else:
        key = frontmatter.get("topic")
        kind = "strategy"
    if not isinstance(key, str) or not key:
        raise TopicTransferError(
            f"{relative.as_posix()} is missing its stable identity"
        )
    return kind, key, relative.stem


def _lab_identity_and_entries(
    data: object, relative: Path
) -> tuple[tuple[str, str, str], list[FaqEntry]]:
    if not isinstance(data, dict):
        raise TopicTransferError(f"{relative.as_posix()} must be a YAML mapping")
    objective = data.get("objective")
    if not isinstance(objective, str) or not objective:
        raise TopicTransferError(f"{relative.as_posix()} is missing objective")
    raw_entries = data.get("faq", [])
    if not isinstance(raw_entries, list):
        raise TopicTransferError(f"{relative.as_posix()} faq must be a list")
    entries: list[FaqEntry] = []
    for raw in raw_entries:
        if not isinstance(raw, dict) or not {"question", "answer"} <= set(raw):
            raise TopicTransferError(f"{relative.as_posix()} has malformed FAQ entry")
        if set(raw) - {"question", "answer", "selected_text"}:
            raise TopicTransferError(
                f"{relative.as_posix()} FAQ entry has unknown keys"
            )
        question = raw["question"]
        answer = raw["answer"]
        selected = raw.get("selected_text")
        if not isinstance(question, str) or not question.strip():
            raise TopicTransferError(
                f"{relative.as_posix()} has an invalid FAQ question"
            )
        if not isinstance(answer, str) or not answer.strip():
            raise TopicTransferError(f"{relative.as_posix()} has an invalid FAQ answer")
        if selected is not None and not isinstance(selected, str):
            raise TopicTransferError(f"{relative.as_posix()} has invalid selected_text")
        entries.append(FaqEntry(question.strip(), selected, answer.strip()))
    return ("lab", objective, relative.stem), entries


def _entry_as_yaml(entry: FaqEntry) -> dict[str, str]:
    value = {"question": entry.question, "answer": entry.answer}
    if entry.selected_text is not None:
        value["selected_text"] = entry.selected_text
    return value


def _merge_entries(
    incoming: list[FaqEntry], local: list[FaqEntry]
) -> tuple[list[FaqEntry], int]:
    result = list(incoming)
    seen = {entry.dedupe_key() for entry in incoming}
    merged = 0
    for entry in local:
        key = entry.dedupe_key()
        if key not in seen:
            result.append(entry)
            seen.add(key)
            merged += 1
    return result, merged


def _read_text(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise TopicTransferError(f"{path} is not valid UTF-8") from exc
    if "\x00" in text:
        raise TopicTransferError(f"{path} contains a NUL byte")
    return text


def _load_yaml(path: Path) -> object:
    return _load_yaml_text(_read_text(path), str(path))


def _load_yaml_text(text: str, label: str) -> object:
    try:
        for event in yaml.parse(text):
            if isinstance(event, AliasEvent):
                raise TopicTransferError(f"{label} cannot contain YAML aliases")
            if isinstance(event, NodeEvent) and event.anchor is not None:
                raise TopicTransferError(f"{label} cannot contain YAML anchors")
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise TopicTransferError(f"{label} is malformed YAML") from exc


def _collapse(value: str) -> str:
    return " ".join(value.split())
