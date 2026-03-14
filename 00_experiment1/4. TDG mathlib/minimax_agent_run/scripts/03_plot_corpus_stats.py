#!/usr/bin/env python3
"""
Stage 1 Visualization: Generate corpus summary plots
"""
import json
import pickle
from pathlib import Path
from collections import Counter
import random

# Paths
OUTPUT_DIR = Path(r"E:\LEAN-experiments\00_experiment1\4. TDG mathlib\data")
FIGS_DIR = Path(r"E:\LEAN-experiments\00_experiment1\4. TDG mathlib\figs")
FIGS_DIR.mkdir(parents=True, exist_ok=True)

# Load TDGs (sample for efficiency)
print("Loading TDGs...")
with open(OUTPUT_DIR / "stage1_tdg_by_theorem.pkl", "rb") as f:
    tdgs = pickle.load(f)

print(f"Loaded {len(tdgs)} TDGs")

# Sample for analysis
random.seed(42)
sample = random.sample(tdgs, min(5000, len(tdgs)))

# Collect statistics
proof_sizes = []
node_counts = []
edge_counts = []
tactic_heads = Counter()
edge_types = Counter()

for tdg in sample:
    proof_sizes.append(tdg.get("num_tactics", 0))
    node_counts.append(len(tdg.get("nodes", [])))
    edge_counts.append(len(tdg.get("edges", [])))

    for node in tdg.get("nodes", []):
        tactic_heads[node.get("tactic_head", "unknown")] += 1

    for edge in tdg.get("edges", []):
        edge_types[edge.get("edge_type", "unknown")] += 1

# Print summary
print("\n" + "=" * 60)
print("Corpus Statistics")
print("=" * 60)

print(f"\nProof Size Distribution:")
print(f"  Min: {min(proof_sizes)}")
print(f"  Max: {max(proof_sizes)}")
print(f"  Avg: {sum(proof_sizes)/len(proof_sizes):.1f}")

print(f"\nNode Count Distribution:")
print(f"  Min: {min(node_counts)}")
print(f"  Max: {max(node_counts)}")
print(f"  Avg: {sum(node_counts)/len(node_counts):.1f}")

print(f"\nEdge Count Distribution:")
print(f"  Min: {min(edge_counts)}")
print(f"  Max: {max(edge_counts)}")
print(f"  Avg: {sum(edge_counts)/len(edge_counts):.1f}")

print(f"\nTop 10 Tactic Heads:")
for head, count in tactic_heads.most_common(10):
    print(f"  {head}: {count}")

print(f"\nEdge Types:")
for edge_type, count in edge_types.most_common():
    print(f"  {edge_type}: {count}")

# Save summary
summary = {
    "proof_sizes": {
        "min": min(proof_sizes),
        "max": max(proof_sizes),
        "avg": sum(proof_sizes)/len(proof_sizes),
        "median": sorted(proof_sizes)[len(proof_sizes)//2]
    },
    "node_counts": {
        "min": min(node_counts),
        "max": max(node_counts),
        "avg": sum(node_counts)/len(node_counts)
    },
    "edge_counts": {
        "min": min(edge_counts),
        "max": max(edge_counts),
        "avg": sum(edge_counts)/len(edge_counts)
    },
    "tactic_heads": dict(tactic_heads.most_common(20)),
    "edge_types": dict(edge_types)
}

with open(FIGS_DIR / "corpus_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print(f"\nSaved to: {FIGS_DIR / 'corpus_summary.json'}")
