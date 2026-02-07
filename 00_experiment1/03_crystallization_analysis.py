"""
Crystallization Analysis: Find Co-Occurring Premise Patterns

Analyzes the theorem-premise DAG to find sets of premises (theorems) that
frequently co-occur across multiple proofs. These are "crystallization candidates" -
premise combinations that could be abstracted into new lemmas.

Uses the network constructed by 00_theorem_premise_network.py
"""

import json
import pickle
import networkx as nx
from pathlib import Path
from collections import defaultdict, Counter
from itertools import combinations
import matplotlib.pyplot as plt
import numpy as np

# Configuration
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_FILE = SCRIPT_DIR / "jsons" / "traced_theorems_unified_v2.jsonl"
CACHE_BUNDLE = SCRIPT_DIR / "cache" / "bundle.pkl"
FIGS_DIR = SCRIPT_DIR / "figs"
PLAN_FILE = SCRIPT_DIR / "papers" / "0_plan.md"

FIGS_DIR.mkdir(exist_ok=True)

# Tactic/hypothesis filter (copied from 00_theorem_premise_network.py)
TACTIC_OR_HYP_FILTER = frozenset({
    # Common tactics
    "simpa", "symm", "rwa", "mpr", "mp", "rfl", "refl", "simp", "rw", "apply", "exact",
    "intro", "intros", "refine", "cases", "rcases", "obtain", "induction", "constructor",
    "ring", "linarith", "omega", "trivial", "decide", "aesop", "ext", "congr", "have",
    "show", "from", "by", "left", "right", "split", "contrapose", "push_neg", "norm_num",
    "positivity", "polyrith", "nlinarith", "field_simp", "assumption", "tidy", "omega",
    "gcongr", "rel_simp", "erw", "rwa", "era", "convert", "ac_rfl", "native_decide",
    # Hypothesis / local names
    "hx", "hf", "hs", "ha", "hb", "hc", "hd", "he", "hh", "hi", "hj", "hk", "hl", "hm",
    "hn", "ho", "hp", "hq", "hr", "ht", "hu", "hv", "hw", "hy", "hz", "h1", "h2", "h3",
    "ih", "IH", "this", "that",
})

def is_tactic_or_hyp(name):
    """True if premise name is a tactic or hypothesis pattern."""
    if not name:
        return True
    suffix = name.split(".")[-1].strip()
    return suffix.lower() in TACTIC_OR_HYP_FILTER


def load_dag_from_cache():
    """Load the theorem-premise DAG from cache."""
    print("="*70)
    print("LOADING THEOREM-PREMISE DAG")
    print("="*70)

    if not CACHE_BUNDLE.exists():
        print(f"ERROR: Cache not found at {CACHE_BUNDLE}")
        print("Please run 00_theorem_premise_network.py first to build the DAG.")
        return None

    print(f"Loading from cache: {CACHE_BUNDLE}")
    with open(CACHE_BUNDLE, "rb") as f:
        bundle = pickle.load(f)

    G = bundle["G_original"]
    print(f"\nLoaded DAG:")
    print(f"  Nodes: {G.number_of_nodes():,}")
    print(f"  Edges: {G.number_of_edges():,}")

    return G


