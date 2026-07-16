import json
import tempfile
import unittest
from pathlib import Path

from ai_workflow.discovery import discover_project
from ai_workflow.validation import validate_contract


class DiscoveryTests(unittest.TestCase):
    def test_discovers_typescript_pnpm_project_without_inventing_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "package.json").write_text(
                json.dumps(
                    {
                        "name": "existing-app",
                        "scripts": {
                            "build": "tsc -b",
                            "test": "vitest run",
                            "lint": "eslint .",
                            "typecheck": "tsc --noEmit",
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")
            (root / "tsconfig.json").write_text("{}\n", encoding="utf-8")
            (root / "README.md").write_text("# Existing App\n", encoding="utf-8")
            (root / "src").mkdir()
            (root / "tests").mkdir()

            contract = discover_project(root)

            self.assertEqual("existing-app", contract["project"]["name"])
            self.assertIn("TypeScript", contract["project"]["languages"])
            self.assertIn("Node.js", contract["project"]["platforms"])
            self.assertEqual("pnpm run build", contract["commands"]["build"]["run"])
            self.assertEqual("pnpm test", contract["commands"]["test"]["run"])
            self.assertEqual(["src"], contract["project"]["source_roots"])
            self.assertEqual(["tests"], contract["project"]["test_roots"])
            self.assertIn("README.md", contract["context"]["read_first"])
            self.assertEqual("needs_review", contract["onboarding"]["status"])
            self.assertNotIn("format", contract["commands"])
            self.assertEqual([], validate_contract(contract))

    def test_discovers_rust_and_go_commands_from_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Cargo.toml").write_text('[package]\nname = "demo"\n', encoding="utf-8")
            (root / "go.mod").write_text("module example.test/demo\n", encoding="utf-8")

            contract = discover_project(root)

            self.assertIn("Rust", contract["project"]["languages"])
            self.assertIn("Go", contract["project"]["languages"])
            self.assertEqual("cargo build", contract["commands"]["rust_build"]["run"])
            self.assertEqual("go test ./...", contract["commands"]["go_test"]["run"])


if __name__ == "__main__":
    unittest.main()
