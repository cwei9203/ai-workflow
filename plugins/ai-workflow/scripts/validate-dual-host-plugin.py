#!/usr/bin/env python3
"""Validate shared Codex/Claude identity and lifecycle-hook wiring."""

import json
import sys
from pathlib import Path


def fail(message: str) -> None:
    print("ERROR: {0}".format(message), file=sys.stderr)
    raise SystemExit(1)


def load(path: Path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail("Invalid JSON at {0}: {1}".format(path, error))
    if not isinstance(value, dict):
        fail("Expected a JSON object at {0}".format(path))
    return value


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    codex = load(root / ".codex-plugin" / "plugin.json")
    claude = load(root / ".claude-plugin" / "plugin.json")
    for field in ("name", "version", "description"):
        if not isinstance(codex.get(field), str) or not codex[field].strip():
            fail("Codex manifest has no valid {0}".format(field))
    for field in ("name", "version"):
        if codex.get(field) != claude.get(field):
            fail("Host manifests disagree on {0}".format(field))
    if "hooks" in codex:
        fail("The validated Codex manifest must not declare unsupported hooks")
    hook_path = claude.get("hooks")
    if not isinstance(hook_path, str) or not hook_path.startswith("./"):
        fail("Hook path must be plugin-relative")
    hooks = load(root / hook_path)
    event_map = hooks.get("hooks")
    if not isinstance(event_map, dict) or set(event_map) != {"SessionStart"}:
        fail("The knowledge reminder must be SessionStart-only")
    script = root / "hooks" / "knowledge-candidate-reminder.py"
    if not script.is_file():
        fail("Missing knowledge reminder script")
    print("Dual-host plugin validation passed: {0}".format(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
