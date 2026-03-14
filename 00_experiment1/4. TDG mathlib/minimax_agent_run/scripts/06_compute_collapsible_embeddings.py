#!/usr/bin/env python3
"""
Stage 3: Collapsible Embedding Identification
Filters stage 2 patterns to find those satisfying the paper's collapsibility conditions.
"""
import json
import pickle
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Optional

# Paths
OUTPUT_DIR = Path(r"E:\LEAN-experiments\00_experiment1\4. TDG mathlib\data")

# ============================================================================
# Stage 3: Collapsibility Conditions
# ============================================================================

def check_path_closure(pattern_nodes: List[int], host_edges: List[Tuple[int, int, str]]) -> bool:
    """
    Check path closure condition:
    If two matched nodes have an intermediate path node in the host TDG,
    that intermediate node must also lie inside the embedding.
    """
    if not host_edges:
        return True

    # Build adjacency list for host
    host_adj = defaultdict(list)
    for src, dst, _ in host_edges:
        host_adj[src].append(dst)

    pattern_set = set(pattern_nodes)

    # Get all node indices that exist
    all_nodes = set()
    for src, dst, _ in host_edges:
        all_nodes.add(src)
        all_nodes.add(dst)

    # For each pair of pattern nodes, check if there's a path through non-pattern nodes
    for i, node_i in enumerate(pattern_nodes):
        for node_j in pattern_nodes[i+1:]:
            # BFS to find if there's a path through non-pattern nodes
            if node_i not in host_adj:
                continue

            visited = {node_i}
            queue = [node_i]
            found_intermediate = False

            while queue and not found_intermediate:
                current = queue.pop(0)
                for neighbor in host_adj.get(current, []):
                    if neighbor not in visited:
                        if neighbor not in pattern_set and neighbor in all_nodes:
                            # Found intermediate node
                            found_intermediate = True
                            break
                        visited.add(neighbor)
                        queue.append(neighbor)

            if found_intermediate:
                # Check if there's a direct edge between pattern nodes
                if node_j not in host_adj.get(node_i, []):
                    # Path closure violated
                    return False

    return True

def check_internal_edge_completeness(pattern_nodes: List[int], pattern_edges: List[Tuple], host_edges: List[Tuple[int, int, str]]) -> bool:
    """
    Check internal edge completeness:
    If host TDG contains an edge between two matched host nodes,
    the candidate must also contain the corresponding edge.
    """
    # Get pattern node set
    pattern_set = set(pattern_nodes)

    # Build host edge set between pattern nodes
    host_internal_edges = set()
    for src, dst, label in host_edges:
        if src in pattern_set and dst in pattern_set:
            host_internal_edges.add((src, dst, label))

    # Check if all host internal edges are in pattern
    for edge in host_internal_edges:
        src, dst, label = edge
        # Find if there's a corresponding edge in pattern
        found = False
        for p_edge in pattern_edges:
            p_src, p_dst, p_label = p_edge
            if p_src == src and p_dst == dst and p_label == label:
                found = True
                break
        if not found:
            return False

    return True

def check_collapsibility(pattern: Dict, host_tdg: Dict) -> Tuple[bool, str]:
    """
    Check if a pattern embedding satisfies collapsibility.

    Returns (is_collapsible, reason)
    """
    pattern_nodes = list(range(len(pattern["nodes"])))
    pattern_edges = pattern.get("edges", [])
    host_edges = host_tdg.get("edges", [])

    # Convert host edges to simpler format
    host_edge_tuples = []
    for edge in host_edges:
        src = edge.get("src_node", "")
        dst = edge.get("dst_node", "")
        edge_type = edge.get("edge_type", "")

        src_parts = src.split("::")
        dst_parts = dst.split("::")

        if len(src_parts) >= 2 and len(dst_parts) >= 2:
            try:
                src_idx = int(src_parts[-1])
                dst_idx = int(dst_parts[-1])
                host_edge_tuples.append((src_idx, dst_idx, edge_type))
            except ValueError:
                pass

    # Check path closure
    if not check_path_closure(pattern_nodes, host_edge_tuples):
        return False, "path_closure_violation"

    # Check internal edge completeness
    if not check_internal_edge_completeness(pattern_nodes, pattern_edges, host_edge_tuples):
        return False, "internal_edge_incomplete"

    return True, "collapsible"

