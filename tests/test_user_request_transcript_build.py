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


if __name__ == "__main__":
    unittest.main()
