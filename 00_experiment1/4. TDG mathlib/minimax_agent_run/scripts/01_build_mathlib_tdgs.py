#!/usr/bin/env python3
"""
Stage 1: TDG Construction for mathlib
Builds Tactic Dependency Graphs from traced theorem proofs.
"""
import json
import re
import pickle
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Set, Optional, Any
import uuid

# Paths
INPUT_DIR = Path(r"E:\LEAN-experiments\00_experiment1\jsons")
OUTPUT_DIR = Path(r"E:\LEAN-experiments\00_experiment1\4. TDG mathlib\data")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# Stage 1B: Tactic Normalization
# ============================================================================

def extract_tactic_head(tactic_text: str) -> str:
    """Extract the head tactic name from tactic text."""
    if not tactic_text:
        return "unknown"

    # Remove leading whitespace and get first token
    tactic_text = tactic_text.strip()
    tokens = tactic_text.split()

    if not tokens:
        return "unknown"

    head = tokens[0]

    # Common tactic variations
    if head in {'rw', 'simp', 'exact', 'apply', 'intro', 'refine', 'have', 'let', 'show', 'assume'}:
        return head
    if head in {'obtain', 'rcases', 'cases', 'induction', 'destruct'}:
        return head
    if head in {'by', 'have', 'suffices', 'suffices_to_show'}:
        return head
    if head in {'calc', 'ring', 'omega', 'linarith', 'decide'}:
        return head
    if head in {'sorry', 'admit'}:
        return head
    if head == '·':  # Bullet point
        return "bullet"
    if head in {'/', '|', '&', '-', '+', '*'}:  # Tactical operators
        return "tactical"

    return head

def normalize_tactic(tactic_text: str) -> Dict[str, str]:
    """Normalize a tactic for matching purposes."""
    head = extract_tactic_head(tactic_text)
    return {
        "raw": tactic_text.strip(),
        "head": head,
        "normalized": head  # Could add more normalization later
    }

# ============================================================================
# Stage 1C: Proof State Parsing
# ============================================================================

def parse_goal(goal_text: str) -> Dict[str, Any]:
    """Parse a goal/proof state into structured form."""
    if not goal_text:
        return {"type": "none", "target": "", "local_declarations": {}}

    lines = goal_text.strip().split('\n')

    # Extract target (line with ⊢) and everything before it is local declarations
    target = ""
    local_declarations = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Goal marker
        if '⊢' in line:
            # This is the target
            target = line.split('⊢', 1)[1].strip()
        # Variable/hypothesis declaration (e.g., "R : Type u" or "h : P")
        elif ':' in line and not line.startswith('⊢'):
            # Parse as name : type
            # Skip instance declarations (inst✝, inst✝¹, etc.)
            if not line.startswith('inst'):
                match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_′]*)', line)
                if match:
                    decl_name = match.group(1)
                    decl_type = line.split(':', 1)[1].strip() if ':' in line else ""
                    local_declarations[decl_name] = decl_type

    return {
        "type": "goal",
        "target": target,
        "local_declarations": local_declarations
    }

def compute_goal_diff(state_before: str, state_after: str) -> Dict[str, Any]:
    """Compute the diff between before/after states."""
    before = parse_goal(state_before)
    after = parse_goal(state_after)

    # Local declarations added/removed
    before_decls = set(before.get("local_declarations", {}).keys())
    after_decls = set(after.get("local_declarations", {}).keys())

    added_decls = after_decls - before_decls
    removed_decls = before_decls - after_decls
    kept_decls = before_decls & after_decls

    # Target changed?
    target_changed = before.get("target", "") != after.get("target", "")

    return {
        "added_declarations": list(added_decls),
        "removed_declarations": list(removed_decls),
        "kept_declarations": list(kept_decls),
        "target_changed": target_changed,
        "before_state": before,
        "after_state": after
    }

# ============================================================================
# Stage 1D: Input/Output Inference
# ============================================================================

def infer_tactic_io(tactic_text: str, state_diff: Dict, premises: List[Dict]) -> Dict[str, Any]:
    """Infer the inputs and outputs of a tactic."""
    head = extract_tactic_head(tactic_text)

    inputs = set()
    outputs = set()

    # From state diff - local declarations
    inputs.update(state_diff.get("kept_declarations", []))
    outputs.update(state_diff.get("added_declarations", []))

    # From tactic text - extract referenced names (simple heuristic)
    tactic_clean = re.sub(r'\[.*?\]', '', tactic_text)  # Remove bracket args
    tactic_clean = re.sub(r'\(.*?\)', '', tactic_clean)  # Remove paren args

    # From premises - collect premise names
    premise_names = []
    for p in premises:
        if isinstance(p, dict) and "surface_name" in p:
            premise_names.append(p["surface_name"])

    return {
        "head": head,
        "inputs": list(inputs),
        "outputs": list(outputs),
        "premise_refs": premise_names,
        "target_changed": state_diff.get("target_changed", False)
    }

