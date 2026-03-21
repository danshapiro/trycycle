#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


TAG_NAME = "review_observations_json"
TAG_RE = re.compile(
    rf"<{TAG_NAME}>(?P<body>.*?)</{TAG_NAME}>",
    re.DOTALL,
)
SEVERITIES = {"critical", "major", "minor", "nit"}
CATEGORIES = {
    "implementation_plan_mismatch",
    "test_plan_mismatch",
    "correctness",
    "edge_case",
    "security",
    "performance",
    "error_handling",
    "missing_test",
    "behavior",
    "other",
}
BLOCKING_SEVERITIES = {"critical", "major"}


class ExtractionError(RuntimeError):
    pass


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ExtractionError(f"could not read reply file: {path}") from exc


def _extract_tagged_json(reply_text: str) -> dict[str, Any]:
    match = TAG_RE.search(reply_text)
    if not match:
        raise ExtractionError(
            f"review reply is missing required <{TAG_NAME}>...</{TAG_NAME}> block"
        )

    body = match.group("body").strip()
    if not body:
        raise ExtractionError(f"review reply has empty <{TAG_NAME}> block")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"review observations block is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ExtractionError("review observations root must be a JSON object")
    return payload


def _expect_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExtractionError(f"{field_name} must be a non-empty string")
    return value.strip()


def _expect_optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ExtractionError(f"{field_name} must be a string when present")
    trimmed = value.strip()
    return trimmed or None


def _normalize_where(raw: Any, index: int) -> dict[str, Any] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ExtractionError(f"observations[{index}].where must be an object when present")

    normalized: dict[str, Any] = {}
    if "file" in raw:
        normalized["file"] = _expect_string(raw["file"], f"observations[{index}].where.file")
    if "line" in raw:
        line = raw["line"]
        if not isinstance(line, int) or line <= 0:
            raise ExtractionError(f"observations[{index}].where.line must be a positive integer")
        normalized["line"] = line
    if "symbol" in raw:
        symbol = _expect_optional_string(raw["symbol"], f"observations[{index}].where.symbol")
        if symbol:
            normalized["symbol"] = symbol
    if not normalized:
        return None
    return normalized


def _normalize_string_list(raw: Any, field_name: str) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ExtractionError(f"{field_name} must be an array when present")
    normalized: list[str] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, str) or not item.strip():
            raise ExtractionError(f"{field_name}[{idx}] must be a non-empty string")
        normalized.append(item.strip())
    return normalized


def _normalize_evidence(raw: Any, index: int) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ExtractionError(f"observations[{index}].evidence must be an object when present")

    normalized: dict[str, Any] = {}
    commands = _normalize_string_list(
        raw.get("commands"), f"observations[{index}].evidence.commands"
    )
    if commands:
        normalized["commands"] = commands

    artifacts = _normalize_string_list(
        raw.get("artifacts"), f"observations[{index}].evidence.artifacts"
    )
    if artifacts:
        normalized["artifacts"] = artifacts

    for key in ("stdout_excerpt", "stderr_excerpt", "traceback_excerpt", "notes"):
        value = _expect_optional_string(
            raw.get(key), f"observations[{index}].evidence.{key}"
        )
        if value:
            normalized[key] = value

    return normalized


def _normalize_observation(raw: Any, index: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ExtractionError(f"observations[{index}] must be an object")

    severity = _expect_string(raw.get("severity"), f"observations[{index}].severity")
    if severity not in SEVERITIES:
        raise ExtractionError(
            f"observations[{index}].severity must be one of: {', '.join(sorted(SEVERITIES))}"
        )

    category = _expect_string(raw.get("category"), f"observations[{index}].category")
    if category not in CATEGORIES:
        raise ExtractionError(
            f"observations[{index}].category must be one of: {', '.join(sorted(CATEGORIES))}"
        )

    normalized = {
        "id": _expect_string(raw.get("id"), f"observations[{index}].id"),
        "severity": severity,
        "category": category,
        "expected": _expect_string(raw.get("expected"), f"observations[{index}].expected"),
        "observed": _expect_string(raw.get("observed"), f"observations[{index}].observed"),
    }

    where = _normalize_where(raw.get("where"), index)
    if where:
        normalized["where"] = where

    evidence = _normalize_evidence(raw.get("evidence"), index)
    if evidence:
        normalized["evidence"] = evidence

    return normalized


def normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    status = _expect_string(payload.get("status"), "status")
    if status not in {"no_issues", "issues_found"}:
        raise ExtractionError("status must be either 'no_issues' or 'issues_found'")

    summary = _expect_optional_string(payload.get("summary"), "summary")
    raw_observations = payload.get("observations")
    if raw_observations is None:
        raise ExtractionError("observations field is required")
    if not isinstance(raw_observations, list):
        raise ExtractionError("observations must be an array")

    observations = [
        _normalize_observation(raw_observation, index)
        for index, raw_observation in enumerate(raw_observations)
    ]

    if status == "no_issues" and observations:
        raise ExtractionError("status 'no_issues' requires an empty observations array")
    if status == "issues_found" and not observations:
        raise ExtractionError("status 'issues_found' requires at least one observation")

    blocking_issue_count = sum(
        1 for observation in observations if observation["severity"] in BLOCKING_SEVERITIES
    )

    normalized = {
        "status": status,
        "summary": summary or "",
        "observations": observations,
        "issue_count": len(observations),
        "blocking_issue_count": blocking_issue_count,
    }
    return normalized


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def extract_command(args: argparse.Namespace) -> int:
    reply_path = Path(args.reply).resolve()
    output_path = Path(args.output).resolve()
    payload = _extract_tagged_json(_read_text(reply_path))
    normalized = normalize_payload(payload)
    _write_json(output_path, normalized)

    result = {
        "status": "ok",
        "reply_path": str(reply_path),
        "observations_path": str(output_path),
        "issue_count": normalized["issue_count"],
        "blocking_issue_count": normalized["blocking_issue_count"],
        "has_blocking_issues": normalized["blocking_issue_count"] > 0,
        "review_status": normalized["status"],
    }
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract and validate structured review observations from a reviewer reply."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract = subparsers.add_parser(
        "extract",
        help="Extract the <review_observations_json> block from a reply and write normalized JSON.",
    )
    extract.add_argument("--reply", required=True, help="Path to the reviewer reply text file.")
    extract.add_argument(
        "--output",
        required=True,
        help="Path to write the normalized review observations JSON.",
    )
    extract.set_defaults(func=extract_command)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ExtractionError as exc:
        print(f"review observations error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
