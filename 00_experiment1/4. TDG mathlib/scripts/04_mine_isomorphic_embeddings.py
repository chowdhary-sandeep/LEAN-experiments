from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from tdg_utils import ROOT


DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"


def load_graphs():
    with (DATA_DIR / "stage1_tdg_by_theorem.jsonl").open("r", encoding="utf-8") as handle:
        for line in handle:
            yield json.loads(line)


def mine_path_witnesses(max_nodes: int = 4):
    candidate_witnesses: dict[tuple, list[dict]] = defaultdict(list)
    candidate_counts = Counter()

    for theorem_graph in load_graphs():
        theorem = theorem_graph["theorem"]
        tactic_nodes = {
            node["node_id"]: node
            for node in theorem_graph["nodes"]
            if node["node_type"] == "tactic"
        }
        outgoing: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for edge in theorem_graph["edges"]:
            if edge["edge_type"] not in {"goal_to_goal", "hyp_to_goal"}:
                continue
            if edge["src_node_id"] in tactic_nodes and edge["dst_node_id"] in tactic_nodes:
                outgoing[edge["src_node_id"]].append((edge["dst_node_id"], edge["edge_type"]))

        for start in tactic_nodes:
            stack = [([start], [])]
            while stack:
                path_nodes, path_edges = stack.pop()
                if len(path_nodes) >= 2:
                    node_labels = tuple(tactic_nodes[node_id]["tactic_head"] for node_id in path_nodes)
                    edge_labels = tuple(edge_type for _, edge_type in path_edges)
                    key = (node_labels, edge_labels)
                    mapping = {str(i): node_id for i, node_id in enumerate(path_nodes)}
                    candidate_witnesses[key].append(
                        {
                            "theorem": theorem,
                            "mapping": mapping,
                            "host_node_ids": list(path_nodes),
                        }
                    )
                    candidate_counts[key] += 1
                if len(path_nodes) == max_nodes:
                    continue
                last = path_nodes[-1]
                for next_node, edge_type in outgoing.get(last, []):
                    if next_node in path_nodes:
                        continue
                    stack.append((path_nodes + [next_node], path_edges + [(next_node, edge_type)]))
    return candidate_witnesses, candidate_counts


def build_outputs(candidate_witnesses: dict[tuple, list[dict]], min_support: int = 3):
    candidates = []
    witnesses = []
    candidate_id = 0
    for key, witness_list in candidate_witnesses.items():
        theorem_support = sorted({witness["theorem"] for witness in witness_list})
        if len(theorem_support) < min_support:
            continue
        node_labels, edge_labels = key
        cid = f"cand_{candidate_id:05d}"
        candidate_id += 1
        candidates.append(
            {
                "candidate_id": cid,
                "num_nodes": len(node_labels),
                "num_edges": len(edge_labels),
                "node_labels": list(node_labels),
                "edge_labels": list(edge_labels),
                "support_theorems": len(theorem_support),
                "witness_count": len(witness_list),
                "sample_theorems": theorem_support[:5],
            }
        )
        for witness_idx, witness in enumerate(witness_list):
            witnesses.append(
                {
                    "candidate_id": cid,
                    "witness_id": f"{cid}::w{witness_idx:04d}",
                    "theorem": witness["theorem"],
                    "mapping_json": json.dumps(witness["mapping"], ensure_ascii=False),
                    "host_node_ids_json": json.dumps(witness["host_node_ids"], ensure_ascii=False),
                }
            )
    return candidates, witnesses


def write_report(candidates: list[dict]) -> None:
    top = sorted(candidates, key=lambda row: (-row["support_theorems"], -row["num_nodes"]))[:20]
    lines = [
        "# Stage 2 Embedding Mining",
        "",
        "## Method",
        "",
        "- mined directed tactic-only path motifs of 2-4 nodes",
        "- kept explicit witness mappings for every host theorem occurrence",
        "- canonicalized motifs by local node order plus edge-type sequence",
        "- excluded `premise_use` from structural matching",
        "",
        "## Top candidates",
        "",
    ]
    for row in top:
        motif = " -> ".join(row["node_labels"])
        lines.append(
            f"- `{row['candidate_id']}` | nodes={row['num_nodes']} | support={row['support_theorems']} | motif=`{motif}` | edges={row['edge_labels']}"
        )
    (REPORTS_DIR / "stage2_embedding_mining.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    REPORTS_DIR.mkdir(exist_ok=True)
    candidate_witnesses, _ = mine_path_witnesses(max_nodes=4)
    candidates, witnesses = build_outputs(candidate_witnesses, min_support=3)
    pd.DataFrame(candidates).to_parquet(DATA_DIR / "stage2_isomorphic_candidates.parquet", index=False)
    pd.DataFrame(witnesses).to_parquet(DATA_DIR / "stage2_isomorphic_witnesses.parquet", index=False)
    write_report(candidates)
    print(f"Wrote {len(candidates)} stage-2 candidates and {len(witnesses)} witnesses.")


if __name__ == "__main__":
    main()
