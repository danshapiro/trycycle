from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class TrycycleExplorerCliTests(unittest.TestCase):
    def test_dump_model_succeeds_for_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "explorer-model.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "trycycle_explorer",
                    "dump-model",
                    "--repo",
                    str(REPO_ROOT),
                    "--output",
                    str(output_path),
                ],
                text=True,
                capture_output=True,
                check=False,
                cwd=REPO_ROOT,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            gate_ids = {gate["id"] for gate in payload["gates"]}
            sample_ids = {sample["id"] for sample in payload["sample_inputs"]}

            self.assertIn("prepare-implementation-workspace", gate_ids)
            self.assertIn("no-worktree-conductor", sample_ids)

    def test_planning_and_review_loop_prompts_are_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "explorer-model.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "trycycle_explorer",
                    "dump-model",
                    "--repo",
                    str(REPO_ROOT),
                    "--output",
                    str(output_path),
                ],
                text=True,
                capture_output=True,
                check=False,
                cwd=REPO_ROOT,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            gates = {gate["id"]: gate for gate in payload["gates"]}
            samples = {sample["id"]: sample for sample in payload["sample_inputs"]}

            planning_prompt_paths = {
                prompt["source_path"]
                for prompt in gates["planning-issue-review-and-synthesis-loop"][
                    "prompts"
                ]
            }
            self.assertIn(
                "subagents/prompt-planning-review.md", planning_prompt_paths
            )
            self.assertIn(
                "subagents/prompt-planning-review-deepen.md", planning_prompt_paths
            )
            self.assertIn(
                "subagents/prompt-planning-synthesis.md", planning_prompt_paths
            )
            self.assertNotIn(
                "subagents/prompt-planning-edit.md", planning_prompt_paths
            )

            review_prompt_paths = {
                prompt["source_path"]
                for prompt in gates["post-implementation-review-loop"]["prompts"]
            }
            self.assertIn(
                "subagents/prompt-post-impl-review-deepen.md", review_prompt_paths
            )
            self.assertIn(
                "subagents/prompt-planning-reconsider.md", review_prompt_paths
            )
            self.assertEqual(
                samples["planning-synthesis"]["selected_prompt_source_id"],
                "planning-issue-review-and-synthesis-loop::subagent-template::prompt-planning-synthesis",
            )
            self.assertEqual(
                samples["post-review-fix"]["selected_prompt_source_id"],
                "post-implementation-review-loop::subagent-template::prompt-executing",
            )

            planning_details = gates["planning-issue-review-and-synthesis-loop"][
                "detail_items"
            ]
            self.assertEqual(len(planning_details), 5)
            self.assertEqual(
                planning_details[1]["prompt_source_path"],
                "subagents/prompt-planning-review-deepen.md",
            )
            self.assertIn("5 ISSUES", planning_details[2]["body"])

            review_details = gates["post-implementation-review-loop"][
                "detail_items"
            ]
            self.assertEqual(len(review_details), 5)
            self.assertEqual(
                review_details[1]["prompt_source_path"],
                "subagents/prompt-post-impl-review-deepen.md",
            )
            self.assertIn("5th blocking deepening pass", review_details[2]["body"])


if __name__ == "__main__":
    unittest.main()
