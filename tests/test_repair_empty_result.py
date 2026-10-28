from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "orchestrator"))

from repair_empty_result import (  # noqa: E402
    MAX_TOOL_OUTPUT_CHARS,
    MAX_TOOL_STEPS,
    RepairError,
    _find_step_boundaries,
    _is_relevant_text,
    _safe_text,
    format_parts,
    get_parts,
    resolve_db_path,
    skip_preamble,
)


class TestSafeText(unittest.TestCase):
    def test_missing_key_returns_empty(self):
        self.assertEqual(_safe_text({}), "")

    def test_none_value_returns_empty(self):
        self.assertEqual(_safe_text({"text": None}), "")

    def test_string_value_returns_string(self):
        self.assertEqual(_safe_text({"text": "hello"}), "hello")

    def test_non_string_value_coerces(self):
        self.assertEqual(_safe_text({"text": 42}), "42")


class TestIsRelevantText(unittest.TestCase):
    def test_empty_returns_false(self):
        self.assertFalse(_is_relevant_text(""))
        self.assertFalse(_is_relevant_text("   "))

    def test_content_returns_true(self):
        self.assertTrue(_is_relevant_text("Hello world"))

    def test_close_tag_prefix_returns_false(self):
        self.assertFalse(_is_relevant_text("</task_result>"))
        self.assertFalse(_is_relevant_text("</task>"))
        self.assertFalse(_is_relevant_text("</tool_result>"))
        self.assertFalse(_is_relevant_text("</tool_call>"))

    def test_open_tag_returns_true(self):
        self.assertTrue(_is_relevant_text("<task>start something"))


class TestSkipPreamble(unittest.TestCase):
    def test_no_step_start_returns_all(self):
        parts = [{"type": "text", "text": "hello"}]
        self.assertEqual(skip_preamble(parts), parts)

    def test_drops_before_first_step_start(self):
        parts = [
            {"type": "text", "text": "preamble"},
            {"type": "step-start"},
            {"type": "text", "text": "body"},
        ]
        result = skip_preamble(parts)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].get("type"), "step-start")

    def test_all_after_step_start_kept(self):
        parts = [
            {"type": "step-start"},
            {"type": "text", "text": "body"},
            {"type": "step-finish"},
        ]
        self.assertEqual(skip_preamble(parts), parts)


class TestFindStepBoundaries(unittest.TestCase):
    def test_empty_returns_empty(self):
        self.assertEqual(_find_step_boundaries([]), [])

    def test_single_step(self):
        parts = [
            {"type": "step-start"},
            {"type": "text", "text": "body"},
            {"type": "step-finish"},
        ]
        boundaries = _find_step_boundaries(parts)
        self.assertEqual(boundaries, [(0, 2)])

    def test_nested_steps(self):
        parts = [
            {"type": "step-start"},
            {"type": "step-start"},
            {"type": "text", "text": "inner"},
            {"type": "step-finish"},
            {"type": "text", "text": "outer"},
            {"type": "step-finish"},
        ]
        boundaries = _find_step_boundaries(parts)
        self.assertEqual(boundaries, [(0, 5), (1, 3)])  # sorted by start index


class TestFormatParts(unittest.TestCase):
    def test_empty_parts_returns_placeholder(self):
        self.assertIn("no extractable content", format_parts([]))

    def test_tool_extraction(self):
        parts = [
            {"type": "step-start"},
            {"type": "tool", "tool": "read", "state": {
                "input": {"filePath": "/foo"},
                "output": "file content here",
                "status": "completed",
            }},
            {"type": "step-finish"},
        ]
        output = format_parts(parts)
        self.assertIn("Tool: read", output)
        self.assertIn("filePath", output)
        self.assertIn("file content here", output)

    def test_tool_with_non_dict_state_skipped(self):
        parts = [
            {"type": "step-start"},
            {"type": "tool", "tool": "bad", "state": None},
            {"type": "step-finish"},
        ]
        output = format_parts(parts)
        self.assertNotIn("Tool: bad", output)

    def test_reasoning_extraction(self):
        parts = [
            {"type": "step-start"},
            {"type": "reasoning", "text": "I should do X"},
            {"type": "step-finish"},
        ]
        output = format_parts(parts)
        self.assertIn("Reasoning:", output)
        self.assertIn("I should do X", output)

    def test_reasoning_none_text_handled(self):
        parts = [
            {"type": "step-start"},
            {"type": "reasoning", "text": None},
            {"type": "step-finish"},
        ]
        output = format_parts(parts)
        self.assertNotIn("Reasoning:", output)

    def test_text_extraction(self):
        parts = [
            {"type": "step-start"},
            {"type": "text", "text": "Here is the result"},
            {"type": "step-finish"},
        ]
        output = format_parts(parts)
        self.assertIn("Text:", output)
        self.assertIn("Here is the result", output)

    def test_text_close_tag_filtered(self):
        parts = [
            {"type": "step-start"},
            {"type": "text", "text": "</task_result>"},
            {"type": "text", "text": "real content"},
            {"type": "step-finish"},
        ]
        output = format_parts(parts)
        self.assertNotIn("</task_result>", output)
        self.assertIn("real content", output)

    def test_tool_output_truncation(self):
        long_output = "x" * (MAX_TOOL_OUTPUT_CHARS + 100)
        parts = [
            {"type": "step-start"},
            {"type": "tool", "tool": "read", "state": {
                "input": {},
                "output": long_output,
                "status": "completed",
            }},
            {"type": "step-finish"},
        ]
        output = format_parts(parts)
        self.assertIn("(truncated)", output)
        self.assertNotIn(long_output, output)

    def test_tool_output_non_string_coerced(self):
        parts = [
            {"type": "step-start"},
            {"type": "tool", "tool": "read", "state": {
                "input": {},
                "output": {"key": "value"},
                "status": "completed",
            }},
            {"type": "step-finish"},
        ]
        output = format_parts(parts)
        self.assertIn("{'key': 'value'}", output)

    def test_only_tools_from_recent_steps(self):
        # Create 5 steps, each with a tool call. Only last MAX_TOOL_STEPS should appear.
        parts = []
        for step in range(5):
            parts.append({"type": "step-start"})
            parts.append({"type": "tool", "tool": f"step{step}", "state": {
                "input": {}, "output": f"result{step}", "status": "completed",
            }})
            parts.append({"type": "step-finish"})
        output = format_parts(parts)
        # Only the last MAX_TOOL_STEPS should be present
        for i in range(5):
            if i >= 5 - MAX_TOOL_STEPS:
                self.assertIn(f"step{i}", output, f"step{i} should be present")
            else:
                self.assertNotIn(f"step{i}", output, f"step{i} should NOT be present")


