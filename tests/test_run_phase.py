from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_PHASE = REPO_ROOT / "orchestrator" / "run_phase.py"
SUBAGENT_RUNNER = REPO_ROOT / "orchestrator" / "subagent_runner.py"
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
    context_records: list[dict],
) -> None:
    share_root.mkdir(parents=True, exist_ok=True)
    (share_root / "kimi.json").write_text(
        json.dumps(
            {
                "work_dirs": [
                    {
                        "path": str(workdir.resolve()),
                        "last_session_id": session_id,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_jsonl(
        _kimi_session_dir(share_root, workdir, session_id) / "context.jsonl",
        context_records,
    )


def _write_fake_kimi_binary(bin_dir: Path) -> Path:
    kimi_path = bin_dir / "kimi"
    kimi_path.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import sys

            if "--help" in sys.argv:
                sys.stdout.write(
                    "Usage: kimi\\n"
                    "--print\\n"
                    "--session\\n"
                    "--continue\\n"
                    "--work-dir\\n"
                    "Only print the final assistant message\\n"
                )
                raise SystemExit(0)

            raise SystemExit(0)
            """
        ),
        encoding="utf-8",
    )
    kimi_path.chmod(0o755)
    return kimi_path


def _write_fake_codex_binary(bin_dir: Path) -> Path:
    codex_path = bin_dir / "codex"
    codex_path.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import sys

            if sys.argv[1:] == ["exec", "--help"]:
                sys.stdout.write(
                    "Run Codex non-interactively\\n"
                    "--output-last-message\\n"
                    "resume\\n"
                )
                raise SystemExit(0)

            raise SystemExit(0)
            """
        ),
        encoding="utf-8",
    )
    codex_path.chmod(0o755)
    return codex_path


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
    def run_runner(
        self,
        *args: str,
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        return subprocess.run(
            [sys.executable, str(SUBAGENT_RUNNER), *args],
            text=True,
            capture_output=True,
            check=False,
            env=merged_env,
            cwd=cwd,
        )

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

    def run_phase(
        self,
        *args: str,
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        return subprocess.run(
            [sys.executable, str(RUN_PHASE), *args],
            text=True,
            capture_output=True,
            check=False,
            env=merged_env,
            cwd=cwd,
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

    def test_prepare_supports_kimi_direct_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            workdir = tmp_path / "repo"
            caller_cwd = tmp_path / "caller"
            workdir.mkdir()
            caller_cwd.mkdir()
            template_path = tmp_path / "template.md"
            share_root = tmp_path / "kimi-share"
            template_path.write_text(
                "<task_input_json>{USER_REQUEST_TRANSCRIPT}</task_input_json>\n",
                encoding="utf-8",
            )
            _write_kimi_share_root(
                share_root,
                workdir=workdir,
                session_id="session-direct",
                context_records=[
                    {"role": "_system_prompt", "content": "ignored"},
                    {"role": "user", "content": "hello from kimi phase"},
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "think", "think": "ignored"},
                            {"type": "text", "text": "visible kimi phase reply"},
                        ],
                    },
                    {"role": "user", "content": "next phase turn"},
                ],
            )

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
                "kimi-cli",
                "--transcript-search-root",
                str(share_root),
                "--require-nonempty-tag",
                "task_input_json",
                cwd=caller_cwd,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "prepared")
            prompt_path = Path(payload["prompt_path"])
            prompt_text = prompt_path.read_text(encoding="utf-8")
            self.assertIn("hello from kimi phase", prompt_text)
            self.assertIn("visible kimi phase reply", prompt_text)

    def test_prepare_resolves_relative_transcript_search_root_from_caller_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            workdir = tmp_path / "repo"
            caller_cwd = tmp_path / "caller"
            search_root = caller_cwd / "relative-sessions"
            workdir.mkdir()
            caller_cwd.mkdir()
            template_path = tmp_path / "template.md"
            template_path.write_text(
                "<task_input_json>{USER_REQUEST_TRANSCRIPT}</task_input_json>\n",
                encoding="utf-8",
            )
            write_codex_transcript(search_root, thread_id="thread-relative")

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
                "relative-sessions",
                "--require-nonempty-tag",
                "task_input_json",
                env={"CODEX_THREAD_ID": "thread-relative"},
                cwd=caller_cwd,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            prompt_path = Path(payload["prompt_path"])
            self.assertIn("ship it", prompt_path.read_text(encoding="utf-8"))

    def test_run_dispatches_with_subagent_runner_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            workdir = tmp_path / "repo"
            bin_dir = tmp_path / "bin"
            workdir.mkdir()
            bin_dir.mkdir()
            template_path = tmp_path / "template.md"
            template_path.write_text("Work in {WORKTREE_PATH}\n", encoding="utf-8")
            _write_fake_codex_binary(bin_dir)

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
                env={"PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"},
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["dispatch"]["status"], "ok")
            self.assertTrue(Path(payload["prompt_path"]).exists())
            self.assertTrue(Path(payload["dispatch"]["result_path"]).exists())

    def test_run_dispatches_with_codex_profile_forwarded_to_subagent_runner(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            workdir = tmp_path / "repo"
            bin_dir = tmp_path / "bin"
            workdir.mkdir()
            bin_dir.mkdir()
            template_path = tmp_path / "template.md"
            template_path.write_text("Work in {WORKTREE_PATH}\n", encoding="utf-8")
            _write_fake_codex_binary(bin_dir)

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
                "--profile",
                "trycycle-max",
                "--dry-run",
                env={"PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"},
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["dispatch"]["selection"]["profile"], "trycycle-max")
            self.assertIn("--profile", payload["dispatch"]["process"]["command"])
            self.assertIn("trycycle-max", payload["dispatch"]["process"]["command"])
            
    def test_run_dispatches_with_host_backend_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            workdir = tmp_path / "repo"
            bin_dir = tmp_path / "bin"
            workdir.mkdir()
            bin_dir.mkdir()
            template_path = tmp_path / "template.md"
            template_path.write_text("Work in {WORKTREE_PATH}\n", encoding="utf-8")
            fake_codex = _write_fake_codex_binary(bin_dir)

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
                "host",
                "--dry-run",
                env={
                    "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
                    "CODEX_THREAD_ID": "thread-123",
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["dispatch"]["backend"], "codex")
            self.assertEqual(payload["dispatch"]["process"]["command"][0], str(fake_codex))

    def test_run_dispatches_with_kimi_backend_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            workdir = tmp_path / "repo"
            bin_dir = tmp_path / "bin"
            workdir.mkdir()
            bin_dir.mkdir()
            template_path = tmp_path / "template.md"
            template_path.write_text("Work in {WORKTREE_PATH}\n", encoding="utf-8")
            fake_kimi = _write_fake_kimi_binary(bin_dir)

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
                "kimi",
                "--dry-run",
                env={"PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"},
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["dispatch"]["status"], "ok")
            self.assertEqual(payload["dispatch"]["backend"], "kimi")
            self.assertEqual(payload["dispatch"]["process"]["command"][0], str(fake_kimi))

    @unittest.skipUnless(
        os.environ.get("TRYCYCLE_RUN_LIVE_KIMI_TESTS") == "1",
        "set TRYCYCLE_RUN_LIVE_KIMI_TESTS=1 to run live Kimi acceptance coverage",
    )
    def test_live_kimi_prepare_and_builder_agree_on_latest_visible_reply(self) -> None:
        if shutil.which("kimi") is None:
            self.skipTest("kimi binary not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            workdir = tmp_path / "work"
            caller_cwd = tmp_path / "caller"
            run_dir = tmp_path / "run"
            prompt_path = tmp_path / "prompt.txt"
            transcript_output = tmp_path / "transcript.json"
            template_path = tmp_path / "template.md"
            workdir.mkdir()
            caller_cwd.mkdir()
            prompt_path.write_text("Reply exactly with TRYCYCLE-LIVE-KIMI-PREPARE\n", encoding="utf-8")
            template_path.write_text(
                "<task_input_json>{USER_REQUEST_TRANSCRIPT}</task_input_json>\n",
                encoding="utf-8",
            )

            run_result = self.run_runner(
                "run",
                "--phase",
                "smoke",
                "--prompt-file",
                str(prompt_path),
                "--workdir",
                str(workdir),
                "--artifacts-dir",
                str(run_dir),
                "--backend",
                "kimi",
                "--timeout-seconds",
                "180",
            )
            self.assertEqual(run_result.returncode, 0, run_result.stderr)
            run_payload = json.loads(run_result.stdout)
            self.assertEqual(run_payload["status"], "ok")

            prepare_result = self.run_phase(
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
                "kimi-cli",
                "--require-nonempty-tag",
                "task_input_json",
                cwd=caller_cwd,
            )
            self.assertEqual(prepare_result.returncode, 0, prepare_result.stderr)
            prepare_payload = json.loads(prepare_result.stdout)

            build_result = self.run_builder(
                "--cli",
                "kimi-cli",
                "--output",
                str(transcript_output),
                cwd=workdir,
            )
            self.assertEqual(build_result.returncode, 0, build_result.stderr)
            transcript = json.loads(transcript_output.read_text(encoding="utf-8"))
            latest_assistant = next(
                turn["text"] for turn in reversed(transcript) if turn["role"] == "assistant"
            )
            normalized_reply = (
                Path(run_payload["reply_path"])
                .read_text(encoding="utf-8")
                .replace("\r\n", "\n")
                .replace("\r", "\n")
                .rstrip("\n")
            )

            self.assertEqual(latest_assistant, normalized_reply)
            self.assertIn(
                latest_assistant,
                Path(prepare_payload["prompt_path"]).read_text(encoding="utf-8"),
            )

    def test_probe_transcript_build_and_kimi_dry_run_complete_within_local_latency_bound(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            workdir = tmp_path / "repo"
            home_dir = tmp_path / "home"
            bin_dir = tmp_path / "bin"
            share_root = tmp_path / "kimi-share"
            output_path = tmp_path / "transcript.json"
            template_path = tmp_path / "template.md"
            workdir.mkdir()
            home_dir.mkdir()
            bin_dir.mkdir()
            template_path.write_text("Work in {WORKTREE_PATH}\n", encoding="utf-8")
            _write_fake_kimi_binary(bin_dir)
            _write_kimi_share_root(
                share_root,
                workdir=workdir,
                session_id="session-direct",
                context_records=[
                    {"role": "user", "content": "hello from kimi phase"},
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "visible kimi phase reply"},
                        ],
                    },
                ],
            )
            env = {
                "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
                "HOME": str(home_dir),
                "KIMI_SHARE_DIR": str(share_root),
            }

            probe_started_at = time.monotonic()
            probe_result = self.run_runner("probe", env=env)
            probe_duration = time.monotonic() - probe_started_at

            build_started_at = time.monotonic()
            build_result = self.run_builder(
                "--cli",
                "kimi-cli",
                "--search-root",
                str(share_root),
                "--output",
                str(output_path),
                cwd=workdir,
            )
            build_duration = time.monotonic() - build_started_at

            dry_run_started_at = time.monotonic()
            dry_run_result = self.run_phase(
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
                "kimi",
                "--dry-run",
                env=env,
            )
            dry_run_duration = time.monotonic() - dry_run_started_at

            self.assertEqual(probe_result.returncode, 0, probe_result.stderr)
            self.assertEqual(build_result.returncode, 0, build_result.stderr)
            self.assertEqual(dry_run_result.returncode, 0, dry_run_result.stderr)
            self.assertLess(probe_duration, 5)
            self.assertLess(build_duration, 5)
            self.assertLess(dry_run_duration, 5)

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

    def test_prepare_auto_detects_opencode_transcript_cli_when_opencode_env_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            workdir = tmp_path / "repo"
            workdir.mkdir()
            template_path = tmp_path / "template.md"
            search_root = tmp_path / "opencode-data"
            search_root.mkdir()
            db_path = search_root / "opencode.db"
            canary = "trycycle-canary-opencode-autodetect"
            template_path.write_text(
                "<task_input_json>{USER_REQUEST_TRANSCRIPT}</task_input_json>\n",
                encoding="utf-8",
            )
            _write_opencode_db(
                db_path,
                session_id="ses_autodetect",
                canary=canary,
                assistant_reply="autodetected opencode reply",
            )

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
                "--canary",
                canary,
                "--transcript-search-root",
                str(search_root),
                "--require-nonempty-tag",
                "task_input_json",
                env={
                    "OPENCODE": "1",
                    "CLAUDECODE": "",
                    "CODEX_THREAD_ID": "",
                    "CODEX_HOME": "",
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "prepared")
            prompt_path = Path(payload["prompt_path"])
            prompt_text = prompt_path.read_text(encoding="utf-8")
            self.assertIn("autodetected opencode reply", prompt_text)