# ============================================================================
# Stage 1E: TDG Edge Building
# ============================================================================

def build_tdg(theorem_record: Dict) -> Dict:
    """Build a TDG for a single theorem."""
    full_name = theorem_record.get("full_name", "unknown")
    file_path = theorem_record.get("file", "")
    proof_text = theorem_record.get("proof_text", "")
    tactics = theorem_record.get("tactics", [])

    if not tactics:
        return None

    # Create nodes
    nodes = []
    for i, t in enumerate(tactics):
        state_before = t.get("state_before", "")
        state_after = t.get("state_after", "")

        # Compute state diff
        state_diff = compute_goal_diff(state_before, state_after)

        # Normalize tactic
        norm = normalize_tactic(t.get("tactic", ""))

        # Infer IO
        io = infer_tactic_io(
            t.get("tactic", ""),
            state_diff,
            t.get("premises", [])
        )

        node = {
            "node_id": f"{full_name}::{i}",
            "theorem": full_name,
            "file": file_path,
            "tactic_index": i,
            "raw_tactic": t.get("tactic", ""),
            "normalized_tactic": norm["normalized"],
            "tactic_head": norm["head"],
            "num_goals_before": t.get("num_goals_before", 1),
            "num_goals_after": t.get("num_goals_after", 1),
            "is_terminal": t.get("is_terminal", False),
            "state_before": state_before,
            "state_after": state_after,
            "context": t.get("context", {}),
            "premises": t.get("premises", []),
            "inputs": io["inputs"],
            "outputs": io["outputs"],
            "premise_refs": io["premise_refs"],
            "target_changed": io["target_changed"]
        }
        nodes.append(node)

    # Create edges based on hypothesis flow
    edges = []

    # Track hypothesis -> node that introduces it
    hyp_introduced_by = {}  # hyp_name -> node_id

    # First pass: track hypothesis introduction
    for node in nodes:
        for hyp in node.get("outputs", []):
            hyp_introduced_by[hyp] = node["node_id"]

    # Second pass: create edges
    for i, node in enumerate(nodes):
        # Check if node uses hypotheses from earlier nodes
        for hyp in node.get("inputs", []):
            if hyp in hyp_introduced_by:
                src_node = hyp_introduced_by[hyp]
                if src_node != node["node_id"]:
                    edges.append({
                        "src_node": src_node,
                        "dst_node": node["node_id"],
                        "edge_type": "hyp_to_goal",
                        "label": f"hyp:{hyp}",
                        "confidence": 0.8,
                        "evidence": f"hypothesis {hyp} produced by {src_node}, used by {node['node_id']}"
                    })

    # Add premise use edges
    for node in nodes:
        for prem in node.get("premise_refs", []):
            edges.append({
                "src_node": f"premise:{prem}",
                "dst_node": node["node_id"],
                "edge_type": "premise_use",
                "label": f"premise:{prem}",
                "confidence": 0.7,
                "evidence": f"premise {prem} used in {node['node_id']}"
            })

    # Add goal flow edges (simplified)
    # If a tactic changes the target, it creates a new goal state
    for i in range(len(nodes) - 1):
        if nodes[i].get("target_changed", False):
            edges.append({
                "src_node": nodes[i]["node_id"],
                "dst_node": nodes[i+1]["node_id"],
                "edge_type": "goal_to_goal",
                "label": "goal_flow",
                "confidence": 0.6,
                "evidence": "target changed between states"
            })

    return {
        "theorem": full_name,
        "file": file_path,
        "proof_text": proof_text,
        "num_tactics": len(nodes),
        "num_edges": len(edges),
        "nodes": nodes,
        "edges": edges
    }

# ============================================================================
# Main Pipeline
# ============================================================================

