from __future__ import annotations

import json
from pathlib import Path


def update_roadmap(*, runs_dir: Path, out_path: Path) -> None:
    # This is an offline, artifact-driven roadmap builder.
    # A future iteration can integrate paper search via external tooling; for now we summarize metrics and propose next steps.
    runs = sorted([p for p in runs_dir.iterdir() if p.is_dir()])

    eval_summaries = []
    attack_summaries = []
    for r in runs:
        mp = r / "eval" / "metrics.json"
        if mp.exists():
            m = json.loads(mp.read_text(encoding="utf-8"))
            eval_summaries.append((r.name, m))
        ap = r / "attack" / "metrics.json"
        if ap.exists():
            m = json.loads(ap.read_text(encoding="utf-8"))
            attack_summaries.append((r.name, m))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_render(eval_summaries, attack_summaries), encoding="utf-8")


def _render(eval_summaries, attack_summaries) -> str:
    lines = []
    lines.append("# Research roadmap")
    lines.append("")
    lines.append("This roadmap is generated from recent evaluation artifacts. Update it after each eval/attack run.")
    lines.append("")

    if eval_summaries:
        best = max(eval_summaries, key=lambda x: float(x[1].get("top1_acc", 0.0)))
        lines.append("## Current best (clean)")
        lines.append("")
        lines.append(f"- **run**: `{best[0]}`")
        lines.append(f"- **top1_acc**: **{float(best[1].get('top1_acc', 0.0)):.4f}**")
        lines.append("")

    if attack_summaries:
        # pick lowest robustness gap as a naive indicator
        def gap(m):
            c = float(m.get("clean_top1", 0.0))
            p = float(m.get("pgd_top1", 0.0))
            return c - p

        best_rob = min(attack_summaries, key=lambda x: gap(x[1]))
        lines.append("## Current best (robustness)")
        lines.append("")
        lines.append(f"- **run**: `{best_rob[0]}`")
        lines.append(f"- **clean_top1**: **{float(best_rob[1].get('clean_top1', 0.0)):.4f}**")
        lines.append(f"- **pgd_top1**: **{float(best_rob[1].get('pgd_top1', 0.0)):.4f}**")
        lines.append("")

    lines.append("## Next experiments (prioritized)")
    lines.append("")
    lines.append("- **Stronger augmentations**: tune crop/resize policy; add RandAugment as an option; verify gains on val and no regression on robustness.")
    lines.append("- **Backbone sweep**: ResNet50 vs ConvNeXt-Tiny vs EfficientNet-B0; use same training budget; compare clean + attacked metrics.")
    lines.append("- **Adversarial robustness**: add adversarial training baseline (PGD training) and compare clean/FGSM/PGD trade-off.")
    lines.append("- **Attack-network lane**: implement UAP generator training and measure transferability across backbones.")
    lines.append("")

    lines.append("## References to scan (starting list)")
    lines.append("")
    lines.append("- **TRADES** (robustness-accuracy tradeoff)")
    lines.append("- **MART** (misclassification aware adversarial training)")
    lines.append("- **UAP** (universal adversarial perturbations) + recent generator-based UAP papers")
    lines.append("")
    return "\n".join(lines)
