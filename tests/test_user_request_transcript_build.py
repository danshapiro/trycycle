from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT_BUILDER = REPO_ROOT / "orchestrator" / "user-request-transcript" / "build.py"
TRANSCRIPT_MODULE_ROOT = REPO_ROOT / "orchestrator" / "user-request-transcript"


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )


def _kimi_session_dir(share_root: Path, workdir: Path, session_id: str) -> Path:
    workdir_hash = hashlib.md5(str(workdir.resolve()).encode("utf-8")).hexdigest()
    return share_root / "sessions" / workdir_hash / session_id


def _kimi_legacy_session_path(share_root: Path, workdir: Path, session_id: str) -> Path:
    workdir_hash = hashlib.md5(str(workdir.resolve()).encode("utf-8")).hexdigest()
    return share_root / "sessions" / workdir_hash / f"{session_id}.jsonl"


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


def _write_kimi_legacy_share_root(
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
    legacy_path = _kimi_legacy_session_path(share_root, workdir, session_id)
    _write_jsonl(legacy_path, context_records)
    return legacy_path


def _write_fake_rg_binary(bin_dir: Path) -> Path:
    rg_path = bin_dir / "rg"
    rg_path.write_text(
        textwrap.dedent(
            f"""\
            #!{sys.executable}
            import json
            import os
            import sys

            log_path = os.environ.get("FAKE_RG_LOG")
            if log_path:
                with open(log_path, "a", encoding="utf-8") as handle:
                    handle.write(json.dumps({{"argv": sys.argv[1:]}}) + "\\n")

            match_path = os.environ.get("FAKE_RG_MATCH")
            if match_path:
                sys.stdout.write(match_path + "\\n")
                raise SystemExit(0)

            raise SystemExit(1)
            """
        ),
        encoding="utf-8",
    )
    rg_path.chmod(0o755)
    return rg_path


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

    def test_kimi_direct_lookup_supports_legacy_flat_session_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            share_root = tmp_path / "kimi-share"
            workdir = tmp_path / "repo"
            workdir.mkdir()
            output_path = tmp_path / "transcript.json"
            _write_kimi_legacy_share_root(
                share_root,
                workdir=workdir,
                session_id="session-legacy",
                last_session_id="session-legacy",
                context_records=[
                    {
                        "role": "user",
                        "content": "hello from legacy kimi",
                    },
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "think", "text": "ignore"},
                            {"type": "text", "text": "visible legacy kimi reply"},
                        ],
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
                    {"role": "user", "text": "hello from legacy kimi"},
                    {"role": "assistant", "text": "visible legacy kimi reply"},
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
            debug_path = session_dir / "debug.jsonl"
            _write_jsonl(
                debug_path,
                [
                    {
                        "type": "user",
                        "message": {
                            "content": [
                                {"type": "text", "text": f"{canary}\ndebug decoy"},
                            ]
                        },
                    }
                ],
            )
            debug_stat = debug_path.stat()
            os.utime(
                debug_path,
                ns=(debug_stat.st_atime_ns, debug_stat.st_mtime_ns + 1_000_000),
            )

            result = self.run_builder(
                "--cli",
                "kimi-cli",
                "--canary",
                canary,
                "--timeout-ms",
                "1000",
                "--poll-ms",
                "10",
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

    def test_kimi_canary_lookup_works_when_metadata_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            share_root = tmp_path / "kimi-share"
            workdir = tmp_path / "repo"
            output_path = tmp_path / "transcript.json"
            canary = "trycycle-kimi-metadata-missing"
            session_dir = _kimi_session_dir(share_root, workdir, "session-fallback")
            workdir.mkdir()
            _write_jsonl(
                session_dir / "context.jsonl",
                [
                    {
                        "type": "user",
                        "message": {
                            "content": [
                                {"type": "text", "text": f"{canary}\nhello from missing metadata"},
                            ]
                        },
                    },
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {"type": "think", "text": "ignore me"},
                                {"type": "text", "text": "fallback still works"},
                            ]
                        },
                    },
                ],
            )

            result = self.run_builder(
                "--cli",
                "kimi-cli",
                "--canary",
                canary,
                "--timeout-ms",
                "1000",
                "--poll-ms",
                "10",
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
                    {"role": "user", "text": f"{canary}\nhello from missing metadata"},
                    {"role": "assistant", "text": "fallback still works"},
                ],
            )

    def test_kimi_canary_lookup_supports_legacy_flat_session_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            share_root = tmp_path / "kimi-share"
            workdir = tmp_path / "repo"
            output_path = tmp_path / "transcript.json"
            canary = "trycycle-kimi-legacy-canary"
            workdir.mkdir()
            _write_jsonl(
                _kimi_legacy_session_path(share_root, workdir, "session-legacy"),
                [
                    {
                        "role": "user",
                        "content": f"{canary}\nlegacy user",
                    },
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "legacy fallback reply"},
                        ],
                    },
                ],
            )

            result = self.run_builder(
                "--cli",
                "kimi-cli",
                "--canary",
                canary,
                "--timeout-ms",
                "1000",
                "--poll-ms",
                "10",
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
                    {"role": "user", "text": f"{canary}\nlegacy user"},
                    {"role": "assistant", "text": "legacy fallback reply"},
                ],
            )

    def test_kimi_canary_lookup_ignores_hash_root_debug_decoy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            share_root = tmp_path / "kimi-share"
            workdir = tmp_path / "repo"
            output_path = tmp_path / "transcript.json"
            canary = "trycycle-kimi-hash-root-decoy"
            workdir.mkdir()
            session_dir = _write_kimi_share_root(
                share_root,
                workdir=workdir,
                session_id="session-fallback",
                last_session_id=None,
                context_records=[
                    {"role": "assistant", "content": "seed"},
                ],
            )
            context_path = session_dir / "context.jsonl"
            _write_jsonl(
                context_path,
                [
                    {"role": "user", "content": f"{canary}\nreal user"},
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "real reply"},
                        ],
                    },
                ],
            )
            debug_path = _kimi_legacy_session_path(share_root, workdir, "debug")
            _write_jsonl(
                debug_path,
                [
                    {"role": "user", "content": f"{canary}\ndebug decoy"},
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "wrong decoy reply"},
                        ],
                    },
                ],
            )
            debug_stat = debug_path.stat()
            os.utime(
                debug_path,
                ns=(debug_stat.st_atime_ns, debug_stat.st_mtime_ns + 1_000_000),
            )

            result = self.run_builder(
                "--cli",
                "kimi-cli",
                "--canary",
                canary,
                "--timeout-ms",
                "1000",
                "--poll-ms",
                "10",
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
                    {"role": "user", "text": f"{canary}\nreal user"},
                    {"role": "assistant", "text": "real reply"},
                ],
            )

    def test_kimi_canary_lookup_limits_ripgrep_to_top_level_transcript_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            bin_dir = tmp_path / "bin"
            share_root = tmp_path / "kimi-share"
            workdir = tmp_path / "repo"
            output_path = tmp_path / "transcript.json"
            log_path = tmp_path / "rg-log.jsonl"
            canary = "trycycle-kimi-rg-scope"
            workdir.mkdir()
            bin_dir.mkdir()
            _write_fake_rg_binary(bin_dir)
            match_path = _kimi_session_dir(share_root, workdir, "session-fallback") / "context.jsonl"
            wire_path = _kimi_session_dir(share_root, workdir, "session-fallback") / "wire.jsonl"
            subcontext_path = _kimi_session_dir(share_root, workdir, "session-fallback") / "context_sub_1.jsonl"
            _write_jsonl(
                match_path,
                [
                    {"role": "user", "content": f"{canary}\nrg scoped user"},
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "rg scoped reply"},
                        ],
                    },
                ],
            )
            _write_jsonl(
                wire_path,
                [
                    {"role": "user", "content": f"{canary}\nwire decoy"},
                ],
            )
            _write_jsonl(
                subcontext_path,
                [
                    {"role": "user", "content": f"{canary}\nsubcontext decoy"},
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
                env={
                    "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
                    "FAKE_RG_LOG": str(log_path),
                    "FAKE_RG_MATCH": str(match_path),
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            log_records = [
                json.loads(line)
                for line in log_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            argv = log_records[-1]["argv"]
            self.assertIn(str(match_path), argv)
            self.assertNotIn(str(share_root / "sessions"), argv)
            self.assertNotIn(str(wire_path), argv)
            self.assertNotIn(str(subcontext_path), argv)
            self.assertNotIn("--glob", argv)

    def test_kimi_extract_transcript_ignores_meta_records_and_keeps_last_visible_assistant_per_interval(
        self,
    ) -> None:
        sys.path.insert(0, str(TRANSCRIPT_MODULE_ROOT))
        try:
            import kimi_cli  # type: ignore
        finally:
            sys.path.pop(0)

        with tempfile.TemporaryDirectory() as tmpdir:
            context_path = Path(tmpdir) / "context.jsonl"
            _write_jsonl(
                context_path,
                [
                    {"role": "_system_prompt", "content": "ignored"},
                    {"role": "_checkpoint", "id": 0},
                    {"role": "user", "content": "first user"},
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "think", "text": "internal"},
                            {"type": "text", "text": "first visible"},
                        ],
                    },
                    {"role": "_usage", "token_count": 123},
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "last visible before next user"},
                        ],
                    },
                    {"role": "user", "content": "second user"},
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "think", "text": "ignored"},
                            {"type": "text", "text": "final visible reply"},
                        ],
                    },
                ],
            )

            turns = kimi_cli.extract_transcript(context_path)

            self.assertEqual(
                [(turn.role, turn.text) for turn in turns],
                [
                    ("user", "first user"),
                    ("assistant", "last visible before next user"),
                    ("user", "second user"),
                    ("assistant", "final visible reply"),
                ],
            )


