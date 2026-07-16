"""Validation and completion gates for project contracts."""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Set


_SUPPORTED_SCHEMA_VERSION = 1
_ONBOARDING_STATUSES = {"needs_review", "complete"}
_COMMAND_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_PLACEHOLDER_PATTERN = re.compile(
    r"(?:\bTODO\b|\bTBD\b|\bPLACEHOLDER\b|\bUNKNOWN\b|REPLACE\s+ME|FILL\s+(?:ME|THIS)\s+IN)",
    re.IGNORECASE,
)

_TOP_LEVEL_KEYS = {
    "$schema",
    "schema_version",
    "project",
    "context",
    "paths",
    "generation",
    "commands",
    "verification",
    "onboarding",
    "discovery",
}
_TOP_LEVEL_REQUIRED = _TOP_LEVEL_KEYS - {"$schema"}
_PROJECT_KEYS = {
    "name",
    "summary",
    "languages",
    "platforms",
    "manifests",
    "source_roots",
    "test_roots",
    "documentation_roots",
}
_CONTEXT_KEYS = {"read_first", "architecture_boundaries"}
_PATHS_KEYS = {"protected", "generated"}
_COMMAND_KEYS = {"run", "description", "source"}
_COMMAND_REQUIRED_KEYS = {"run", "description"}
_GENERATION_RULE_KEYS = {"name", "inputs", "outputs", "command", "description"}
_VERIFICATION_KEYS = {"default", "rules"}
_VERIFICATION_RULE_KEYS = {"name", "patterns", "require"}
_ONBOARDING_KEYS = {"status", "review_notes"}
_DISCOVERY_KEYS = {"evidence", "warnings"}
_EVIDENCE_KEYS = {"fact", "source", "value"}


class ContractValidationError(ValueError):
    """Raised when an incomplete or invalid contract is marked complete."""

    def __init__(self, issues: Sequence[str]) -> None:
        self.issues = list(issues)
        super().__init__("Project contract is not ready:\n- " + "\n- ".join(self.issues))


def _check_keys(
    value: Mapping[str, Any],
    location: str,
    required: Iterable[str],
    allowed: Iterable[str],
    issues: List[str],
) -> None:
    required_keys = set(required)
    allowed_keys = set(allowed)
    for key in sorted(required_keys - set(value)):
        issues.append("%s.%s is required" % (location, key) if location else "%s is required" % key)
    for key in sorted(set(value) - allowed_keys):
        issues.append("%s.%s is not supported" % (location, key) if location else "%s is not supported" % key)


def _validate_string(value: Any, location: str, issues: List[str], allow_empty: bool = False) -> bool:
    if not isinstance(value, str):
        issues.append("%s must be a string" % location)
        return False
    if not allow_empty and not value.strip():
        issues.append("%s must be a non-empty string" % location)
        return False
    return True


def _validate_string_list(value: Any, location: str, issues: List[str]) -> List[str]:
    if not isinstance(value, list):
        issues.append("%s must be a list" % location)
        return []
    result: List[str] = []
    seen: Set[str] = set()
    for index, item in enumerate(value):
        item_location = "%s[%d]" % (location, index)
        if not _validate_string(item, item_location, issues):
            continue
        if item in seen:
            issues.append("%s contains duplicate value %r" % (location, item))
        else:
            seen.add(item)
            result.append(item)
    return result


def _validate_path_list(value: Any, location: str, issues: List[str]) -> List[str]:
    paths = _validate_string_list(value, location, issues)
    for path in paths:
        if "\\" in path:
            issues.append("%s path %r must use '/' separators" % (location, path))
        if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
            issues.append("%s path %r must be repository-relative" % (location, path))
        if ".." in path.split("/"):
            issues.append("%s path %r must not traverse outside the repository" % (location, path))
    return paths


def _contains_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        return bool(_PLACEHOLDER_PATTERN.search(value))
    if isinstance(value, list):
        return any(_contains_placeholder(item) for item in value)
    if isinstance(value, Mapping):
        return any(_contains_placeholder(item) for item in value.values())
    return False


def _validate_project(contract: Mapping[str, Any], issues: List[str]) -> Mapping[str, Any]:
    project = contract.get("project")
    if not isinstance(project, Mapping):
        issues.append("project must be an object")
        return {}
    _check_keys(project, "project", _PROJECT_KEYS, _PROJECT_KEYS, issues)
    _validate_string(project.get("name"), "project.name", issues)
    _validate_string(project.get("summary"), "project.summary", issues, allow_empty=True)
    _validate_string_list(project.get("languages"), "project.languages", issues)
    _validate_string_list(project.get("platforms"), "project.platforms", issues)
    for key in ("manifests", "source_roots", "test_roots", "documentation_roots"):
        _validate_path_list(project.get(key), "project.%s" % key, issues)
    return project


