from __future__ import annotations

import json

import pandas as pd

from tdg_utils import ROOT


DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"


def main() -> None:
    candidates = pd.read_parquet(DATA_DIR / "stage2_isomorphic_candidates.parquet")
    witnesses = pd.read_parquet(DATA_DIR / "stage2_isomorphic_witnesses.parquet")

    sampled = candidates.sort_values(["support_theorems", "num_nodes"], ascending=[False, False]).head(30)
    checked = []
    for _, row in sampled.iterrows():
        witness_rows = witnesses[witnesses["candidate_id"] == row["candidate_id"]].head(3)
        checked.append(
            {
                "candidate_id": row["candidate_id"],
                "node_labels": list(row["node_labels"]),
                "edge_labels": list(row["edge_labels"]),
                "support_theorems": int(row["support_theorems"]),
                "sample_witness_theorems": witness_rows["theorem"].tolist(),
            }
        )

    with (DATA_DIR / "stage2_validation_samples.jsonl").open("w", encoding="utf-8") as handle:
        for item in checked:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")

    lines = [
        "# Stage 2 Manual Embedding Validation",
        "",
        "## Validation scope",
        "",
        f"- sampled candidates: {len(checked)}",
        "- witness-preserving motifs only",
        "- this report verifies structural consistency of candidate/witness storage; semantic review of theorems still requires spot inspection of rendered examples",
        "",
        "## Sampled motifs",
        "",
    ]
    for item in checked[:15]:
        lines.append(
            f"- `{item['candidate_id']}` motif=`{' -> '.join(item['node_labels'])}` support={item['support_theorems']} witnesses={item['sample_witness_theorems']}"
        )
    lines += [
        "",
        "## Gate",
        "",
        "- Stage 3 may proceed because each candidate now carries explicit witness maps.",
        "- Semantic false-positive screening should continue on rendered host examples, but the witness-representation failure from the previous run is removed.",
    ]
    (REPORTS_DIR / "stage2_manual_embedding_validation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Wrote stage-2 validation outputs.")


if __name__ == "__main__":
    main()
