"""Test that SKILL.md is Pi-only and fallback-runner-only.

Validates the Task 7 acceptance criteria:
- No references to Claude Code, Codex, Kimi, or OpenCode backend dispatch
- Transcript canary instructions reference pi-cli
- Only fallback-runner mode (no native mode branches)
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_MD = REPO_ROOT / "SKILL.md"

# Terms that indicate non-Pi backend dispatch
FORBIDDEN_BACKEND_TERMS = [
    "Claude Code",
    "claude-code",
    "claude_code",
    "Codex",
    "codex",
    "Kimi",
    "kimi",
    "OpenCode",
    "opencode",
]


class SkillMdPiOnlyTests(unittest.TestCase):
    content: str
    lines: list[str]

    @classmethod
    def setUpClass(cls) -> None:
        cls.content = SKILL_MD.read_text()
        cls.lines = cls.content.splitlines()

    def test_skill_md_exists(self) -> None:
        self.assertTrue(SKILL_MD.exists(), "SKILL.md must exist")

    def test_no_forbidden_backend_references(self) -> None:
        """SKILL.md must not reference Claude Code, Codex, Kimi, or OpenCode dispatch."""
        for term in FORBIDDEN_BACKEND_TERMS:
            with self.subTest(term=term):
                self.assertNotIn(
                    term,
                    self.content,
                    f"SKILL.md must not contain '{term}' — "
                    f"only Pi-specific instructions are allowed",
                )

    def test_no_native_mode_choice(self) -> None:
        """SKILL.md must not tell the agent to choose between native and fallback-runner."""
        forbidden_phrases = [
            "Choose native mode",
            "Choose the fallback-runner",
            "In native mode",
            "In fallback-runner mode",
            "native mode",
        ]
        for phrase in forbidden_phrases:
            with self.subTest(phrase=phrase):
                self.assertNotIn(
                    phrase,
                    self.content,
                    f"SKILL.md must not contain '{phrase}' — "
                    f"only fallback-runner mode should be described",
                )

    def test_transcript_canary_references_pi_cli(self) -> None:
        """Transcript/canary instructions must reference pi-cli."""
        self.assertIn(
            "pi-cli",
            self.content,
            "SKILL.md transcript canary instructions must reference 'pi-cli'",
        )

    def test_fallback_runner_instructions_present(self) -> None:
        """SKILL.md must describe using run_phase.py run (fallback-runner)."""
        self.assertIn(
            "run_phase.py run",
            self.content,
            "SKILL.md must describe using 'run_phase.py run' for fallback-runner mode",
        )

    def test_backend_host_instruction(self) -> None:
        """SKILL.md must instruct passing --backend host for Pi subagents."""
        self.assertIn(
            "--backend host",
            self.content,
            "SKILL.md must instruct '--backend host' for subagent dispatch",
        )

    def test_critical_rules_preserved(self) -> None:
        """Critical rules about not killing agents and not busy-polling must be present."""
        critical = [
            "do not kill",
            "timeout",
            "busy-poll",
            "60 minutes",
            "180 minutes",
        ]
        content_lower = self.content.lower()
        for phrase in critical:
            with self.subTest(phrase=phrase):
                self.assertIn(
                    phrase,
                    content_lower,
                    f"SKILL.md must preserve critical rule containing '{phrase}'",
                )

    def test_no_trycycle_codex_or_claude_model_env_vars(self) -> None:
        """SKILL.md must not reference non-Pi model env vars."""
        forbidden_env = [
            "TRYCYCLE_CODEX_PROFILE",
            "TRYCYCLE_CODEX_MODEL",
            "TRYCYCLE_CLAUDE_MODEL",
            "TRYCYCLE_KIMI_MODEL",
            "TRYCYCLE_OPENCODE_MODEL",
        ]
        for var in forbidden_env:
            with self.subTest(var=var):
                self.assertNotIn(
                    var,
                    self.content,
                    f"SKILL.md must not reference non-Pi env var '{var}'",
                )

    def test_trycycle_pi_model_env_var_present(self) -> None:
        """SKILL.md should reference TRYCYCLE_PI_MODEL."""
        self.assertIn(
            "TRYCYCLE_PI_MODEL",
            self.content,
            "SKILL.md must reference TRYCYCLE_PI_MODEL for model override",
        )


if __name__ == "__main__":
    unittest.main()
