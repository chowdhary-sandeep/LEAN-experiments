#!/usr/bin/env python3
"""
Stage 2: Isomorphic Embedding Mining
Finds common isomorphic TDG subgraphs across the mathlib corpus.
"""
import json
import pickle
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, List, Set, Tuple, Optional
import random

# Paths
OUTPUT_DIR = Path(r"E:\LEAN-experiments\00_experiment1\4. TDG mathlib\data")

# ============================================================================
# Stage 2A: Subgraph Representation
# ============================================================================

class SubgraphPattern:
    """Represents a candidate subgraph pattern."""

    def __init__(self):
        self.nodes: List[str] = []  # tactic heads
        self.edges: List[Tuple[int, int, str]] = []  # (src_idx, dst_idx, edge_type)
        self.theorem_count: int = 0
        self.witnesses: List[Dict] = []  # List of theorem TDGs where this appears

    def to_key(self) -> str:
        """Convert to hashable key for matching."""
        nodes_tuple = tuple(self.nodes)
        edges_tuple = tuple(sorted(self.edges))
        return (nodes_tuple, edges_tuple)

    def __hash__(self):
        return hash(self.to_key())

    def __eq__(self, other):
        return self.to_key() == other.to_key()

# ============================================================================
# Stage 2B: Matching Granularity
# ============================================================================

def get_node_label(node: Dict) -> str:
    """Get the label for node matching."""
    return node.get("tactic_head", "unknown")

def get_edge_label(edge: Dict) -> str:
    """Get the label for edge matching."""
    return edge.get("edge_type", "unknown")

# ============================================================================
# Stage 2C: Candidate Generation
# ============================================================================