class TestGetParts(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="repair_test_"))
        self.db_path = self.tmpdir / "test.db"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _create_db(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS part (
                id TEXT PRIMARY KEY,
                message_id TEXT,
                session_id TEXT,
                time_created INTEGER,
                time_updated INTEGER,
                data TEXT
            )
        """)
        conn.commit()
        return conn

    def test_returns_parts_ordered(self):
        conn = self._create_db()
        conn.execute(
            "INSERT INTO part VALUES (?, ?, ?, ?, ?, ?)",
            ("p1", "m1", "ses_test", 1000, 1000, json.dumps({"type": "text", "text": "first"})),
        )
        conn.execute(
            "INSERT INTO part VALUES (?, ?, ?, ?, ?, ?)",
            ("p2", "m2", "ses_test", 2000, 2000, json.dumps({"type": "text", "text": "second"})),
        )
        conn.commit()
        conn.close()

        parts = get_parts(self.db_path, "ses_test")
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0]["text"], "first")
        self.assertEqual(parts[1]["text"], "second")

    def test_skips_malformed_json(self):
        conn = self._create_db()
        conn.execute(
            "INSERT INTO part VALUES (?, ?, ?, ?, ?, ?)",
            ("p1", "m1", "ses_test", 1000, 1000, "not valid json{{{"),
        )
        conn.execute(
            "INSERT INTO part VALUES (?, ?, ?, ?, ?, ?)",
            ("p2", "m2", "ses_test", 2000, 2000, json.dumps({"type": "text", "text": "valid"})),
        )
        conn.commit()
        conn.close()

        parts = get_parts(self.db_path, "ses_test")
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0]["text"], "valid")

    def test_empty_session_returns_empty_list(self):
        self._create_db().close()
        parts = get_parts(self.db_path, "ses_nonexistent")
        self.assertEqual(parts, [])


class TestResolveDbPath(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="repair_dbpath_"))
    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_env_db_path_found(self):
        db = self.tmpdir / "custom.db"
        db.touch()
        with patch.dict(os.environ, {"OPENCODE_DB_PATH": str(db)}):
            result = resolve_db_path()
        self.assertEqual(result, db)

    def test_env_db_path_not_found_raises(self):
        with patch.dict(os.environ, {"OPENCODE_DB_PATH": "/nonexistent/db"}):
            with self.assertRaises(FileNotFoundError):
                resolve_db_path()

    def test_env_data_dir_found(self):
        data_dir = self.tmpdir / "opencode_data"
        data_dir.mkdir()
        db = data_dir / "opencode.db"
        db.touch()
        with patch.dict(os.environ, {
            "OPENCODE_DATA_DIR": str(data_dir),
            "OPENCODE_DB_PATH": "",
        }):
            result = resolve_db_path()
        self.assertEqual(result, db)

    def test_not_found_raises(self):
        with patch.dict(os.environ, {
            "OPENCODE_DB_PATH": "",
            "OPENCODE_DATA_DIR": "",
            "XDG_DATA_HOME": "/nonexistent",
        }, clear=True):
            with patch("repair_empty_result.Path.home", return_value=Path("/nonexistent")):
                with self.assertRaises(RepairError):
                    resolve_db_path()


if __name__ == "__main__":
    unittest.main()
