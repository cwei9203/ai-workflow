import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .discovery import discover_project
from .installation import LAUNCHER_MARKER, MANAGED_END, MANAGED_START, install_workflow
from .io_utils import contract_path, find_project_root, read_json, write_json
from .knowledge import KnowledgeError, knowledge_candidates, load_ledger, mark_knowledge_decision
from .migration import find_legacy_copilot_files, migrate_legacy_copilot
from .tasks import TaskError, advance_task, archive_task, load_current_task, start_task
from .validation import (
    complete_onboarding,
    validate_contract,
    validate_contract_paths,
    validate_project_notes,
)
from .verification import (
    VerificationError,
    evaluate_change_policy,
    get_changed_files,
    run_verification,
    select_required_commands,
)


def _source_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_root(value: Optional[str]) -> Path:
    return Path(value).resolve() if value else find_project_root()


def _merge_unique(original: object, discovered: object) -> List[object]:
    result = list(original) if isinstance(original, list) else []
    if isinstance(discovered, list):
        for item in discovered:
            if item not in result:
                result.append(item)
    return result


def _merge_discovery(existing: Dict[str, object], detected: Dict[str, object]) -> Dict[str, object]:
    project = existing.setdefault("project", {})
    detected_project = detected.get("project", {})
    if isinstance(project, dict) and isinstance(detected_project, dict):
        for key in (
            "languages",
            "platforms",
            "manifests",
            "source_roots",
            "test_roots",
            "documentation_roots",
        ):
            project[key] = _merge_unique(project.get(key), detected_project.get(key))
        if not project.get("name"):
            project["name"] = detected_project.get("name")

    commands = existing.setdefault("commands", {})
    detected_commands = detected.get("commands", {})
    if isinstance(commands, dict) and isinstance(detected_commands, dict):
        for name, definition in detected_commands.items():
            commands.setdefault(name, definition)

    context = existing.setdefault("context", {})
    detected_context = detected.get("context", {})
    if isinstance(context, dict) and isinstance(detected_context, dict):
        context["read_first"] = _merge_unique(
            context.get("read_first"), detected_context.get("read_first")
        )

    paths = existing.setdefault("paths", {})
    detected_paths = detected.get("paths", {})
    if isinstance(paths, dict) and isinstance(detected_paths, dict):
        for key in ("protected", "generated"):
            paths[key] = _merge_unique(paths.get(key), detected_paths.get(key))

    existing["discovery"] = detected.get("discovery", {})
    return existing


def _doctor_structure(root: Path) -> List[str]:
    issues = []
    workflow_files = ["entry.md", "onboard.md", "analyze.md", "change.md", "review.md", "learn.md"]
    runtime_files = [
        "__init__.py",
        "__main__.py",
        "cli.py",
        "discovery.py",
        "installation.py",
        "io_utils.py",
        "knowledge.py",
        "migration.py",
        "tasks.py",
        "validation.py",
        "verification.py",
    ]
    required = [
        root / "AGENTS.md",
        root / "CLAUDE.md",
        root / "aiw",
        root / "aiw.cmd",
        root / ".ai-workflow" / "VERSION",
        root / ".ai-workflow" / "project.json",
        root / ".ai-workflow" / "project.schema.json",
        root / ".ai-workflow" / "project-notes.md",
        root / ".ai-workflow" / "knowledge" / "index.md",
        root / ".ai-workflow" / "knowledge" / "ledger.json",
        root / ".ai-workflow" / "knowledge" / "learnings.md",
    ]
    required.extend(root / ".ai-workflow" / "workflow" / name for name in workflow_files)
    required.extend(
        root / ".ai-workflow" / "runtime" / "ai_workflow" / name for name in runtime_files
    )
    for path in required:
        if not path.is_file():
            issues.append("Missing installed file: {0}".format(path.relative_to(root)))
    for adapter_name in ("AGENTS.md", "CLAUDE.md"):
        adapter = root / adapter_name
        if adapter.is_file():
            content = adapter.read_bytes().decode("utf-8")
            if content.count(MANAGED_START) != 1 or content.count(MANAGED_END) != 1:
                issues.append("Invalid or missing managed adapter block: {0}".format(adapter_name))
    for launcher_name in ("aiw", "aiw.cmd"):
        launcher = root / launcher_name
        if launcher.is_file() and LAUNCHER_MARKER not in launcher.read_text(
            encoding="utf-8", errors="ignore"
        ):
            issues.append("The root {0} launcher is not managed by this workflow.".format(launcher_name))
    return issues