def extract_subgraphs(tdg: Dict, max_size: int = 5) -> List[SubgraphPattern]:
    """Extract all possible subgraphs up to max_size from a TDG."""
    nodes = tdg.get("nodes", [])
    edges = tdg.get("edges", [])

    if len(nodes) < 2:
        return []

    # Build adjacency list
    adj = defaultdict(list)
    for edge in edges:
        src = edge.get("src_node", "")
        dst = edge.get("dst_node", "")
        # Extract node indices
        src_parts = src.split("::")
        dst_parts = dst.split("::")
        if len(src_parts) >= 2 and len(dst_parts) >= 2:
            try:
                src_idx = int(src_parts[-1])
                dst_idx = int(dst_parts[-1])
                edge_type = get_edge_label(edge)
                adj[src_idx].append((dst_idx, edge_type))
            except ValueError:
                pass

    subgraphs = []

    # Generate connected subgraphs of size 2 to max_size
    for start_node in range(len(nodes)):
        # BFS to find connected nodes
        visited = {start_node}
        queue = [(start_node, [start_node], [])]  # (current, node_list, edge_list)

        while queue:
            current, node_list, edge_list = queue.pop(0)

            if len(node_list) >= 2:
                # Create subgraph pattern
                pattern = SubgraphPattern()
                pattern.nodes = [get_node_label(nodes[i]) for i in node_list]
                # Sort edges by source,dst for canonical form
                pattern.edges = sorted(edge_list, key=lambda x: (x[0], x[1]))
                subgraphs.append(pattern)

            if len(node_list) >= max_size:
                continue

            # Explore neighbors
            for neighbor, edge_type in adj[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    # Add edge from current to neighbor
                    new_edge = (current, neighbor, edge_type)
                    queue.append((neighbor, node_list + [neighbor], edge_list + [new_edge]))

    return subgraphs

def mine_patterns(tdgs: List[Dict], min_support: int = 2, max_size: int = 4) -> Dict:
    """Mine frequent subgraph patterns."""
    print(f"Mining patterns from {len(tdgs)} TDGs...")

    pattern_counts = Counter()
    pattern_witnesses = defaultdict(list)

    # Sample for efficiency
    sample_size = min(10000, len(tdgs))
    random.seed(42)
    sampled_tdgs = random.sample(tdgs, sample_size)

    print(f"Processing {sample_size} TDGs...")

    for i, tdg in enumerate(sampled_tdgs):
        if (i + 1) % 2000 == 0:
            print(f"  Processed {i + 1}/{sample_size}...")

        theorem = tdg.get("theorem", "unknown")

        # Extract subgraphs
        subgraphs = extract_subgraphs(tdg, max_size)

        # Count unique patterns (by key)
        seen_keys = set()
        for subgraph in subgraphs:
            key = subgraph.to_key()
            if key not in seen_keys:
                seen_keys.add(key)
                pattern_counts[key] += 1
                pattern_witnesses[key].append(theorem)

    # Filter by support
    print(f"\nFiltering patterns with support >= {min_support}...")

    frequent_patterns = []
    for key, count in pattern_counts.items():
        if count >= min_support:
            nodes, edges = key
            pattern = {
                "nodes": list(nodes),
                "edges": [(e[0], e[1], e[2]) for e in edges],
                "support": count,
                "theorems": pattern_witnesses[key][:5]  # Sample of witnesses
            }
            frequent_patterns.append(pattern)

    print(f"Found {len(frequent_patterns)} frequent patterns")

    return {
        "patterns": frequent_patterns,
        "total_patterns": len(frequent_patterns),
        "sample_size": sample_size,
        "min_support": min_support,
        "max_size": max_size
    }

# ============================================================================
# Stage 2E: Frequency Analysis
# ============================================================================

def analyze_support_distribution(patterns: List[Dict]) -> Dict:
    """Analyze support distribution of patterns."""
    supports = [p["support"] for p in patterns]

    return {
        "total_patterns": len(patterns),
        "min_support": min(supports) if supports else 0,
        "max_support": max(supports) if supports else 0,
        "avg_support": sum(supports) / len(supports) if supports else 0,
        "support_distribution": {
            "2": len([s for s in supports if s == 2]),
            "3-5": len([s for s in supports if 3 <= s <= 5]),
            "6-10": len([s for s in supports if 6 <= s <= 10]),
            "11+": len([s for s in supports if s >= 11])
        }
    }

# ============================================================================
# Main
# ============================================================================

def main():
    print("=" * 60)
    print("Stage 2: Isomorphic Embedding Mining")
    print("=" * 60)

    # Load TDGs
    print("\nLoading TDGs...")
    with open(OUTPUT_DIR / "stage1_tdg_by_theorem.pkl", "rb") as f:
        tdgs = pickle.load(f)
    print(f"Loaded {len(tdgs)} TDGs")

    # Mine patterns with different support thresholds
    results = {}

    for min_support in [2, 3, 5, 10]:
        print(f"\n--- Mining with min_support={min_support} ---")
        result = mine_patterns(tdgs, min_support=min_support, max_size=4)
        support_analysis = analyze_support_distribution(result["patterns"])
        result["support_analysis"] = support_analysis
        results[min_support] = result

        print(f"Patterns found: {result['total_patterns']}")
        print(f"Support distribution: {support_analysis['support_distribution']}")

    # Save results
    print("\nSaving results...")

    # Save full patterns at min_support=2
    with open(OUTPUT_DIR / "stage2_isomorphic_candidates.json", "w", encoding="utf-8") as f:
        json.dump(results[2], f, indent=2, ensure_ascii=False)

    # Save summary
    summary = {
        min_support: {
            "total_patterns": r["total_patterns"],
            "support_distribution": r["support_analysis"]["support_distribution"]
        }
        for min_support, r in results.items()
    }

    with open(OUTPUT_DIR / "stage2_mining_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\nOutputs saved:")
    print("  - stage2_isomorphic_candidates.json")
    print("  - stage2_mining_summary.json")

    # Print top patterns
    print("\n" + "=" * 60)
    print("Top 10 Patterns (min_support=2):")
    print("=" * 60)

    top_patterns = sorted(results[2]["patterns"], key=lambda x: x["support"], reverse=True)[:10]
    for i, p in enumerate(top_patterns):
        print(f"\n{i + 1}. Support: {p['support']}")
        print(f"   Nodes: {p['nodes']}")
        print(f"   Edges: {p['edges']}")
        print(f"   Sample theorems: {p['theorems'][:3]}")

    print("\n" + "=" * 60)
    print("Stage 2 Complete")
    print("=" * 60)

    return results

if __name__ == "__main__":
    main()
