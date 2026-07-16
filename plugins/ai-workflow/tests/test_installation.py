import json
import tempfile
import unittest
from pathlib import Path

from ai_workflow.installation import MANAGED_END, MANAGED_START, install_workflow


class InstallationTests(unittest.TestCase):
    def test_existing_crlf_content_outside_managed_block_is_byte_preserved(self):
        with tempfile.TemporaryDirectory() as source_directory, tempfile.TemporaryDirectory() as target_directory:
            target = Path(target_directory)
            original = b"# Existing rules\r\n\r\nKeep these bytes.\r\n"
            (target / "AGENTS.md").write_bytes(original)

            install_workflow(Path(source_directory), target)
            installed = (target / "AGENTS.md").read_bytes()

            self.assertTrue(installed.startswith(original))
            self.assertIn(MANAGED_START.encode("utf-8") + b"\r\n", installed)

    def test_existing_unmanaged_workflow_directory_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as source_directory, tempfile.TemporaryDirectory() as target_directory:
            target = Path(target_directory)
            existing = target / ".ai-workflow" / "workflow" / "entry.md"
            existing.parent.mkdir(parents=True)
            existing.write_text("unrelated existing content\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                install_workflow(Path(source_directory), target)

            self.assertEqual("unrelated existing content\n", existing.read_text(encoding="utf-8"))
            self.assertFalse((target / "AGENTS.md").exists())

    def test_malformed_managed_block_fails_before_partial_install(self):
        with tempfile.TemporaryDirectory() as source_directory, tempfile.TemporaryDirectory() as target_directory:
            target = Path(target_directory)
            (target / "AGENTS.md").write_text(MANAGED_START + "\nbroken\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                install_workflow(Path(source_directory), target)

            self.assertFalse((target / ".ai-workflow").exists())
            self.assertFalse((target / "CLAUDE.md").exists())

    def test_reversed_managed_markers_fail_before_partial_install(self):
        with tempfile.TemporaryDirectory() as source_directory, tempfile.TemporaryDirectory() as target_directory:
            target = Path(target_directory)
            (target / "AGENTS.md").write_text(
                MANAGED_END + "\ncontent\n" + MANAGED_START + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                install_workflow(Path(source_directory), target)

            self.assertFalse((target / ".ai-workflow").exists())
            self.assertFalse((target / "CLAUDE.md").exists())

    def test_existing_unmanaged_launcher_blocks_install_without_overwrite(self):
        with tempfile.TemporaryDirectory() as source_directory, tempfile.TemporaryDirectory() as target_directory:
            target = Path(target_directory)
            (target / "aiw").write_text("#!/bin/sh\necho business-tool\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                install_workflow(Path(source_directory), target)

            self.assertEqual("#!/bin/sh\necho business-tool\n", (target / "aiw").read_text(encoding="utf-8"))
            self.assertFalse((target / ".ai-workflow").exists())

    def test_install_is_idempotent_and_preserves_existing_agent_content(self):
        with tempfile.TemporaryDirectory() as source_directory, tempfile.TemporaryDirectory() as target_directory:
            source_root = Path(source_directory)
            target = Path(target_directory)
            (target / "AGENTS.md").write_text("# Existing rules\n\nKeep this exactly.\n", encoding="utf-8")
            (target / "package.json").write_text(
                json.dumps({"name": "target", "scripts": {"test": "node --test"}}),
                encoding="utf-8",
            )

            first = install_workflow(source_root, target)
            agents_after_first = (target / "AGENTS.md").read_text(encoding="utf-8")
            second = install_workflow(source_root, target)
            agents_after_second = (target / "AGENTS.md").read_text(encoding="utf-8")

            self.assertTrue(first["installed"])
            self.assertTrue(second["installed"])
            self.assertEqual(agents_after_first, agents_after_second)
            self.assertTrue(agents_after_second.startswith("# Existing rules\n\nKeep this exactly.\n"))
            self.assertEqual(1, agents_after_second.count(MANAGED_START))
            self.assertEqual(1, agents_after_second.count(MANAGED_END))
            self.assertTrue((target / "CLAUDE.md").is_file())
            self.assertTrue((target / ".ai-workflow" / "workflow" / "entry.md").is_file())
            self.assertTrue((target / ".ai-workflow" / "project.json").is_file())
            self.assertTrue((target / "aiw").is_file())
            self.assertTrue((target / "aiw.cmd").is_file())
            windows_launcher = (target / "aiw.cmd").read_text(encoding="utf-8")
            self.assertIn("python -m ai_workflow", windows_launcher)
            self.assertIn("py -3 -m ai_workflow", windows_launcher)
            self.assertIn("setlocal", windows_launcher)
            self.assertIn("pushd", windows_launcher)
            self.assertIn("popd", windows_launcher)
            self.assertFalse((target / ".github" / "copilot-instructions.md").exists())

    def test_reinstall_keeps_user_edited_project_contract(self):
        with tempfile.TemporaryDirectory() as source_directory, tempfile.TemporaryDirectory() as target_directory:
            source_root = Path(source_directory)
            target = Path(target_directory)
            install_workflow(source_root, target)
            contract_path = target / ".ai-workflow" / "project.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["project"]["summary"] = "Human maintained summary"
            contract_path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")

            install_workflow(source_root, target)

            preserved = json.loads(contract_path.read_text(encoding="utf-8"))
            self.assertEqual("Human maintained summary", preserved["project"]["summary"])

    def test_legacy_full_adapters_are_replaced_with_thin_entries_during_migration(self):
        with tempfile.TemporaryDirectory() as source_directory, tempfile.TemporaryDirectory() as target_directory:
            target = Path(target_directory)
            legacy = (
                "Read REPO-ROOT/.github/copilot-instructions.md\n"
                "Treat the processed request as \"the LATEST chat message\"\n"
            )
            (target / "AGENTS.md").write_text(legacy, encoding="utf-8")
            (target / "CLAUDE.md").write_text(legacy, encoding="utf-8")
            legacy_instruction = target / ".github" / "copilot-instructions.md"
            legacy_instruction.parent.mkdir(parents=True)
            legacy_instruction.write_text("legacy\n", encoding="utf-8")

            report = install_workflow(
                Path(source_directory),
                target,
                remove_legacy_copilot=True,
            )

            self.assertTrue(report["migration"]["applied"])
            for adapter_name in ("AGENTS.md", "CLAUDE.md"):
                content = (target / adapter_name).read_text(encoding="utf-8")
                self.assertIn(MANAGED_START, content)
                self.assertNotIn("copilot-instructions", content)
                self.assertLessEqual(len(content.splitlines()), 12)
            self.assertFalse(legacy_instruction.exists())


if __name__ == "__main__":
    unittest.main()
