from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT_BUILDER = REPO_ROOT / "orchestrator" / "prompt_builder" / "build.py"


class PromptBuilderBuildTests(unittest.TestCase):
    def test_writes_rendered_prompt_to_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / "template.md"
            output_path = Path(tmpdir) / "prompt.txt"
            template_path.write_text("Work in {WORKTREE_PATH}\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROMPT_BUILDER),
                    "--template",
                    str(template_path),
                    "--set",
                    "WORKTREE_PATH=/tmp/example",
                    "--output",
                    str(output_path),
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertEqual(output_path.read_text(encoding="utf-8"), "Work in /tmp/example\n")

    def test_respects_conditional_blocks_when_output_file_is_used(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / "template.md"
            output_path = Path(tmpdir) / "prompt.txt"
            template_path.write_text(
                "{{#if CONVERSATION}}<conversation>{CONVERSATION}</conversation>\n{{/if}}",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROMPT_BUILDER),
                    "--template",
                    str(template_path),
                    "--set",
                    "CONVERSATION=hello",
                    "--output",
                    str(output_path),
                    "--require-nonempty-tag",
                    "conversation",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                output_path.read_text(encoding="utf-8"),
                "<conversation>hello</conversation>\n",
            )


if __name__ == "__main__":
    unittest.main()
