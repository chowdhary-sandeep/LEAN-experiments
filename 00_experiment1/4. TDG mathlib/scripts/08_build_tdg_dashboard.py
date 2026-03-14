from __future__ import annotations

from collections import defaultdict, deque
import json
from pathlib import Path

import pandas as pd

from tdg_utils import ROOT, theorem_slug


DATA_DIR = ROOT / "data"
DASHBOARD_DIR = ROOT / "dashboard_data"
GRAPHS_DIR = DASHBOARD_DIR / "graphs"


def _node_sort_key(node: dict) -> tuple[int, int, str]:
    node_type = node.get("node_type", "")
    if node_type == "special":
        head = node.get("tactic_head", "")
        if head == "in":
            return (0, -1, node["node_id"])
        if head == "out":
            return (2, 10**9, node["node_id"])
    tactic_index = node.get("tactic_index")
    return (1, tactic_index if tactic_index is not None else 10**8, node["node_id"])


def compute_node_positions(graph: dict) -> dict[str, dict[str, float]]:
    """Compute node positions using improved layered layout with proper spacing."""
    nodes = {node["node_id"]: node for node in graph["nodes"]}
    adjacency: dict[str, set[str]] = defaultdict(set)
    indegree = {node_id: 0 for node_id in nodes}
    reverse_adj: dict[str, set[str]] = defaultdict(set)

    for edge in graph["edges"]:
        src = edge["src_node_id"]
        dst = edge["dst_node_id"]
        if src not in nodes or dst not in nodes or dst in adjacency[src]:
            continue
        adjacency[src].add(dst)
        reverse_adj[dst].add(src)
        indegree[dst] += 1

    # Topological sort with levels
    queue = deque(sorted((node_id for node_id, deg in indegree.items() if deg == 0), key=lambda node_id: _node_sort_key(nodes[node_id])))
    topo_order: list[str] = []
    level = {node_id: 0 for node_id in nodes}

    while queue:
        node_id = queue.popleft()
        topo_order.append(node_id)
        for dst in sorted(adjacency[node_id], key=lambda other: _node_sort_key(nodes[other])):
            level[dst] = max(level[dst], level[node_id] + 1)
            indegree[dst] -= 1
            if indegree[dst] == 0:
                queue.append(dst)

    if len(topo_order) != len(nodes):
        topo_order = sorted(nodes, key=lambda node_id: _node_sort_key(nodes[node_id]))
        for rank, node_id in enumerate(topo_order):
            level[node_id] = rank

    layers: dict[int, list[str]] = defaultdict(list)
    for node_id in topo_order:
        layers[level[node_id]].append(node_id)

    # Improved positioning with better spacing
    max_width = max((len(layer) for layer in layers.values()), default=1)

    # Dynamic spacing based on graph size
    if max_width <= 3:
        dx = 180.0
    elif max_width <= 6:
        dx = 140.0
    elif max_width <= 10:
        dx = 100.0
    else:
        dx = 80.0
    dy = 120.0

    # Position nodes with centering and better spread
    positions: dict[str, dict[str, float]] = {}
    for depth in sorted(layers):
        layer = sorted(layers[depth], key=lambda node_id: _node_sort_key(nodes[node_id]))
        # Center the layer
        start_x = -((len(layer) - 1) * dx) / 2.0
        for index, node_id in enumerate(layer):
            x = start_x + index * dx
            y = depth * dy

            # Add slight jitter to overlapping nodes at same position
            x += (index % 3 - 1) * 15

            positions[node_id] = {
                "x": round(x, 2),
                "y": round(y, 2),
            }

    return positions


