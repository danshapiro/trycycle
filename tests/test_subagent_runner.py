from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SUBAGENT_RUNNER = REPO_ROOT / "orchestrator" / "subagent_runner.py"
ORCHESTRATOR_ROOT = REPO_ROOT / "orchestrator"


def _kimi_session_dir(share_root: Path, workdir: Path, session_id: str) -> Path:
    workdir_hash = hashlib.md5(str(workdir.resolve()).encode("utf-8")).hexdigest()
    return share_root / "sessions" / workdir_hash / session_id


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
            session_dir = share_root / "sessions" / workdir_hash / session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            context_path = session_dir / "context.jsonl"

            mode = os.environ.get("FAKE_KIMI_MODE", "success")
            reply_text = os.environ.get("FAKE_KIMI_REPLY", "fake kimi reply")

            records = []
            if mode != "stale":
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
                    prompt_text="normalize me\n",
                )
                self.assertEqual((status, message), ("ok", "Kimi helper ok"))

                mismatch_status, mismatch_message = subagent_runner._classify_run_result(
                    backend="kimi",
                    run_result={**base_run_result, "reply_text": "materially different"},
                    timeout_seconds=60,
                    success_message="Kimi helper ok",
                    workdir=workdir,
                    prompt_text="normalize me\n",
                )
                self.assertEqual(mismatch_status, "escalate_to_user")
                self.assertIn("materially different", mismatch_message)
            finally:
                if old_share_dir is None:
                    os.environ.pop("KIMI_SHARE_DIR", None)
                else:
                    os.environ["KIMI_SHARE_DIR"] = old_share_dir


if __name__ == "__main__":
    unittest.main()
