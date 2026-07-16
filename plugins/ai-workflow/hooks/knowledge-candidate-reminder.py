#!/usr/bin/env python3
"""Read-only SessionStart hook for Codex and Claude Code."""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional


def _hook_input() -> Dict[str, object]:
    if sys.stdin.isatty():
        return {}
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _find_project(start: Path) -> Optional[Path]:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".ai-workflow" / "project.json").is_file():
            return candidate
    return None


def _pending_count(root: Path) -> int:
    ledger_path = root / ".ai-workflow" / "knowledge" / "ledger.json"
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        decisions = ledger.get("tasks", {})
    except (OSError, json.JSONDecodeError, AttributeError):
        decisions = {}
    if not isinstance(decisions, dict):
        decisions = {}
    count = 0
    archive = root / ".ai-workflow" / "tasks" / "archive"
    for task_file in archive.glob("*/task.json") if archive.is_dir() else ():
        try:
            task = json.loads(task_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        task_id = task.get("id") if isinstance(task, dict) else None
        if (
            isinstance(task_id, str)
            and task.get("state") == "completed"
            and task.get("kind") != "learn"
            and task_id not in decisions
        ):
            count += 1
    return count


def _emit(message: str) -> None:
    if os.environ.get("PLUGIN_DATA"):
        print(json.dumps({
            "systemMessage": "AIW:KNOWLEDGE_CANDIDATES",
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": message,
            },
        }))
    else:
        print(message)


def main() -> int:
    payload = _hook_input()
    raw_cwd = payload.get("cwd")
    start = Path(raw_cwd) if isinstance(raw_cwd, str) and raw_cwd else Path.cwd()
    root = _find_project(start)
    if root is None:
        return 0
    count = _pending_count(root)
    if count:
        _emit(
            "This repository has {0} archived task(s) without a durable-knowledge decision. "
            "Do not publish automatically. When relevant, run './aiw knowledge status', inspect "
            "the task evidence through workflow/learn.md, then mark each source task published "
            "or dismissed.".format(count)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