def process_theorems(input_file: Path, output_dir: Path, limit: Optional[int] = None):
    """Process all theorem records and build TDGs."""
    tdgs = []
    stats = {
        "total_processed": 0,
        "tactic_proofs": 0,
        "empty_proofs": 0,
        "errors": 0,
        "node_count": 0,
        "edge_count": 0
    }

    print(f"Processing theorems from {input_file}...")

    with open(input_file, "r", encoding="utf-8", errors="replace") as f:
        for line_num, line in enumerate(f):
            if limit and line_num >= limit:
                break

            try:
                record = json.loads(line)

                # Filter: tactic proofs only
                if record.get("proof_type") != "tactic":
                    continue

                # Skip empty tactics
                if not record.get("tactics"):
                    stats["empty_proofs"] += 1
                    continue

                stats["tactic_proofs"] += 1

                # Build TDG
                tdg = build_tdg(record)

                if tdg:
                    tdgs.append(tdg)
                    stats["node_count"] += tdg["num_tactics"]
                    stats["edge_count"] += tdg["num_edges"]

                stats["total_processed"] += 1

                if (line_num + 1) % 5000 == 0:
                    print(f"  Processed {line_num + 1} records, built {len(tdgs)} TDGs...")

            except Exception as e:
                stats["errors"] += 1
                if stats["errors"] < 5:
                    print(f"  Error: {e}")

    print(f"\nProcessed {stats['total_processed']} records")
    print(f"  Tactic proofs: {stats['tactic_proofs']}")
    print(f"  TDGs built: {len(tdgs)}")
    print(f"  Total nodes: {stats['node_count']}")
    print(f"  Total edges: {stats['edge_count']}")
    print(f"  Errors: {stats['errors']}")

    return tdgs, stats

def save_outputs(tdgs: List[Dict], stats: Dict, output_dir: Path):
    """Save TDG outputs to files."""

    # Save as JSONL
    print(f"\nSaving TDGs to {output_dir}...")
    with open(output_dir / "stage1_tdg_by_theorem.jsonl", "w", encoding="utf-8") as f:
        for tdg in tdgs:
            f.write(json.dumps(tdg, ensure_ascii=False) + "\n")

    # Save as pickle for efficient loading
    with open(output_dir / "stage1_tdg_by_theorem.pkl", "wb") as f:
        pickle.dump(tdgs, f)

    # Save stats
    with open(output_dir / "stage1_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    # Save schema
    schema = {
        "tdg_schema": {
            "theorem": "theorem full name",
            "file": "source file path",
            "proof_text": "raw proof text",
            "num_tactics": "number of tactic nodes",
            "num_edges": "number of dependency edges",
            "nodes": "list of tactic nodes",
            "edges": "list of dependency edges"
        },
        "node_schema": {
            "node_id": "unique node identifier",
            "theorem": "theorem full name",
            "file": "source file path",
            "tactic_index": "position in proof (0-based)",
            "raw_tactic": "raw tactic text",
            "normalized_tactic": "normalized tactic for matching",
            "tactic_head": "head tactic name (rw, simp, etc.)",
            "num_goals_before": "goals before execution",
            "num_goals_after": "goals after execution",
            "is_terminal": "whether this tactic closes proof",
            "state_before": "proof state before",
            "state_after": "proof state after",
            "context": "variables, hypotheses, typeclasses, goal",
            "premises": "list of premise references",
            "inputs": "inferred input hypotheses",
            "outputs": "inferred output hypotheses",
            "premise_refs": "premise names used",
            "target_changed": "whether goal target changed"
        },
        "edge_schema": {
            "src_node": "source node ID",
            "dst_node": "destination node ID",
            "edge_type": "goal_to_goal|hyp_to_goal|premise_use",
            "label": "human-readable label",
            "confidence": "confidence score 0-1",
            "evidence": "why this edge exists"
        }
    }

    with open(output_dir / "stage1_tdg_schema.md", "w", encoding="utf-8") as f:
        f.write("# Stage 1 TDG Schema\n\n")
        for section, content in schema.items():
            f.write(f"## {section}\n")
            f.write("```json\n")
            f.write(json.dumps(content, indent=2))
            f.write("\n```\n\n")

    print("Outputs saved:")
    print(f"  - stage1_tdg_by_theorem.jsonl")
    print(f"  - stage1_tdg_by_theorem.pkl")
    print(f"  - stage1_stats.json")
    print(f"  - stage1_tdg_schema.md")

def main():
    print("=" * 60)
    print("Stage 1: TDG Construction")
    print("=" * 60)

    input_file = INPUT_DIR / "traced_theorems_unified_v2.jsonl"

    # Process theorems
    tdgs, stats = process_theorems(input_file, OUTPUT_DIR, limit=None)

    # Save outputs
    save_outputs(tdgs, stats, OUTPUT_DIR)

    print("\n" + "=" * 60)
    print("Stage 1 Complete")
    print("=" * 60)

    return tdgs, stats

if __name__ == "__main__":
    main()
