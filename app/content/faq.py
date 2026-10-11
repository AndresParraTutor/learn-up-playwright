from __future__ import annotations

import re
from pathlib import Path

import yaml

FAQ_SECTION_MARKER = "\n## FAQ\n"
_ENTRY_RE = re.compile(
    r"(?:^|\n)### (?P<title>[^\n]+)\n"
    r"(?:(?:<!-- selected: (?P<selected>.*?) -->)\n)?"
    r"\n(?P<body>.*?)(?=\n### |\Z)",
    re.DOTALL,
)


def parse_faq_entries(markdown: str) -> list[tuple[str, str | None, str]]:
    if not markdown.strip():
        return []
    entries: list[tuple[str, str | None, str]] = []
    for match in _ENTRY_RE.finditer(markdown.strip()):
        title = match.group("title").strip()
        selected = match.group("selected")
        body = match.group("body").strip()
        if not title or not body:
            raise ValueError("Una entrada FAQ debe tener título y respuesta.")
        entries.append((title, selected.strip() if selected else None, body))
    if not entries or render_faq_entries(entries).strip() != markdown.strip():
        raise ValueError("El bloque FAQ tiene un formato no reconocido.")
    return entries


def render_faq_entries(entries: list[tuple[str, str | None, str]]) -> str:
    blocks: list[str] = []
    for title, selected, body in entries:
        clean_title = " ".join(title.split())
        clean_selected = " ".join(selected.split()) if selected else None
        heading = f"### {clean_title}"
        if clean_selected:
            heading += f"\n<!-- selected: {clean_selected} -->"
        blocks.append(f"{heading}\n\n{body.strip()}")
    return "\n\n".join(blocks).strip()


def append_faq_entry(
    markdown: str, title: str, selected_text: str | None, answer: str
) -> str:
    entries = parse_faq_entries(markdown) if markdown.strip() else []
    entries.append((title, selected_text, answer))
    return render_faq_entries(entries)


def remove_faq_entry(markdown: str, index: int) -> str:
    entries = parse_faq_entries(markdown)
    if index < 0 or index >= len(entries):
        raise IndexError("Entrada FAQ inexistente.")
    entries.pop(index)
    return render_faq_entries(entries)


def faq_from_lesson_text(text: str) -> str:
    if FAQ_SECTION_MARKER not in text:
        return ""
    return text.split(FAQ_SECTION_MARKER, 1)[1].strip()


def sync_markdown_faq_section(path: Path, faq_markdown: str) -> None:
    text = path.read_text(encoding="utf-8")
    base = text.split(FAQ_SECTION_MARKER, 1)[0].rstrip()
    if faq_markdown.strip():
        base += FAQ_SECTION_MARKER + faq_markdown.strip()
    path.write_text(base.rstrip() + "\n", encoding="utf-8", newline="\n")


def sync_lab_yaml_faq(path: Path, faq_markdown: str) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = parse_faq_entries(faq_markdown) if faq_markdown.strip() else []
    data["faq"] = [
        {"question": title, "selected_text": selected, "answer": body}
        for title, selected, body in entries
    ]
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )


def faq_from_lab_data(data: dict) -> str:
    raw = data.get("faq", [])
    if raw is None:
        return ""
    if not isinstance(raw, list):
        raise ValueError("faq debe ser una lista.")
    entries: list[tuple[str, str | None, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Cada FAQ del laboratorio debe ser un objeto.")
        entries.append(
            (
                str(item["question"]),
                str(item["selected_text"]) if item.get("selected_text") else None,
                str(item["answer"]),
            )
        )
    return render_faq_entries(entries)
