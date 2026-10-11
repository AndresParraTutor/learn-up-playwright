from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = REPO_ROOT / "hosted" / "deployment-policy.json"
SECRET_PATTERNS = (
    re.compile(r"sk-(?:proj|svcacct)-[A-Za-z0-9_-]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(
        r"(?i)(?:OPENAI_API_KEY|LEARNUP_LLM_API_KEY)[ \t]*=[ \t]*[^\s<][^\s]{7,}"
    ),
)


class HostedPackageError(ValueError):
    pass


def _load_policy(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HostedPackageError(f"No se pudo leer la política {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise HostedPackageError("La política de despliegue debe ser un objeto JSON.")
    return value


def _string_list(policy: dict[str, object], key: str) -> list[str]:
    value = policy.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise HostedPackageError(f"La política requiere una lista de strings en {key}.")
    return value


def _inside_repo(repo_root: Path, relative: str) -> Path:
    candidate = (repo_root / relative).resolve()
    try:
        candidate.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise HostedPackageError(f"Ruta fuera del repositorio: {relative}") from exc
    return candidate


def _candidate_files(
    repo_root: Path, roots: list[str], ignored_components: set[str]
) -> list[Path]:
    files: set[Path] = set()
    for relative in roots:
        root = _inside_repo(repo_root, relative)
        if not root.is_dir():
            raise HostedPackageError(f"No existe el directorio candidato {relative}.")
        for current, directory_names, file_names in os.walk(
            root, topdown=True, followlinks=False
        ):
            current_path = Path(current)
            included_directories: list[str] = []
            for name in directory_names:
                path = current_path / name
                relative_path = path.relative_to(repo_root)
                if set(relative_path.parts) & ignored_components:
                    continue
                if path.is_symlink():
                    raise HostedPackageError(
                        f"No se permiten enlaces en el paquete: {path}"
                    )
                included_directories.append(name)
            directory_names[:] = included_directories
            for name in file_names:
                path = current_path / name
                relative_path = path.relative_to(repo_root)
                if set(relative_path.parts) & ignored_components:
                    continue
                if path.is_symlink():
                    raise HostedPackageError(
                        f"No se permiten enlaces en el paquete: {path}"
                    )
                if path.is_file():
                    files.add(path)
    return sorted(files)


def _check_paths(
    repo_root: Path, files: list[Path], policy: dict[str, object]
) -> None:
    forbidden_components = set(_string_list(policy, "forbidden_path_components"))
    forbidden_filenames = set(_string_list(policy, "forbidden_filenames"))
    forbidden_suffixes = tuple(_string_list(policy, "forbidden_suffixes"))
    for path in files:
        relative = path.resolve().relative_to(repo_root.resolve())
        parts = set(relative.parts)
        if parts & forbidden_components:
            raise HostedPackageError(f"Ruta local prohibida en el paquete: {relative}")
        if path.name in forbidden_filenames:
            raise HostedPackageError(f"Archivo local prohibido en el paquete: {relative}")
        if any(path.name.endswith(suffix) for suffix in forbidden_suffixes):
            raise HostedPackageError(f"Tipo de archivo prohibido en el paquete: {relative}")


def _check_required(repo_root: Path, policy: dict[str, object]) -> None:
    missing = [
        relative
        for relative in _string_list(policy, "required_paths")
        if not _inside_repo(repo_root, relative).is_file()
    ]
    if missing:
        raise HostedPackageError("Faltan archivos requeridos: " + ", ".join(missing))


def _scan_secrets(repo_root: Path, files: list[Path]) -> None:
    findings: list[str] = []
    for path in files:
        raw = path.read_bytes()
        if b"\x00" in raw:
            continue
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            relative = path.resolve().relative_to(repo_root.resolve())
            raise HostedPackageError(
                f"El archivo candidato no es UTF-8: {relative}"
            ) from exc
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            findings.append(path.resolve().relative_to(repo_root.resolve()).as_posix())
    if findings:
        raise HostedPackageError(
            "El escaneo detectó posibles secretos en: " + ", ".join(findings)
        )


def _check_generated(repo_root: Path, topics: list[str]) -> None:
    script = repo_root / "scripts" / "export_hosted_content.py"
    output_dir = repo_root / "hosted" / "generated"
    for topic_slug in topics:
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                topic_slug,
                "--output-dir",
                str(output_dir),
                "--check",
            ],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise HostedPackageError(
                f"El manifiesto generado de {topic_slug} no coincide: {detail}"
            )


def verify(repo_root: Path, policy_path: Path) -> int:
    policy = _load_policy(policy_path)
    roots = _string_list(policy, "candidate_roots")
    topics = _string_list(policy, "topics")
    ignored_components = set(_string_list(policy, "ignored_worktree_components"))
    files = _candidate_files(repo_root, roots, ignored_components)
    _check_paths(repo_root, files, policy)
    _check_required(repo_root, policy)
    _scan_secrets(repo_root, files)
    _check_generated(repo_root, topics)
    return len(files)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verifica exclusiones, secretos y artefactos del paquete alojado."
    )
    parser.add_argument("--policy", type=Path, default=POLICY_PATH)
    args = parser.parse_args()
    try:
        count = verify(REPO_ROOT, args.policy)
    except HostedPackageError as exc:
        parser.error(str(exc))
    print(f"Paquete alojado verificado: {count} archivos candidatos.")


if __name__ == "__main__":
    main()
