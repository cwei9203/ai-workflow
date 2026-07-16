import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class PluginContractTests(unittest.TestCase):
    def test_codex_and_claude_manifests_share_identity(self):
        codex = json.loads(
            (PROJECT_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        claude = json.loads(
            (PROJECT_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual(codex["name"], claude["name"])
        self.assertEqual(codex["version"], claude["version"])
        self.assertNotIn("hooks", codex)
        self.assertTrue((PROJECT_ROOT / claude["hooks"]).is_file())

    def test_shared_hook_is_session_start_only_and_points_to_existing_script(self):
        hooks = json.loads(
            (PROJECT_ROOT / "hooks" / "claude-hooks.json").read_text(encoding="utf-8")
        )
        self.assertEqual(["SessionStart"], list(hooks["hooks"]))
        command = hooks["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        self.assertIn("knowledge-candidate-reminder.py", command)
        self.assertTrue((PROJECT_ROOT / "hooks" / "knowledge-candidate-reminder.py").is_file())


if __name__ == "__main__":
    unittest.main()
