import tempfile
import unittest
from pathlib import Path

from ai_workflow.discovery import discover_project
from ai_workflow.validation import (
    complete_onboarding,
    validate_contract,
    validate_contract_paths,
    validate_project_notes,
)


class ValidationTests(unittest.TestCase):
    def test_strict_project_paths_must_exist_in_target_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = discover_project(root)
            contract["project"]["manifests"] = ["missing.toml"]
            contract["project"]["source_roots"] = ["missing-src"]
            contract["context"]["read_first"] = ["missing.md"]

            issues = validate_contract_paths(contract, root, strict=True)

            self.assertTrue(any("missing.toml" in issue for issue in issues))
            self.assertTrue(any("missing-src" in issue for issue in issues))
            self.assertTrue(any("missing.md" in issue for issue in issues))

    def test_project_notes_require_each_project_specific_section(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project-notes.md"
            path.write_text(
                "# Project Notes\n\n## Purpose\n\n<!-- placeholder -->\n",
                encoding="utf-8",
            )

            issues = validate_project_notes(path, strict=True)

            self.assertTrue(any("Purpose" in issue for issue in issues))
            self.assertTrue(any("Architecture" in issue for issue in issues))

    def test_project_notes_accept_explicit_not_applicable_with_reason(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project-notes.md"
            path.write_text(
                "# Project Notes\n\n"
                "## Purpose\n\nProvides a command-line formatter.\n\n"
                "## Architecture\n\nA parser feeds a pure formatter.\n\n"
                "## Critical invariants\n\nOutput is deterministic.\n\n"
                "## Development caveats\n\nRun golden tests after grammar changes.\n\n"
                "## Terminology\n\nN/A — domain terminology is defined by the input grammar.\n",
                encoding="utf-8",
            )

            self.assertEqual([], validate_project_notes(path, strict=True))

    def test_strict_validation_requires_semantic_project_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = discover_project(root)

            issues = validate_contract(contract, strict=True)

            self.assertTrue(any("summary" in issue for issue in issues))
            self.assertTrue(any("verification command" in issue for issue in issues))

    def test_complete_onboarding_sets_status_after_contract_is_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = discover_project(root)
            contract["project"]["summary"] = "A deliberately configured project"
            contract["commands"]["test"] = {"run": "python -m unittest", "description": "Tests"}
            contract["verification"]["default"] = ["test"]
            contract["onboarding"]["review_notes"] = []

            completed = complete_onboarding(contract)

            self.assertEqual("complete", completed["onboarding"]["status"])
            self.assertEqual([], validate_contract(completed, strict=True))


if __name__ == "__main__":
    unittest.main()
