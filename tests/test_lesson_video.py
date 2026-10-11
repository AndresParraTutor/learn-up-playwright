import json
import subprocess
from pathlib import Path

import pytest

from app.services import lesson_video


def test_prepare_html_source_as_notebooklm_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(lesson_video, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(lesson_video, "MEDIA_ROOT", tmp_path / "media")
    source = tmp_path / "selenium.html"
    source.write_text(
        """
        <html>
          <head>
            <title>Selenium Overview</title>
            <link rel="canonical" href="https://www.selenium.dev/documentation/overview/">
            <style>.hidden { display: none; }</style>
          </head>
          <body>
            <nav>Menú que no pertenece al artículo</nav>
            <main><h1>Selenium</h1><p>Automatiza navegadores reales.</p></main>
            <script>window.secret = true;</script>
          </body>
        </html>
        """,
        encoding="utf-8",
    )

    prepared = lesson_video._prepare_source_for_notebook("playwright", source)

    assert prepared.name == "selenium.html.txt"
    assert prepared.parent == tmp_path / ".learnup-cache" / "playwright" / "notebook_sources"
    assert not (tmp_path / "media").exists()
    converted = prepared.read_text(encoding="utf-8")
    assert "Título: Selenium Overview" in converted
    assert "URL canónica: https://www.selenium.dev/documentation/overview/" in converted
    assert "Automatiza navegadores reales." in converted
    assert "Menú que no pertenece" not in converted
    assert "window.secret" not in converted
    assert ".hidden" not in converted


def test_prepare_json_source_as_notebooklm_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(lesson_video, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(lesson_video, "MEDIA_ROOT", tmp_path / "media")
    source = tmp_path / "metadata.json"
    source.write_text('{"version":"1.62.1","name":"@playwright/test"}', encoding="utf-8")

    prepared = lesson_video._prepare_source_for_notebook("playwright", source)

    assert prepared.name == "metadata.json.txt"
    assert prepared.parent == tmp_path / ".learnup-cache" / "playwright" / "notebook_sources"
    assert not (tmp_path / "media").exists()
    converted = prepared.read_text(encoding="utf-8")
    assert converted.startswith("Fuente original: metadata.json")
    assert '"name": "@playwright/test"' in converted
    assert '"version": "1.62.1"' in converted


def test_run_captured_forces_utf8_and_normalizes_missing_streams(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def fake_subprocess_run(
        cmd: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        observed.update(kwargs)
        return subprocess.CompletedProcess(cmd, 0, stdout=None, stderr=None)

    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)

    result = lesson_video._run_captured(["notebooklm", "language", "list"])

    assert observed == {
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "capture_output": True,
    }
    assert result.stdout == ""
    assert result.stderr == ""


def test_console_safe_escapes_characters_unsupported_by_windows_code_page() -> None:
    assert lesson_video._console_safe("Español 日本語", "cp1252") == (
        "Español \\u65e5\\u672c\\u8a9e"
    )


def test_sync_sources_reconciles_remote_titles_and_converts_unsupported_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    sources_dir = repo_root / "sources" / "playwright"
    sources_dir.mkdir(parents=True)
    (sources_dir / "existing.md").write_text("Existente", encoding="utf-8")
    (sources_dir / "fresh.md").write_text("Nueva", encoding="utf-8")
    (sources_dir / "page.html").write_text(
        "<main><h1>Referencia</h1><p>Contenido útil.</p></main>",
        encoding="utf-8",
    )
    (sources_dir / "package.json").write_text('{"version":"1.0"}', encoding="utf-8")
    (sources_dir / "INTAKE.md").write_text("No subir", encoding="utf-8")
    (sources_dir / "SOURCES.md").write_text("No subir", encoding="utf-8")

    monkeypatch.setattr(lesson_video, "REPO_ROOT", repo_root)
    monkeypatch.setattr(lesson_video, "MEDIA_ROOT", repo_root / "media")
    monkeypatch.setattr(lesson_video, "_notebooklm_cmd", lambda *args: list(args))
    uploaded: list[str] = []

    def fake_run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        if cmd[:2] == ["source", "list"]:
            stdout = json.dumps({"sources": [{"title": "existing.md"}]})
            return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")
        if cmd[:2] == ["source", "add"]:
            uploaded.append(Path(cmd[2]).name)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        raise AssertionError(f"Comando inesperado: {cmd}")

    monkeypatch.setattr(lesson_video, "_run", fake_run)

    lesson_video._sync_sources("playwright", "notebook-id")

    assert uploaded == ["fresh.md", "package.json.txt", "page.html.txt"]
    state_file = repo_root / "media" / "playwright" / ".sources_added.json"
    assert set(json.loads(state_file.read_text(encoding="utf-8"))) == {
        "existing.md",
        "fresh.md",
        "package.json",
        "page.html",
    }


def test_sync_sources_checkpoints_each_successful_upload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    sources_dir = repo_root / "sources" / "playwright"
    sources_dir.mkdir(parents=True)
    (sources_dir / "a.md").write_text("A", encoding="utf-8")
    (sources_dir / "b.md").write_text("B", encoding="utf-8")

    monkeypatch.setattr(lesson_video, "REPO_ROOT", repo_root)
    monkeypatch.setattr(lesson_video, "MEDIA_ROOT", repo_root / "media")
    monkeypatch.setattr(lesson_video, "_notebooklm_cmd", lambda *args: list(args))

    def fake_run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        if cmd[:2] == ["source", "list"]:
            return subprocess.CompletedProcess(
                cmd, 0, stdout=json.dumps({"sources": []}), stderr=""
            )
        if cmd[:3] == ["source", "add", str(sources_dir / "a.md")]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:3] == ["source", "add", str(sources_dir / "b.md")]:
            raise lesson_video.LessonVideoError("fallo simulado")
        raise AssertionError(f"Comando inesperado: {cmd}")

    monkeypatch.setattr(lesson_video, "_run", fake_run)

    with pytest.raises(lesson_video.LessonVideoError, match="fallo simulado"):
        lesson_video._sync_sources("playwright", "notebook-id")

    state_file = repo_root / "media" / "playwright" / ".sources_added.json"
    assert json.loads(state_file.read_text(encoding="utf-8")) == ["a.md"]
