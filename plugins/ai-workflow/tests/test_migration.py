import json
import tempfile
import unittest
from pathlib import Path

from ai_workflow.migration import find_legacy_copilot_files, migrate_legacy_copilot


class MigrationTests(unittest.TestCase):
    def test_migration_only_removes_clear_candidates_after_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy_instruction = root / ".github" / "copilot-instructions.md"
            legacy_script = root / ".github" / "Scripts" / "copilotBuild.ps1"
            legacy_prompt = root / ".github" / "prompts" / "investigate.prompt.md"
            legacy_adapter = root / "AGENTS.md"
            unrelated_prompt = root / ".github" / "prompts" / "team.prompt.md"
            workflow = root / ".github" / "workflows" / "ci.yml"
            copilot_named_workflow = root / ".github" / "workflows" / "copilot-license-audit.yml"
            copilot_policy = root / ".github" / "docs" / "copilot-team-policy.md"
            for path, content in [
                (legacy_instruction, "legacy\n"),
                (legacy_script, "Write-Host legacy\n"),
                (legacy_prompt, "# Investigate\nCopilot_Investigate.md\n# !!!INVESTIGATE!!!\n"),
                (
                    legacy_adapter,
                    "Read REPO-ROOT/.github/copilot-instructions.md\n"
                    "Treat the processed request as \"the LATEST chat message\"\n",
                ),
                (unrelated_prompt, "# Team prompt\n"),
                (workflow, "name: CI\n"),
                (copilot_named_workflow, "name: Copilot license audit\n"),
                (copilot_policy, "# Team policy\n"),
            ]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            candidates = find_legacy_copilot_files(root)
            self.assertEqual(
                {
                    Path(".github/copilot-instructions.md"),
                    Path(".github/Scripts/copilotBuild.ps1"),
                    Path(".github/prompts/investigate.prompt.md"),
                    Path("AGENTS.md"),
                },
                set(candidates),
            )

            preview = migrate_legacy_copilot(root, apply=False, timestamp="20260716-120000")
            self.assertEqual(4, len(preview["candidates"]))
            self.assertTrue(legacy_instruction.exists())

            result = migrate_legacy_copilot(root, apply=True, timestamp="20260716-120000")
            backup = root / ".ai-workflow" / "migrations" / "20260716-120000"

            self.assertFalse(legacy_instruction.exists())
            self.assertFalse(legacy_script.exists())
            self.assertFalse(legacy_prompt.exists())
            self.assertFalse(legacy_adapter.exists())
            self.assertTrue(unrelated_prompt.exists())
            self.assertTrue(workflow.exists())
            self.assertTrue(copilot_named_workflow.exists())
            self.assertTrue(copilot_policy.exists())
            self.assertTrue((backup / ".github" / "copilot-instructions.md").is_file())
            manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(4, len(manifest["files"]))
            self.assertTrue(result["applied"])


if __name__ == "__main__":
    unittest.main()
