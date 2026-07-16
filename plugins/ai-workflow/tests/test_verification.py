import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

from ai_workflow.verification import (
    evaluate_change_policy,
    get_changed_files,
    run_verification,
    select_required_commands,
)


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.contract = {
            "commands": {
                "test": {"run": "test-command", "description": "Tests"},
                "lint": {"run": "lint-command", "description": "Lint"},
                "docs": {"run": "docs-command", "description": "Docs"},
                "deploy": {"run": "deploy-command", "description": "Not a verification command"},
            },
            "verification": {
                "default": ["lint"],
                "rules": [
                    {"name": "source", "patterns": ["src/**"], "require": ["test", "lint"]},
                    {"name": "docs", "patterns": ["docs/**"], "require": ["docs"]},
                ],
            },
            "paths": {"protected": ["vendor/**"], "generated": ["generated/**"]},
            "generation": {
                "rules": [
                    {
                        "name": "schema",
                        "inputs": ["schemas/**"],
                        "outputs": ["generated/**"],
                        "command": "generate",
                    }
                ]
            },
        }
        self.contract["commands"]["generate"] = {
            "run": "generate-command",
            "description": "Generate",
        }

    def test_selects_deduplicated_commands_in_contract_order(self):
        selected = select_required_commands(self.contract, ["src/a.py", "docs/readme.md"])
        self.assertEqual(["lint", "test", "docs"], selected)

    def test_all_selects_every_referenced_command(self):
        selected = select_required_commands(self.contract, [], run_all=True)
        self.assertEqual(["generate", "lint", "test", "docs"], selected)

    def test_generation_command_precedes_default_checks(self):
        selected = select_required_commands(self.contract, ["schemas/api.json"])
        self.assertEqual(["generate", "lint"], selected)

    def test_protected_and_output_only_changes_are_policy_violations(self):
        violations = evaluate_change_policy(
            self.contract,
            ["vendor/library.c", "generated/client.ts"],
        )
        self.assertTrue(any("Protected path" in violation for violation in violations))
        self.assertTrue(any("without a declared input" in violation for violation in violations))

    def test_generated_output_is_allowed_with_declared_input(self):
        self.assertEqual(
            [],
            evaluate_change_policy(
                self.contract,
                ["schemas/api.json", "generated/client.ts"],
            ),
        )

    def test_changed_files_include_tracked_staged_and_untracked_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            (root / "README.md").write_text("before\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=root, check=True, capture_output=True)
            (root / "README.md").write_text("after\n", encoding="utf-8")
            (root / "src").mkdir()
            (root / "src" / "new.py").write_text("value = 1\n", encoding="utf-8")

            self.assertEqual(["README.md", "src/new.py"], get_changed_files(root))

    def test_changed_files_preserve_unicode_and_newline_names(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(["git", "config", "core.quotePath", "true"], cwd=root, check=True)
            (root / "README.md").write_text("baseline\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=root, check=True, capture_output=True)
            (root / "src").mkdir()
            unicode_name = "src/文件.py"
            newline_name = "src/line\nbreak.py"
            (root / unicode_name).write_text("value = 1\n", encoding="utf-8")
            (root / newline_name).write_text("value = 2\n", encoding="utf-8")

            changed = get_changed_files(root)

            self.assertEqual([newline_name, unicode_name], sorted(changed))
            self.assertEqual(["lint", "test"], select_required_commands(self.contract, [unicode_name]))

    def test_failure_propagates_and_all_results_are_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = {
                "commands": {
                    "pass": {
                        "run": f'"{sys.executable}" -c "print(123)"',
                        "description": "Pass",
                    },
                    "fail": {
                        "run": f'"{sys.executable}" -c "raise SystemExit(7)"',
                        "description": "Fail",
                    },
                },
                "verification": {"default": ["pass", "fail"], "rules": []},
            }

            result = run_verification(root, contract, ["pass", "fail"])

            self.assertFalse(result["passed"])
            self.assertEqual([0, 7], [item["exit_code"] for item in result["results"]])

    def test_unknown_required_command_is_preserved_and_fails_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = {
                "commands": {},
                "verification": {"default": ["missing"], "rules": []},
            }
            selected = select_required_commands(contract, [])
            result = run_verification(root, contract, selected)

            self.assertEqual(["missing"], selected)
            self.assertFalse(result["passed"])
            self.assertEqual(2, result["results"][0]["exit_code"])


if __name__ == "__main__":
    unittest.main()
