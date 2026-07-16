import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


_LEGACY_ADAPTER_SIGNATURES = (
    "REPO-ROOT/.github/copilot-instructions.md",
    "Treat the processed request as \"the LATEST chat message\"",
)

_LEGACY_PROMPT_SIGNATURES = {
    ".github/prompts/ask.prompt.md": ("Leveraging the Knowledge Base", "analysis work"),
    ".github/prompts/investigate.prompt.md": ("Copilot_Investigate.md", "# !!!INVESTIGATE!!!"),
    ".github/prompts/review.prompt.md": ("Review Task for Investigation", "## REVIEW COMMENTS"),
    ".github/prompts/refine.prompt.md": ("copilotRemember.ps1", "# !!!LEARNING!!!"),
    ".github/prompts/kb.prompt.md": ("Copilot_KB.md", "# !!!KNOWLEDGE BASE!!!"),
    ".github/prompts/kb-refine.prompt.md": ("Knowledge Base Refine", "Index_<PROJECT>.md"),
}


def _is_ignored(relative: Path) -> bool:
    return any(part in {".git", ".ai-workflow"} for part in relative.parts)


def find_legacy_copilot_files(project_root: Path) -> List[Path]:
    """Return conservative, path-based legacy Copilot candidates.

    The migration intentionally does not delete generic prompt files or GitHub
    workflows merely because they may once have been used by an AI tool.
    """

    root = project_root.resolve()
    candidates = []
    search_roots = [root / ".github"]
    for top_level_name in ("COPILOT.md", "Copilot.md", "copilot.md"):
        top_level = root / top_level_name
        if top_level.is_file():
            candidates.append(top_level.relative_to(root))
    for adapter_name in ("AGENTS.md", "CLAUDE.md"):
        adapter = root / adapter_name
        if not adapter.is_file():
            continue
        try:
            content = adapter.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if all(signature in content for signature in _LEGACY_ADAPTER_SIGNATURES):
            candidates.append(adapter.relative_to(root))

    for relative_name, signatures in _LEGACY_PROMPT_SIGNATURES.items():
        prompt = root / Path(relative_name)
        if not prompt.is_file():
            continue
        try:
            content = prompt.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if all(signature in content for signature in signatures):
            candidates.append(prompt.relative_to(root))

    for search_root in search_roots:
        if not search_root.exists():
            continue
        for path in search_root.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            if _is_ignored(relative):
                continue
            relative_posix = relative.as_posix()
            is_main_instruction = relative_posix.lower() == ".github/copilot-instructions.md"
            is_legacy_script = (
                len(relative.parts) == 3
                and relative.parts[0].lower() == ".github"
                and relative.parts[1].lower() == "scripts"
                and path.name.lower().startswith("copilot")
                and path.suffix.lower() in {".ps1", ".txt"}
            )
            is_legacy_task_log = (
                len(relative.parts) == 3
                and relative.parts[0].lower() == ".github"
                and relative.parts[1].lower() == "tasklogs"
                and path.name.lower().startswith("copilot_")
                and path.suffix.lower() == ".md"
            )
            if is_main_instruction or is_legacy_script or is_legacy_task_log:
                candidates.append(relative)

    return sorted(set(candidates), key=lambda item: item.as_posix().lower())


def migrate_legacy_copilot(
    project_root: Path,
    apply: bool = False,
    timestamp: Optional[str] = None,
) -> Dict[str, object]:
    root = project_root.resolve()
    candidates = find_legacy_copilot_files(root)
    result: Dict[str, object] = {
        "applied": False,
        "candidates": [path.as_posix() for path in candidates],
        "backup": None,
    }
    if not apply or not candidates:
        return result

    stamp = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = root / ".ai-workflow" / "migrations" / stamp
    if backup_root.exists():
        raise FileExistsError("Migration backup already exists: {0}".format(backup_root))

    copied = []
    try:
        for relative in candidates:
            source = root / relative
            destination = backup_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(source), str(destination))
            copied.append(relative)

        manifest = {
            "migration": "legacy-copilot-removal",
            "files": [
                {"original": relative.as_posix(), "backup": relative.as_posix()}
                for relative in copied
            ],
        }
        backup_root.mkdir(parents=True, exist_ok=True)
        (backup_root / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        for relative in copied:
            (root / relative).unlink()
    except Exception:
        # Originals are not deleted until every backup and the manifest exist.
        # If deletion itself fails, backed-up copies remain available.
        raise

    result.update(
        {
            "applied": True,
            "backup": backup_root.relative_to(root).as_posix(),
        }
    )
    return result