def _cmd_init(args: argparse.Namespace) -> int:
    target = Path(args.target).resolve()
    report = install_workflow(
        _source_root(),
        target,
        remove_legacy_copilot=args.remove_legacy_copilot,
    )
    print("AI development workflow installed in {0}".format(report["target"]))
    for warning in report["warnings"]:
        print("WARNING: {0}".format(warning))
    migration = report.get("migration")
    if isinstance(migration, dict) and migration.get("applied"):
        print("Legacy Copilot files backed up to {0}".format(migration["backup"]))
    print("Next: open the project with Codex or Claude Code and follow .ai-workflow/workflow/onboard.md")
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    root = _resolve_root(args.project_root)
    contract = read_json(contract_path(root))
    issues = (
        _doctor_structure(root)
        + validate_contract(contract, strict=args.strict)
        + validate_contract_paths(contract, root, strict=args.strict)
        + validate_project_notes(root / ".ai-workflow" / "project-notes.md", strict=args.strict)
    )
    try:
        load_ledger(root)
    except KnowledgeError as error:
        issues.append(str(error))
    onboarding = contract.get("onboarding", {})
    status = onboarding.get("status", "unknown") if isinstance(onboarding, dict) else "unknown"
    legacy = find_legacy_copilot_files(root)
    print("Project: {0}".format(root))
    print("Onboarding: {0}".format(status))
    if legacy:
        message = "Legacy Copilot files remain: {0}".format(
            ", ".join(path.as_posix() for path in legacy)
        )
        if args.strict:
            issues.append(message)
        else:
            print("WARNING: {0}".format(message))
    if issues:
        for issue in issues:
            print("ERROR: {0}".format(issue))
        return 1
    if status != "complete":
        print("Onboarding is structurally valid but still needs project-specific review.")
    else:
        print("Workflow installation and project contract are valid.")
    return 0


def _cmd_project_show(args: argparse.Namespace) -> int:
    root = _resolve_root(args.project_root)
    print(json.dumps(read_json(contract_path(root)), indent=2, ensure_ascii=False))
    return 0


def _cmd_project_discover(args: argparse.Namespace) -> int:
    root = _resolve_root(args.project_root)
    detected = discover_project(root)
    if args.write:
        existing = read_json(contract_path(root))
        before = json.dumps(existing, sort_keys=True, ensure_ascii=False)
        merged = _merge_discovery(existing, detected)
        after = json.dumps(merged, sort_keys=True, ensure_ascii=False)
        if before != after:
            onboarding = merged.setdefault("onboarding", {})
            if isinstance(onboarding, dict):
                onboarding["status"] = "needs_review"
                notes = onboarding.setdefault("review_notes", [])
                message = "Review facts added by the latest deterministic discovery pass."
                if isinstance(notes, list) and message not in notes:
                    notes.append(message)
        write_json(contract_path(root), merged)
        print("Merged newly discovered facts into .ai-workflow/project.json")
    else:
        print(json.dumps(detected, indent=2, ensure_ascii=False))
    return 0


def _cmd_project_complete(args: argparse.Namespace) -> int:
    root = _resolve_root(args.project_root)
    structure_issues = _doctor_structure(root)
    if structure_issues:
        raise ValueError("Workflow installation is incomplete: {0}".format("; ".join(structure_issues)))
    legacy = find_legacy_copilot_files(root)
    if legacy:
        raise ValueError(
            "Legacy Copilot files remain. Preview and run './aiw migrate-copilot --apply' first."
        )
    notes_issues = validate_project_notes(
        root / ".ai-workflow" / "project-notes.md", strict=True
    )
    if notes_issues:
        raise ValueError("Project notes are incomplete: {0}".format("; ".join(notes_issues)))
    contract = read_json(contract_path(root))
    path_issues = validate_contract_paths(contract, root, strict=True)
    if path_issues:
        raise ValueError("Project context paths are invalid: {0}".format("; ".join(path_issues)))
    completed = complete_onboarding(contract)
    write_json(contract_path(root), completed)
    print("Project onboarding marked complete.")
    return 0


