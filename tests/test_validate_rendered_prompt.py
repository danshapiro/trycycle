from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / "orchestrator" / "prompt_builder" / "validate_rendered.py"


class ValidateRenderedPromptTests(unittest.TestCase):
    def run_validator(self, prompt_text: str, *args: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text(prompt_text, encoding="utf-8")
            return subprocess.run(
                ["python3", str(VALIDATOR), "--prompt-file", str(prompt_path), *args],
                text=True,
                capture_output=True,
                check=False,
            )

    def test_accepts_prompt_without_placeholders(self) -> None:
        result = self.run_validator(
            "<task_input_json>{\"goal\": \"ship preview\"}</task_input_json>\n"
            "Work in /tmp/example\n",
            "--require-nonempty-tag",
            "task_input_json",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejects_unsubstituted_placeholders(self) -> None:
        result = self.run_validator("Work in {WORKTREE_PATH}\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("unsubstituted placeholders: WORKTREE_PATH", result.stderr)

    def test_rejects_missing_required_tag(self) -> None:
        result = self.run_validator("hello\n", "--require-nonempty-tag", "task_input_json")
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing required <task_input_json> block", result.stderr)

    def test_rejects_empty_required_tag(self) -> None:
        result = self.run_validator(
            "<task_input_json>   \n\t </task_input_json>\n",
            "--require-nonempty-tag",
            "task_input_json",
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("empty <task_input_json> block", result.stderr)

    def test_ignores_placeholder_like_text_inside_allowed_tag(self) -> None:
        result = self.run_validator(
            "<task_input_json>{\"text\": \"historical {WORKTREE_PATH}\"}</task_input_json>\n"
            "Work in /tmp/example\n",
            "--require-nonempty-tag",
            "task_input_json",
            "--ignore-tag-for-placeholders",
            "task_input_json",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_ignores_nested_same_name_tag_body_for_placeholders(self) -> None:
        result = self.run_validator(
            "<conversation>\n"
            "Earlier transcript text mentioned <conversation>nested</conversation> tags.\n"
            "It also included historical placeholders such as {IMPLEMENTATION_PLAN_PATH}, "
            "{WORKTREE_PATH}, and {TEST_PLAN_PATH}.\n"
            "</conversation>\n"
            "Work in /tmp/example\n",
            "--require-nonempty-tag",
            "conversation",
            "--ignore-tag-for-placeholders",
            "conversation",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_does_not_ignore_placeholders_between_ignored_tag_blocks(self) -> None:
        result = self.run_validator(
            "<conversation>historical {WORKTREE_PATH}</conversation>\n"
            "Current prompt still has {TEST_PLAN_PATH}\n"
            "<conversation>historical {IMPLEMENTATION_PLAN_PATH}</conversation>\n",
            "--ignore-tag-for-placeholders",
            "conversation",
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("unsubstituted placeholders: TEST_PLAN_PATH", result.stderr)


if __name__ == "__main__":
    unittest.main()
