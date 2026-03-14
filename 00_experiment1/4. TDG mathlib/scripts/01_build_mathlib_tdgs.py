from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass

import pandas as pd

from tdg_utils import (
    ROOT,
    extract_identifier_refs,
    extract_tactic_head,
    goal_match_key,
    iter_tactic_records,
    parse_state,
)


DATA_DIR = ROOT / "data"


@dataclass
class ProofObject:
    theorem: str
    object_id: str
    object_kind: str
    proposition: str
    source_name: str
    producer_node_id: str
    origin: str


@dataclass
class TdgNode:
    theorem: str
    node_id: str
    node_type: str
    tactic_index: int | None
    tactic_head: str
    raw_tactic: str
    annotated_tactic: str
    num_goals_before: int | None
    num_goals_after: int | None
    active_goal_input_id: str
    actual_inputs_json: str
    actual_outputs_json: str
    file: str


@dataclass
class TdgEdge:
    theorem: str
    src_node_id: str
    dst_node_id: str
    edge_type: str
    label: str
    object_id: str
    object_kind: str
    confidence: float
    evidence: str


def make_object_manager(theorem: str):
    counters = Counter()
    objects: list[dict] = []
    producers: dict[str, str] = {}

    def new_object(kind: str, proposition: str, source_name: str, producer_node_id: str, origin: str) -> str:
        counters[kind] += 1
        object_id = f"{theorem}::{kind[0]}{counters[kind] - 1}"
        producers[object_id] = producer_node_id
        objects.append(
            asdict(
                ProofObject(
                    theorem=theorem,
                    object_id=object_id,
                    object_kind=kind,
                    proposition=proposition,
                    source_name=source_name,
                    producer_node_id=producer_node_id,
                    origin=origin,
                )
            )
        )
        return object_id

    return new_object, objects, producers


def initialize_goal_entry(goal, in_node_id: str, new_object, shared_hyp_index: dict[tuple[str, str], str]):
    hyp_objects: dict[str, str] = {}
    for name in goal.hypothesis_names:
        proposition = goal.hypothesis_map.get(name, "")
        key = (name, proposition)
        if key not in shared_hyp_index:
            shared_hyp_index[key] = new_object("hypothesis", proposition, name, in_node_id, "initial_state")
        hyp_objects[name] = shared_hyp_index[key]
    goal_object = new_object("goal", goal.target, goal.case_label or f"goal_{goal.index}", in_node_id, "initial_state")
    return {"goal": goal, "goal_object": goal_object, "hyp_objects": hyp_objects}


def materialize_output_goal(theorem: str, goal, producer_node_id: str, input_entry, new_object, shared_hyp_index):
    hyp_objects: dict[str, str] = {}
    new_hyp_objects = []
    for name in goal.hypothesis_names:
        proposition = goal.hypothesis_map.get(name, "")
        if name in input_entry["hyp_objects"] and input_entry["goal"].hypothesis_map.get(name) == proposition:
            hyp_objects[name] = input_entry["hyp_objects"][name]
            continue
        key = (name, proposition)
        if key in shared_hyp_index and shared_hyp_index[key] in input_entry["hyp_objects"].values():
            hyp_objects[name] = shared_hyp_index[key]
            continue
        hyp_id = new_object("hypothesis", proposition, name, producer_node_id, "tactic_output")
        hyp_objects[name] = hyp_id
        shared_hyp_index[key] = hyp_id
        new_hyp_objects.append(
            {
                "object_id": hyp_id,
                "kind": "hypothesis",
                "name": name,
                "proposition": proposition,
            }
        )
    goal_object = new_object("goal", goal.target, goal.case_label or f"goal_{goal.index}", producer_node_id, "tactic_output")
    goal_output = {
        "object_id": goal_object,
        "kind": "goal",
        "name": goal.case_label or f"goal_{goal.index}",
        "proposition": goal.target,
    }
    return {"goal": goal, "goal_object": goal_object, "hyp_objects": hyp_objects}, [goal_output] + new_hyp_objects


