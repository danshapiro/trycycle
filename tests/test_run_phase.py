from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_PHASE = REPO_ROOT / "orchestrator" / "run_phase.py"


def write_codex_transcript(root: Path, *, thread_id: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / f"rollout-{thread_id}.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "event_msg",
                        "payload": {
                            "type": "user_message",
                            "message": "ship it",
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "assistant",
                            "content": [
                                {"type": "output_text", "text": "ready"},
                            ],
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_claude_transcript(root: Path, *, canary: str) -> None:
    project_dir = root / "sample-project"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "sample.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "user",
                        "message": {
                            "content": f"{canary}\nreview request",
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {"type": "text", "text": "reviewed"},
                            ]
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )


class RunPhaseTests(unittest.TestCase):
    def run_phase(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        return subprocess.run(
            [sys.executable, str(RUN_PHASE), *args],
            text=True,
            capture_output=True,
            check=False,
            env=merged_env,
        )

    def test_prepare_builds_transcript_and_prompt_for_codex(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            workdir = tmp_path / "repo"
            workdir.mkdir()
            template_path = tmp_path / "template.md"
            search_root = tmp_path / "sessions"
            template_path.write_text(
                "<task_input_json>{USER_REQUEST_TRANSCRIPT}</task_input_json>\n"
                "Work in {WORKTREE_PATH}\n",
                encoding="utf-8",
            )
            write_codex_transcript(search_root, thread_id="thread-123")

            result = self.run_phase(
                "prepare",
                "--phase",
                "planning-initial",
                "--template",
                str(template_path),
                "--workdir",
                str(workdir),
                "--set",
                f"WORKTREE_PATH={workdir}",
                "--transcript-placeholder",
                "USER_REQUEST_TRANSCRIPT",
                "--transcript-cli",
                "codex-cli",
                "--transcript-search-root",
                str(search_root),
                "--require-nonempty-tag",
                "task_input_json",
                env={"CODEX_THREAD_ID": "thread-123"},
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "prepared")
            transcript_path = Path(payload["transcript_paths"]["USER_REQUEST_TRANSCRIPT"])
            prompt_path = Path(payload["prompt_path"])
            self.assertTrue(transcript_path.exists())
            self.assertTrue(prompt_path.exists())
            self.assertIn("ship it", prompt_path.read_text(encoding="utf-8"))
            self.assertIn(str(workdir), prompt_path.read_text(encoding="utf-8"))

    def test_prepare_supports_claude_canary_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            workdir = tmp_path / "repo"
            workdir.mkdir()
            template_path = tmp_path / "template.md"
            search_root = tmp_path / "projects"
            canary = "trycycle-canary-12345678"
            template_path.write_text(
                "<task_input_json>{USER_REQUEST_TRANSCRIPT}</task_input_json>\n",
                encoding="utf-8",
            )
            write_claude_transcript(search_root, canary=canary)

            result = self.run_phase(
                "prepare",
                "--phase",
                "planning-initial",
                "--template",
                str(template_path),
                "--workdir",
                str(workdir),
                "--transcript-placeholder",
                "USER_REQUEST_TRANSCRIPT",
                "--transcript-cli",
                "claude-code",
                "--transcript-search-root",
                str(search_root),
                "--canary",
                canary,
                "--require-nonempty-tag",
                "task_input_json",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            prompt_path = Path(payload["prompt_path"])
            self.assertIn("review request", prompt_path.read_text(encoding="utf-8"))

    def test_run_dispatches_with_subagent_runner_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            workdir = tmp_path / "repo"
            workdir.mkdir()
            template_path = tmp_path / "template.md"
            template_path.write_text("Work in {WORKTREE_PATH}\n", encoding="utf-8")

            result = self.run_phase(
                "run",
                "--phase",
                "smoke",
                "--template",
                str(template_path),
                "--workdir",
                str(workdir),
                "--set",
                f"WORKTREE_PATH={workdir}",
                "--backend",
                "codex",
                "--dry-run",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["dispatch"]["status"], "ok")
            self.assertTrue(Path(payload["prompt_path"]).exists())
            self.assertTrue(Path(payload["dispatch"]["result_path"]).exists())

    def test_prepare_fails_cleanly_when_transcript_lookup_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            workdir = tmp_path / "repo"
            workdir.mkdir()
            template_path = tmp_path / "template.md"
            search_root = tmp_path / "sessions"
            template_path.write_text(
                "<task_input_json>{USER_REQUEST_TRANSCRIPT}</task_input_json>\n",
                encoding="utf-8",
            )
            search_root.mkdir()

            result = self.run_phase(
                "prepare",
                "--phase",
                "planning-initial",
                "--template",
                str(template_path),
                "--workdir",
                str(workdir),
                "--transcript-placeholder",
                "USER_REQUEST_TRANSCRIPT",
                "--transcript-cli",
                "codex-cli",
                "--transcript-search-root",
                str(search_root),
                env={"CODEX_THREAD_ID": "missing-thread"},
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("canary is required", result.stderr)


if __name__ == "__main__":
    unittest.main()