def _create_opencode_db(db_path: Path, sessions: list[dict]) -> None:
    """Create a minimal OpenCode SQLite DB with the given session/message/part data."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE session (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            directory TEXT NOT NULL,
            title TEXT NOT NULL,
            version TEXT NOT NULL,
            time_created INTEGER NOT NULL,
            time_updated INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE message (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            time_created INTEGER NOT NULL,
            time_updated INTEGER NOT NULL,
            data TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE part (
            id TEXT PRIMARY KEY,
            message_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            time_created INTEGER NOT NULL,
            time_updated INTEGER NOT NULL,
            data TEXT NOT NULL
        )
    """)
    for session in sessions:
        conn.execute(
            "INSERT INTO session VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session["id"], "proj1", session.get("directory", "/tmp"),
             session.get("title", "test"), "1.3.0",
             session.get("time_created", 1000), session.get("time_updated", 2000)),
        )
        for msg in session.get("messages", []):
            conn.execute(
                "INSERT INTO message VALUES (?, ?, ?, ?, ?)",
                (msg["id"], session["id"], msg.get("time_created", 1000),
                 msg.get("time_updated", 2000), json.dumps(msg["data"])),
            )
            for part in msg.get("parts", []):
                conn.execute(
                    "INSERT INTO part VALUES (?, ?, ?, ?, ?, ?)",
                    (part["id"], msg["id"], session["id"],
                     part.get("time_created", 1000), part.get("time_updated", 2000),
                     json.dumps(part["data"])),
                )
    conn.commit()
    conn.close()


