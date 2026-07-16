import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .io_utils import read_json, workflow_root, write_json


class TaskError(RuntimeError):
    pass


LIFECYCLES = {
    "analyze": ["intake", "context_ready", "analyzing", "reporting", "completed"],
    "change": [
        "intake",
        "context_ready",
        "acceptance_defined",
        "implementing",
        "verifying",
        "reviewing",
        "completed",
    ],
    "review": ["intake", "context_ready", "reviewing", "completed"],
    "learn": ["intake", "context_ready", "extracting", "publishing", "completed"],
}


def _tasks_root(project_root: Path) -> Path:
    return workflow_root(project_root) / "tasks"


def _current_path(project_root: Path) -> Path:
    return _tasks_root(project_root) / "current.json"


def _slugify(title: str) -> str:
    value = re.sub(r"[^\w-]+", "-", title.lower(), flags=re.UNICODE).strip("-_	")
    return (value or "task")[:48]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _task_dir(project_root: Path, task_id: str) -> Path:
    return _tasks_root(project_root) / "active" / task_id


def _meaningful_markdown(path: Path) -> bool:
    if not path.is_file():
        return False
    content = path.read_text(encoding="utf-8")
    content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
    lines = [
        line.strip()
        for line in content.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return bool(lines)


def start_task(
    project_root: Path,
    title: str,
    kind: str = "change",
    now: Optional[str] = None,
) -> Dict[str, object]:
    root = project_root.resolve()
    if kind not in LIFECYCLES:
        raise TaskError("Unknown task kind: {0}".format(kind))
    if load_current_task(root) is not None:
        raise TaskError("A task is already active. Complete or archive it first.")

    stamp = now or datetime.now().strftime("%Y%m%d-%H%M%S")
    task_id = "{0}-{1}".format(stamp, _slugify(title))
    directory = _task_dir(root, task_id)
    if directory.exists():
        raise TaskError("Task already exists: {0}".format(task_id))
    directory.mkdir(parents=True)

    task: Dict[str, object] = {
        "id": task_id,
        "title": title,
        "kind": kind,
        "state": LIFECYCLES[kind][0],
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "verification": {"status": "not_run", "selected": []},
    }
    write_json(directory / "task.json", task)
    write_json(_current_path(root), {"id": task_id})

    (directory / "request.md").write_text(
        "# Request\n\n{0}\n".format(title), encoding="utf-8"
    )
    (directory / "context.md").write_text(
        "# Context\n\n<!-- Record relevant files, constraints, and existing patterns. -->\n",
        encoding="utf-8",
    )
    (directory / "acceptance.md").write_text(
        "# Acceptance\n\n<!-- Replace this placeholder with observable completion criteria. -->\n",
        encoding="utf-8",
    )
    (directory / "plan.md").write_text(
        "# Plan\n\n<!-- Record ordered implementation steps. -->\n", encoding="utf-8"
    )
    (directory / "decisions.md").write_text(
        "# Decisions\n\n<!-- Record non-trivial choices and rejected alternatives. -->\n",
        encoding="utf-8",
    )
    (directory / "verification.md").write_text("# Verification\n", encoding="utf-8")
    (directory / "review.md").write_text(
        "# Review\n\n<!-- Record findings or state why none remain. -->\n", encoding="utf-8"
    )
    if kind == "analyze":
        (directory / "report.md").write_text(
            "# Report\n\n<!-- Record evidence-backed analysis and conclusions. -->\n",
            encoding="utf-8",
        )
    if kind == "learn":
        (directory / "learnings.md").write_text(
            "# Learnings\n\n<!-- Record durable rules and their source task references. -->\n",
            encoding="utf-8",
        )
    return task


def load_current_task(project_root: Path) -> Optional[Dict[str, object]]:
    pointer = _current_path(project_root)
    if not pointer.is_file():
        return None
    current = read_json(pointer)
    task_id = current.get("id")
    if not isinstance(task_id, str):
        raise TaskError("Invalid current task pointer.")
    task_file = _task_dir(project_root, task_id) / "task.json"
    if not task_file.is_file():
        raise TaskError("Current task does not exist: {0}".format(task_id))
    return read_json(task_file)


def _completion_gate(project_root: Path, task: Dict[str, object]) -> None:
    directory = _task_dir(project_root, str(task["id"]))
    kind = task["kind"]
    if kind == "change":
        if not _meaningful_markdown(directory / "acceptance.md"):
            raise TaskError("Acceptance criteria must still be present when completing the task.")
        _verification_gate(project_root, task)
        verification = task.get("verification", {})
        if not isinstance(verification, dict) or verification.get("status") != "passed":
            raise TaskError("A change task requires passing verification before completion.")
        selected = verification.get("selected", [])
        if not isinstance(selected, list) or not selected:
            raise TaskError("A change task requires at least one verification command.")
        if not _meaningful_markdown(directory / "review.md"):
            raise TaskError("Complete review.md before completing the task.")
    elif kind == "analyze" and not _meaningful_markdown(directory / "report.md"):
        raise TaskError("Complete report.md before completing an analyze task.")
    elif kind == "review" and not _meaningful_markdown(directory / "review.md"):
        raise TaskError("Complete review.md before completing a review task.")
    elif kind == "learn" and not _meaningful_markdown(directory / "learnings.md"):
        raise TaskError("Complete learnings.md before completing a learn task.")


def _verification_gate(project_root: Path, task: Dict[str, object]) -> None:
    verification = task.get("verification", {})
    if not isinstance(verification, dict) or verification.get("status") != "passed":
        raise TaskError("A change task requires passing verification before review.")
    selected = verification.get("selected", [])
    if not isinstance(selected, list) or not selected:
        raise TaskError("A change task requires at least one verification command.")
    expected_fingerprint = verification.get("workspace_fingerprint")
    if isinstance(expected_fingerprint, str):
        from .verification import workspace_fingerprint

        current_fingerprint = workspace_fingerprint(project_root)
        if current_fingerprint != expected_fingerprint:
            raise TaskError("Product changes differ from the last passing verification; verify again.")


def advance_task(project_root: Path, target_state: Optional[str] = None) -> Dict[str, object]:
    root = project_root.resolve()
    task = load_current_task(root)
    if task is None:
        raise TaskError("No active task.")
    lifecycle: List[str] = LIFECYCLES[str(task["kind"])]
    current_index = lifecycle.index(str(task["state"]))
    if current_index + 1 >= len(lifecycle):
        raise TaskError("The current task is already completed.")
    expected = lifecycle[current_index + 1]
    target = target_state or expected
    if target != expected:
        raise TaskError("Invalid transition: expected '{0}', received '{1}'.".format(expected, target))

    directory = _task_dir(root, str(task["id"]))
    if target == "acceptance_defined" and not _meaningful_markdown(directory / "acceptance.md"):
        raise TaskError("Replace the acceptance.md placeholder before advancing.")
    if target == "reviewing" and task.get("kind") == "change":
        _verification_gate(root, task)
    if target == "completed":
        _completion_gate(root, task)

    task["state"] = target
    task["updated_at"] = _now_iso()
    write_json(directory / "task.json", task)
    return task


def record_verification(
    project_root: Path,
    report: Dict[str, object],
    require_current: bool = True,
) -> bool:
    root = project_root.resolve()
    task = load_current_task(root)
    if task is None:
        if require_current:
            raise TaskError("No active task.")
        return False
    if task.get("kind") == "change" and task.get("state") not in {"verifying", "reviewing"}:
        if require_current:
            raise TaskError("Record final change verification only in verifying or reviewing state.")
        return False
    status = "passed" if report.get("passed") else "failed"
    task["verification"] = {
        "status": status,
        "selected": list(report.get("selected", [])),
        "recorded_at": _now_iso(),
    }
    fingerprint = report.get("workspace_fingerprint")
    if isinstance(fingerprint, str):
        task["verification"]["workspace_fingerprint"] = fingerprint
    directory = _task_dir(root, str(task["id"]))
    write_json(directory / "task.json", task)
    with (directory / "verification.md").open("a", encoding="utf-8") as stream:
        stream.write("\n## {0}\n\n".format(status.upper()))
        for result in report.get("results", []):
            stream.write(
                "- `{0}`: exit `{1}` ({2}s)\n".format(
                    result.get("name"), result.get("exit_code"), result.get("duration_seconds", 0)
                )
            )
    return True


def archive_task(project_root: Path) -> Path:
    root = project_root.resolve()
    task = load_current_task(root)
    if task is None:
        raise TaskError("No active task.")
    if task.get("state") != "completed":
        raise TaskError("Only completed tasks can be archived.")
    source = _task_dir(root, str(task["id"]))
    destination = _tasks_root(root) / "archive" / str(task["id"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise TaskError("Archived task already exists: {0}".format(destination))
    shutil.move(str(source), str(destination))
    _current_path(root).unlink()
    return destination