def match_preserved_siblings(before_siblings, after_goals):
    remaining = set(range(len(after_goals)))
    matches: dict[int, int] = {}
    for sibling_index, goal in enumerate(before_siblings):
        for after_index in list(remaining):
            if goal_match_key(goal) == goal_match_key(after_goals[after_index]):
                matches[after_index] = sibling_index
                remaining.remove(after_index)
                break
    return matches


def build_theorem_tdg(record: dict) -> tuple[dict, list[dict], list[dict], list[dict], dict]:
    theorem = record["full_name"]
    file_path = record["file"]
    new_object, objects, producers = make_object_manager(theorem)
    nodes: list[dict] = []
    edges: list[dict] = []
    stats = Counter()

    in_node_id = f"{theorem}::in"
    out_node_id = f"{theorem}::out"
    nodes.append(asdict(TdgNode(theorem, in_node_id, "special", None, "in", "", "", None, None, "", "[]", "[]", file_path)))
    nodes.append(asdict(TdgNode(theorem, out_node_id, "special", None, "out", "", "", None, None, "", "[]", "[]", file_path)))

    initial_goals = parse_state(record["tactics"][0].get("state_before", ""))
    shared_hyp_index: dict[tuple[str, str], str] = {}
    open_goals = [initialize_goal_entry(goal, in_node_id, new_object, shared_hyp_index) for goal in initial_goals]
    nested_subproof_producer = in_node_id

    premise_objects: dict[str, str] = {}

    for tactic in record["tactics"]:
        node_id = f"{theorem}::t{tactic['index']}"
        tactic_head = extract_tactic_head(tactic.get("tactic", ""))
        before_goals = parse_state(tactic.get("state_before", ""))
        after_goals = parse_state(tactic.get("state_after", ""))
        local_refs = extract_identifier_refs(tactic.get("tactic", ""))
        resolved_premises = [premise.get("full_name", premise.get("surface_name", "")) for premise in tactic.get("premises", [])]
        raw_tactic = tactic.get("tactic", "")

        active_entry = None
        sibling_entries = []
        if before_goals:
            before_active = before_goals[0]
            active_match_index = next(
                (i for i, entry in enumerate(open_goals) if goal_match_key(entry["goal"]) == goal_match_key(before_active)),
                None,
            )
            if active_match_index is not None:
                active_entry = open_goals[active_match_index]
                remaining_entries = [entry for i, entry in enumerate(open_goals) if i != active_match_index]
            else:
                active_entry = initialize_goal_entry(before_active, nested_subproof_producer, new_object, shared_hyp_index)
                remaining_entries = list(open_goals)
                stats["resynced_active_goals"] += 1

            for sibling_goal in before_goals[1:]:
                sibling_match_index = next(
                    (i for i, entry in enumerate(remaining_entries) if goal_match_key(entry["goal"]) == goal_match_key(sibling_goal)),
                    None,
                )
                if sibling_match_index is not None:
                    sibling_entries.append(remaining_entries.pop(sibling_match_index))
                else:
                    sibling_entries.append(initialize_goal_entry(sibling_goal, nested_subproof_producer, new_object, shared_hyp_index))
                    stats["resynced_sibling_goals"] += 1
        elif open_goals:
            active_entry = open_goals[0]
            sibling_entries = open_goals[1:]
        else:
            raise RuntimeError(f"tactic {node_id} has no parseable before-goal state")

        actual_inputs = [
            {
                "object_id": active_entry["goal_object"],
                "kind": "goal",
                "slot": "goal",
                "name": active_entry["goal"].case_label or f"goal_{active_entry['goal'].index}",
            }
        ]
        edges.append(
            asdict(
                TdgEdge(
                    theorem=theorem,
                    src_node_id=producers[active_entry["goal_object"]],
                    dst_node_id=node_id,
                    edge_type="goal_to_goal",
                    label="goal->goal",
                    object_id=active_entry["goal_object"],
                    object_kind="goal",
                    confidence=0.99,
                    evidence="consumed active goal from proof state",
                )
            )
        )
        stats["goal_to_goal"] += 1

        seen_input_objects = {active_entry["goal_object"]}
        for ref in local_refs:
            if ref in active_entry["hyp_objects"]:
                object_id = active_entry["hyp_objects"][ref]
                if object_id in seen_input_objects:
                    continue
                seen_input_objects.add(object_id)
                actual_inputs.append(
                    {
                        "object_id": object_id,
                        "kind": "hypothesis",
                        "slot": "hypothesis",
                        "name": ref,
                    }
                )
                edges.append(
                    asdict(
                        TdgEdge(
                            theorem=theorem,
                            src_node_id=producers[object_id],
                            dst_node_id=node_id,
                            edge_type="hyp_to_goal",
                            label=f"{ref}->hyp",
                            object_id=object_id,
                            object_kind="hypothesis",
                            confidence=0.90,
                            evidence=f"explicit hypothesis reference `{ref}` in tactic text",
                        )
                    )
                )
                stats["hyp_to_goal"] += 1

        for premise in resolved_premises:
            if premise not in premise_objects:
                premise_objects[premise] = new_object("premise", premise, premise, in_node_id, "global_premise")
            object_id = premise_objects[premise]
            actual_inputs.append(
                {
                    "object_id": object_id,
                    "kind": "premise",
                    "slot": "premise",
                    "name": premise,
                }
            )
            edges.append(
                asdict(
                    TdgEdge(
                        theorem=theorem,
                        src_node_id=in_node_id,
                        dst_node_id=node_id,
                        edge_type="premise_use",
                        label="premise->arg",
                        object_id=object_id,
                        object_kind="premise",
                        confidence=0.75,
                        evidence="resolved premise reference",
                    )
                )
            )
            stats["premise_use"] += 1

        preserved_map = match_preserved_siblings([entry["goal"] for entry in sibling_entries], after_goals)
        new_open_goals = []
        actual_outputs = []
        produced_goal_count = 0
        for after_index, goal in enumerate(after_goals):
            if after_index in preserved_map:
                sibling_entry = sibling_entries[preserved_map[after_index]]
                new_open_goals.append(sibling_entry)
                continue
            materialized_entry, outputs = materialize_output_goal(
                theorem,
                goal,
                node_id,
                active_entry,
                new_object,
                shared_hyp_index,
            )
            new_open_goals.append(materialized_entry)
            actual_outputs.extend(outputs)
            produced_goal_count += 1

        nodes.append(
            asdict(
                TdgNode(
                    theorem=theorem,
                    node_id=node_id,
                    node_type="tactic",
                    tactic_index=tactic["index"],
                    tactic_head=tactic_head,
                    raw_tactic=tactic.get("tactic", ""),
                    annotated_tactic=tactic.get("annotated_tactic", ""),
                    num_goals_before=tactic.get("num_goals_before"),
                    num_goals_after=tactic.get("num_goals_after"),
                    active_goal_input_id=active_entry["goal_object"],
                    actual_inputs_json=json.dumps(actual_inputs, ensure_ascii=False),
                    actual_outputs_json=json.dumps(actual_outputs, ensure_ascii=False),
                    file=file_path,
                )
            )
        )

        if not after_goals:
            edges.append(
                asdict(
                    TdgEdge(
                        theorem=theorem,
                        src_node_id=node_id,
                        dst_node_id=out_node_id,
                        edge_type="goal_to_goal",
                        label="proof_complete",
                        object_id=active_entry["goal_object"],
                        object_kind="goal",
                        confidence=0.99,
                        evidence="tactic removed the last active goal and produced no new goals",
                    )
                )
            )
            stats["goal_to_goal"] += 1

        if produced_goal_count > 1:
            stats["branching_steps"] += 1
        stats["actual_input_objects"] += len(actual_inputs)
        stats["actual_output_objects"] += len(actual_outputs)
        open_goals = new_open_goals
        if "\n" in raw_tactic and "by" in raw_tactic:
            nested_subproof_producer = node_id

    theorem_graph = {
        "theorem": theorem,
        "file": file_path,
        "statement": record.get("statement", ""),
        "proof_text": record.get("proof_text", ""),
        "nodes": nodes,
        "edges": edges,
        "objects": objects,
    }
    return theorem_graph, nodes, edges, objects, dict(stats)