def _cmd_task_start(args: argparse.Namespace) -> int:
    root = _resolve_root(args.project_root)
    contract = read_json(contract_path(root))
    onboarding = contract.get("onboarding", {})
    if not isinstance(onboarding, dict) or onboarding.get("status") != "complete":
        raise TaskError("Complete project onboarding before starting workflow tasks.")
    task = start_task(root, args.title, kind=args.kind)
    print("Started {0} task {1}".format(task["kind"], task["id"]))
    return 0


def _cmd_task_status(args: argparse.Namespace) -> int:
    root = _resolve_root(args.project_root)
    task = load_current_task(root)
    if task is None:
        print("No active task.")
    else:
        print(json.dumps(task, indent=2, ensure_ascii=False))
    return 0


def _cmd_task_advance(args: argparse.Namespace) -> int:
    root = _resolve_root(args.project_root)
    task = advance_task(root, args.state)
    print("Task {0} advanced to {1}".format(task["id"], task["state"]))
    return 0


def _cmd_task_archive(args: argparse.Namespace) -> int:
    root = _resolve_root(args.project_root)
    path = archive_task(root)
    print("Archived task to {0}".format(path.relative_to(root)))
    return 0


def _cmd_knowledge_status(args: argparse.Namespace) -> int:
    root = _resolve_root(args.project_root)
    candidates = knowledge_candidates(root)
    if args.json:
        print(json.dumps({"count": len(candidates), "candidates": candidates}, indent=2, ensure_ascii=False))
        return 0
    if not candidates:
        print("No pending knowledge candidates.")
        return 0
    print("Pending knowledge candidates: {0}".format(len(candidates)))
    for candidate in candidates:
        print("- {0}: {1}".format(candidate["id"], candidate["title"]))
    print("Review evidence with workflow/learn.md, then mark each candidate published or dismissed.")
    return 0


def _cmd_knowledge_mark(args: argparse.Namespace) -> int:
    root = _resolve_root(args.project_root)
    mark_knowledge_decision(root, args.task_id, args.decision, reason=args.reason or "")
    print("Knowledge candidate {0} marked {1}.".format(args.task_id, args.decision))
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    root = _resolve_root(args.project_root)
    contract = read_json(contract_path(root))
    contract_issues = validate_contract(contract, strict=False)
    if contract_issues:
        raise VerificationError(
            "Project contract is invalid: {0}".format("; ".join(contract_issues))
        )
    if args.all:
        files: Sequence[str] = []
    elif args.files:
        files = args.files
    else:
        files = get_changed_files(root)
    selected = select_required_commands(contract, files, run_all=args.all)
    print("Changed files: {0}".format(", ".join(files) if files else "(none or --all)"))
    print("Selected checks: {0}".format(", ".join(selected) if selected else "(none)"))
    violations = [] if args.all else evaluate_change_policy(contract, files)
    if violations:
        for violation in violations:
            print("POLICY ERROR: {0}".format(violation), file=sys.stderr)
        return 1
    if args.dry_run:
        return 0 if selected else 2
    report = run_verification(root, contract, selected, fail_fast=args.fail_fast)
    for result in report["results"]:
        print("[{0}] {1} (exit {2}, {3}s)".format(
            "PASS" if result["exit_code"] == 0 else "FAIL",
            result["name"],
            result["exit_code"],
            result["duration_seconds"],
        ))
        if result.get("stdout"):
            print(result["stdout"].rstrip())
        if result.get("stderr"):
            print(result["stderr"].rstrip(), file=sys.stderr)
    return 0 if report["passed"] else 1


def _cmd_migrate(args: argparse.Namespace) -> int:
    root = _resolve_root(args.project_root)
    report = migrate_legacy_copilot(root, apply=args.apply)
    if not report["candidates"]:
        print("No legacy Copilot files found.")
        return 0
    for path in report["candidates"]:
        print(path)
    if report["applied"]:
        # Legacy root adapters may have been removed as whole files. Refreshing
        # the installation recreates only the thin managed adapters while
        # preserving the project contract and project-owned knowledge.
        install_workflow(_source_root(), root)
        print("Backed up and removed legacy files. Backup: {0}".format(report["backup"]))
    else:
        print("Preview only. Re-run with --apply to back up and remove these files.")
    return 0


