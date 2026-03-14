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
    ordered = sorted(
        witness_rows,
        key=lambda row: witness_sort_key(row["host_node_ids"]),
    )
    for row in ordered:
        host_set = set(row["host_node_ids"])
        if host_set & used_nodes:
            continue
        selected.append(row)
        used_nodes.update(host_set)
    return selected


def main() -> None:
    REPORTS_DIR.mkdir(exist_ok=True)

    candidates = pd.read_parquet(DATA_DIR / "stage3_collapsible_candidates.parquet")
    stage2_witnesses = pd.read_parquet(DATA_DIR / "stage2_isomorphic_witnesses.parquet")
    stage3_witnesses = pd.read_parquet(DATA_DIR / "stage3_collapsible_witnesses.parquet")

    accepted = stage3_witnesses[stage3_witnesses["is_collapsible"]].merge(
        stage2_witnesses[["candidate_id", "witness_id", "theorem", "host_node_ids_json", "mapping_json"]],
        on=["candidate_id", "witness_id", "theorem"],
        how="left",
    )

    candidate_lookup = {
        row["candidate_id"]: {
            "num_nodes": len(list(row["node_labels"])),
            "num_edges": len(list(row["edge_labels"])),
            "node_labels": list(row["node_labels"]),
            "edge_labels": list(row["edge_labels"]),
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
                "edge_labels": meta["edge_labels"],
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
        raise RuntimeError("No accepted collapsible witnesses available for compression analysis.")

    candidate_df = candidate_df.sort_values(
        ["estimated_corpus_savings", "disjoint_witness_count", "disjoint_theorem_support"],
        ascending=[False, False, False],
    )

    candidate_df.to_parquet(DATA_DIR / "stage4_candidate_compression_ranking.parquet", index=False)
    theorem_df.to_parquet(DATA_DIR / "stage4_theorem_level_compression.parquet", index=False)

    top_by_support = candidate_df.sort_values(
        ["raw_collapsible_theorem_support", "raw_collapsible_witness_count"],
        ascending=[False, False],
    ).head(15)
    top_by_compression = candidate_df.head(20)

    report_lines = [
        "# Stage 4 Compression Power Analysis",
        "",
        "## Method",
        "",
        "- started from accepted collapsible witnesses only",
        "- grouped witnesses by `(candidate, theorem)`",
        "- selected theorem-local disjoint witnesses by node-set non-overlap using a deterministic greedy selector",
        "- estimated savings per selected witness as `Size(candidate) - 1`, where size is the number of tactic nodes in the candidate",
        "- estimated corpus compression power as `disjoint_witness_count * (Size(candidate) - 1)`",
        "",
        "## Important note",
        "",
        "- This is an overlap-aware compression proxy, not the final paper-faithful refactoring metric.",
        "- It is still useful because it corrects the current support-only bias toward very small motifs.",
        "",
        "## Top candidates by estimated corpus savings",
        "",
    ]
    for _, row in top_by_compression.iterrows():
        report_lines.append(
            f"- `{row['candidate_id']}` motif=`{' -> '.join(row['node_labels'])}` size={row['candidate_num_nodes']} disjoint_hits={row['disjoint_witness_count']} savings_per_hit={row['savings_per_hit']} estimated_corpus_savings={row['estimated_corpus_savings']}"
        )

    report_lines += [
        "",
        "## Top candidates by raw collapsible support",
        "",
    ]
    for _, row in top_by_support.iterrows():
        report_lines.append(
            f"- `{row['candidate_id']}` motif=`{' -> '.join(row['node_labels'])}` raw_theorem_support={row['raw_collapsible_theorem_support']} raw_witnesses={row['raw_collapsible_witness_count']} estimated_corpus_savings={row['estimated_corpus_savings']}"
        )

    report_lines += [
        "",
        "## Interpretation",
        "",
        "- If support and compression rankings agree, the motif is both frequent and useful.",
        "- If they diverge, support-only mining was overvaluing small frequent motifs or undervaluing somewhat larger motifs.",
        "- This ranking should replace raw support as the main candidate ordering for the next round of tactic discovery work.",
    ]

    (REPORTS_DIR / "stage4_compression_power.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print("Wrote stage-4 compression power outputs.")


if __name__ == "__main__":
    main()
