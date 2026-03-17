from __future__ import annotations

import json
from pathlib import Path


def aggregate_reports(*, runs_dir: Path, out_path: Path) -> None:
    runs = sorted([p for p in runs_dir.iterdir() if p.is_dir()])
    rows = []
    for r in runs:
        metrics_path = r / "eval" / "metrics.json"
        if metrics_path.exists():
            rows.append(("eval", r.name, json.loads(metrics_path.read_text(encoding="utf-8"))))
        attack_path = r / "attack" / "metrics.json"
        if attack_path.exists():
            rows.append(("attack", r.name, json.loads(attack_path.read_text(encoding="utf-8"))))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_render(rows), encoding="utf-8")


def _render(rows) -> str:
    lines = []
    lines.append("# Aggregated report")
    lines.append("")
    if not rows:
        lines.append("No run metrics found.")
        lines.append("")
        return "\n".join(lines)

    lines.append("| kind | run | key | value |")
    lines.append("|---|---|---:|---:|")
    for kind, run, m in rows:
        for key in ("top1_acc", "clean_top1", "fgsm_top1", "pgd_top1"):
            if key in m:
                lines.append(f"| {kind} | `{run}` | `{key}` | {m[key]} |")
    lines.append("")
    return "\n".join(lines)
