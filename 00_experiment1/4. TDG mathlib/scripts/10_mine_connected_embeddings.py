from __future__ import annotations

import json
from collections import Counter, defaultdict
from itertools import combinations

import pandas as pd

from tdg_utils import ROOT


DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"


def load_graphs():
    with (DATA_DIR / "stage1_tdg_by_theorem.jsonl").open("r", encoding="utf-8") as handle:
        for line in handle:
            yield json.loads(line)


def tactic_index(node_id: str) -> int:
    return int(node_id.rsplit("::t", 1)[1]) if "::t" in node_id else -1


def canonicalize_subgraph(node_ids: list[str], tactic_nodes: dict[str, dict], host_edges: list[tuple[str, str, str]]):
    ordered_host_nodes = sorted(node_ids, key=tactic_index)
    local_index = {host_id: idx for idx, host_id in enumerate(ordered_host_nodes)}
    node_labels = [tactic_nodes[host_id]["tactic_head"] for host_id in ordered_host_nodes]
    edges_local = sorted(
        [
            (local_index[src], local_index[dst], edge_type)
            for src, dst, edge_type in host_edges
            if src in local_index and dst in local_index
        ],
        key=lambda item: (item[0], item[1], item[2]),
    )
    key = (tuple(node_labels), tuple(edges_local))
    mapping = {str(i): host_id for i, host_id in enumerate(ordered_host_nodes)}
    return key, mapping, ordered_host_nodes


def connected_node_sets(neighbors: dict[str, set[str]], max_nodes: int = 4):
    seen = set()
    for start in neighbors:
        stack = [(frozenset([start]), set(neighbors[start]))]
        while stack:
            current, frontier = stack.pop()
            if len(current) >= 2 and current not in seen:
                seen.add(current)
                yield current
            if len(current) == max_nodes:
                continue
            for nxt in sorted(frontier):
                if nxt in current:
                    continue
                new_current = frozenset(set(current) | {nxt})
                new_frontier = (frontier | neighbors[nxt]) - new_current
                stack.append((new_current, new_frontier))


def mine_connected_witnesses(max_nodes: int = 4):
    candidate_witnesses: dict[tuple, list[dict]] = defaultdict(list)
    candidate_counts = Counter()

    for theorem_graph in load_graphs():
        theorem = theorem_graph["theorem"]
        tactic_nodes = {
            node["node_id"]: node
            for node in theorem_graph["nodes"]
            if node["node_type"] == "tactic"
        }
        structural_edges = [
            (edge["src_node_id"], edge["dst_node_id"], edge["edge_type"])
            for edge in theorem_graph["edges"]
            if edge["edge_type"] in {"goal_to_goal", "hyp_to_goal"}
            and edge["src_node_id"] in tactic_nodes
            and edge["dst_node_id"] in tactic_nodes
        ]
        neighbors: dict[str, set[str]] = defaultdict(set)
        for src, dst, _ in structural_edges:
            neighbors[src].add(dst)
            neighbors[dst].add(src)
        for node_id in tactic_nodes:
            neighbors.setdefault(node_id, set())

        theorem_seen = set()
        for node_set in connected_node_sets(neighbors, max_nodes=max_nodes):
            host_edges = [edge for edge in structural_edges if edge[0] in node_set and edge[1] in node_set]
            if not host_edges:
                continue
            key, mapping, ordered_host_nodes = canonicalize_subgraph(list(node_set), tactic_nodes, host_edges)
            witness_identity = (key, tuple(ordered_host_nodes))
            if witness_identity in theorem_seen:
                continue
            theorem_seen.add(witness_identity)
            candidate_witnesses[key].append(
                {
                    "theorem": theorem,
                    "mapping": mapping,
                    "host_node_ids": ordered_host_nodes,
                }
            )
            candidate_counts[key] += 1
    return candidate_witnesses, candidate_counts


def build_outputs(candidate_witnesses: dict[tuple, list[dict]], min_support: int = 3):
    candidates = []
    witnesses = []
    candidate_id = 0
    for key, witness_list in candidate_witnesses.items():
        theorem_support = sorted({witness["theorem"] for witness in witness_list})
        if len(theorem_support) < min_support:
            continue
        node_labels, edges_local = key
        cid = f"conn_{candidate_id:05d}"
        candidate_id += 1
        candidates.append(
            {
                "candidate_id": cid,
                "num_nodes": len(node_labels),
                "num_edges": len(edges_local),
                "node_labels": list(node_labels),
                "edges_local_json": json.dumps(list(edges_local), ensure_ascii=False),
                "support_theorems": len(theorem_support),
                "witness_count": len(witness_list),
                "sample_theorems": theorem_support[:5],
            }
        )
        for witness_idx, witness in enumerate(witness_list):
            witnesses.append(
                {
                    "candidate_id": cid,
                    "witness_id": f"{cid}::w{witness_idx:05d}",
                    "theorem": witness["theorem"],
                    "mapping_json": json.dumps(witness["mapping"], ensure_ascii=False),
                    "host_node_ids_json": json.dumps(witness["host_node_ids"], ensure_ascii=False),
                }
            )
    return candidates, witnesses


def write_report(candidates: list[dict]) -> None:
    top = sorted(candidates, key=lambda row: (-row["support_theorems"], -row["num_nodes"], -row["num_edges"]))[:25]
    lines = [
        "# Stage 2B Connected Embedding Mining",
        "",
        "## Method",
        "",
        "- mined connected tactic-only subgraphs of 2-4 nodes",
        "- preserved directed labeled internal edges (`goal_to_goal`, `hyp_to_goal`)",
        "- canonicalized candidates by topological host order plus local directed edge set",
        "- stored explicit witness maps for every accepted occurrence",
        "",
        "## Top connected candidates",
        "",
    ]
    for row in top:
        motif = " / ".join(row["node_labels"])
        lines.append(
            f"- `{row['candidate_id']}` | nodes={row['num_nodes']} | edges={row['num_edges']} | support={row['support_theorems']} | motif=`{motif}`"
        )
    (REPORTS_DIR / "stage2b_connected_embedding_mining.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    REPORTS_DIR.mkdir(exist_ok=True)
    candidate_witnesses, _ = mine_connected_witnesses(max_nodes=4)
    candidates, witnesses = build_outputs(candidate_witnesses, min_support=3)
    pd.DataFrame(candidates).to_parquet(DATA_DIR / "stage2b_connected_candidates.parquet", index=False)
    pd.DataFrame(witnesses).to_parquet(DATA_DIR / "stage2b_connected_witnesses.parquet", index=False)
    write_report(candidates)
    print(f"Wrote {len(candidates)} connected-subgraph candidates and {len(witnesses)} witnesses.")


if __name__ == "__main__":
    main()