class OpenCodeTranscriptTests(UserRequestTranscriptBuildTests):
    def test_opencode_canary_finds_correct_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            db_path = tmp_path / "opencode.db"
            canary = "trycycle-canary-12345678901234567890"
            _create_opencode_db(db_path, [
                {
                    "id": "ses_abc123",
                    "directory": "/tmp",
                    "time_created": 1000,
                    "time_updated": 2000,
                    "messages": [
                        {
                            "id": "msg_001",
                            "data": {"role": "user"},
                            "time_created": 1001,
                            "time_updated": 1001,
                            "parts": [
                                {
                                    "id": "prt_001",
                                    "data": {"type": "text", "text": f"Build something {canary}"},
                                    "time_created": 1001,
                                    "time_updated": 1001,
                                },
                            ],
                        },
                        {
                            "id": "msg_002",
                            "data": {"role": "assistant"},
                            "time_created": 1002,
                            "time_updated": 1002,
                            "parts": [
                                {
                                    "id": "prt_002",
                                    "data": {"type": "text", "text": "I'll help you build that."},
                                    "time_created": 1002,
                                    "time_updated": 1002,
                                },
                            ],
                        },
                    ],
                },
            ])
            result = self.run_builder(
                "--cli", "opencode",
                "--canary", canary,
                "--search-root", str(tmp_path),
                env={"HOME": str(tmp_path)},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            turns = json.loads(result.stdout)
            self.assertEqual(len(turns), 2)
            self.assertEqual(turns[0]["role"], "user")
            self.assertIn(canary, turns[0]["text"])
            self.assertEqual(turns[1]["role"], "assistant")
            self.assertEqual(turns[1]["text"], "I'll help you build that.")

    def test_opencode_multi_turn_transcript(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            db_path = tmp_path / "opencode.db"
            canary = "trycycle-canary-multiturn-test"
            _create_opencode_db(db_path, [
                {
                    "id": "ses_multi",
                    "directory": "/tmp",
                    "time_created": 1000,
                    "time_updated": 2000,
                    "messages": [
                        {
                            "id": "msg_001",
                            "data": {"role": "user"},
                            "time_created": 1001,
                            "time_updated": 1001,
                            "parts": [
                                {
                                    "id": "prt_001",
                                    "data": {"type": "text", "text": f"user1 {canary}"},
                                    "time_created": 1001,
                                    "time_updated": 1001,
                                },
                            ],
                        },
                        {
                            "id": "msg_002",
                            "data": {"role": "assistant"},
                            "time_created": 1002,
                            "time_updated": 1002,
                            "parts": [
                                {
                                    "id": "prt_002",
                                    "data": {"type": "text", "text": "assistant1"},
                                    "time_created": 1002,
                                    "time_updated": 1002,
                                },
                            ],
                        },
                        {
                            "id": "msg_003",
                            "data": {"role": "user"},
                            "time_created": 1003,
                            "time_updated": 1003,
                            "parts": [
                                {
                                    "id": "prt_003",
                                    "data": {"type": "text", "text": "user2"},
                                    "time_created": 1003,
                                    "time_updated": 1003,
                                },
                            ],
                        },
                        {
                            "id": "msg_004",
                            "data": {"role": "assistant"},
                            "time_created": 1004,
                            "time_updated": 1004,
                            "parts": [
                                {
                                    "id": "prt_004",
                                    "data": {"type": "text", "text": "assistant2"},
                                    "time_created": 1004,
                                    "time_updated": 1004,
                                },
                            ],
                        },
                    ],
                },
            ])
            result = self.run_builder(
                "--cli", "opencode",
                "--canary", canary,
                "--search-root", str(tmp_path),
                env={"HOME": str(tmp_path)},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            turns = json.loads(result.stdout)
            self.assertEqual(len(turns), 4)
            self.assertEqual(turns[0]["role"], "user")
            self.assertEqual(turns[1]["role"], "assistant")
            self.assertEqual(turns[2]["role"], "user")
            self.assertEqual(turns[3]["role"], "assistant")

    def test_opencode_transcript_skips_empty_and_non_text_parts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            db_path = tmp_path / "opencode.db"
            canary = "trycycle-canary-filter-test"
            _create_opencode_db(db_path, [
                {
                    "id": "ses_filter",
                    "directory": "/tmp",
                    "time_created": 1000,
                    "time_updated": 2000,
                    "messages": [
                        {
                            "id": "msg_001",
                            "data": {"role": "user"},
                            "time_created": 1001,
                            "time_updated": 1001,
                            "parts": [
                                {
                                    "id": "prt_001",
                                    "data": {"type": "text", "text": f"visible user {canary}"},
                                    "time_created": 1001,
                                    "time_updated": 1001,
                                },
                            ],
                        },
                        {
                            "id": "msg_002",
                            "data": {"role": "assistant"},
                            "time_created": 1002,
                            "time_updated": 1002,
                            "parts": [
                                {
                                    "id": "prt_002",
                                    "data": {"type": "tool_use", "name": "bash"},
                                    "time_created": 1002,
                                    "time_updated": 1002,
                                },
                                {
                                    "id": "prt_003",
                                    "data": {"type": "text", "text": "   "},
                                    "time_created": 1003,
                                    "time_updated": 1003,
                                },
                            ],
                        },
                        {
                            "id": "msg_003",
                            "data": {"role": "assistant"},
                            "time_created": 1004,
                            "time_updated": 1004,
                            "parts": [
                                {
                                    "id": "prt_004",
                                    "data": {"type": "text", "text": "visible reply"},
                                    "time_created": 1004,
                                    "time_updated": 1004,
                                },
                            ],
                        },
                    ],
                },
            ])
            result = self.run_builder(
                "--cli", "opencode",
                "--canary", canary,
                "--search-root", str(tmp_path),
                env={"HOME": str(tmp_path)},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            turns = json.loads(result.stdout)
            self.assertEqual(len(turns), 2)
            self.assertEqual(turns[0]["role"], "user")
            self.assertEqual(turns[1]["role"], "assistant")
            self.assertEqual(turns[1]["text"], "visible reply")

    def test_opencode_transcript_fails_gracefully_when_db_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            result = self.run_builder(
                "--cli", "opencode",
                "--canary", "nonexistent-canary",
                "--search-root", str(tmp_path),
                env={"HOME": str(tmp_path)},
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("not found", result.stderr)

    def test_opencode_canary_timeout_when_canary_not_in_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            db_path = tmp_path / "opencode.db"
            _create_opencode_db(db_path, [
                {
                    "id": "ses_empty",
                    "directory": "/tmp",
                    "time_created": 1000,
                    "time_updated": 2000,
                    "messages": [
                        {
                            "id": "msg_001",
                            "data": {"role": "user"},
                            "time_created": 1001,
                            "time_updated": 1001,
                            "parts": [
                                {
                                    "id": "prt_001",
                                    "data": {"type": "text", "text": "no canary here"},
                                    "time_created": 1001,
                                    "time_updated": 1001,
                                },
                            ],
                        },
                    ],
                },
            ])
            result = self.run_builder(
                "--cli", "opencode",
                "--canary", "nonexistent-canary-xyz",
                "--search-root", str(tmp_path),
                "--timeout-ms", "500",
                env={"HOME": str(tmp_path)},
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("canary", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
