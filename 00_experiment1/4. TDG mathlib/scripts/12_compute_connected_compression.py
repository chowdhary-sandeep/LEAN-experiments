from __future__ import annotations

import json
import re
from collections import defaultdict

import pandas as pd

from tdg_utils import ROOT


DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"


TACTIC_ID_RE = re.compile(r"::t(\d+)$")


def tactic_index(node_id: str) -> int:
    match = TACTIC_ID_RE.search(node_id)
    return int(match.group(1)) if match else -1


def witness_sort_key(host_node_ids: list[str]) -> tuple[int, int, int]:
    indices = sorted(tactic_index(node_id) for node_id in host_node_ids)
    if not indices:
        return (10**9, 10**9, 10**9)
    return (indices[-1], indices[0], len(indices))


def select_disjoint_witnesses(witness_rows: list[dict]) -> list[dict]:
    selected = []
    used_nodes: set[str] = set()
    ordered = sorted(witness_rows, key=lambda row: witness_sort_key(row["host_node_ids"]))
    for row in ordered:
        host_set = set(row["host_node_ids"])
        if host_set & used_nodes:
            continue
        selected.append(row)
        used_nodes.update(host_set)
    return selected


def main() -> None:
    REPORTS_DIR.mkdir(exist_ok=True)

    candidates = pd.read_parquet(DATA_DIR / "stage3b_connected_collapsible_candidates.parquet")
    stage2_witnesses = pd.read_parquet(DATA_DIR / "stage2b_connected_witnesses.parquet")
    stage3_witnesses = pd.read_parquet(DATA_DIR / "stage3b_connected_collapsible_witnesses.parquet")

    accepted = stage3_witnesses[stage3_witnesses["is_collapsible"]].merge(
        stage2_witnesses[["candidate_id", "witness_id", "theorem", "host_node_ids_json", "mapping_json"]],
        on=["candidate_id", "witness_id", "theorem"],
        how="left",
    )

    candidate_lookup = {
        row["candidate_id"]: {
            "num_nodes": int(row["num_nodes"]),
            "num_edges": int(row["num_edges"]),
            "node_labels": list(row["node_labels"]),
            "raw_collapsible_theorem_support": int(row["collapsible_theorem_support"]),
            "raw_collapsible_witness_count": int(row["collapsible_witness_count"]),
        }
        for _, row in candidates.iterrows()
    }

    grouped: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for _, row in accepted.iterrows():
        grouped[row["candidate_id"]][row["theorem"]].append(
            {
                "candidate_id": row["candidate_id"],
                "witness_id": row["witness_id"],
                "theorem": row["theorem"],
                "host_node_ids": json.loads(row["host_node_ids_json"]),
                "mapping": json.loads(row["mapping_json"]),
            }
        )

    theorem_level_rows = []
    candidate_rows = []
    for candidate_id, theorem_map in grouped.items():
        meta = candidate_lookup[candidate_id]
        tactic_size = meta["num_nodes"]
        savings_per_hit = max(tactic_size - 1, 0)
        disjoint_hits_total = 0
        disjoint_theorems = 0
        for theorem, witness_rows in theorem_map.items():
            chosen = select_disjoint_witnesses(witness_rows)
            hit_count = len(chosen)
            disjoint_hits_total += hit_count
            disjoint_theorems += int(hit_count > 0)
            theorem_level_rows.append(
                {
                    "candidate_id": candidate_id,
                    "theorem": theorem,
                    "candidate_num_nodes": tactic_size,
                    "savings_per_hit": savings_per_hit,
                    "raw_witness_count": len(witness_rows),
                    "disjoint_witness_count": hit_count,
                    "estimated_theorem_savings": hit_count * savings_per_hit,
                    "selected_witness_ids_json": json.dumps([row["witness_id"] for row in chosen], ensure_ascii=False),
                    "selected_host_node_ids_json": json.dumps([row["host_node_ids"] for row in chosen], ensure_ascii=False),
                }
            )
        candidate_rows.append(
            {
                "candidate_id": candidate_id,
                "candidate_num_nodes": tactic_size,
                "candidate_num_edges": meta["num_edges"],
                "node_labels": meta["node_labels"],
                "raw_collapsible_theorem_support": meta["raw_collapsible_theorem_support"],
                "raw_collapsible_witness_count": meta["raw_collapsible_witness_count"],
                "disjoint_theorem_support": disjoint_theorems,
                "disjoint_witness_count": disjoint_hits_total,
                "savings_per_hit": savings_per_hit,
                "estimated_corpus_savings": disjoint_hits_total * savings_per_hit,
            }
        )

    candidate_df = pd.DataFrame(candidate_rows)
    theorem_df = pd.DataFrame(theorem_level_rows)
    if candidate_df.empty:
        raise RuntimeError("No accepted connected collapsible witnesses available for compression analysis.")

    candidate_df = candidate_df.sort_values(
        ["estimated_corpus_savings", "candidate_num_nodes", "disjoint_witness_count"],
        ascending=[False, False, False],
    )
    candidate_df.to_parquet(DATA_DIR / "stage4b_connected_compression_ranking.parquet", index=False)
    theorem_df.to_parquet(DATA_DIR / "stage4b_connected_theorem_compression.parquet", index=False)

    top = candidate_df.head(25)
    larger = candidate_df[candidate_df["candidate_num_nodes"] >= 3].head(20)
    lines = [
        "# Stage 4B Connected Compression Power",
        "",
        "## Method",
        "",
        "- started from accepted connected-subgraph collapsible witnesses",
        "- selected theorem-local disjoint witnesses by node-set non-overlap",
        "- estimated corpus savings as `disjoint_witness_count * (Size(candidate) - 1)`",
        "",
        "## Top connected candidates by estimated corpus savings",
        "",
    ]
    for _, row in top.iterrows():
        lines.append(
            f"- `{row['candidate_id']}` | nodes={row['candidate_num_nodes']} | motif=`{' / '.join(row['node_labels'])}` | disjoint_hits={row['disjoint_witness_count']} | estimated_corpus_savings={row['estimated_corpus_savings']}"
        )
    lines += [
        "",
        "## Larger connected candidates (size >= 3)",
        "",
    ]
    for _, row in larger.iterrows():
        lines.append(
            f"- `{row['candidate_id']}` | nodes={row['candidate_num_nodes']} | motif=`{' / '.join(row['node_labels'])}` | disjoint_hits={row['disjoint_witness_count']} | estimated_corpus_savings={row['estimated_corpus_savings']}"
        )
    (REPORTS_DIR / "stage4b_connected_compression_power.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Wrote connected-subgraph compression outputs.")


if __name__ == "__main__":
    main()
