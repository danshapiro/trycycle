from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "orchestrator"))

from review_observations import ExtractionError, normalize_payload  # noqa: E402


class ReviewObservationsTests(unittest.TestCase):
    def test_accepts_acceptance_artifact_gap_categories(self) -> None:
        payload = {
            "status": "issues_found",
            "summary": "artifact evidence is incomplete",
            "observations": [
                {
                    "id": "A1",
                    "severity": "critical",
                    "category": "artifact_gap",
                    "expected": "screenshot artifact demonstrates the requested page state",
                    "observed": "the implementation report did not list a screenshot",
                },
                {
                    "id": "A2",
                    "severity": "major",
                    "category": "acceptance_gap",
                    "expected": "artifact shows the requested generated output",
                    "observed": "the artifact shows the old output",
                },
            ],
        }

        normalized = normalize_payload(payload)

        self.assertEqual(normalized["issue_count"], 2)
        self.assertEqual(normalized["blocking_issue_count"], 2)

    def test_rejects_unknown_category(self) -> None:
        payload = {
            "status": "issues_found",
            "observations": [
                {
                    "id": "X1",
                    "severity": "major",
                    "category": "not_a_category",
                    "expected": "known category",
                    "observed": "unknown category",
                }
            ],
        }

        with self.assertRaises(ExtractionError):
            normalize_payload(payload)


if __name__ == "__main__":
    unittest.main()
