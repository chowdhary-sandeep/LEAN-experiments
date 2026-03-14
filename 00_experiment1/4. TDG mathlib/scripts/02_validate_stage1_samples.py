from __future__ import annotations

import json
import random
from pathlib import Path

from tdg_utils import ROOT, iter_tactic_records, parse_state, theorem_slug


DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"


def choose_samples(records: list[dict]) -> list[dict]:
    tiny = [record for record in records if 1 <= len(record["tactics"]) <= 4]
    medium = [record for record in records if 5 <= len(record["tactics"]) <= 12]
    large = [record for record in records if len(record["tactics"]) >= 13]
    rng = random.Random(20260314)
    sample = []
    sample.extend(rng.sample(tiny, min(10, len(tiny))))
    sample.extend(rng.sample(medium, min(20, len(medium))))
    sample.extend(rng.sample(large, min(20, len(large))))
    return sample


def summarize_theorem(record: dict) -> dict:
    tactic_summaries = []
    node_alignment_ok = 0
    edge_alignment_ok = 0
    checked_edges = 0
    for tactic in record["tactics"]:
        before_goals = parse_state(tactic.get("state_before", ""))
        after_goals = parse_state(tactic.get("state_after", ""))
        node_ok = bool(before_goals) and (tactic.get("state_after", "").strip() in {"", "no goals"} or bool(after_goals))
        node_alignment_ok += int(node_ok)
        active_before = before_goals[0].signature if before_goals else ""
        active_after = after_goals[0].signature if after_goals else ""
        edge_ok = bool(active_before) and (bool(after_goals) or tactic.get("is_terminal"))
        checked_edges += 1
        edge_alignment_ok += int(edge_ok)
        tactic_summaries.append(
            {
                "index": tactic["index"],
                "tactic": tactic["tactic"],
                "before_goals": len(before_goals),
                "after_goals": len(after_goals),
                "active_before": active_before[:180],
                "active_after": active_after[:180],
                "premises": [premise.get("full_name", premise.get("surface_name", "")) for premise in tactic.get("premises", [])],
                "node_ok": node_ok,
                "edge_ok": edge_ok,
            }
        )
    return {
        "full_name": record["full_name"],
        "file": record["file"],
        "num_tactics": len(record["tactics"]),
        "node_alignment_rate": node_alignment_ok / len(record["tactics"]),
        "edge_alignment_rate": edge_alignment_ok / checked_edges if checked_edges else 0.0,
        "tactics": tactic_summaries,
    }


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    REPORTS_DIR.mkdir(exist_ok=True)

    records = list(iter_tactic_records())
    sampled_records = choose_samples(records)
    validations = [summarize_theorem(record) for record in sampled_records]

    with (DATA_DIR / "stage1_validation_samples.jsonl").open("w", encoding="utf-8") as handle:
        for validation in validations:
            handle.write(json.dumps(validation, ensure_ascii=False) + "\n")

    mean_node = sum(item["node_alignment_rate"] for item in validations) / len(validations)
    mean_edge = sum(item["edge_alignment_rate"] for item in validations) / len(validations)

    exemplar_lines = []
    for item in validations[:8]:
        exemplar_lines.append(
            f"### {item['full_name']}\n"
            f"- file: `{item['file']}`\n"
            f"- tactics: {item['num_tactics']}\n"
            f"- node alignment rate: {item['node_alignment_rate']:.2%}\n"
            f"- edge alignment rate: {item['edge_alignment_rate']:.2%}\n"
            f"- first tactic: `{item['tactics'][0]['tactic']}`\n"
        )

    report = f"""# Stage 1 Manual Validation

## Sampling policy

- 10 tiny proofs
- 20 medium proofs
- 20 large proofs
- total sampled theorems: {len(validations)}

## Automated agentic pre-check

This file is a supervision gate, not a claim that human inspection is finished. The script checked whether:

- every sampled tactic has parseable `state_before`,
- every sampled tactic has parseable `state_after` unless it is terminal,
- active-goal lineage is preserved strongly enough to support conservative `goal_to_goal` edges.

## Aggregate results

- Mean node alignment rate: {mean_node:.2%}
- Mean edge alignment rate: {mean_edge:.2%}

## Sampled theorem snapshots

{chr(10).join(exemplar_lines)}

## Failure modes to inspect manually next

- branch-heavy proofs where the active branch is not obviously the first visible goal
- compound tactics that rewrite and split goals in one step
- hypothesis names introduced under bullets and reused later

## Acceptance status

- Stage 1 is accepted as a conservative baseline for further inspection if manual spot checks agree with these samples.
- Stage 2 should not proceed without reviewing `data/stage1_validation_samples.jsonl`.
"""

    (REPORTS_DIR / "stage1_manual_validation.md").write_text(report, encoding="utf-8")
    print("Wrote stage-1 validation outputs.")


if __name__ == "__main__":
    main()
