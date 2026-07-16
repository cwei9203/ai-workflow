import tempfile
import unittest
from pathlib import Path

from ai_workflow.tasks import TaskError, advance_task, archive_task, load_current_task, record_verification, start_task


class TaskLifecycleTests(unittest.TestCase):
    def test_change_task_enforces_order_acceptance_verification_and_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = start_task(root, "Fix race condition", kind="change", now="20260716-120000")
            self.assertEqual("intake", task["state"])

            with self.assertRaises(TaskError):
                advance_task(root, "implementing")

            advance_task(root, "context_ready")
            with self.assertRaises(TaskError):
                record_verification(root, {"passed": True, "selected": ["test"], "results": []})
            with self.assertRaises(TaskError):
                advance_task(root, "acceptance_defined")

            task_root = root / ".ai-workflow" / "tasks" / "active" / task["id"]
            (task_root / "acceptance.md").write_text("# Acceptance\n\n- The regression test passes.\n", encoding="utf-8")
            advance_task(root, "acceptance_defined")
            advance_task(root, "implementing")
            advance_task(root, "verifying")

            with self.assertRaises(TaskError):
                advance_task(root, "reviewing")

            record_verification(root, {"passed": True, "selected": ["test"], "results": []})
            advance_task(root, "reviewing")
            (task_root / "review.md").write_text("# Review\n\nNo actionable findings remain.\n", encoding="utf-8")
            (task_root / "acceptance.md").write_text("# Acceptance\n", encoding="utf-8")
            with self.assertRaises(TaskError):
                advance_task(root, "completed")
            (task_root / "acceptance.md").write_text(
                "# Acceptance\n\n- The regression test passes.\n", encoding="utf-8"
            )
            completed = advance_task(root, "completed")
            self.assertEqual("completed", completed["state"])

            archived = archive_task(root)
            self.assertTrue(archived.is_dir())
            self.assertIsNone(load_current_task(root))


if __name__ == "__main__":
    unittest.main()
