import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ai_workflow.knowledge import KnowledgeError, knowledge_candidates, mark_knowledge_decision


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class KnowledgeTests(unittest.TestCase):
    def _archived_task(self, root: Path, task_id: str = "20260716-120000-fix") -> Path:
        task_root = root / ".ai-workflow" / "tasks" / "archive" / task_id
        task_root.mkdir(parents=True)
        (task_root / "task.json").write_text(
            json.dumps({
                "id": task_id,
                "title": "Fix durable issue",
                "kind": "change",
                "state": "completed",
            }),
            encoding="utf-8",
        )
        knowledge = root / ".ai-workflow" / "knowledge"
        knowledge.mkdir(parents=True, exist_ok=True)
        (knowledge / "ledger.json").write_text(
            json.dumps({"version": 1, "tasks": {}}), encoding="utf-8"
        )
        (knowledge / "learnings.md").write_text("# Durable Learnings\n", encoding="utf-8")
        return task_root

    def test_candidates_require_an_explicit_decision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._archived_task(root)
            candidates = knowledge_candidates(root)
            self.assertEqual(["20260716-120000-fix"], [item["id"] for item in candidates])

            with self.assertRaises(KnowledgeError):
                mark_knowledge_decision(root, candidates[0]["id"], "dismissed")
            mark_knowledge_decision(
                root, candidates[0]["id"], "dismissed", reason="One-off dependency outage"
            )
            self.assertEqual([], knowledge_candidates(root))
            with self.assertRaises(KnowledgeError):
                mark_knowledge_decision(
                    root, candidates[0]["id"], "dismissed", reason="Changed my mind"
                )

    def test_published_decision_requires_source_citation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._archived_task(root)
            with self.assertRaises(KnowledgeError):
                mark_knowledge_decision(root, "20260716-120000-fix", "published")
            learnings = root / ".ai-workflow" / "knowledge" / "learnings.md"
            learnings.write_text(
                "# Durable Learnings\n\n- Source tasks: 20260716-120000-fix\n",
                encoding="utf-8",
            )
            mark_knowledge_decision(root, "20260716-120000-fix", "published")
            self.assertEqual([], knowledge_candidates(root))

    def test_hook_is_read_only_and_adapts_output_for_both_hosts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._archived_task(root)
            (root / ".ai-workflow" / "project.json").write_text("{}", encoding="utf-8")
            hook = PROJECT_ROOT / "hooks" / "knowledge-candidate-reminder.py"
            before = (root / ".ai-workflow" / "knowledge" / "ledger.json").read_bytes()

            claude = subprocess.run(
                [sys.executable, str(hook)],
                input=json.dumps({"cwd": str(root)}),
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertIn("without a durable-knowledge decision", claude.stdout)

            environment = os.environ.copy()
            environment["PLUGIN_DATA"] = str(root / ".plugin-data")
            codex = subprocess.run(
                [sys.executable, str(hook)],
                input=json.dumps({"cwd": str(root)}),
                text=True,
                capture_output=True,
                env=environment,
                check=True,
            )
            payload = json.loads(codex.stdout)
            self.assertEqual("SessionStart", payload["hookSpecificOutput"]["hookEventName"])
            self.assertEqual(
                before,
                (root / ".ai-workflow" / "knowledge" / "ledger.json").read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