def compute_collapsibility(tdgs: List[Dict], patterns: List[Dict], min_support: int = 3) -> Dict:
    """Compute collapsibility for all pattern embeddings."""
    print(f"Computing collapsibility for {len(patterns)} patterns...")

    # Build TDG lookup
    tdg_lookup = {tdg["theorem"]: tdg for tdg in tdgs}

    results = {
        "collapsible": [],
        "non_collapsible": [],
        "stats": {
            "total_checked": 0,
            "collapsible_count": 0,
            "non_collapsible_count": 0,
            "by_reason": defaultdict(int)
        }
    }

    for i, pattern in enumerate(patterns):
        if pattern["support"] < min_support:
            continue

        pattern_nodes = pattern["nodes"]
        pattern_edges = pattern["edges"]

        # Check each witness theorem
        collapsible_count = 0
        non_collapsible_by_reason = defaultdict(int)

        for theorem_name in pattern.get("theorems", []):
            if theorem_name not in tdg_lookup:
                continue

            host_tdg = tdg_lookup[theorem_name]
            is_collapsible, reason = check_collapsibility(pattern, host_tdg)

            results["stats"]["total_checked"] += 1

            if is_collapsible:
                collapsible_count += 1
            else:
                non_collapsible_by_reason[reason] += 1
                results["stats"]["by_reason"][reason] += 1

        # If majority are collapsible, add to collapsible list
        total_checked = collapsible_count + sum(non_collapsible_by_reason.values())
        if total_checked > 0 and collapsible_count > 0:
            if collapsible_count / total_checked >= 0.5:  # At least 50% collapsible
                results["collapsible"].append({
                    "pattern": pattern,
                    "collapsible_ratio": collapsible_count / total_checked,
                    "checked_count": total_checked
                })
                results["stats"]["collapsible_count"] += 1
            else:
                results["non_collapsible"].append({
                    "pattern": pattern,
                    "reasons": dict(non_collapsible_by_reason)
                })
                results["stats"]["non_collapsible_count"] += 1

        if (i + 1) % 500 == 0:
            print(f"  Processed {i + 1}/{len(patterns)} patterns...")

    print(f"\nCollapsible patterns: {results['stats']['collapsible_count']}")
    print(f"Non-collapsible patterns: {results['stats']['non_collapsible_count']}")
    print(f"Failure reasons: {dict(results['stats']['by_reason'])}")

    return results

# ============================================================================
# Main
# ============================================================================

def main():
    print("=" * 60)
    print("Stage 3: Collapsible Embedding Identification")
    print("=" * 60)

    # Load TDGs
    print("\nLoading TDGs...")
    with open(OUTPUT_DIR / "stage1_tdg_by_theorem.pkl", "rb") as f:
        tdgs = pickle.load(f)
    print(f"Loaded {len(tdgs)} TDGs")

    # Load patterns
    print("\nLoading patterns...")
    with open(OUTPUT_DIR / "stage2_isomorphic_candidates.json", "r", encoding="utf-8") as f:
        patterns_data = json.load(f)
    patterns = patterns_data.get("patterns", [])
    print(f"Loaded {len(patterns)} patterns")

    # Compute collapsibility
    results = compute_collapsibility(tdgs, patterns, min_support=3)

    # Save results
    print("\nSaving results...")

    with open(OUTPUT_DIR / "stage3_collapsible_candidates.json", "w", encoding="utf-8") as f:
        # Convert to JSON-serializable format
        output = {
            "collapsible": [
                {
                    "pattern": r["pattern"],
                    "collapsible_ratio": r["collapsible_ratio"],
                    "checked_count": r["checked_count"]
                }
                for r in results["collapsible"]
            ],
            "stats": {
                "collapsible_count": results["stats"]["collapsible_count"],
                "non_collapsible_count": results["stats"]["non_collapsible_count"],
                "by_reason": dict(results["stats"]["by_reason"])
            }
        }
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("\nOutputs saved:")
    print("  - stage3_collapsible_candidates.json")

    # Print top collapsible patterns
    print("\n" + "=" * 60)
    print("Top 10 Collapsible Patterns:")
    print("=" * 60)

    collapsible_sorted = sorted(results["collapsible"], key=lambda x: x["collapsible_ratio"], reverse=True)[:10]
    for i, item in enumerate(collapsible_sorted):
        p = item["pattern"]
        print(f"\n{i + 1}. {p['nodes']} -> {p['nodes']}")
        print(f"   Edges: {p['edges']}")
        print(f"   Support: {p['support']}, Ratio: {item['collapsible_ratio']:.2f}")

    print("\n" + "=" * 60)
    print("Stage 3 Complete")
    print("=" * 60)

    return results

if __name__ == "__main__":
    main()
