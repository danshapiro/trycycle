from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT_BUILDER = REPO_ROOT / "orchestrator" / "user-request-transcript" / "build.py"


class UserRequestTranscriptBuildTests(unittest.TestCase):
    def run_builder(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        return subprocess.run(
            [sys.executable, str(TRANSCRIPT_BUILDER), *args],
            text=True,
            capture_output=True,
            check=False,
            env=merged_env,
        )

    def test_codex_direct_lookup_writes_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            search_root = Path(tmpdir) / "sessions"
            search_root.mkdir()
            output_path = Path(tmpdir) / "transcript.json"
            transcript_path = search_root / "rollout-thread-123.jsonl"
            transcript_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "event_msg",
                                "payload": {
                                    "type": "user_message",
                                    "message": "hello",
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
                                        {"type": "output_text", "text": "world"},
                                    ],
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "event_msg",
                                "payload": {
                                    "type": "user_message",
                                    "message": "next",
                                },
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = self.run_builder(
                "--cli",
                "codex-cli",
                "--search-root",
                str(search_root),
                "--output",
                str(output_path),
                env={"CODEX_THREAD_ID": "thread-123"},
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            rendered = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(
                rendered,
                [
                    {"role": "user", "text": "hello"},
                    {"role": "assistant", "text": "world"},
                    {"role": "user", "text": "next"},
                ],
            )

    def test_claude_canary_lookup_writes_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            search_root = Path(tmpdir) / "projects"
            project_dir = search_root / "sample-project"
            project_dir.mkdir(parents=True)
            output_path = Path(tmpdir) / "transcript.json"
            canary = "trycycle-canary-12345678"
            transcript_path = project_dir / "sample.jsonl"
            transcript_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "user",
                                "message": {
                                    "content": f"{canary}\nhello",
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "assistant",
                                "message": {
                                    "content": [
                                        {"type": "text", "text": "world"},
                                    ]
                                },
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = self.run_builder(
                "--cli",
                "claude-code",
                "--canary",
                canary,
                "--search-root",
                str(search_root),
                "--output",
                str(output_path),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            rendered = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(
                rendered,
                [
                    {"role": "user", "text": f"{canary}\nhello"},
                ],
            )


if __name__ == "__main__":
    unittest.main()
