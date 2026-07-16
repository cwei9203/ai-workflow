import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from .io_utils import read_json, workflow_root, write_json


class KnowledgeError(RuntimeError):
    pass


ALLOWED_DECISIONS = {"published", "dismissed"}


def _knowledge_root(project_root: Path) -> Path:
    return workflow_root(project_root) / "knowledge"


def _ledger_path(project_root: Path) -> Path:
    return _knowledge_root(project_root) / "ledger.json"


def _archive_root(project_root: Path) -> Path:
    return workflow_root(project_root) / "tasks" / "archive"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_ledger(project_root: Path) -> Dict[str, object]:
    path = _ledger_path(project_root)
    if not path.is_file():
        return {"version": 1, "tasks": {}}
    ledger = read_json(path)
    if ledger.get("version") != 1 or not isinstance(ledger.get("tasks"), dict):
        raise KnowledgeError("Invalid knowledge ledger: .ai-workflow/knowledge/ledger.json")
    return ledger


def knowledge_candidates(project_root: Path) -> List[Dict[str, object]]:
    root = project_root.resolve()
    ledger = load_ledger(root)
    decisions = ledger["tasks"]
    assert isinstance(decisions, dict)
    result: List[Dict[str, object]] = []
    archive = _archive_root(root)
    if not archive.is_dir():
        return result
    for task_file in sorted(archive.glob("*/task.json")):
        task = read_json(task_file)
        task_id = task.get("id")
        if (
            isinstance(task_id, str)
            and task.get("state") == "completed"
            and task.get("kind") != "learn"
            and task_id not in decisions
        ):
            result.append(
                {
                    "id": task_id,
                    "title": task.get("title", ""),
                    "kind": task.get("kind", "unknown"),
                    "archive": task_file.parent.relative_to(root).as_posix(),
                }
            )
    return result


def mark_knowledge_decision(
    project_root: Path,
    task_id: str,
    decision: str,
    reason: str = "",
) -> Dict[str, object]:
    root = project_root.resolve()
    if decision not in ALLOWED_DECISIONS:
        raise KnowledgeError("Knowledge decision must be 'published' or 'dismissed'.")
    task_file = _archive_root(root) / task_id / "task.json"
    if not task_file.is_file():
        raise KnowledgeError("Archived task does not exist: {0}".format(task_id))
    task = read_json(task_file)
    if task.get("state") != "completed" or task.get("kind") == "learn":
        raise KnowledgeError("Only completed non-learn tasks can receive a knowledge decision.")
    normalized_reason = reason.strip()
    if decision == "dismissed" and not normalized_reason:
        raise KnowledgeError("A dismissed candidate requires --reason.")
    if decision == "published":
        learnings = _knowledge_root(root) / "learnings.md"
        content = learnings.read_text(encoding="utf-8") if learnings.is_file() else ""
        cited = False
        for line in content.splitlines():
            if "source tasks:" not in line.lower():
                continue
            raw_sources = line.split(":", 1)[1]
            sources = {item.strip().strip("`") for item in raw_sources.split(",")}
            if task_id in sources:
                cited = True
                break
        if not cited:
            raise KnowledgeError(
                "Published knowledge must cite the source task ID in knowledge/learnings.md."
            )
    ledger = load_ledger(root)
    decisions = ledger["tasks"]
    assert isinstance(decisions, dict)
    if task_id in decisions:
        raise KnowledgeError("Knowledge candidate already has a decision: {0}".format(task_id))
    record: Dict[str, object] = {
        "decision": decision,
        "decided_at": _now_iso(),
    }
    if normalized_reason:
        record["reason"] = normalized_reason
    decisions[task_id] = record
    write_json(_ledger_path(root), ledger)
    return record
