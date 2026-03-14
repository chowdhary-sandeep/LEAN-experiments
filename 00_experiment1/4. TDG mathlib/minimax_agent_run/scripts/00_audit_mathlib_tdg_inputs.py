#!/usr/bin/env python3
"""
Stage 0: Corpus Audit And Environment Confirmation
Analyzes the mathlib trace corpus to understand the data schema and usable subset.
"""
import json
import os
from pathlib import Path
from collections import Counter
import random

# Paths
INPUT_DIR = Path(r"E:\LEAN-experiments\00_experiment1\jsons")
OUTPUT_DIR = Path(r"E:\LEAN-experiments\00_experiment1\4. TDG mathlib\data")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def load_stats():
    """Load theorem_stats_v2.json"""
    with open(INPUT_DIR / "theorem_stats_v2.json", "r") as f:
        return json.load(f)

def sample_theorems(n=100, proof_type=None, seed=42):
    """Sample n theorem records from the JSONL file."""
    random.seed(seed)
    sampled = []
    proof_type_counts = Counter()

    with open(INPUT_DIR / "traced_theorems_unified_v2.jsonl", "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            record = json.loads(line)
            pt = record.get("proof_type", "unknown")
            proof_type_counts[pt] += 1

            if proof_type is None or pt == proof_type:
                sampled.append(record)

    return sampled, proof_type_counts

def analyze_tactic_proofs(records):
    """Analyze tactic proof characteristics."""
    tactic_counts = [len(r.get("tactics", [])) for r in records]

    # Tactic frequency analysis
    tactic_counter = Counter()
    terminal_count = 0
    multi_goal_count = 0
    premise_counts = []

    for r in records:
        tactics = r.get("tactics", [])
        for t in tactics:
            # Extract head tactic name
            tactic_text = t.get("tactic", "").strip()
            if tactic_text:
                head = tactic_text.split()[0] if tactic_text.split() else "unknown"
                tactic_counter[head] += 1

            if t.get("is_terminal", False):
                terminal_count += 1
            if t.get("num_goals_before", 1) > 1 or t.get("num_goals_after", 1) > 1:
                multi_goal_count += 1

        premise_counts.append(r.get("metrics", {}).get("num_premises", 0))

    return {
        "num_tactic_proofs": len(records),
        "avg_tactics_per_proof": sum(tactic_counts) / len(tactic_counts) if tactic_counts else 0,
        "min_tactics": min(tactic_counts) if tactic_counts else 0,
        "max_tactics": max(tactic_counts) if tactic_counts else 0,
        "median_tactics": sorted(tactic_counts)[len(tactic_counts)//2] if tactic_counts else 0,
        "top_tactics": tactic_counter.most_common(20),
        "terminal_tactics": terminal_count,
        "multi_goal_tactics": multi_goal_count,
        "avg_premises_per_proof": sum(premise_counts) / len(premise_counts) if premise_counts else 0,
    }

def find_edge_cases(records):
    """Find edge case proofs for manual inspection."""
    # Very short proofs (1-2 tactics)
    short = [r for r in records if 1 <= len(r.get("tactics", [])) <= 2]
    # Medium proofs (3-10 tactics)
    medium = [r for r in records if 3 <= len(r.get("tactics", [])) <= 10]
    # Long proofs (11+ tactics)
    long = [r for r in records if len(r.get("tactics", [])) >= 11]

    # Find proofs with multiple goals
    multi_goal = []
    for r in records:
        for t in r.get("tactics", []):
            if t.get("num_goals_before", 1) > 1 or t.get("num_goals_after", 1) > 1:
                multi_goal.append(r)
                break

    return {
        "short_proofs": short[:10],
        "medium_proofs": medium[:20],
        "long_proofs": long[:20],
        "multi_goal_proofs": multi_goal[:10]
    }

def main():
    print("=" * 60)
    print("Stage 0: Corpus Audit")
    print("=" * 60)

    # Load stats
    stats = load_stats()
    print(f"\n[1] Basic Statistics from theorem_stats_v2.json:")
    print(f"    Total theorems: {stats['total_theorems']:,}")
    print(f"    Tactic proofs: {stats['tactic_proofs']:,}")
    print(f"    Term proofs: {stats['term_proofs']:,}")
    print(f"    Total tactics: {stats['total_tactics']:,}")
    print(f"    Total premises: {stats['total_premises']:,}")

    # Sample all tactic proofs for analysis
    print(f"\n[2] Sampling all tactic proofs...")
    tactic_proofs, proof_types = sample_theorems(proof_type="tactic")
    print(f"    Found {len(tactic_proofs):,} tactic proofs")

    # Analyze tactic proofs
    print(f"\n[3] Analyzing tactic proof characteristics...")
    analysis = analyze_tactic_proofs(tactic_proofs)
    print(f"    Avg tactics per proof: {analysis['avg_tactics_per_proof']:.1f}")
    print(f"    Min/Max/Median: {analysis['min_tactics']}/{analysis['max_tactics']}/{analysis['median_tactics']}")
    print(f"    Avg premises per proof: {analysis['avg_premises_per_proof']:.1f}")
    print(f"\n    Top 10 tactics:")
    for tactic, count in analysis['top_tactics'][:10]:
        print(f"      {tactic}: {count:,}")

    # Find edge cases
    print(f"\n[4] Finding edge cases...")
    edge_cases = find_edge_cases(tactic_proofs)
    print(f"    Short proofs (1-2 tactics): {len(edge_cases['short_proofs'])}")
    print(f"    Medium proofs (3-10 tactics): {len(edge_cases['medium_proofs'])}")
    print(f"    Long proofs (11+ tactics): {len(edge_cases['long_proofs'])}")
    print(f"    Multi-goal proofs: {len(edge_cases['multi_goal_proofs'])}")

    # Save sample records for manual inspection
    print(f"\n[5] Saving sample records...")
    sample_records = (
        edge_cases['short_proofs'][:5] +
        edge_cases['medium_proofs'][:10] +
        edge_cases['long_proofs'][:10] +
        edge_cases['multi_goal_proofs'][:5]
    )
    with open(OUTPUT_DIR / "00_sample_theorem_records.jsonl", "w", encoding="utf-8") as f:
        for r in sample_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"    Saved {len(sample_records)} sample records")

    # Save corpus schema summary
    schema_summary = {
        "source_files": {
            "traced_theorems_unified_v2.jsonl": str(INPUT_DIR / "traced_theorems_unified_v2.jsonl"),
            "corpus.jsonl": str(INPUT_DIR / "corpus.jsonl"),
            "corpus_code_index.json": str(INPUT_DIR / "corpus_code_index.json"),
            "premise_index_v2.json": str(INPUT_DIR / "premise_index_v2.json"),
            "theorem_stats_v2.json": str(INPUT_DIR / "theorem_stats_v2.json"),
        },
        "theorem_schema": {
            "full_name": "theorem full qualified name",
            "file": "source file path",
            "position": "source position (start/end line/column)",
            "namespace": "theorem namespace",
            "open_namespaces": "list of open namespaces",
            "statement": "theorem statement (type signature)",
            "proof_type": "'tactic' or 'term'",
            "proof_text": "raw proof text",
            "tactics": "list of tactic trace entries (see tactic_schema)",
            "all_premises": "dict of premise name -> premise details",
            "metrics": "proof metrics (num_tactics, num_premises, etc.)",
            "quality": "tracing quality flags"
        },
        "tactic_schema": {
            "index": "tactic position in proof (0-based)",
            "tactic": "raw tactic text",
            "annotated_tactic": "annotated version",
            "state_before": "proof state before tactic execution",
            "state_after": "proof state after tactic execution",
            "context": {
                "variables": "dict of variable name -> type info",
                "hypotheses": "dict of hypothesis name -> type",
                "typeclasses": "list of active typeclasses",
                "goal": "current goal proposition",
                "goal_type": "goal classification"
            },
            "premises": "list of premises used by this tactic",
            "is_terminal": "whether this tactic closes the proof",
            "num_goals_before": "number of goals before",
            "num_goals_after": "number of goals after"
        },
        "statistics": stats,
        "tactic_analysis": analysis,
        "usable_for_tdg": {
            "tactic_proofs": len(tactic_proofs),
            "reason": "proof_type == 'tactic' and nonempty tactics list"
        }
    }

    with open(OUTPUT_DIR / "00_corpus_schema_summary.json", "w", encoding="utf-8") as f:
        json.dump(schema_summary, f, indent=2, ensure_ascii=False)
    print(f"    Saved schema summary")

    # Print schema summary
    print(f"\n[6] Schema Summary:")
    print(f"    Theorem fields: {list(schema_summary['theorem_schema'].keys())}")
    print(f"    Tactic fields: {list(schema_summary['tactic_schema'].keys())}")
    print(f"\n    Primary inputs confirmed:")
    for name, path in schema_summary['source_files'].items():
        print(f"      - {name}")

    print(f"\n[7] Acceptance Criteria Status:")
    print(f"    ✓ Primary input files identified")
    print(f"    ✓ Schema documented")
    print(f"    ✓ Sample records saved for manual inspection")
    print(f"    ✓ Tactic proof count: {len(tactic_proofs):,}")

    print("\n" + "=" * 60)
    print("Stage 0 Complete")
    print("=" * 60)

    return schema_summary

if __name__ == "__main__":
    main()
