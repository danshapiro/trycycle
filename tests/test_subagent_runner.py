from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SUBAGENT_RUNNER = REPO_ROOT / "orchestrator" / "subagent_runner.py"
ORCHESTRATOR_ROOT = REPO_ROOT / "orchestrator"


def _kimi_session_dir(share_root: Path, workdir: Path, session_id: str) -> Path:
    workdir_hash = hashlib.md5(str(workdir.resolve()).encode("utf-8")).hexdigest()
    return share_root / "sessions" / workdir_hash / session_id


def _kimi_legacy_session_path(share_root: Path, workdir: Path, session_id: str) -> Path:
    workdir_hash = hashlib.md5(str(workdir.resolve()).encode("utf-8")).hexdigest()
    return share_root / "sessions" / workdir_hash / f"{session_id}.jsonl"


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )


def _write_fake_kimi_binary(bin_dir: Path) -> Path:
    kimi_path = bin_dir / "kimi"
    kimi_path.write_text(
        textwrap.dedent(
            f"""\
            #!{sys.executable}
            import hashlib
            import json
            import os
            from pathlib import Path
            import sys

            def read_flag_value(flag):
                if flag not in sys.argv:
                    return None
                index = sys.argv.index(flag)
                if index + 1 >= len(sys.argv):
                    return None
                return sys.argv[index + 1]

            def append_log():
                log_path = os.environ.get("FAKE_KIMI_LOG")
                if not log_path:
                    return
                with open(log_path, "a", encoding="utf-8") as handle:
                    handle.write(json.dumps({{"argv": sys.argv[1:]}}) + "\\n")

            append_log()

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

            share_root = Path(os.environ["KIMI_SHARE_DIR"])
            workdir = Path(read_flag_value("--work-dir"))
            session_id = read_flag_value("--session")
            prompt_text = sys.stdin.read()
            workdir_hash = hashlib.md5(str(workdir.resolve()).encode("utf-8")).hexdigest()
            sessions_root = share_root / "sessions" / workdir_hash
            legacy_layout = os.environ.get("FAKE_KIMI_LEGACY_LAYOUT", "0") == "1"
            if legacy_layout:
                sessions_root.mkdir(parents=True, exist_ok=True)
                context_path = sessions_root / f"{{session_id}}.jsonl"
            else:
                session_dir = sessions_root / session_id
                session_dir.mkdir(parents=True, exist_ok=True)
                context_path = session_dir / os.environ.get("FAKE_KIMI_CONTEXT_FILENAME", "context.jsonl")
            context_path.parent.mkdir(parents=True, exist_ok=True)

            mode = os.environ.get("FAKE_KIMI_MODE", "success")
            reply_text = os.environ.get("FAKE_KIMI_REPLY", "fake kimi reply")
            include_user = os.environ.get("FAKE_KIMI_INCLUDE_USER", "1") == "1"

            records = []
            if mode != "stale" and include_user:
                records.append({{"role": "user", "content": prompt_text.rstrip("\\n")}})
            if mode not in {{"failure", "stale"}}:
                records.append(
                    {{
                        "role": "assistant",
                        "content": [
                            {{"type": "text", "text": reply_text}},
                        ],
                    }}
                )

            with context_path.open("a", encoding="utf-8") as handle:
                for record in records:
                    handle.write(json.dumps(record) + "\\n")

            if mode == "failure":
                sys.stdout.write("LLM not set")
                raise SystemExit(0)

            sys.stdout.write(reply_text)
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
            f"""\
            #!{sys.executable}
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


def _write_fake_claude_binary(bin_dir: Path) -> Path:
    claude_path = bin_dir / "claude"
    claude_path.write_text(
        textwrap.dedent(
            f"""\
            #!{sys.executable}
            import sys

            if "--help" in sys.argv:
                sys.stdout.write(
                    "-p, --print\\n"
                    "--output-format\\n"
                    "--resume\\n"
                    "--session-id\\n"
                )
                raise SystemExit(0)

            raise SystemExit(0)
            """
        ),
        encoding="utf-8",
    )
    claude_path.chmod(0o755)
    return claude_path


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class SubagentRunnerTests(unittest.TestCase):
    def run_runner(
        self,
        *args: str,
        env: dict[str, str] | None = None,
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
        )

    def test_probe_selects_kimi_when_it_is_the_only_available_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            bin_dir = tmp_path / "bin"
            home_dir = tmp_path / "home"
            share_root = tmp_path / "share"
            log_path = tmp_path / "kimi-log.jsonl"
            bin_dir.mkdir()
            home_dir.mkdir()
            share_root.mkdir()
            _write_fake_kimi_binary(bin_dir)

            result = self.run_runner(
                "probe",
                env={
                    "PATH": str(bin_dir),
                    "HOME": str(home_dir),
                    "KIMI_SHARE_DIR": str(share_root),
                    "FAKE_KIMI_LOG": str(log_path),
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["selected_backend"], "kimi")
            self.assertEqual(payload["backend_order"], ["codex", "claude", "kimi"])
            self.assertTrue(payload["backends"]["kimi"]["available"])
            self.assertTrue(payload["backends"]["kimi"]["supports_resume"])

    def test_run_with_kimi_backend_returns_ok_when_context_matches_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            bin_dir = tmp_path / "bin"
            home_dir = tmp_path / "home"
            share_root = tmp_path / "share"
            workdir = tmp_path / "work"
            artifacts_dir = tmp_path / "artifacts"
            prompt_path = tmp_path / "prompt.txt"
            log_path = tmp_path / "kimi-log.jsonl"
            bin_dir.mkdir()
            home_dir.mkdir()
            share_root.mkdir()
            workdir.mkdir()
            prompt_path.write_text("Reply exactly with test success\n", encoding="utf-8")
            _write_fake_kimi_binary(bin_dir)

            result = self.run_runner(
                "run",
                "--phase",
                "smoke",
                "--prompt-file",
                str(prompt_path),
                "--workdir",
                str(workdir),
                "--artifacts-dir",
                str(artifacts_dir),
                "--backend",
                "kimi",
                "--effort",
                "max",
                "--model",
                "kimi-test-model",
                env={
                    "PATH": str(bin_dir),
                    "HOME": str(home_dir),
                    "KIMI_SHARE_DIR": str(share_root),
                    "FAKE_KIMI_LOG": str(log_path),
                    "FAKE_KIMI_MODE": "success",
                    "FAKE_KIMI_REPLY": "visible persisted reply",
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["backend"], "kimi")
            self.assertTrue(payload["session_id"])
            reply_path = Path(payload["reply_path"])
            stdout_path = Path(payload["stdout_path"])
            self.assertEqual(reply_path.read_text(encoding="utf-8"), "visible persisted reply")
            self.assertEqual(stdout_path.read_text(encoding="utf-8"), "visible persisted reply")
            log_records = _read_jsonl(log_path)
            argv = log_records[-1]["argv"]
            self.assertIn("--print", argv)
            self.assertIn("--final-message-only", argv)
            self.assertIn("--work-dir", argv)
            self.assertIn(str(workdir), argv)
            self.assertIn("--session", argv)
            self.assertIn("--thinking", argv)
            self.assertIn("--model", argv)
            self.assertIn("kimi-test-model", argv)

    def test_run_with_kimi_backend_accepts_new_persisted_reply_without_prompt_echo(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            bin_dir = tmp_path / "bin"
            home_dir = tmp_path / "home"
            share_root = tmp_path / "share"
            workdir = tmp_path / "work"
            artifacts_dir = tmp_path / "artifacts"
            prompt_path = tmp_path / "prompt.txt"
            log_path = tmp_path / "kimi-log.jsonl"
            bin_dir.mkdir()
            home_dir.mkdir()
            share_root.mkdir()
            workdir.mkdir()
            prompt_path.write_text("Reply exactly with delta-only success\n", encoding="utf-8")
            _write_fake_kimi_binary(bin_dir)

            result = self.run_runner(
                "run",
                "--phase",
                "smoke",
                "--prompt-file",
                str(prompt_path),
                "--workdir",
                str(workdir),
                "--artifacts-dir",
                str(artifacts_dir),
                "--backend",
                "kimi",
                env={
                    "PATH": str(bin_dir),
                    "HOME": str(home_dir),
                    "KIMI_SHARE_DIR": str(share_root),
                    "FAKE_KIMI_LOG": str(log_path),
                    "FAKE_KIMI_MODE": "success",
                    "FAKE_KIMI_REPLY": "delta-only success",
                    "FAKE_KIMI_INCLUDE_USER": "0",
                    "FAKE_KIMI_CONTEXT_FILENAME": "context_1.jsonl",
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["backend"], "kimi")

    def test_run_with_kimi_backend_supports_legacy_flat_session_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            bin_dir = tmp_path / "bin"
            home_dir = tmp_path / "home"
            share_root = tmp_path / "share"
            workdir = tmp_path / "work"
            artifacts_dir = tmp_path / "artifacts"
            prompt_path = tmp_path / "prompt.txt"
            log_path = tmp_path / "kimi-log.jsonl"
            bin_dir.mkdir()
            home_dir.mkdir()
            share_root.mkdir()
            workdir.mkdir()
            prompt_path.write_text("Reply exactly with legacy flat success\n", encoding="utf-8")
            _write_fake_kimi_binary(bin_dir)

            result = self.run_runner(
                "run",
                "--phase",
                "smoke",
                "--prompt-file",
                str(prompt_path),
                "--workdir",
                str(workdir),
                "--artifacts-dir",
                str(artifacts_dir),
                "--backend",
                "kimi",
                env={
                    "PATH": str(bin_dir),
                    "HOME": str(home_dir),
                    "KIMI_SHARE_DIR": str(share_root),
                    "FAKE_KIMI_LOG": str(log_path),
                    "FAKE_KIMI_MODE": "success",
                    "FAKE_KIMI_REPLY": "legacy flat success",
                    "FAKE_KIMI_LEGACY_LAYOUT": "1",
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["backend"], "kimi")
            self.assertEqual(
                _read_jsonl(_kimi_legacy_session_path(share_root, workdir, payload["session_id"]))[-1]["content"][0]["text"],
                "legacy flat success",
            )

    def test_resume_with_kimi_backend_uses_explicit_session_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            bin_dir = tmp_path / "bin"
            home_dir = tmp_path / "home"
            share_root = tmp_path / "share"
            workdir = tmp_path / "work"
            artifacts_dir = tmp_path / "artifacts"
            prompt_path = tmp_path / "prompt.txt"
            log_path = tmp_path / "kimi-log.jsonl"
            session_id = "kimi-resume-session"
            bin_dir.mkdir()
            home_dir.mkdir()
            share_root.mkdir()
            workdir.mkdir()
            prompt_path.write_text("resume prompt\n", encoding="utf-8")
            _write_fake_kimi_binary(bin_dir)

            result = self.run_runner(
                "resume",
                "--phase",
                "smoke",
                "--session-id",
                session_id,
                "--prompt-file",
                str(prompt_path),
                "--workdir",
                str(workdir),
                "--artifacts-dir",
                str(artifacts_dir),
                "--backend",
                "kimi",
                env={
                    "PATH": str(bin_dir),
                    "HOME": str(home_dir),
                    "KIMI_SHARE_DIR": str(share_root),
                    "FAKE_KIMI_LOG": str(log_path),
                    "FAKE_KIMI_MODE": "success",
                    "FAKE_KIMI_REPLY": "resume visible reply",
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["session_id"], session_id)
            argv = _read_jsonl(log_path)[-1]["argv"]
            self.assertIn("--session", argv)
            self.assertIn(session_id, argv)
            self.assertNotIn("--continue", argv)

    def test_resume_with_kimi_backend_escalates_when_persisted_reply_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            bin_dir = tmp_path / "bin"
            home_dir = tmp_path / "home"
            share_root = tmp_path / "share"
            workdir = tmp_path / "work"
            artifacts_dir = tmp_path / "artifacts"
            prompt_path = tmp_path / "prompt.txt"
            log_path = tmp_path / "kimi-log.jsonl"
            session_id = "kimi-stale-session"
            bin_dir.mkdir()
            home_dir.mkdir()
            share_root.mkdir()
            workdir.mkdir()
            prompt_path.write_text("resume prompt\n", encoding="utf-8")
            _write_fake_kimi_binary(bin_dir)
            _write_jsonl(
                _kimi_session_dir(share_root, workdir, session_id) / "context.jsonl",
                [
                    {"role": "user", "content": "old prompt"},
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "stale persisted reply"},
                        ],
                    },
                ],
            )

            result = self.run_runner(
                "resume",
                "--phase",
                "smoke",
                "--session-id",
                session_id,
                "--prompt-file",
                str(prompt_path),
                "--workdir",
                str(workdir),
                "--artifacts-dir",
                str(artifacts_dir),
                "--backend",
                "kimi",
                env={
                    "PATH": str(bin_dir),
                    "HOME": str(home_dir),
                    "KIMI_SHARE_DIR": str(share_root),
                    "FAKE_KIMI_LOG": str(log_path),
                    "FAKE_KIMI_MODE": "stale",
                    "FAKE_KIMI_REPLY": "stale persisted reply",
                },
            )

            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "escalate_to_user")
            self.assertIn("stale persisted reply", payload["message"])

    def test_run_with_kimi_backend_escalates_when_stdout_is_not_backed_by_visible_assistant_output(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            bin_dir = tmp_path / "bin"
            home_dir = tmp_path / "home"
            share_root = tmp_path / "share"
            workdir = tmp_path / "work"
            artifacts_dir = tmp_path / "artifacts"
            prompt_path = tmp_path / "prompt.txt"
            log_path = tmp_path / "kimi-log.jsonl"
            bin_dir.mkdir()
            home_dir.mkdir()
            share_root.mkdir()
            workdir.mkdir()
            prompt_path.write_text("This should fail\n", encoding="utf-8")
            _write_fake_kimi_binary(bin_dir)

            result = self.run_runner(
                "run",
                "--phase",
                "smoke",
                "--prompt-file",
                str(prompt_path),
                "--workdir",
                str(workdir),
                "--artifacts-dir",
                str(artifacts_dir),
                "--backend",
                "kimi",
                env={
                    "PATH": str(bin_dir),
                    "HOME": str(home_dir),
                    "KIMI_SHARE_DIR": str(share_root),
                    "FAKE_KIMI_LOG": str(log_path),
                    "FAKE_KIMI_MODE": "failure",
                },
            )

            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "escalate_to_user")
            self.assertIn("LLM not set", payload["message"])
            self.assertEqual(Path(payload["stdout_path"]).read_text(encoding="utf-8"), "LLM not set")
            self.assertEqual(Path(payload["reply_path"]).read_text(encoding="utf-8"), "LLM not set")

    def test_classify_run_result_normalizes_kimi_reply_text_and_rejects_material_mismatches(
        self,
    ) -> None:
        sys.path.insert(0, str(ORCHESTRATOR_ROOT))
        try:
            import subagent_runner  # type: ignore
        finally:
            sys.path.pop(0)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            share_root = tmp_path / "share"
            workdir = tmp_path / "work"
            session_id = "kimi-direct-helper"
            share_root.mkdir()
            workdir.mkdir()
            context_path = _kimi_session_dir(share_root, workdir, session_id) / "context.jsonl"
            _write_jsonl(
                context_path,
                [
                    {"role": "user", "content": "normalize me"},
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "normalized reply"},
                        ],
                    },
                ],
            )

            base_run_result = {
                "command": ["kimi"],
                "exit_code": 0,
                "reply_text": "normalized reply\r\n",
                "timed_out": False,
                "dry_run": False,
                "session_id": session_id,
                "kimi_baseline_line_counts": {},
            }

            old_share_dir = os.environ.get("KIMI_SHARE_DIR")
            os.environ["KIMI_SHARE_DIR"] = str(share_root)
            try:
                status, message = subagent_runner._classify_run_result(
                    backend="kimi",
                    run_result=base_run_result,
                    timeout_seconds=60,
                    success_message="Kimi helper ok",
                    workdir=workdir,
                )
                self.assertEqual((status, message), ("ok", "Kimi helper ok"))

                mismatch_status, mismatch_message = subagent_runner._classify_run_result(
                    backend="kimi",
                    run_result={**base_run_result, "reply_text": "materially different"},
                    timeout_seconds=60,
                    success_message="Kimi helper ok",
                    workdir=workdir,
                )
                self.assertEqual(mismatch_status, "escalate_to_user")
                self.assertIn("materially different", mismatch_message)
            finally:
                if old_share_dir is None:
                    os.environ.pop("KIMI_SHARE_DIR", None)
                else:
                    os.environ["KIMI_SHARE_DIR"] = old_share_dir

    def test_classify_run_result_rejects_debug_jsonl_match_when_session_context_is_stale(
        self,
    ) -> None:
        sys.path.insert(0, str(ORCHESTRATOR_ROOT))
        try:
            import subagent_runner  # type: ignore
        finally:
            sys.path.pop(0)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            share_root = tmp_path / "share"
            workdir = tmp_path / "work"
            session_id = "kimi-stale-context"
            share_root.mkdir()
            workdir.mkdir()
            session_dir = _kimi_session_dir(share_root, workdir, session_id)
            context_path = session_dir / "context.jsonl"
            debug_path = session_dir / "debug.jsonl"
            _write_jsonl(
                context_path,
                [
                    {"role": "user", "content": "old prompt"},
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "stale persisted reply"},
                        ],
                    },
                ],
            )
            _write_jsonl(
                debug_path,
                [
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "debug-only reply"},
                        ],
                    },
                ],
            )

            old_share_dir = os.environ.get("KIMI_SHARE_DIR")
            os.environ["KIMI_SHARE_DIR"] = str(share_root)
            try:
                status, message = subagent_runner._classify_run_result(
                    backend="kimi",
                    run_result={
                        "command": ["kimi"],
                        "exit_code": 0,
                        "reply_text": "debug-only reply\n",
                        "timed_out": False,
                        "dry_run": False,
                        "session_id": session_id,
                        "kimi_baseline_line_counts": {
                            str(context_path.resolve()): len(
                                context_path.read_text(encoding="utf-8").splitlines()
                            )
                        },
                    },
                    timeout_seconds=60,
                    success_message="Kimi helper ok",
                    workdir=workdir,
                )
                self.assertEqual(status, "escalate_to_user")
                self.assertIn("debug-only reply", message)
            finally:
                if old_share_dir is None:
                    os.environ.pop("KIMI_SHARE_DIR", None)
                else:
                    os.environ["KIMI_SHARE_DIR"] = old_share_dir

    def test_classify_run_result_requires_final_visible_kimi_reply_to_match_stdout(
        self,
    ) -> None:
        sys.path.insert(0, str(ORCHESTRATOR_ROOT))
        try:
            import subagent_runner  # type: ignore
        finally:
            sys.path.pop(0)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            share_root = tmp_path / "share"
            workdir = tmp_path / "work"
            session_id = "kimi-final-turn"
            share_root.mkdir()
            workdir.mkdir()
            context_path = _kimi_session_dir(share_root, workdir, session_id) / "context.jsonl"
            _write_jsonl(
                context_path,
                [
                    {"role": "user", "content": "prompt"},
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "printed reply"},
                        ],
                    },
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "later different reply"},
                        ],
                    },
                ],
            )

            old_share_dir = os.environ.get("KIMI_SHARE_DIR")
            os.environ["KIMI_SHARE_DIR"] = str(share_root)
            try:
                started_at = time.monotonic()
                status, message = subagent_runner._classify_run_result(
                    backend="kimi",
                    run_result={
                        "command": ["kimi"],
                        "exit_code": 0,
                        "reply_text": "printed reply\n",
                        "timed_out": False,
                        "dry_run": False,
                        "session_id": session_id,
                        "kimi_baseline_line_counts": {},
                    },
                    timeout_seconds=60,
                    success_message="Kimi helper ok",
                    workdir=workdir,
                )
                self.assertEqual(status, "escalate_to_user")
                self.assertIn("printed reply", message)
                self.assertLess(time.monotonic() - started_at, 5)
            finally:
                if old_share_dir is None:
                    os.environ.pop("KIMI_SHARE_DIR", None)
                else:
                    os.environ["KIMI_SHARE_DIR"] = old_share_dir

    def test_run_with_codex_backend_dry_run_returns_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            bin_dir = tmp_path / "bin"
            home_dir = tmp_path / "home"
            prompt_path = tmp_path / "prompt.txt"
            artifacts_dir = tmp_path / "artifacts"
            bin_dir.mkdir()
            home_dir.mkdir()
            prompt_path.write_text("Codex dry run\n", encoding="utf-8")
            fake_codex = _write_fake_codex_binary(bin_dir)

            result = self.run_runner(
                "run",
                "--phase",
                "smoke",
                "--prompt-file",
                str(prompt_path),
                "--workdir",
                str(tmp_path),
                "--artifacts-dir",
                str(artifacts_dir),
                "--backend",
                "codex",
                "--dry-run",
                env={
                    "PATH": str(bin_dir),
                    "HOME": str(home_dir),
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["backend"], "codex")
            self.assertEqual(payload["process"]["command"][0], str(fake_codex))

    def test_run_with_codex_backend_uses_profile_override_from_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            bin_dir = tmp_path / "bin"
            home_dir = tmp_path / "home"
            prompt_path = tmp_path / "prompt.txt"
            artifacts_dir = tmp_path / "artifacts"
            bin_dir.mkdir()
            home_dir.mkdir()
            prompt_path.write_text("Codex dry run\n", encoding="utf-8")
            _write_fake_codex_binary(bin_dir)

            result = self.run_runner(
                "run",
                "--phase",
                "smoke",
                "--prompt-file",
                str(prompt_path),
                "--workdir",
                str(tmp_path),
                "--artifacts-dir",
                str(artifacts_dir),
                "--backend",
                "codex",
                "--dry-run",
                env={
                    "PATH": str(bin_dir),
                    "HOME": str(home_dir),
                    "TRYCYCLE_CODEX_PROFILE": "trycycle-max",
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["selection"]["profile"], "trycycle-max")
            self.assertEqual(
                payload["selection"]["profile_source"],
                "env:TRYCYCLE_CODEX_PROFILE",
            )
            self.assertIn("--profile", payload["process"]["command"])
            self.assertIn("trycycle-max", payload["process"]["command"])

    def test_run_with_codex_backend_prefers_explicit_profile_over_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            bin_dir = tmp_path / "bin"
            home_dir = tmp_path / "home"
            prompt_path = tmp_path / "prompt.txt"
            artifacts_dir = tmp_path / "artifacts"
            bin_dir.mkdir()
            home_dir.mkdir()
            prompt_path.write_text("Codex dry run\n", encoding="utf-8")
            _write_fake_codex_binary(bin_dir)

            result = self.run_runner(
                "run",
                "--phase",
                "smoke",
                "--prompt-file",
                str(prompt_path),
                "--workdir",
                str(tmp_path),
                "--artifacts-dir",
                str(artifacts_dir),
                "--backend",
                "codex",
                "--profile",
                "cli-profile",
                "--dry-run",
                env={
                    "PATH": str(bin_dir),
                    "HOME": str(home_dir),
                    "TRYCYCLE_CODEX_PROFILE": "env-profile",
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["selection"]["profile"], "cli-profile")
            self.assertEqual(payload["selection"]["profile_source"], "argument")
            self.assertIn("--profile", payload["process"]["command"])
            self.assertIn("cli-profile", payload["process"]["command"])
            self.assertNotIn("env-profile", payload["process"]["command"])

    def test_run_with_kimi_backend_uses_model_override_from_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            bin_dir = tmp_path / "bin"
            home_dir = tmp_path / "home"
            share_root = tmp_path / "share"
            prompt_path = tmp_path / "prompt.txt"
            artifacts_dir = tmp_path / "artifacts"
            bin_dir.mkdir()
            home_dir.mkdir()
            share_root.mkdir()
            prompt_path.write_text("Kimi dry run\n", encoding="utf-8")
            _write_fake_kimi_binary(bin_dir)

            result = self.run_runner(
                "run",
                "--phase",
                "smoke",
                "--prompt-file",
                str(prompt_path),
                "--workdir",
                str(tmp_path),
                "--artifacts-dir",
                str(artifacts_dir),
                "--backend",
                "kimi",
                "--dry-run",
                env={
                    "PATH": str(bin_dir),
                    "HOME": str(home_dir),
                    "KIMI_SHARE_DIR": str(share_root),
                    "TRYCYCLE_KIMI_MODEL": "kimi-local-model",
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["selection"]["model"], "kimi-local-model")
            self.assertEqual(payload["selection"]["model_source"], "env:TRYCYCLE_KIMI_MODEL")
            self.assertIn("--model", payload["process"]["command"])
            self.assertIn("kimi-local-model", payload["process"]["command"])

    def test_run_with_kimi_backend_prefers_explicit_model_over_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            bin_dir = tmp_path / "bin"
            home_dir = tmp_path / "home"
            share_root = tmp_path / "share"
            prompt_path = tmp_path / "prompt.txt"
            artifacts_dir = tmp_path / "artifacts"
            bin_dir.mkdir()
            home_dir.mkdir()
            share_root.mkdir()
            prompt_path.write_text("Kimi dry run\n", encoding="utf-8")
            _write_fake_kimi_binary(bin_dir)

            result = self.run_runner(
                "run",
                "--phase",
                "smoke",
                "--prompt-file",
                str(prompt_path),
                "--workdir",
                str(tmp_path),
                "--artifacts-dir",
                str(artifacts_dir),
                "--backend",
                "kimi",
                "--model",
                "kimi-cli-arg-model",
                "--dry-run",
                env={
                    "PATH": str(bin_dir),
                    "HOME": str(home_dir),
                    "KIMI_SHARE_DIR": str(share_root),
                    "TRYCYCLE_KIMI_MODEL": "kimi-env-model",
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["selection"]["model"], "kimi-cli-arg-model")
            self.assertEqual(payload["selection"]["model_source"], "argument")
            self.assertIn("--model", payload["process"]["command"])
            self.assertIn("kimi-cli-arg-model", payload["process"]["command"])
            self.assertNotIn("kimi-env-model", payload["process"]["command"])

    def test_run_with_kimi_backend_rejects_codex_profile_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            bin_dir = tmp_path / "bin"
            home_dir = tmp_path / "home"
            prompt_path = tmp_path / "prompt.txt"
            artifacts_dir = tmp_path / "artifacts"
            bin_dir.mkdir()
            home_dir.mkdir()
            prompt_path.write_text("Kimi dry run\n", encoding="utf-8")
            _write_fake_kimi_binary(bin_dir)

            result = self.run_runner(
                "run",
                "--phase",
                "smoke",
                "--prompt-file",
                str(prompt_path),
                "--workdir",
                str(tmp_path),
                "--artifacts-dir",
                str(artifacts_dir),
                "--backend",
                "kimi",
                "--profile",
                "codex-only-profile",
                "--dry-run",
                env={
                    "PATH": str(bin_dir),
                    "HOME": str(home_dir),
                },
            )

            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "escalate_to_user")
            self.assertIn("supported only for the codex backend", payload["message"])

    def test_run_with_claude_backend_dry_run_returns_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            bin_dir = tmp_path / "bin"
            home_dir = tmp_path / "home"
            prompt_path = tmp_path / "prompt.txt"
            artifacts_dir = tmp_path / "artifacts"
            bin_dir.mkdir()
            home_dir.mkdir()
            prompt_path.write_text("Claude dry run\n", encoding="utf-8")
            fake_claude = _write_fake_claude_binary(bin_dir)

            result = self.run_runner(
                "run",
                "--phase",
                "smoke",
                "--prompt-file",
                str(prompt_path),
                "--workdir",
                str(tmp_path),
                "--artifacts-dir",
                str(artifacts_dir),
                "--backend",
                "claude",
                "--dry-run",
                env={
                    "PATH": str(bin_dir),
                    "HOME": str(home_dir),
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["backend"], "claude")
            self.assertEqual(payload["process"]["command"][0], str(fake_claude))

    @unittest.skipUnless(
        os.environ.get("TRYCYCLE_RUN_LIVE_KIMI_TESTS") == "1",
        "set TRYCYCLE_RUN_LIVE_KIMI_TESTS=1 to run live Kimi acceptance coverage",
    )
    def test_live_kimi_run_and_resume_preserve_session_identity(self) -> None:
        if shutil.which("kimi") is None:
            self.skipTest("kimi binary not available")

        sys.path.insert(0, str(ORCHESTRATOR_ROOT))
        try:
            import subagent_runner  # type: ignore
        finally:
            sys.path.pop(0)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            workdir = tmp_path / "work"
            workdir.mkdir()
            prompt1 = tmp_path / "prompt1.txt"
            prompt2 = tmp_path / "prompt2.txt"
            run1_dir = tmp_path / "run1"
            run2_dir = tmp_path / "run2"
            prompt1.write_text("Reply exactly with TRYCYCLE-LIVE-KIMI-1\n", encoding="utf-8")
            prompt2.write_text("Reply exactly with TRYCYCLE-LIVE-KIMI-2\n", encoding="utf-8")

            run1 = self.run_runner(
                "run",
                "--phase",
                "smoke",
                "--prompt-file",
                str(prompt1),
                "--workdir",
                str(workdir),
                "--artifacts-dir",
                str(run1_dir),
                "--backend",
                "kimi",
                "--timeout-seconds",
                "180",
            )
            self.assertEqual(run1.returncode, 0, run1.stderr)
            run1_payload = json.loads(run1.stdout)
            self.assertEqual(run1_payload["status"], "ok")

            run2 = self.run_runner(
                "resume",
                "--phase",
                "smoke",
                "--session-id",
                run1_payload["session_id"],
                "--prompt-file",
                str(prompt2),
                "--workdir",
                str(workdir),
                "--artifacts-dir",
                str(run2_dir),
                "--backend",
                "kimi",
                "--timeout-seconds",
                "180",
            )
            self.assertEqual(run2.returncode, 0, run2.stderr)
            run2_payload = json.loads(run2.stdout)
            self.assertEqual(run2_payload["status"], "ok")
            self.assertEqual(run2_payload["session_id"], run1_payload["session_id"])
            self.assertIn(
                "TRYCYCLE-LIVE-KIMI-2",
                Path(run2_payload["reply_path"]).read_text(encoding="utf-8"),
            )

            context_path = subagent_runner._find_kimi_context_path(
                workdir=workdir,
                session_id=run2_payload["session_id"],
            )
            self.assertIsNotNone(context_path)
            self.assertIn(
                "TRYCYCLE-LIVE-KIMI-2",
                Path(context_path).read_text(encoding="utf-8"),
            )

    @unittest.skipUnless(
        os.environ.get("TRYCYCLE_RUN_LIVE_KIMI_TESTS") == "1",
        "set TRYCYCLE_RUN_LIVE_KIMI_TESTS=1 to run live Kimi acceptance coverage",
    )
    def test_live_kimi_zero_exit_misconfiguration_escalates(self) -> None:
        if shutil.which("kimi") is None:
            self.skipTest("kimi binary not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            workdir = tmp_path / "work"
            share_root = tmp_path / "isolated-share"
            prompt_path = tmp_path / "prompt.txt"
            artifacts_dir = tmp_path / "run"
            workdir.mkdir()
            prompt_path.write_text("Reply exactly with TRYCYCLE-LIVE-KIMI-FAIL\n", encoding="utf-8")

            result = self.run_runner(
                "run",
                "--phase",
                "smoke",
                "--prompt-file",
                str(prompt_path),
                "--workdir",
                str(workdir),
                "--artifacts-dir",
                str(artifacts_dir),
                "--backend",
                "kimi",
                "--timeout-seconds",
                "60",
                env={"KIMI_SHARE_DIR": str(share_root)},
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "escalate_to_user")
            stdout_text = Path(payload["stdout_path"]).read_text(encoding="utf-8")
            self.assertTrue(stdout_text.strip())
            self.assertIn(stdout_text.strip().splitlines()[0], payload["message"])
            self.assertNotIn("kimi exited with code 0", payload["message"])


if __name__ == "__main__":
    unittest.main()