def write_schema() -> None:
    schema = """# Stage 1 TDG Schema

## Core principle

This TDG is built from proof states, not from raw tactic adjacency alone.

For each traced tactic application, the builder reconstructs:

- actual input goal: the active goal consumed by the tactic
- actual input hypotheses: explicitly referenced local hypotheses available in the active goal context
- actual input premises: resolved global premise references
- actual output goals: new goals appearing after the tactic, excluding preserved sibling goals
- actual output hypotheses: new local hypotheses introduced in produced goals

Each proof object is given a theorem-local id and a producer node. TDG edges are then induced by object flow:

- a goal edge exists when one tactic consumes a goal object produced by an earlier node
- a hypothesis edge exists when one tactic explicitly consumes a local hypothesis object produced earlier
- a premise edge exists when a tactic consumes a resolved premise object rooted at `in`

## Special nodes

- `in`: producer for initial proof-state goals/hypotheses and theorem-external premises
- `out`: terminal sink for completed proofs

## Edge labels

- `goal->goal`
- `<hyp_name>->hyp`
- `premise->arg`
- `proof_complete`

## Important limitation

This is still an approximation of the paper's formal input/output signatures because Lean traces do not expose tactic semantics directly. However, it is now proof-state-driven and object-level, rather than a tactic-sequence heuristic.
"""
    (DATA_DIR / "stage1_tdg_schema.md").write_text(schema, encoding="utf-8")


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    theorem_path = DATA_DIR / "stage1_tdg_by_theorem.jsonl"
    node_path = DATA_DIR / "stage1_tdg_nodes.parquet"
    edge_path = DATA_DIR / "stage1_tdg_edges.parquet"
    object_path = DATA_DIR / "stage1_tdg_objects.parquet"
    stats_path = DATA_DIR / "stage1_stats.json"

    all_nodes: list[dict] = []
    all_edges: list[dict] = []
    all_objects: list[dict] = []
    aggregate = Counter()

    with theorem_path.open("w", encoding="utf-8") as theorem_handle:
        for index, record in enumerate(iter_tactic_records(), start=1):
            theorem_graph, nodes, edges, objects, stats = build_theorem_tdg(record)
            theorem_handle.write(json.dumps(theorem_graph, ensure_ascii=False) + "\n")
            all_nodes.extend(nodes)
            all_edges.extend(edges)
            all_objects.extend(objects)
            aggregate.update(stats)
            aggregate["theorems"] += 1
            aggregate["tactic_nodes"] += len(record["tactics"])
            if index % 5000 == 0:
                print(f"processed {index} tactic proofs")

    pd.DataFrame(all_nodes).to_parquet(node_path, index=False)
    pd.DataFrame(all_edges).to_parquet(edge_path, index=False)
    pd.DataFrame(all_objects).to_parquet(object_path, index=False)

    stats = {
        "theorems": aggregate["theorems"],
        "tactic_nodes": aggregate["tactic_nodes"],
        "all_nodes": len(all_nodes),
        "all_edges": len(all_edges),
        "all_objects": len(all_objects),
        "edge_type_counts": {
            "goal_to_goal": aggregate["goal_to_goal"],
            "hyp_to_goal": aggregate["hyp_to_goal"],
            "premise_use": aggregate["premise_use"],
        },
        "branching_steps": aggregate["branching_steps"],
        "actual_input_objects": aggregate["actual_input_objects"],
        "actual_output_objects": aggregate["actual_output_objects"],
    }
    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    write_schema()
    print("Wrote proof-state-driven stage-1 TDG artifacts.")


if __name__ == "__main__":
    main()