def _validate_context(contract: Mapping[str, Any], issues: List[str]) -> Any:
    context = contract.get("context")
    if not isinstance(context, Mapping):
        issues.append("context must be an object")
        return None
    _check_keys(context, "context", _CONTEXT_KEYS, _CONTEXT_KEYS, issues)
    _validate_path_list(context.get("read_first"), "context.read_first", issues)
    _validate_string_list(
        context.get("architecture_boundaries"), "context.architecture_boundaries", issues
    )
    return context


def _validate_paths(contract: Mapping[str, Any], issues: List[str]) -> Any:
    paths = contract.get("paths")
    if not isinstance(paths, Mapping):
        issues.append("paths must be an object")
        return None
    _check_keys(paths, "paths", _PATHS_KEYS, _PATHS_KEYS, issues)
    _validate_path_list(paths.get("protected"), "paths.protected", issues)
    _validate_path_list(paths.get("generated"), "paths.generated", issues)
    return paths


def _validate_commands(contract: Mapping[str, Any], issues: List[str]) -> Mapping[str, Any]:
    commands = contract.get("commands")
    if not isinstance(commands, Mapping):
        issues.append("commands must be an object")
        return {}

    for name, command in commands.items():
        location = "commands.%s" % name
        if not isinstance(name, str) or not _COMMAND_NAME_PATTERN.match(name):
            issues.append("command name %r must match %s" % (name, _COMMAND_NAME_PATTERN.pattern))
            continue
        if not isinstance(command, Mapping):
            issues.append("%s must be an object" % location)
            continue
        _check_keys(command, location, _COMMAND_REQUIRED_KEYS, _COMMAND_KEYS, issues)
        _validate_string(command.get("run"), "%s.run" % location, issues)
        _validate_string(command.get("description"), "%s.description" % location, issues)
        if "source" in command:
            _validate_string(command.get("source"), "%s.source" % location, issues)
    return commands


def _validate_command_references(
    values: Any,
    location: str,
    commands: Mapping[str, Any],
    issues: List[str],
) -> List[str]:
    references = _validate_string_list(values, location, issues)
    for command_name in references:
        if not _COMMAND_NAME_PATTERN.match(command_name):
            issues.append("%s contains invalid command name %r" % (location, command_name))
        elif command_name not in commands:
            issues.append("%s references unknown command %r" % (location, command_name))
    return references


def _validate_generation(
    contract: Mapping[str, Any], commands: Mapping[str, Any], issues: List[str]
) -> Any:
    generation = contract.get("generation")
    if not isinstance(generation, Mapping):
        issues.append("generation must be an object")
        return None
    _check_keys(generation, "generation", {"rules"}, {"rules"}, issues)
    rules = generation.get("rules")
    if not isinstance(rules, list):
        issues.append("generation.rules must be a list")
        return generation

    names: Set[str] = set()
    for index, rule in enumerate(rules):
        location = "generation.rules[%d]" % index
        if not isinstance(rule, Mapping):
            issues.append("%s must be an object" % location)
            continue
        _check_keys(
            rule,
            location,
            _GENERATION_RULE_KEYS - {"description"},
            _GENERATION_RULE_KEYS,
            issues,
        )
        name = rule.get("name")
        if _validate_string(name, "%s.name" % location, issues):
            if name in names:
                issues.append("generation rule name %r is duplicated" % name)
            names.add(name)
        inputs = _validate_path_list(rule.get("inputs"), "%s.inputs" % location, issues)
        outputs = _validate_path_list(rule.get("outputs"), "%s.outputs" % location, issues)
        if not inputs:
            issues.append("%s.inputs must identify at least one input" % location)
        if not outputs:
            issues.append("%s.outputs must identify at least one generated output" % location)
        command = rule.get("command")
        if _validate_string(command, "%s.command" % location, issues):
            if not _COMMAND_NAME_PATTERN.match(command):
                issues.append("%s.command contains an invalid command name" % location)
            elif command not in commands:
                issues.append("%s.command references unknown command %r" % (location, command))
        if "description" in rule:
            _validate_string(rule.get("description"), "%s.description" % location, issues)
    return generation


