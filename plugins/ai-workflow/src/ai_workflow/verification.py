import fnmatch
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from .io_utils import atomic_write_text, workflow_root


class VerificationError(RuntimeError):
    pass


def _append_unique(target: List[str], names: Iterable[str]) -> None:
    for name in names:
        if name not in target:
            target.append(name)


def _matches(path: str, patterns: Sequence[object]) -> bool:
    normalized = path.replace("\\", "/")
    return any(
        fnmatch.fnmatch(normalized, pattern)
        for pattern in patterns
        if isinstance(pattern, str)
    )


def evaluate_change_policy(
    contract: Dict[str, object], changed_files: Sequence[str]
) -> List[str]:
    """Return hard policy violations for a concrete set of changed files."""

    violations: List[str] = []
    paths = contract.get("paths", {})
    if isinstance(paths, dict):
        protected = paths.get("protected", [])
        if isinstance(protected, list):
            for path in changed_files:
                if _matches(path, protected):
                    violations.append("Protected path changed: {0}".format(path))

    generation = contract.get("generation", {})
    rules = generation.get("rules", []) if isinstance(generation, dict) else []
    if isinstance(rules, list):
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            inputs = rule.get("inputs", [])
            outputs = rule.get("outputs", [])
            if not isinstance(inputs, list) or not isinstance(outputs, list):
                continue
            output_changes = [path for path in changed_files if _matches(path, outputs)]
            input_changed = any(_matches(path, inputs) for path in changed_files)
            if output_changes and not input_changed:
                violations.append(
                    "Generated output changed without a declared input ({0}): {1}".format(
                        rule.get("name", "unnamed rule"), ", ".join(output_changes)
                    )
                )
    return violations


def select_required_commands(
    contract: Dict[str, object],
    changed_files: Sequence[str],
    run_all: bool = False,
) -> List[str]:
    verification = contract.get("verification", {})
    commands = contract.get("commands", {})
    if not isinstance(verification, dict) or not isinstance(commands, dict):
        return []

    selected: List[str] = []
    generation = contract.get("generation", {})
    generation_rules = generation.get("rules", []) if isinstance(generation, dict) else []
    if isinstance(generation_rules, list):
        for rule in generation_rules:
            if not isinstance(rule, dict):
                continue
            patterns = []
            for key in ("inputs", "outputs"):
                values = rule.get(key, [])
                if isinstance(values, list):
                    patterns.extend(values)
            if run_all or any(_matches(path, patterns) for path in changed_files):
                command = rule.get("command")
                if isinstance(command, str):
                    _append_unique(selected, [command])

    defaults = verification.get("default", [])
    if isinstance(defaults, list):
        _append_unique(selected, [name for name in defaults if isinstance(name, str)])

    rules = verification.get("rules", [])
    if not isinstance(rules, list):
        rules = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        patterns = rule.get("patterns", [])
        required = rule.get("require", [])
        if not isinstance(patterns, list) or not isinstance(required, list):
            continue
        matches = run_all or any(_matches(path, patterns) for path in changed_files)
        if matches:
            _append_unique(selected, [name for name in required if isinstance(name, str)])

    # Preserve unknown references so direct callers cannot silently turn an
    # invalid required check into a passing, smaller selection. The CLI also
    # validates the full contract before reaching execution.
    return selected


def get_changed_files(project_root: Path) -> List[str]:
    root = project_root.resolve()
    probe = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=str(root),
        text=True,
        capture_output=True,
    )
    if probe.returncode != 0:
        raise VerificationError("--changed requires a Git worktree; use --all or --files instead.")

    commands = [
        ["git", "diff", "--name-only", "--relative", "-z"],
        ["git", "diff", "--name-only", "--relative", "--cached", "-z"],
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
    ]
    changed: List[str] = []
    for command in commands:
        completed = subprocess.run(command, cwd=str(root), capture_output=True)
        if completed.returncode != 0:
            message = os.fsdecode(completed.stderr).strip()
            raise VerificationError(message or "Unable to inspect changed files.")
        _append_unique(
            changed,
            [os.fsdecode(value) for value in completed.stdout.split(b"\0") if value],
        )
    return changed


def workspace_fingerprint(project_root: Path) -> Optional[str]:
    """Hash the current product diff while excluding workflow task evidence."""

    root = project_root.resolve()
    try:
        changed = get_changed_files(root)
    except VerificationError:
        return None
    excluded_prefixes = (".ai-workflow/tasks/", ".ai-workflow/logs/")
    relevant = sorted(
        path for path in changed if not path.replace("\\", "/").startswith(excluded_prefixes)
    )
    digest = hashlib.sha256()
    for relative in relevant:
        normalized = relative.replace("\\", "/")
        digest.update(normalized.encode("utf-8"))
        digest.update(b"\0")
        path = root / relative
        if path.is_symlink():
            digest.update(b"symlink\0")
            digest.update(os.readlink(str(path)).encode("utf-8"))
        elif path.is_file():
            digest.update(b"file\0")
            with path.open("rb") as stream:
                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
        else:
            digest.update(b"deleted\0")
        digest.update(b"\0")
    return digest.hexdigest()


def run_verification(
    project_root: Path,
    contract: Dict[str, object],
    selected: Sequence[str],
    fail_fast: bool = False,
) -> Dict[str, object]:
    root = project_root.resolve()
    command_map = contract.get("commands", {})
    if not isinstance(command_map, dict):
        command_map = {}

    results = []
    for name in selected:
        definition = command_map.get(name)
        if not isinstance(definition, dict) or not isinstance(definition.get("run"), str):
            results.append(
                {
                    "name": name,
                    "command": None,
                    "exit_code": 2,
                    "duration_seconds": 0.0,
                    "stdout": "",
                    "stderr": "Command is missing or invalid in project.json.",
                }
            )
            if fail_fast:
                break
            continue

        command = definition["run"]
        started = time.monotonic()
        completed = subprocess.run(
            command,
            cwd=str(root),
            shell=True,
            text=True,
            capture_output=True,
        )
        results.append(
            {
                "name": name,
                "command": command,
                "exit_code": completed.returncode,
                "duration_seconds": round(time.monotonic() - started, 3),
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        )
        if fail_fast and completed.returncode != 0:
            break

    passed = bool(selected) and len(results) == len(selected) and all(
        item["exit_code"] == 0 for item in results
    )
    report: Dict[str, object] = {
        "passed": passed,
        "selected": list(selected),
        "results": results,
        "workspace_fingerprint": workspace_fingerprint(root),
    }

    logs = workflow_root(root) / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    atomic_write_text(logs / "latest.json", json.dumps(report, indent=2, ensure_ascii=False) + "\n")

    try:
        from .tasks import record_verification

        record_verification(root, report, require_current=False)
    except (FileNotFoundError, ValueError):
        pass
    return report
