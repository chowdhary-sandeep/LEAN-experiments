from __future__ import annotations

import json
from collections import defaultdict

import networkx as nx
import pandas as pd

from tdg_utils import ROOT


DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"


def load_host_graphs():
    graphs = {}
    with (DATA_DIR / "stage1_tdg_by_theorem.jsonl").open("r", encoding="utf-8") as handle:
        for line in handle:
            graph = json.loads(line)
            dg = nx.DiGraph()
            tactic_nodes = {node["node_id"] for node in graph["nodes"] if node["node_type"] == "tactic"}
            for node_id in tactic_nodes:
                dg.add_node(node_id)
            for edge in graph["edges"]:
                if edge["src_node_id"] in tactic_nodes and edge["dst_node_id"] in tactic_nodes and edge["edge_type"] in {"goal_to_goal", "hyp_to_goal"}:
                    dg.add_edge(edge["src_node_id"], edge["dst_node_id"], edge_type=edge["edge_type"])
            graphs[graph["theorem"]] = dg
    return graphs


def check_collapsible(candidate_row, witness_row, host_graph):
    mapping = json.loads(witness_row["mapping_json"])
    node_labels = list(candidate_row["node_labels"])
    edge_labels = list(candidate_row["edge_labels"])
    ordered_host_nodes = [mapping[str(i)] for i in range(len(node_labels))]
    candidate_edges = {(ordered_host_nodes[i], ordered_host_nodes[i + 1], edge_labels[i]) for i in range(len(edge_labels))}
    matched_set = set(ordered_host_nodes)

    for u, v, data in host_graph.edges(data=True):
        if u in matched_set and v in matched_set:
            triple = (u, v, data["edge_type"])
            if triple not in candidate_edges:
                return False, "missing_internal_edge"

    for i, src in enumerate(ordered_host_nodes):
        for j in range(i + 1, len(ordered_host_nodes)):
            dst = ordered_host_nodes[j]
            reduced = host_graph.copy()
            reduced.remove_nodes_from(matched_set - {src, dst})
            if nx.has_path(reduced, src, dst):
                shortest_path = nx.shortest_path(reduced, src, dst)
                internal = set(shortest_path[1:-1])
                if internal - matched_set:
                    return False, "intermediate_path_violation"
    return True, "ok"


def main() -> None:
    candidates = pd.read_parquet(DATA_DIR / "stage2_isomorphic_candidates.parquet")
    witnesses = pd.read_parquet(DATA_DIR / "stage2_isomorphic_witnesses.parquet")
    host_graphs = load_host_graphs()

    candidate_lookup = {row["candidate_id"]: row for _, row in candidates.iterrows()}
    witness_results = []
    candidate_summary = defaultdict(lambda: {"total": 0, "accepted": 0, "theorems": set()})

    for _, witness in witnesses.iterrows():
        candidate = candidate_lookup[witness["candidate_id"]]
        host_graph = host_graphs[witness["theorem"]]
        accepted, reason = check_collapsible(candidate, witness, host_graph)
        witness_results.append(
            {
                "candidate_id": witness["candidate_id"],
                "witness_id": witness["witness_id"],
                "theorem": witness["theorem"],
                "is_collapsible": accepted,
                "failure_reason": reason,
            }
        )
        summary = candidate_summary[witness["candidate_id"]]
        summary["total"] += 1
        summary["accepted"] += int(accepted)
        if accepted:
            summary["theorems"].add(witness["theorem"])

    candidate_rows = []
    for _, candidate in candidates.iterrows():
        summary = candidate_summary[candidate["candidate_id"]]
        candidate_rows.append(
            {
                "candidate_id": candidate["candidate_id"],
                "node_labels": list(candidate["node_labels"]),
                "edge_labels": list(candidate["edge_labels"]),
                "support_theorems": int(candidate["support_theorems"]),
                "witness_count": int(candidate["witness_count"]),
                "collapsible_witness_count": int(summary["accepted"]),
                "collapsible_theorem_support": len(summary["theorems"]),
                "is_candidate_collapsible": summary["accepted"] > 0,
            }
        )

    pd.DataFrame(candidate_rows).to_parquet(DATA_DIR / "stage3_collapsible_candidates.parquet", index=False)
    pd.DataFrame(witness_results).to_parquet(DATA_DIR / "stage3_collapsible_witnesses.parquet", index=False)

    top = sorted(candidate_rows, key=lambda row: (-row["collapsible_theorem_support"], -row["collapsible_witness_count"]))[:20]
    lines = [
        "# Stage 3 Collapsibility",
        "",
        "## Method",
        "",
        "- evaluated each stage-2 witness against its host theorem TDG",
        "- enforced internal-edge completeness on the matched host nodes",
        "- enforced path-closure by checking for outside-node detours between matched endpoints",
        "",
        "## Top collapsible candidates",
        "",
    ]
    for row in top:
        if not row["is_candidate_collapsible"]:
            continue
        lines.append(
            f"- `{row['candidate_id']}` motif=`{' -> '.join(row['node_labels'])}` collapsible_support={row['collapsible_theorem_support']} witness_hits={row['collapsible_witness_count']}"
        )
    (REPORTS_DIR / "stage3_collapsibility.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Wrote stage-3 collapsibility outputs.")


if __name__ == "__main__":
    main()