def _write_opencode_db(
    db_path: Path,
    *,
    session_id: str,
    canary: str,
    assistant_reply: str,
) -> None:
    """Create a minimal OpenCode SQLite DB with one session containing a canary user message."""
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
    conn.execute(
        "INSERT INTO session VALUES (?, ?, ?, ?, ?, ?, ?)",
        (session_id, "proj1", "/tmp", "test", "1.3.0", 1000, 2000),
    )
    conn.execute(
        "INSERT INTO message VALUES (?, ?, ?, ?, ?)",
        ("msg_001", session_id, 1001, 1001, json.dumps({"role": "user"})),
    )
    conn.execute(
        "INSERT INTO part VALUES (?, ?, ?, ?, ?, ?)",
        ("prt_001", "msg_001", session_id, 1001, 1001,
         json.dumps({"type": "text", "text": f"Request with {canary}"})),
    )
    conn.execute(
        "INSERT INTO message VALUES (?, ?, ?, ?, ?)",
        ("msg_002", session_id, 1002, 1002, json.dumps({"role": "assistant"})),
    )
    conn.execute(
        "INSERT INTO part VALUES (?, ?, ?, ?, ?, ?)",
        ("prt_002", "msg_002", session_id, 1002, 1002,
         json.dumps({"type": "text", "text": assistant_reply})),
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    unittest.main()
