import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class CliEndToEndTests(unittest.TestCase):
    def test_doctor_detects_missing_runtime_and_launchers(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "damaged-project"
            target.mkdir()
            environment = self._environment()
            initialized = subprocess.run(
                [sys.executable, "-m", "ai_workflow", "init", str(target)],
                cwd=PROJECT_ROOT,
                env=environment,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, initialized.returncode, initialized.stderr)
            (target / "aiw.cmd").unlink()
            (target / ".ai-workflow" / "runtime" / "ai_workflow" / "__main__.py").unlink()

            doctor = subprocess.run(
                [sys.executable, "-m", "ai_workflow", "doctor", "--project-root", str(target)],
                cwd=PROJECT_ROOT,
                env=environment,
                text=True,
                capture_output=True,
            )

            self.assertEqual(1, doctor.returncode)
            self.assertIn("aiw.cmd", doctor.stdout)
            self.assertIn("__main__.py", doctor.stdout)

    @staticmethod
    def _environment():
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
        return environment

    def test_init_doctor_and_local_launcher(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project with spaces"
            target.mkdir()
            (target / "package.json").write_text(
                json.dumps({"name": "space-project", "scripts": {"test": "node --test"}}),
                encoding="utf-8",
            )
            environment = self._environment()

            initialized = subprocess.run(
                [sys.executable, "-m", "ai_workflow", "init", str(target)],
                cwd=PROJECT_ROOT,
                env=environment,
                text=True,
                capture_output=True,
            )
            doctor = subprocess.run(
                [str(target / "aiw"), "doctor"],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
            )
            blocked_task = subprocess.run(
                [str(target / "aiw"), "task", "start", "Too early"],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(0, initialized.returncode, initialized.stderr)
            self.assertEqual(0, doctor.returncode, doctor.stderr)
            self.assertEqual(1, blocked_task.returncode)
            self.assertIn("Complete project onboarding", blocked_task.stderr)
            self.assertIn("installed", initialized.stdout.lower())
            self.assertIn("onboarding", doctor.stdout.lower())

    def test_agent_completed_project_context_passes_strict_doctor(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "ready-project"
            target.mkdir()
            (target / "package.json").write_text(
                json.dumps({"name": "ready", "scripts": {"test": "node --test"}}),
                encoding="utf-8",
            )
            environment = self._environment()
            initialized = subprocess.run(
                [sys.executable, "-m", "ai_workflow", "init", str(target)],
                cwd=PROJECT_ROOT,
                env=environment,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, initialized.returncode, initialized.stderr)

            contract_path = target / ".ai-workflow" / "project.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["project"]["summary"] = "A Node.js project used to prove complete onboarding."
            contract["verification"]["default"] = ["test"]
            contract["onboarding"]["review_notes"] = []
            contract_path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
            (target / ".ai-workflow" / "project-notes.md").write_text(
                "# Project Notes\n\n"
                "## Purpose\n\nProves onboarding behavior.\n\n"
                "## Architecture\n\nOne package with no internal layers.\n\n"
                "## Critical invariants\n\nThe test command must remain non-interactive.\n\n"
                "## Development caveats\n\nInstall Node.js dependencies before verification.\n\n"
                "## Terminology\n\nN/A — no domain-specific terminology.\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [str(target / "aiw"), "project", "complete"],
                cwd=target,
                text=True,
                capture_output=True,
            )
            doctor = subprocess.run(
                [str(target / "aiw"), "doctor", "--strict"],
                cwd=target,
                text=True,
                capture_output=True,
            )

            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertEqual(0, doctor.returncode, doctor.stdout + doctor.stderr)
            self.assertIn("valid", doctor.stdout.lower())

    def test_full_change_task_runs_from_intake_through_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "lifecycle-project"
            target.mkdir()
            (target / "source.py").write_text("value = 1\n", encoding="utf-8")
            environment = self._environment()

            initialized = subprocess.run(
                [sys.executable, "-m", "ai_workflow", "init", str(target)],
                cwd=PROJECT_ROOT,
                env=environment,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, initialized.returncode, initialized.stderr)
            contract_path = target / ".ai-workflow" / "project.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["project"]["summary"] = "A fixture that exercises the complete change lifecycle."
            contract["commands"]["test"] = {
                "run": f'"{sys.executable}" -c "print(\'verified\')"',
                "description": "Deterministic fixture verification",
            }
            contract["verification"]["default"] = ["test"]
            contract["onboarding"]["review_notes"] = []
            contract_path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
            (target / ".ai-workflow" / "project-notes.md").write_text(
                "# Project Notes\n\n"
                "## Purpose\n\nExercises the reusable workflow.\n\n"
                "## Architecture\n\nA single source module.\n\n"
                "## Critical invariants\n\nVerification must remain deterministic.\n\n"
                "## Development caveats\n\nNo external dependencies.\n\n"
                "## Terminology\n\nN/A — the fixture has no domain terminology.\n",
                encoding="utf-8",
            )

            def aiw(*arguments):
                return subprocess.run(
                    [str(target / "aiw"), *arguments],
                    cwd=PROJECT_ROOT,
                    text=True,
                    capture_output=True,
                )

            self.assertEqual(0, aiw("project", "complete").returncode)
            subprocess.run(["git", "init"], cwd=target, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=target, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=target, check=True)
            subprocess.run(["git", "add", "."], cwd=target, check=True)
            subprocess.run(["git", "commit", "-m", "baseline"], cwd=target, check=True, capture_output=True)

            started = aiw("task", "start", "Change fixture value", "--kind", "change")
            self.assertEqual(0, started.returncode, started.stderr)
            self.assertEqual(0, aiw("task", "advance", "context_ready").returncode)
            current = json.loads(
                (target / ".ai-workflow" / "tasks" / "current.json").read_text(encoding="utf-8")
            )
            task_root = target / ".ai-workflow" / "tasks" / "active" / current["id"]
            (task_root / "acceptance.md").write_text(
                "# Acceptance\n\n- The source value is updated and verification passes.\n",
                encoding="utf-8",
            )
            self.assertEqual(0, aiw("task", "advance", "acceptance_defined").returncode)
            self.assertEqual(0, aiw("task", "advance", "implementing").returncode)
            (target / "source.py").write_text("value = 2\n", encoding="utf-8")
            self.assertEqual(0, aiw("task", "advance", "verifying").returncode)
            verified = aiw("verify", "--changed")
            self.assertEqual(0, verified.returncode, verified.stdout + verified.stderr)
            self.assertIn("PASS", verified.stdout)
            (target / "source.py").write_text("value = 3\n", encoding="utf-8")
            stale = aiw("task", "advance", "reviewing")
            self.assertEqual(1, stale.returncode)
            self.assertIn("verify again", stale.stderr)
            (target / "source.py").write_text("value = 2\n", encoding="utf-8")
            self.assertEqual(0, aiw("task", "advance", "reviewing").returncode)
            (task_root / "review.md").write_text(
                "# Review\n\nNo actionable findings remain after inspecting the final diff.\n",
                encoding="utf-8",
            )
            self.assertEqual(0, aiw("task", "advance", "completed").returncode)
            self.assertEqual(0, aiw("task", "archive").returncode)
            self.assertFalse((target / ".ai-workflow" / "tasks" / "current.json").exists())
            self.assertTrue((target / ".ai-workflow" / "tasks" / "archive" / current["id"]).is_dir())


if __name__ == "__main__":
    unittest.main()
