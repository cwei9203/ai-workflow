import shutil
from pathlib import Path
from typing import Dict, List, Optional

from .discovery import discover_project
from .io_utils import atomic_write_text, contract_path, workflow_root, write_json
from .migration import migrate_legacy_copilot


MANAGED_START = "<!-- ai-development-workflow:start -->"
MANAGED_END = "<!-- ai-development-workflow:end -->"
LAUNCHER_MARKER = "ai-development-workflow:managed"


def _package_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resource_root(source_root: Path) -> Path:
    candidates = [
        source_root.resolve(),
        _package_root(),
        Path(__file__).resolve().parents[1],
        Path(__file__).resolve().parent,
    ]
    for candidate in candidates:
        if (candidate / "templates" / "workflow" / "entry.md").is_file():
            return candidate
    raise FileNotFoundError("Unable to locate workflow templates.")


def _managed_block(body: str, newline: str = "\n") -> str:
    normalized_body = body.replace("\r\n", "\n").replace("\r", "\n").strip()
    normalized = "{0}\n{1}\n{2}".format(MANAGED_START, normalized_body, MANAGED_END)
    return normalized.replace("\n", newline)


def update_managed_block(path: Path, body: str) -> None:
    if not path.exists():
        atomic_write_text(path, _managed_block(body) + "\n")
        return

    original = path.read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in original else "\n"
    block = _managed_block(body, newline=newline)
    start_count = original.count(MANAGED_START)
    end_count = original.count(MANAGED_END)
    if start_count != end_count or start_count > 1:
        raise ValueError("Invalid managed block markers in {0}".format(path))
    if start_count == 1:
        start = original.index(MANAGED_START)
        end = original.index(MANAGED_END, start) + len(MANAGED_END)
        updated = original[:start] + block + original[end:]
    else:
        separator = "" if not original else (newline if original.endswith(("\n", "\r")) else newline * 2)
        updated = original + separator + block + newline
    atomic_write_text(path, updated)


def _preflight_managed_block(path: Path) -> None:
    if not path.exists():
        return
    content = path.read_bytes().decode("utf-8")
    start_count = content.count(MANAGED_START)
    end_count = content.count(MANAGED_END)
    markers_reversed = (
        start_count == 1
        and end_count == 1
        and content.index(MANAGED_START) > content.index(MANAGED_END)
    )
    if start_count != end_count or start_count > 1 or markers_reversed:
        raise ValueError("Invalid managed block markers in {0}".format(path))


def _copy_text(source: Path, destination: Path, overwrite: bool = True) -> None:
    if destination.exists() and not overwrite:
        return
    atomic_write_text(destination, source.read_text(encoding="utf-8"))


def _copy_runtime(resources: Path, destination: Path) -> None:
    package_source = _package_root() / "src" / "ai_workflow"
    if not package_source.is_dir():
        # When running from an already-installed runtime.
        package_source = Path(__file__).resolve().parent
    package_destination = destination / "ai_workflow"
    package_destination.mkdir(parents=True, exist_ok=True)
    for source in package_source.glob("*.py"):
        _copy_text(source, package_destination / source.name)

    template_destination = destination / "templates"
    for source in (resources / "templates").rglob("*"):
        if source.is_file():
            relative = source.relative_to(resources / "templates")
            _copy_text(source, template_destination / relative)


def _install_launcher(path: Path, content: str, warnings: List[str], executable: bool = False) -> None:
    if path.exists() and LAUNCHER_MARKER not in path.read_text(encoding="utf-8", errors="ignore"):
        warnings.append("Kept existing launcher because it is not managed: {0}".format(path.name))
        return
    atomic_write_text(path, content, executable=executable)


def _preflight_launcher(path: Path) -> None:
    if not path.exists():
        return
    if LAUNCHER_MARKER not in path.read_text(encoding="utf-8", errors="ignore"):
        raise ValueError(
            "Existing {0} is not managed by this workflow; rename it before installation.".format(
                path.name
            )
        )


def install_workflow(
    source_root: Path,
    target_root: Path,
    remove_legacy_copilot: bool = False,
) -> Dict[str, object]:
    target = target_root.resolve()
    if not target.is_dir():
        raise NotADirectoryError("Target project does not exist: {0}".format(target))
    resources = _resource_root(source_root)
    installed_root = workflow_root(target)
    warnings: List[str] = []

    # Fail before writing anything when an existing adapter cannot be updated
    # without ambiguity.
    _preflight_managed_block(target / "AGENTS.md")
    _preflight_managed_block(target / "CLAUDE.md")
    _preflight_launcher(target / "aiw")
    _preflight_launcher(target / "aiw.cmd")
    if installed_root.exists() and any(installed_root.iterdir()) and not (
        installed_root / "VERSION"
    ).is_file():
        raise ValueError(
            "Existing .ai-workflow directory is not marked as managed; move or adopt it explicitly first."
        )

    # Kernel documents are version-owned and are refreshed on reinstall.
    for source in (resources / "templates" / "workflow").glob("*.md"):
        _copy_text(source, installed_root / "workflow" / source.name)

    # Project-owned knowledge, decisions, and notes are seeded only once.
    for source in (resources / "templates" / "knowledge").glob("*"):
        if not source.is_file():
            continue
        _copy_text(source, installed_root / "knowledge" / source.name, overwrite=False)
    notes_template = resources / "templates" / "project-notes.md"
    if notes_template.is_file():
        _copy_text(notes_template, installed_root / "project-notes.md", overwrite=False)

    schema = resources / "templates" / "project.schema.json"
    if schema.is_file():
        _copy_text(schema, installed_root / "project.schema.json")

    if not contract_path(target).exists():
        write_json(contract_path(target), discover_project(target))

    _copy_runtime(resources, installed_root / "runtime")
    atomic_write_text(installed_root / "VERSION", "0.2.0\n")
    atomic_write_text(
        installed_root / ".gitignore",
        "logs/\nmigrations/\nruntime/**/__pycache__/\n*.pyc\n",
    )

    migration: Optional[Dict[str, object]] = None
    if remove_legacy_copilot:
        # Run after the managed workflow directory exists for backups, but
        # before adapters are written so a legacy full-file adapter can be
        # replaced by the thin managed entry below.
        migration = migrate_legacy_copilot(target, apply=True)

    agents_body = (resources / "templates" / "AGENTS.block.md").read_text(encoding="utf-8")
    claude_body = (resources / "templates" / "CLAUDE.block.md").read_text(encoding="utf-8")
    update_managed_block(target / "AGENTS.md", agents_body)
    update_managed_block(target / "CLAUDE.md", claude_body)

    shell_launcher = """#!/bin/sh
# ai-development-workflow:managed
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT" || exit 1
PYTHONPATH="$ROOT/.ai-workflow/runtime${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m ai_workflow "$@"
"""
    windows_launcher = """@echo off
rem ai-development-workflow:managed
setlocal
set "PYTHONPATH=%~dp0.ai-workflow\\runtime;%PYTHONPATH%"
pushd "%~dp0" >nul
python -c "import sys" >nul 2>nul
if errorlevel 1 goto use_py
python -m ai_workflow %*
set "AIW_EXIT=%ERRORLEVEL%"
goto finish
:use_py
py -3 -m ai_workflow %*
set "AIW_EXIT=%ERRORLEVEL%"
:finish
popd >nul
exit /b %AIW_EXIT%
"""
    _install_launcher(target / "aiw", shell_launcher, warnings, executable=True)
    _install_launcher(target / "aiw.cmd", windows_launcher, warnings)

    return {
        "installed": True,
        "target": str(target),
        "warnings": warnings,
        "migration": migration,
    }
