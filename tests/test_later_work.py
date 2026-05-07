from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LATER_WORK = REPO_ROOT / "orchestrator" / "later_work.py"


class LaterWorkCommandTests(unittest.TestCase):
    def run_cmd(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(LATER_WORK), *args],
            text=True,
            capture_output=True,
            check=False,
            cwd=REPO_ROOT,
        )

    def test_init_creates_store_and_cross_platform_wrapper_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            init = self.run_cmd("init", "--artifacts-dir", tmpdir)

            self.assertEqual(init.returncode, 0, init.stderr)
            payload = json.loads(init.stdout)
            store_path = Path(payload["later_work_path"])
            wrapper_path = Path(payload["file_later_work_wrapper_path"])
            wrapper_argv = payload["file_later_work_argv"]

            self.assertTrue(store_path.exists())
            self.assertTrue(wrapper_path.exists())
            self.assertEqual(wrapper_path.suffix, ".py")
            self.assertEqual(
                wrapper_argv,
                [str(Path(sys.executable).resolve()), str(wrapper_path)],
            )
            self.assertIn("file_later_work_command_posix", payload)
            self.assertIn("file_later_work_command_powershell", payload)
            self.assertIn("file_later_work_command_cmd", payload)
            self.assertIn(
                payload["file_later_work_command"],
                {
                    payload["file_later_work_command_posix"],
                    payload["file_later_work_command_powershell"],
                    payload["file_later_work_command_cmd"],
                },
            )
            self.assertEqual(store_path.read_text(encoding="utf-8"), "")

            append = subprocess.run(
                [
                    *wrapper_argv,
                    "--title",
                    "Renderer wraps long labels incorrectly",
                    "--severity",
                    "major",
                    "--why-it-matters",
                    "Long labels can make unrelated screens hard to use.",
                    "--why-later-not-current",
                    "The current request only touches command palette label text.",
                    "--evidence",
                    "Observed while reading ui/text_renderer.py.",
                    "--suggested-follow-up",
                    "Audit text wrapping separately.",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(append.returncode, 0, append.stderr)
            receipt = json.loads(append.stdout)
            self.assertEqual(receipt["status"], "filed")
            self.assertRegex(receipt["id"], r"^LW-[0-9a-f]{8}$")
            self.assertNotIn(str(store_path), append.stdout)
            self.assertNotIn("Renderer wraps", append.stdout)

            stored_lines = store_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(stored_lines), 1)
            stored = json.loads(stored_lines[0])
            self.assertEqual(stored["title"], "Renderer wraps long labels incorrectly")
            self.assertEqual(stored["severity"], "major")

    def test_append_rejects_missing_later_work_boundary_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "later-work.jsonl"
            result = self.run_cmd(
                "append",
                "--path",
                str(store_path),
                "--title",
                "Missing boundary",
                "--severity",
                "major",
                "--why-it-matters",
                "It matters.",
                "--evidence",
                "Evidence.",
                "--suggested-follow-up",
                "Follow up.",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("why-later-not-current", result.stderr)
            self.assertFalse(store_path.exists())

    def test_summarize_outputs_markdown_at_finish(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "later-work.jsonl"
            append = self.run_cmd(
                "append",
                "--path",
                str(store_path),
                "--title",
                "Renderer wraps long labels incorrectly",
                "--severity",
                "critical",
                "--why-it-matters",
                "Some screens can become unusable.",
                "--why-later-not-current",
                "The requested feature does not depend on renderer layout behavior.",
                "--evidence",
                "Observed in ui/text_renderer.py.",
                "--suggested-follow-up",
                "Plan a renderer hardening pass.",
            )
            self.assertEqual(append.returncode, 0, append.stderr)

            summary = self.run_cmd("summarize", "--path", str(store_path))

            self.assertEqual(summary.returncode, 0, summary.stderr)
            self.assertIn("## Later Work Found During This Run", summary.stdout)
            self.assertIn("Renderer wraps long labels incorrectly", summary.stdout)
            self.assertIn("Severity: critical", summary.stdout)

    def test_summarize_empty_store_reports_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "later-work.jsonl"
            store_path.write_text("", encoding="utf-8")

            summary = self.run_cmd("summarize", "--path", str(store_path))

            self.assertEqual(summary.returncode, 0, summary.stderr)
            self.assertEqual(summary.stdout.strip(), "No later work was filed.")


if __name__ == "__main__":
    unittest.main()
