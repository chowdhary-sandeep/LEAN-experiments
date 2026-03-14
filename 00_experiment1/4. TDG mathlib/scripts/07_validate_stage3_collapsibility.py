from __future__ import annotations

import json

import pandas as pd

from tdg_utils import ROOT


DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"


def main() -> None:
    candidates = pd.read_parquet(DATA_DIR / "stage3_collapsible_candidates.parquet")
    witnesses = pd.read_parquet(DATA_DIR / "stage3_collapsible_witnesses.parquet")

    accepted = candidates[candidates["is_candidate_collapsible"]].sort_values(
        ["collapsible_theorem_support", "collapsible_witness_count"],
        ascending=[False, False],
    ).head(20)
    rejected = candidates[~candidates["is_candidate_collapsible"]].sort_values(
        ["support_theorems", "witness_count"],
        ascending=[False, False],
    ).head(20)

    sample_rows = []
    for frame, label in [(accepted, "accepted"), (rejected, "rejected")]:
        for _, row in frame.iterrows():
            witness_rows = witnesses[witnesses["candidate_id"] == row["candidate_id"]].head(2)
            sample_rows.append(
                {
                    "bucket": label,
                    "candidate_id": row["candidate_id"],
                    "node_labels": list(row["node_labels"]),
                    "edge_labels": list(row["edge_labels"]),
                    "sample_witnesses": witness_rows[["theorem", "failure_reason"]].to_dict(orient="records"),
                }
            )

    with (DATA_DIR / "stage3_validation_samples.jsonl").open("w", encoding="utf-8") as handle:
        for row in sample_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    lines = [
        "# Stage 3 Manual Collapsibility Validation",
        "",
        f"- accepted candidate sample size: {len(accepted)}",
        f"- rejected candidate sample size: {len(rejected)}",
        "",
        "## Accepted examples",
        "",
    ]
    for _, row in accepted.head(10).iterrows():
        lines.append(
            f"- `{row['candidate_id']}` motif=`{' -> '.join(row['node_labels'])}` support={row['collapsible_theorem_support']}"
        )
    lines += [
        "",
        "## Rejected examples",
        "",
    ]
    for _, row in rejected.head(10).iterrows():
        lines.append(
            f"- `{row['candidate_id']}` motif=`{' -> '.join(row['node_labels'])}` support={row['support_theorems']}"
        )
    lines += [
        "",
        "## Gate",
        "",
        "- Rejected cases are retained with explicit failure reasons in `data/stage3_collapsible_witnesses.parquet`.",
        "- Manual inspection should focus on whether the accepted path motifs are genuinely refactorable in Lean, not just graph-collapsible.",
    ]
    (REPORTS_DIR / "stage3_manual_collapsibility_validation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Wrote stage-3 validation outputs.")


if __name__ == "__main__":
    main()
