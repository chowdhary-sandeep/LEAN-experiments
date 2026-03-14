from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tdg_utils import ROOT, theorem_slug


DATA_DIR = ROOT / "data"
DASHBOARD_DIR = ROOT / "dashboard_data"
GRAPHS_DIR = DASHBOARD_DIR / "graphs"


def load_collapsible_hits() -> dict[str, list[dict]]:
    stage2_witnesses = pd.read_parquet(DATA_DIR / "stage2_isomorphic_witnesses.parquet")
    stage3_witnesses = pd.read_parquet(DATA_DIR / "stage3_collapsible_witnesses.parquet")
    stage3_candidates = pd.read_parquet(DATA_DIR / "stage3_collapsible_candidates.parquet")

    accepted = stage3_witnesses[stage3_witnesses["is_collapsible"]].merge(
        stage2_witnesses[["candidate_id", "witness_id", "theorem", "mapping_json", "host_node_ids_json"]],
        on=["candidate_id", "witness_id", "theorem"],
        how="left",
    )
    candidate_lookup = {
        row["candidate_id"]: {
            "node_labels": list(row["node_labels"]),
            "edge_labels": list(row["edge_labels"]),
            "collapsible_theorem_support": int(row["collapsible_theorem_support"]),
            "collapsible_witness_count": int(row["collapsible_witness_count"]),
        }
        for _, row in stage3_candidates.iterrows()
    }

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
                    "edge_labels": candidate["edge_labels"],
                    "host_node_ids": json.loads(row["host_node_ids_json"]),
                    "mapping": json.loads(row["mapping_json"]),
                    "collapsible_theorem_support": candidate["collapsible_theorem_support"],
                    "collapsible_witness_count": candidate["collapsible_witness_count"],
                }
            )
        theorem_hits[theorem] = hits[:200]
    return theorem_hits


def compact_graph(graph: dict, collapsible_hits: list[dict]) -> dict:
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
                    "statement": graph["statement"].replace("\n", " ")[:240],
                }
            )
            if line_num % 5000 == 0:
                print(f"dashboard assets: processed {line_num} theorems")

    (DASHBOARD_DIR / "index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote dashboard assets for {len(index)} theorems.")


if __name__ == "__main__":
    main()