def extract_theorem_premise_sets(data_file):
    """
    Extract premise sets for each theorem from the JSONL.
    Returns: dict mapping theorem_name -> set of premise names
    """
    print("\n" + "="*70)
    print("EXTRACTING PREMISE SETS FROM THEOREMS")
    print("="*70)

    theorem_premises = {}
    total_theorems = 0
    tactic_theorems = 0

    with open(data_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            total_theorems += 1

            # Only process tactic proofs
            if entry.get("proof_type") != "tactic":
                continue

            tactic_theorems += 1
            theorem_name = entry.get("full_name")
            if not theorem_name:
                continue

            # Get all premises (filter out tactics/hypotheses)
            all_premises = entry.get("all_premises", {})
            premise_set = {
                p for p in all_premises.keys()
                if p and not is_tactic_or_hyp(p)
            }

            if premise_set:
                theorem_premises[theorem_name] = premise_set

    print(f"\nProcessed {total_theorems:,} total theorems")
    print(f"  Tactic proofs: {tactic_theorems:,}")
    print(f"  Theorems with premises: {len(theorem_premises):,}")
    print(f"  Avg premises per theorem: {np.mean([len(p) for p in theorem_premises.values()]):.1f}")

    return theorem_premises


def find_frequent_premise_sets(theorem_premises, min_set_size=2, max_set_size=5, min_support=5):
    """
    Find frequent premise co-occurrence patterns (itemsets) using efficient algorithm.

    Args:
        theorem_premises: dict of theorem -> set of premises
        min_set_size: minimum premise set size to consider (must be >=2)
        max_set_size: maximum premise set size to consider
        min_support: minimum number of theorems a pattern must appear in

    Returns:
        dict mapping premise_set (frozenset) -> list of theorem names using it
    """
    print("\n" + "="*70)
    print("MINING FREQUENT PREMISE CO-OCCURRENCE PATTERNS")
    print("="*70)
    print(f"  Min set size: {min_set_size}")
    print(f"  Max set size: {max_set_size}")
    print(f"  Min support: {min_support} theorems")

    # Start with size-2 patterns only (most efficient)
    print(f"\n  Step 1: Mining premise pairs (size 2)...")
    pattern_support = defaultdict(list)

    total_theorems_processed = 0
    for theorem_name, premise_set in theorem_premises.items():
        # Only generate size-2 combinations (pairs)
        if len(premise_set) >= 2:
            for premise_combo in combinations(sorted(premise_set), 2):
                pattern = frozenset(premise_combo)
                pattern_support[pattern].append(theorem_name)

        total_theorems_processed += 1
        if total_theorems_processed % 10000 == 0:
            print(f"    Processed {total_theorems_processed:,} theorems...")

    print(f"\n  Total theorems processed: {total_theorems_processed:,}")
    print(f"  Unique size-2 patterns: {len(pattern_support):,}")

    # Filter by minimum support
    frequent_patterns = {
        pattern: theorems
        for pattern, theorems in pattern_support.items()
        if len(theorems) >= min_support
    }

    print(f"  Frequent size-2 patterns (>={min_support} support): {len(frequent_patterns):,}")

    # Optionally expand to size-3 if requested and if we have frequent pairs
    if max_set_size >= 3 and frequent_patterns:
        print(f"\n  Step 2: Mining premise triples (size 3) from frequent pairs...")

        # Only expand frequent pairs to triples
        size3_patterns = defaultdict(list)
        count = 0

        for theorem_name, premise_set in theorem_premises.items():
            if len(premise_set) >= 3:
                # Generate size-3 combinations
                for premise_combo in combinations(sorted(premise_set), 3):
                    pattern = frozenset(premise_combo)
                    # Only keep if all size-2 subsets are frequent
                    subsets_frequent = all(
                        frozenset(sub) in frequent_patterns
                        for sub in combinations(premise_combo, 2)
                    )
                    if subsets_frequent:
                        size3_patterns[pattern].append(theorem_name)

            count += 1
            if count % 10000 == 0:
                print(f"    Processed {count:,} theorems...")

        # Add frequent size-3 patterns
        frequent_size3 = {
            pattern: theorems
            for pattern, theorems in size3_patterns.items()
            if len(theorems) >= min_support
        }

        print(f"  Frequent size-3 patterns: {len(frequent_size3):,}")
        frequent_patterns.update(frequent_size3)

    print(f"\n  Total frequent patterns: {len(frequent_patterns):,}")
    return frequent_patterns


def compute_crystallization_value(pattern, theorems_using):
    """
    Compute compression gain from crystallizing a premise pattern.

    If k theorems each use m premises {P1, P2, ..., Pm}, we could create
    a lemma L that proves the common consequence. Then:
    - Each theorem replaces m premise uses with 1 lemma use: saves m-1 per theorem
    - We pay m premise uses once to define L
    - Net savings: k*(m-1) - m = k*m - k - m

    Args:
        pattern: frozenset of premise names
        theorems_using: list of theorem names using this pattern

    Returns:
        savings: net premise references saved
    """
    m = len(pattern)  # number of premises in pattern
    k = len(theorems_using)  # number of theorems using pattern

    # Savings per theorem: (m-1) premise refs (replace m with 1 lemma)
    # Cost to define lemma: m premise refs
    savings = k * (m - 1) - m

    return savings


def analyze_crystallization_candidates(frequent_patterns):
    """
    Analyze and rank crystallization candidates by compression value.
    """
    print("\n" + "="*70)
    print("COMPUTING CRYSTALLIZATION VALUES")
    print("="*70)

    candidates = []

    for pattern, theorems in frequent_patterns.items():
        savings = compute_crystallization_value(pattern, theorems)

        if savings > 0:
            candidates.append({
                'pattern': pattern,
                'size': len(pattern),
                'support': len(theorems),
                'savings': savings,
                'theorems': theorems
            })

    # Sort by savings
    candidates.sort(key=lambda x: x['savings'], reverse=True)

    print(f"\nCandidates with positive savings: {len(candidates):,}")
    if candidates:
        total_savings = sum(c['savings'] for c in candidates)
        print(f"Total premise savings: {total_savings:,}")

        print(f"\nTop 20 Crystallization Candidates:")
        for i, c in enumerate(candidates[:20], 1):
            # Show pattern (truncate if too long)
            pattern_str = ', '.join(sorted([p.split('.')[-1][:20] for p in c['pattern']])[:3])
            if len(c['pattern']) > 3:
                pattern_str += f", ... (+{len(c['pattern'])-3} more)"

            print(f"  {i:2d}. [{c['size']} premises, {c['support']:3d} theorems] "
                  f"saves {c['savings']:4d} refs: {{{pattern_str}}}")

    return candidates


def plot_crystallization_landscape(candidates, save_path):
    """Visualize crystallization analysis results."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Crystallization Analysis: Premise Co-Occurrence Patterns',
                 fontsize=16, fontweight='bold', family='monospace')

    if not candidates:
        fig.text(0.5, 0.5, 'No crystallization candidates found',
                ha='center', va='center', fontsize=20)
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        return

    # 1. Pattern size distribution
    ax = axes[0, 0]
    sizes = [c['size'] for c in candidates]
    ax.hist(sizes, bins=range(min(sizes), max(sizes)+2), edgecolor='black', color='white', align='left')
    ax.set_xlabel('Premise Set Size', fontsize=10, family='monospace')
    ax.set_ylabel('Frequency', fontsize=10, family='monospace')
    ax.set_title('A. Pattern Size Distribution', fontsize=11, family='monospace', fontweight='bold')
    ax.grid(True, alpha=0.3)

    # 2. Support vs Savings
    ax = axes[0, 1]
    supports = [c['support'] for c in candidates[:1000]]
    savings = [c['savings'] for c in candidates[:1000]]
    ax.scatter(supports, savings, s=10, alpha=0.5, color='black')
    ax.set_xlabel('Support (# theorems)', fontsize=10, family='monospace')
    ax.set_ylabel('Compression Savings', fontsize=10, family='monospace')
    ax.set_title('B. Support vs Compression Value', fontsize=11, family='monospace', fontweight='bold')
    ax.grid(True, alpha=0.3)

    # 3. Top 15 by savings
    ax = axes[1, 0]
    top_15 = candidates[:15]
    labels = [f"S{c['size']}" for c in top_15]
    savings_vals = [c['savings'] for c in top_15]
    y_pos = np.arange(len(labels))
    ax.barh(y_pos, savings_vals, edgecolor='black', color='white')
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=8, family='monospace')
    ax.set_xlabel('Premise References Saved', fontsize=10, family='monospace')
    ax.set_title('C. Top 15 Crystallization Candidates', fontsize=11, family='monospace', fontweight='bold')
    ax.grid(True, alpha=0.3, axis='x')
    ax.invert_yaxis()

    # 4. Cumulative savings
    ax = axes[1, 1]
    cumulative = np.cumsum([c['savings'] for c in candidates])
    x = np.arange(1, len(cumulative) + 1)
    ax.plot(x, cumulative, 'k-', linewidth=2)
    ax.set_xlabel('Number of Patterns', fontsize=10, family='monospace')
    ax.set_ylabel('Cumulative Savings', fontsize=10, family='monospace')
    ax.set_title('D. Cumulative Compression Gain', fontsize=11, family='monospace', fontweight='bold')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"\nSaved crystallization landscape to: {save_path}")
    plt.close()


def inspect_top_candidates(candidates, theorem_premises, top_n=5):
    """Manually inspect top crystallization candidates."""
    print("\n" + "="*70)
    print(f"MANUAL INSPECTION: TOP {top_n} CRYSTALLIZATION CANDIDATES")
    print("="*70)

    for i, c in enumerate(candidates[:top_n], 1):
        print(f"\n{i}. Crystallization Candidate:")
        print(f"   Premise set size: {c['size']}")
        print(f"   Support: {c['support']} theorems")
        print(f"   Compression savings: {c['savings']} premise references")

        # Show premises
        print(f"   Premises:")
        for p in sorted(c['pattern']):
            short_name = p.split('.')[-1]
            print(f"     - {short_name}")

        # Show sample theorems using this pattern
        print(f"   Sample theorems using this pattern (first 3):")
        for thm in c['theorems'][:3]:
            # Safe ASCII encoding
            short_thm = thm.split('.')[-1].encode('ascii', 'replace').decode('ascii')
            total_premises = len(theorem_premises.get(thm, set()))
            print(f"     - {short_thm} (uses {total_premises} total premises)")


def main():
    """Run crystallization analysis."""
    print("="*70)
    print("CRYSTALLIZATION ANALYSIS: PREMISE CO-OCCURRENCE PATTERNS")
    print("Following theorem-premise DAG from 00_theorem_premise_network.py")
    print("="*70)

    # Load DAG (optional - mainly for validation)
    G = load_dag_from_cache()
    if G is None:
        print("\nWARNING: Could not load DAG from cache. Proceeding with JSONL analysis.")

    # Extract premise sets from theorems
    theorem_premises = extract_theorem_premise_sets(DATA_FILE)

    # Mine frequent premise patterns
    frequent_patterns = find_frequent_premise_sets(
        theorem_premises,
        min_set_size=2,
        max_set_size=5,
        min_support=2
    )

    # Compute crystallization values
    candidates = analyze_crystallization_candidates(frequent_patterns)

    # Manual inspection
    if candidates:
        inspect_top_candidates(candidates, theorem_premises, top_n=5)

    # Visualize
    plot_path = FIGS_DIR / "crystallization_premise_cooccurrence.png"
    plot_crystallization_landscape(candidates, plot_path)

    # Summary
    print("\n" + "="*70)
    print("CRYSTALLIZATION ANALYSIS COMPLETE")
    print("="*70)
    if candidates:
        total_savings = sum(c['savings'] for c in candidates)
        print(f"Found {len(candidates):,} crystallization candidates")
        print(f"Total premise savings: {total_savings:,} references")
        print(f"Figure saved to: {plot_path}")
    else:
        print("No crystallization candidates found with positive savings.")


if __name__ == "__main__":
    main()