def load_collapsible_hits() -> dict[str, list[dict]]:
    stage2_witnesses = pd.read_parquet(DATA_DIR / "stage2b_connected_witnesses.parquet")
    stage3_witnesses = pd.read_parquet(DATA_DIR / "stage3b_connected_collapsible_witnesses.parquet")
    stage3_candidates = pd.read_parquet(DATA_DIR / "stage3b_connected_collapsible_candidates.parquet")
    stage4_candidates = pd.read_parquet(DATA_DIR / "stage4b_connected_compression_ranking.parquet")

    accepted = stage3_witnesses[stage3_witnesses["is_collapsible"]].merge(
        stage2_witnesses[["candidate_id", "witness_id", "theorem", "mapping_json", "host_node_ids_json"]],
        on=["candidate_id", "witness_id", "theorem"],
        how="left",
    )
    candidate_lookup = {
        row["candidate_id"]: {
            "node_labels": list(row["node_labels"]),
            "num_nodes": int(row["candidate_num_nodes"]) if "candidate_num_nodes" in row else int(row["num_nodes"]),
            "collapsible_theorem_support": int(row["collapsible_theorem_support"]),
            "collapsible_witness_count": int(row["collapsible_witness_count"]),
            "estimated_corpus_savings": 0,
        }
        for _, row in stage3_candidates.iterrows()
    }
    for _, row in stage4_candidates.iterrows():
        if row["candidate_id"] in candidate_lookup:
            candidate_lookup[row["candidate_id"]]["estimated_corpus_savings"] = int(row["estimated_corpus_savings"])

    theorem_hits: dict[str, list[dict]] = {}
    for theorem, frame in accepted.groupby("theorem"):
        ordered = frame.sort_values(["candidate_id", "witness_id"])
        hits = []
        for _, row in ordered.iterrows():
            candidate = candidate_lookup[row["candidate_id"]]
            hits.append(
                {
                    "candidate_id": row["candidate_id"],
                    "witness_id": row["witness_id"],
                    "node_labels": candidate["node_labels"],
                    "candidate_num_nodes": candidate["num_nodes"],
                    "host_node_ids": json.loads(row["host_node_ids_json"]),
                    "mapping": json.loads(row["mapping_json"]),
                    "collapsible_theorem_support": candidate["collapsible_theorem_support"],
                    "collapsible_witness_count": candidate["collapsible_witness_count"],
                    "estimated_corpus_savings": candidate["estimated_corpus_savings"],
                }
            )
        hits.sort(
            key=lambda hit: (
                -hit["estimated_corpus_savings"],
                -hit["candidate_num_nodes"],
                -len(hit["host_node_ids"]),
                hit["candidate_id"],
            )
        )
        theorem_hits[theorem] = hits[:200]
    return theorem_hits


def compact_graph(graph: dict, collapsible_hits: list[dict]) -> dict:
    positions = compute_node_positions(graph)
    node_payload = []
    for node in graph["nodes"]:
        if node["node_type"] == "special":
            label = node["tactic_head"]
        else:
            label = node["tactic_head"]
        node_payload.append(
            {
                "id": node["node_id"],
                "type": node["node_type"],
                "label": label,
                "tactic_index": node["tactic_index"],
                "raw_tactic": node["raw_tactic"],
                "inputs": json.loads(node["actual_inputs_json"]),
                "outputs": json.loads(node["actual_outputs_json"]),
                "position": positions.get(node["node_id"], {"x": 0.0, "y": 0.0}),
            }
        )

    edge_payload = [
        {
            "source": edge["src_node_id"],
            "target": edge["dst_node_id"],
            "edge_type": edge["edge_type"],
            "label": edge["label"],
            "object_id": edge["object_id"],
            "object_kind": edge["object_kind"],
            "evidence": edge["evidence"],
        }
        for edge in graph["edges"]
    ]
    object_payload = [
        {
            "id": obj["object_id"],
            "kind": obj["object_kind"],
            "name": obj["source_name"],
            "proposition": obj["proposition"],
            "producer": obj["producer_node_id"],
            "origin": obj["origin"],
        }
        for obj in graph["objects"]
    ]
    return {
        "theorem": graph["theorem"],
        "file": graph["file"],
        "statement": graph["statement"],
        "proof_text": graph["proof_text"],
        "nodes": node_payload,
        "edges": edge_payload,
        "objects": object_payload,
        "collapsible_hits": collapsible_hits,
    }


def main() -> None:
    DASHBOARD_DIR.mkdir(exist_ok=True)
    GRAPHS_DIR.mkdir(exist_ok=True)
    index = []
    theorem_hits = load_collapsible_hits()

    with (DATA_DIR / "stage1_tdg_by_theorem.jsonl").open("r", encoding="utf-8") as handle:
        for line_num, line in enumerate(handle, start=1):
            graph = json.loads(line)
            hits = theorem_hits.get(graph["theorem"], [])
            compact = compact_graph(graph, hits)
            slug = theorem_slug(graph["theorem"])
            out_path = GRAPHS_DIR / f"{slug}.json"
            out_path.write_text(json.dumps(compact, ensure_ascii=False), encoding="utf-8")
            index.append(
                {
                    "theorem": graph["theorem"],
                    "slug": slug,
                    "file": graph["file"],
                    "num_nodes": len(compact["nodes"]),
                    "num_edges": len(compact["edges"]),
                    "proof_length": sum(1 for node in compact["nodes"] if node["type"] == "tactic"),
                    "collapsible_hits": len(hits),
                }
            )
            if line_num % 5000 == 0:
                print(f"dashboard assets: processed {line_num} theorems")

    (DASHBOARD_DIR / "index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote dashboard assets for {len(index)} theorems.")


if __name__ == "__main__":
    main()