def _validate_verification(
    contract: Mapping[str, Any], commands: Mapping[str, Any], issues: List[str]
) -> List[str]:
    verification = contract.get("verification")
    if not isinstance(verification, Mapping):
        issues.append("verification must be an object")
        return []
    _check_keys(
        verification, "verification", _VERIFICATION_KEYS, _VERIFICATION_KEYS, issues
    )
    references = _validate_command_references(
        verification.get("default"), "verification.default", commands, issues
    )
    rules = verification.get("rules")
    if not isinstance(rules, list):
        issues.append("verification.rules must be a list")
        return references

    names: Set[str] = set()
    for index, rule in enumerate(rules):
        location = "verification.rules[%d]" % index
        if not isinstance(rule, Mapping):
            issues.append("%s must be an object" % location)
            continue
        _check_keys(rule, location, _VERIFICATION_RULE_KEYS, _VERIFICATION_RULE_KEYS, issues)
        name = rule.get("name")
        if _validate_string(name, "%s.name" % location, issues):
            if name in names:
                issues.append("verification rule name %r is duplicated" % name)
            names.add(name)
        patterns = _validate_path_list(rule.get("patterns"), "%s.patterns" % location, issues)
        if not patterns:
            issues.append("%s.patterns must identify at least one path pattern" % location)
        required = _validate_command_references(
            rule.get("require"), "%s.require" % location, commands, issues
        )
        if not required:
            issues.append("%s.require must select at least one command" % location)
        references.extend(required)
    return references


def _validate_onboarding(contract: Mapping[str, Any], issues: List[str]) -> Any:
    onboarding = contract.get("onboarding")
    if not isinstance(onboarding, Mapping):
        issues.append("onboarding must be an object")
        return None
    _check_keys(onboarding, "onboarding", _ONBOARDING_KEYS, _ONBOARDING_KEYS, issues)
    status = onboarding.get("status")
    if status not in _ONBOARDING_STATUSES:
        issues.append("onboarding.status must be 'needs_review' or 'complete'")
    _validate_string_list(onboarding.get("review_notes"), "onboarding.review_notes", issues)
    return onboarding


def _validate_discovery(contract: Mapping[str, Any], issues: List[str]) -> None:
    discovery = contract.get("discovery")
    if not isinstance(discovery, Mapping):
        issues.append("discovery must be an object")
        return
    _check_keys(discovery, "discovery", _DISCOVERY_KEYS, _DISCOVERY_KEYS, issues)
    evidence = discovery.get("evidence")
    if not isinstance(evidence, list):
        issues.append("discovery.evidence must be a list")
    else:
        for index, item in enumerate(evidence):
            location = "discovery.evidence[%d]" % index
            if not isinstance(item, Mapping):
                issues.append("%s must be an object" % location)
                continue
            _check_keys(item, location, {"fact", "source"}, _EVIDENCE_KEYS, issues)
            _validate_string(item.get("fact"), "%s.fact" % location, issues)
            _validate_string(item.get("source"), "%s.source" % location, issues)
    _validate_string_list(discovery.get("warnings"), "discovery.warnings", issues)


