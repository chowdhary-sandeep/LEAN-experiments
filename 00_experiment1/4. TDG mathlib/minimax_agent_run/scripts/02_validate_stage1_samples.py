#!/usr/bin/env python3
"""
Stage 1 Manual Validation: Sample TDGs for manual inspection
Performs agentic raw-data check to validate TDG construction.
"""
import json
import pickle
import random
from pathlib import Path
from collections import Counter

# Paths
OUTPUT_DIR = Path(r"E:\LEAN-experiments\00_experiment1\4. TDG mathlib\data")
REPORT_DIR = Path(r"E:\LEAN-experiments\00_experiment1\4. TDG mathlib\reports")

# Load TDGs (use pickle for efficiency)
print("Loading TDGs...")
with open(OUTPUT_DIR / "stage1_tdg_by_theorem.pkl", "rb") as f:
    tdgs = pickle.load(f)

print(f"Loaded {len(tdgs)} TDGs")

# Stratify by proof size
tiny = [t for t in tdgs if t["num_tactics"] <= 2]
medium = [t for t in tdgs if 3 <= t["num_tactics"] <= 10]
large = [t for t in tdgs if t["num_tactics"] >= 11]

print(f"\nSize distribution:")
print(f"  Tiny (1-2 tactics): {len(tiny)}")
print(f"  Medium (3-10): {len(medium)}")
print(f"  Large (11+): {len(large)}")

# Sample stratified
random.seed(42)
sample_size = {"tiny": 10, "medium": 20, "large": 20}

tiny_sample = random.sample(tiny, min(sample_size["tiny"], len(tiny)))
medium_sample = random.sample(medium, min(sample_size["medium"], len(medium)))
large_sample = random.sample(large, min(sample_size["large"], len(large)))

all_samples = tiny_sample + medium_sample + large_sample
print(f"\nTotal validation samples: {len(all_samples)}")

# Save sample TDGs
print("\nSaving sample TDGs...")
with open(OUTPUT_DIR / "stage1_validation_samples.jsonl", "w", encoding="utf-8") as f:
    for tdg in all_samples:
        f.write(json.dumps(tdg, ensure_ascii=False) + "\n")

# Analyze edge types
edge_types = Counter()
tactic_heads = Counter()
confidence_scores = []

for tdg in all_samples:
    for edge in tdg.get("edges", []):
        edge_types[edge.get("edge_type", "unknown")] += 1
        confidence_scores.append(edge.get("confidence", 0))

    for node in tdg.get("nodes", []):
        tactic_heads[node.get("tactic_head", "unknown")] += 1

print(f"\nEdge type distribution (validation sample):")
for etype, count in edge_types.most_common():
    print(f"  {etype}: {count}")

print(f"\nTactic head distribution (validation sample):")
for head, count in tactic_heads.most_common(10):
    print(f"  {head}: {count}")

print(f"\nConfidence scores:")
if confidence_scores:
    print(f"  Mean: {sum(confidence_scores)/len(confidence_scores):.3f}")
    print(f"  Min: {min(confidence_scores):.3f}")
    print(f"  Max: {max(confidence_scores):.3f}")

# Generate validation report
print("\nGenerating validation report...")

report = {
    "sample_count": len(all_samples),
    "samples_by_size": {
        "tiny": len(tiny_sample),
        "medium": len(medium_sample),
        "large": len(large_sample)
    },
    "edge_types": dict(edge_types),
    "tactic_heads": dict(tactic_heads.most_common(20)),
    "confidence_stats": {
        "mean": sum(confidence_scores)/len(confidence_scores) if confidence_scores else 0,
        "min": min(confidence_scores) if confidence_scores else 0,
        "max": max(confidence_scores) if confidence_scores else 0
    },
    "node_correctness_checklist": [
        "Each node has unique node_id",
        "Each node has tactic_index matching position",
        "Each node has raw_tactic and normalized_tactic",
        "Each node has state_before and state_after",
        "Each node has inputs and outputs inferred"
    ],
    "edge_correctness_checklist": [
        "hyp_to_goal edges connect hypothesis producer to consumer",
        "premise_use edges reference actual premises",
        "goal_to_goal edges track target changes"
    ]
}

with open(REPORT_DIR / "stage1_manual_validation.json", "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

print("Validation samples saved to: stage1_validation_samples.jsonl")
print("Report saved to: reports/stage1_manual_validation.json")

# Print first sample as example
print("\n" + "=" * 60)
print("Example TDG (first in sample):")
print("=" * 60)
if all_samples:
    example = all_samples[0]
    print(f"\nTheorem: {example['theorem']}")
    print(f"File: {example['file']}")
    print(f"Proof: {example['proof_text'][:200]}...")
    print(f"\nNodes ({example['num_tactics']}):")
    for i, node in enumerate(example['nodes'][:3]):
        print(f"  [{i}] {node['tactic_head']}: {node['raw_tactic'][:60]}")
        print(f"       inputs: {node.get('inputs', [])}, outputs: {node.get('outputs', [])}")
    print(f"  ... ({example['num_tactics'] - 3} more)")
    print(f"\nEdges ({example['num_edges']}):")
    for edge in example['edges'][:5]:
        print(f"  {edge['src_node'][-30:]} -> {edge['dst_node'][-30:]}")
        print(f"    type: {edge['edge_type']}, confidence: {edge['confidence']}")
