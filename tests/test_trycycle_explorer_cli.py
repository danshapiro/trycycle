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


if __name__ == "__main__":
    unittest.main()
