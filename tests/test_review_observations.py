from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_OBSERVATIONS = REPO_ROOT / "orchestrator" / "review_observations.py"


def _run_review_observations(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REVIEW_OBSERVATIONS), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def _reply(observations: list[dict], *, status: str = "issues_found") -> str:
    payload = {
        "status": status,
        "summary": "summary",
        "observations": observations,
    }
    return (
        "<review_observations_json>"
        + json.dumps(payload)
        + "</review_observations_json>\n"
    )


class ReviewObservationsTests(unittest.TestCase):
    def test_combine_renumbers_accumulated_observations_and_counts_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            reply1 = tmp_path / "reply1.txt"
            reply2 = tmp_path / "reply2.txt"
            obs1 = tmp_path / "obs1.json"
            obs2 = tmp_path / "obs2.json"
            combined = tmp_path / "combined.json"

            base_observation = {
                "id": "R1",
                "severity": "critical",
                "category": "correctness",
                "expected": "first expected",
                "observed": "first observed",
                "where": {"file": "src/a.py", "line": 10},
                "evidence": {"commands": ["pytest"], "notes": "first evidence"},
            }
            second_observation = {
                "id": "R1",
                "severity": "major",
                "category": "missing_test",
                "expected": "second expected",
                "observed": "second observed",
                "where": {"file": "tests/test_a.py", "line": 20},
                "evidence": {
                    "commands": ["pytest tests/test_a.py"],
                    "notes": "second evidence",
                },
            }
            reply1.write_text(_reply([base_observation]), encoding="utf-8")
            reply2.write_text(_reply([second_observation]), encoding="utf-8")

            self.assertEqual(
                _run_review_observations(
                    "extract", "--reply", str(reply1), "--output", str(obs1)
                ).returncode,
                0,
            )
            self.assertEqual(
                _run_review_observations(
                    "extract", "--reply", str(reply2), "--output", str(obs2)
                ).returncode,
                0,
            )

            result = _run_review_observations(
                "combine",
                "--output",
                str(combined),
                str(obs1),
                str(obs2),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(combined.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "issues_found")
            self.assertEqual(payload["issue_count"], 2)
            self.assertEqual(payload["blocking_issue_count"], 2)
            self.assertEqual([item["id"] for item in payload["observations"]], ["R1", "R2"])
            self.assertEqual(payload["observations"][0]["expected"], "first expected")
            self.assertEqual(payload["observations"][1]["expected"], "second expected")

            stdout_payload = json.loads(result.stdout)
            self.assertEqual(stdout_payload["status"], "ok")
            self.assertEqual(stdout_payload["observations_path"], str(combined.resolve()))
            self.assertTrue(stdout_payload["has_blocking_issues"])

    def test_combine_all_no_issue_artifacts_returns_no_issues(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            reply_path = tmp_path / "reply.txt"
            obs_path = tmp_path / "obs.json"
            combined = tmp_path / "combined.json"
            reply_path.write_text(_reply([], status="no_issues"), encoding="utf-8")

            extract = _run_review_observations(
                "extract", "--reply", str(reply_path), "--output", str(obs_path)
            )
            self.assertEqual(extract.returncode, 0, extract.stderr)

            result = _run_review_observations("combine", "--output", str(combined), str(obs_path))

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(combined.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "no_issues")
            self.assertEqual(payload["observations"], [])
            self.assertEqual(payload["issue_count"], 0)
            self.assertEqual(payload["blocking_issue_count"], 0)


if __name__ == "__main__":
    unittest.main()