def validate_contract(contract: Any, strict: bool = False) -> List[str]:
    """Return deterministic diagnostics without mutating *contract*.

    Structural, path, and command-reference errors are always reported.
    ``strict`` adds semantic onboarding gates required before completion.
    """

    issues: List[str] = []
    if not isinstance(contract, Mapping):
        return ["project contract must be a JSON object"]

    _check_keys(contract, "", _TOP_LEVEL_REQUIRED, _TOP_LEVEL_KEYS, issues)
    if "$schema" in contract:
        _validate_string(contract.get("$schema"), "$schema", issues)
    if contract.get("schema_version") != _SUPPORTED_SCHEMA_VERSION:
        issues.append("schema_version must be %d" % _SUPPORTED_SCHEMA_VERSION)

    project = _validate_project(contract, issues)
    context = _validate_context(contract, issues)
    paths = _validate_paths(contract, issues)
    commands = _validate_commands(contract, issues)
    generation = _validate_generation(contract, commands, issues)
    references = _validate_verification(contract, commands, issues)
    onboarding = _validate_onboarding(contract, issues)
    _validate_discovery(contract, issues)

    if strict:
        summary = project.get("summary") if isinstance(project, Mapping) else None
        if not isinstance(summary, str) or not summary.strip():
            issues.append("project.summary is required before onboarding can complete")
        elif _contains_placeholder(summary):
            issues.append("project.summary contains placeholder text")

        valid_references = {
            command_name
            for command_name in references
            if command_name in commands
            and isinstance(commands[command_name], Mapping)
            and isinstance(commands[command_name].get("run"), str)
            and bool(commands[command_name].get("run", "").strip())
        }
        if not valid_references:
            issues.append(
                "at least one valid verification command is required before onboarding can complete"
            )

        review_notes = onboarding.get("review_notes") if isinstance(onboarding, Mapping) else None
        if isinstance(review_notes, list) and review_notes:
            issues.append("onboarding.review_notes must be resolved before onboarding can complete")

        semantic_sections = {
            "project": {
                key: value for key, value in project.items() if key != "name"
            }
            if isinstance(project, Mapping)
            else project,
            "context": context,
            "paths": paths,
            "generation": generation,
            "commands": commands,
            "verification": contract.get("verification"),
        }
        if _contains_placeholder(semantic_sections):
            issues.append("project contract contains placeholder text")

        generated_paths = set()
        if isinstance(paths, Mapping) and isinstance(paths.get("generated"), list):
            generated_paths = set(paths["generated"])
        generated_outputs = set()
        if isinstance(generation, Mapping) and isinstance(generation.get("rules"), list):
            for rule in generation["rules"]:
                if isinstance(rule, Mapping) and isinstance(rule.get("outputs"), list):
                    generated_outputs.update(rule["outputs"])
        for pattern in sorted(generated_paths - generated_outputs):
            issues.append(
                "paths.generated pattern %r has no generation rule output" % pattern
            )
        for pattern in sorted(generated_outputs - generated_paths):
            issues.append(
                "generation output pattern %r is missing from paths.generated" % pattern
            )

    # One malformed value may be reached through more than one semantic gate;
    # keep the report stable and concise.
    return list(dict.fromkeys(issues))


_PROJECT_NOTE_SECTIONS = (
    "Purpose",
    "Architecture",
    "Critical invariants",
    "Development caveats",
    "Terminology",
)


def validate_project_notes(path: Path, strict: bool = False) -> List[str]:
    """Validate the human-readable semantic half of project onboarding."""

    if not path.is_file():
        return ["project-notes.md is missing"]
    if not strict:
        return []
    content = path.read_text(encoding="utf-8")
    issues: List[str] = []
    matches = list(re.finditer(r"(?mi)^##\s+(.+?)\s*$", content))
    sections = {match.group(1).strip(): (match, index) for index, match in enumerate(matches)}
    for section in _PROJECT_NOTE_SECTIONS:
        entry = sections.get(section)
        if entry is None:
            issues.append("project-notes.md is missing section %r" % section)
            continue
        match, index = entry
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        body = content[match.end() : end]
        without_comments = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL).strip()
        if not without_comments:
            issues.append("project-notes.md section %r still needs project-specific content" % section)
        elif _contains_placeholder(without_comments):
            issues.append("project-notes.md section %r contains placeholder text" % section)
    return issues


def validate_contract_paths(
    contract: Mapping[str, Any], project_root: Path, strict: bool = False
) -> List[str]:
    """Validate exact project context paths against the target repository."""

    if not strict:
        return []
    root = project_root.resolve()
    issues: List[str] = []
    project = contract.get("project", {})
    context = contract.get("context", {})
    locations = []
    if isinstance(project, Mapping):
        for key in ("manifests", "source_roots", "test_roots", "documentation_roots"):
            values = project.get(key, [])
            if isinstance(values, list):
                locations.extend(("project.%s" % key, value) for value in values if isinstance(value, str))
    if isinstance(context, Mapping):
        values = context.get("read_first", [])
        if isinstance(values, list):
            locations.extend(("context.read_first", value) for value in values if isinstance(value, str))
    for location, relative in locations:
        if not (root / relative).exists():
            issues.append("%s path does not exist: %s" % (location, relative))
    return issues


def complete_onboarding(contract: Any) -> Dict[str, Any]:
    """Return a completed copy of *contract* after enforcing strict gates."""

    if not isinstance(contract, Mapping):
        raise ContractValidationError(["project contract must be a JSON object"])
    completed = copy.deepcopy(dict(contract))
    issues = validate_contract(completed, strict=True)
    if issues:
        raise ContractValidationError(issues)

    completed["onboarding"]["status"] = "complete"
    return completed


__all__ = [
    "ContractValidationError",
    "complete_onboarding",
    "validate_contract",
    "validate_contract_paths",
    "validate_project_notes",
]
