from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT_BUILDER = REPO_ROOT / "orchestrator" / "user-request-transcript" / "build.py"


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )


def _kimi_session_dir(share_root: Path, workdir: Path, session_id: str) -> Path:
    workdir_hash = hashlib.md5(str(workdir.resolve()).encode("utf-8")).hexdigest()
    return share_root / "sessions" / workdir_hash / session_id


def _write_kimi_share_root(
    share_root: Path,
    *,
    workdir: Path,
    session_id: str,
    last_session_id: str | None,
    context_records: list[dict],
) -> Path:
    share_root.mkdir(parents=True, exist_ok=True)
    (share_root / "kimi.json").write_text(
        json.dumps(
            {
                "work_dirs": [
                    {
                        "path": str(workdir.resolve()),
                        "last_session_id": last_session_id,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    session_dir = _kimi_session_dir(share_root, workdir, session_id)
    _write_jsonl(session_dir / "context.jsonl", context_records)
    return session_dir


class UserRequestTranscriptBuildTests(unittest.TestCase):
    def run_builder(
        self,
        *args: str,
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        return subprocess.run(
            [sys.executable, str(TRANSCRIPT_BUILDER), *args],
            text=True,
            capture_output=True,
            check=False,
            env=merged_env,
            cwd=cwd,
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

    def test_kimi_direct_lookup_writes_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            share_root = tmp_path / "kimi-share"
            workdir = tmp_path / "repo"
            workdir.mkdir()
            output_path = tmp_path / "transcript.json"
            _write_kimi_share_root(
                share_root,
                workdir=workdir,
                session_id="session-direct",
                last_session_id="session-direct",
                context_records=[
                    {
                        "type": "user",
                        "message": {
                            "content": [
                                {"type": "text", "text": "hello from kimi"},
                            ]
                        },
                    },
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {"type": "think", "text": "internal chain of thought"},
                                {"type": "text", "text": "visible kimi reply"},
                            ]
                        },
                    },
                    {
                        "type": "user",
                        "message": {
                            "content": [
                                {"type": "text", "text": "next turn"},
                            ]
                        },
                    },
                ],
            )

            result = self.run_builder(
                "--cli",
                "kimi-cli",
                "--search-root",
                str(share_root),
                "--output",
                str(output_path),
                cwd=workdir,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            rendered = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(
                rendered,
                [
                    {"role": "user", "text": "hello from kimi"},
                    {"role": "assistant", "text": "visible kimi reply"},
                    {"role": "user", "text": "next turn"},
                ],
            )

    def test_kimi_canary_lookup_works_when_last_session_id_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            share_root = tmp_path / "kimi-share"
            workdir = tmp_path / "repo"
            workdir.mkdir()
            output_path = tmp_path / "transcript.json"
            canary = "trycycle-kimi-canary-123456"
            session_dir = _write_kimi_share_root(
                share_root,
                workdir=workdir,
                session_id="session-fallback",
                last_session_id=None,
                context_records=[
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {"type": "text", "text": "ignored direct lookup seed"},
                            ]
                        },
                    },
                ],
            )
            _write_jsonl(
                session_dir / "context.jsonl",
                [
                    {
                        "type": "user",
                        "message": {
                            "content": [
                                {"type": "text", "text": f"{canary}\nhello from canary"},
                            ]
                        },
                    },
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {"type": "think", "text": "ignore me"},
                                {"type": "text", "text": "chosen top-level context"},
                            ]
                        },
                    },
                    {
                        "type": "user",
                        "message": {
                            "content": [
                                {"type": "text", "text": "after fallback"},
                            ]
                        },
                    },
                ],
            )
            _write_jsonl(
                session_dir / "wire.jsonl",
                [
                    {
                        "type": "user",
                        "message": {
                            "content": [
                                {"type": "text", "text": f"{canary}\nwire decoy"},
                            ]
                        },
                    }
                ],
            )
            _write_jsonl(
                session_dir / "context_sub_1.jsonl",
                [
                    {
                        "type": "user",
                        "message": {
                            "content": [
                                {"type": "text", "text": f"{canary}\nsubcontext decoy"},
                            ]
                        },
                    }
                ],
            )

            result = self.run_builder(
                "--cli",
                "kimi-cli",
                "--canary",
                canary,
                "--search-root",
                str(share_root),
                "--output",
                str(output_path),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            rendered = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(
                rendered,
                [
                    {"role": "user", "text": f"{canary}\nhello from canary"},
                    {"role": "assistant", "text": "chosen top-level context"},
                    {"role": "user", "text": "after fallback"},
                ],
            )


if __name__ == "__main__":
    unittest.main()