def _add_root_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project-root", help="Target project root; defaults to automatic lookup")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aiw", description="AI development workflow runtime")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Install the workflow into an existing project")
    init.add_argument("target", nargs="?", default=".")
    init.add_argument(
        "--remove-legacy-copilot",
        action="store_true",
        help="Back up and remove clearly named legacy Copilot files",
    )
    init.set_defaults(handler=_cmd_init)

    doctor = subparsers.add_parser("doctor", help="Validate installation and project contract")
    _add_root_argument(doctor)
    doctor.add_argument(
        "--strict",
        action="store_true",
        help="Run semantic completeness checks required before onboarding completion",
    )
    doctor.set_defaults(handler=_cmd_doctor)

    project = subparsers.add_parser("project", help="Inspect or complete the project adapter")
    project_sub = project.add_subparsers(dest="project_command", required=True)
    project_show = project_sub.add_parser("show")
    _add_root_argument(project_show)
    project_show.set_defaults(handler=_cmd_project_show)
    project_discover = project_sub.add_parser("discover")
    _add_root_argument(project_discover)
    project_discover.add_argument("--write", action="store_true")
    project_discover.set_defaults(handler=_cmd_project_discover)
    project_complete = project_sub.add_parser("complete")
    _add_root_argument(project_complete)
    project_complete.set_defaults(handler=_cmd_project_complete)

    task = subparsers.add_parser("task", help="Manage durable workflow tasks")
    task_sub = task.add_subparsers(dest="task_command", required=True)
    task_start = task_sub.add_parser("start")
    _add_root_argument(task_start)
    task_start.add_argument("title")
    task_start.add_argument("--kind", choices=sorted(("analyze", "change", "review", "learn")), default="change")
    task_start.set_defaults(handler=_cmd_task_start)
    task_status = task_sub.add_parser("status")
    _add_root_argument(task_status)
    task_status.set_defaults(handler=_cmd_task_status)
    task_advance = task_sub.add_parser("advance")
    _add_root_argument(task_advance)
    task_advance.add_argument("state", nargs="?")
    task_advance.set_defaults(handler=_cmd_task_advance)
    task_archive = task_sub.add_parser("archive")
    _add_root_argument(task_archive)
    task_archive.set_defaults(handler=_cmd_task_archive)

    knowledge = subparsers.add_parser("knowledge", help="Review archived tasks for durable knowledge")
    knowledge_sub = knowledge.add_subparsers(dest="knowledge_command", required=True)
    knowledge_status = knowledge_sub.add_parser("status")
    _add_root_argument(knowledge_status)
    knowledge_status.add_argument("--json", action="store_true")
    knowledge_status.set_defaults(handler=_cmd_knowledge_status)
    knowledge_mark = knowledge_sub.add_parser("mark")
    _add_root_argument(knowledge_mark)
    knowledge_mark.add_argument("task_id")
    knowledge_mark.add_argument("decision", choices=sorted(("published", "dismissed")))
    knowledge_mark.add_argument("--reason")
    knowledge_mark.set_defaults(handler=_cmd_knowledge_mark)

    verify = subparsers.add_parser("verify", help="Select and run project verification checks")
    _add_root_argument(verify)
    selection = verify.add_mutually_exclusive_group()
    selection.add_argument(
        "--changed",
        action="store_true",
        help="Select checks from tracked, staged, and untracked changes (default)",
    )
    selection.add_argument("--all", action="store_true")
    selection.add_argument("--files", nargs="+")
    verify.add_argument("--dry-run", action="store_true")
    verify.add_argument("--fail-fast", action="store_true")
    verify.set_defaults(handler=_cmd_verify)

    migrate = subparsers.add_parser("migrate-copilot", help="Preview or remove legacy Copilot files")
    _add_root_argument(migrate)
    migrate.add_argument("--apply", action="store_true")
    migrate.set_defaults(handler=_cmd_migrate)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (
        FileNotFoundError,
        NotADirectoryError,
        ValueError,
        KnowledgeError,
        TaskError,
        VerificationError,
    ) as error:
        print("ERROR: {0}".format(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
