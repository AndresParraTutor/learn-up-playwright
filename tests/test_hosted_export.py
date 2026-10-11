from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.export_hosted_content import (
    HostedExportError,
    build_topic_artifacts,
    export_topic,
)
from scripts.verify_hosted_package import (
    POLICY_PATH,
    REPO_ROOT,
    HostedPackageError,
    _candidate_files,
    _scan_secrets,
    verify,
)


def test_hosted_export_has_stable_ids_and_complete_course() -> None:
    artifacts = build_topic_artifacts(REPO_ROOT, "playwright")
    seed = json.loads(artifacts["playwright.seed.json"])
    media = json.loads(artifacts["playwright.media.json"])

    assert seed["counts"] == {
        "domains": 7,
        "objectives": 25,
        "lessons": 25,
        "questions": 75,
        "labs": 25,
        "mocks": 1,
    }
    assert seed["lessons"][0]["id"].startswith("topic:playwright:lesson:")
    assert seed["questions"][0]["id"] == "topic:playwright:question:1.1-001"
    assert seed["questions"][0]["choices"][0]["id"].endswith(":choice:0")
    assert seed["topic"]["assessment"]["enabled"] is False
    assert media["present_count"] == 25
    assert media["missing_count"] == 0
    assert sum(item["bytes"] or 0 for item in media["objects"]) == 857_538_801
    assert all(not Path(item["source_path"]).is_absolute() for item in media["objects"])


def test_hosted_export_check_detects_stale_output(tmp_path: Path) -> None:
    export_topic(REPO_ROOT, "playwright", tmp_path, check=False)
    export_topic(REPO_ROOT, "playwright", tmp_path, check=True)
    seed_path = tmp_path / "playwright.seed.json"
    seed_path.write_bytes(seed_path.read_bytes() + b"\n")

    with pytest.raises(HostedExportError, match="no están actualizados"):
        export_topic(REPO_ROOT, "playwright", tmp_path, check=True)


def test_hosted_candidate_policy_and_secret_scan_pass() -> None:
    assert verify(REPO_ROOT, POLICY_PATH) >= 5


def test_secret_scan_allows_empty_example_but_rejects_a_value(tmp_path: Path) -> None:
    example = tmp_path / ".env.example"
    example.write_text("OPENAI_API_KEY=\nOPENAI_MODEL=\n", encoding="utf-8")
    _scan_secrets(tmp_path, [example])

    example.write_text("OPENAI_API_KEY=not-a-real-secret\n", encoding="utf-8")
    with pytest.raises(HostedPackageError, match="posibles secretos"):
        _scan_secrets(tmp_path, [example])


def test_candidate_scan_prunes_ignored_dependency_symlinks(tmp_path: Path) -> None:
    candidate = tmp_path / "hosted"
    candidate.mkdir()
    included = candidate / "README.md"
    included.write_text("candidate", encoding="utf-8")
    ignored_bin = candidate / "node_modules" / ".bin"
    ignored_bin.mkdir(parents=True)
    target = candidate / "tool.js"
    target.write_text("tool", encoding="utf-8")
    link = ignored_bin / "tool"
    try:
        link.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"El entorno no permite crear symlinks: {exc}")

    assert _candidate_files(tmp_path, ["hosted"], {"node_modules"}) == [
        included,
        target,
    ]


def test_candidate_scan_rejects_a_nonignored_symlink(tmp_path: Path) -> None:
    candidate = tmp_path / "hosted"
    candidate.mkdir()
    target = tmp_path / "outside.txt"
    target.write_text("outside", encoding="utf-8")
    link = candidate / "outside.txt"
    try:
        link.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"El entorno no permite crear symlinks: {exc}")

    with pytest.raises(HostedPackageError, match="No se permiten enlaces"):
        _candidate_files(tmp_path, ["hosted"], {"node_modules"})
