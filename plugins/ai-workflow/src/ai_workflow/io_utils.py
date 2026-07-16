import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional


WORKFLOW_DIR = ".ai-workflow"
CONTRACT_FILE = "project.json"


def workflow_root(project_root: Path) -> Path:
    return project_root.resolve() / WORKFLOW_DIR


def contract_path(project_root: Path) -> Path:
    return workflow_root(project_root) / CONTRACT_FILE


def find_project_root(start: Optional[Path] = None) -> Path:
    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if contract_path(candidate).is_file():
            return candidate
    raise FileNotFoundError(
        "No .ai-workflow/project.json was found in this directory or its parents. "
        "Run 'aiw init <project>' first."
    )


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object in {0}".format(path))
    return value


def atomic_write_text(path: Path, content: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".{0}.".format(path.name), dir=str(path.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
        if executable:
            temporary.chmod(0o755)
        os.replace(str(temporary), str(path))
    finally:
        if temporary.exists():
            temporary.unlink()


def write_json(path: Path, value: Dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")
