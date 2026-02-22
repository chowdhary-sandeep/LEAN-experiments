"""
Search Proof Dynamics: Adjacent Possible in Mathematical Discovery

Analyzes how the space of discoverable theorems evolves as knowledge accumulates.
Based on: papers/experiment2_plan_simple_discovery_process.md

Experiments implemented:
1. Adjacent Possible Dynamics - How |A_t| evolves under different strategies
2. Temporal Accessibility vs Discovery - Dilution factors and discovery timing
3. Pathway Diversity - Bottleneck identification
5. Strategy Comparison - BFS, Random, Greedy
6. Memory-Constrained Discovery - Coverage vs memory size
"""

import json
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict, deque
import networkx as nx
import random
from tqdm import tqdm

# Configuration
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_FILE = SCRIPT_DIR / "jsons" / "traced_theorems_unified_v2.jsonl"
CACHE_BUNDLE = SCRIPT_DIR / "cache" / "bundle.pkl"
OUTPUT_JSON = SCRIPT_DIR / "experiment2_search_proof_results.json"

print("="*80)
print("SEARCH PROOF DYNAMICS: Adjacent Possible Analysis")
print("="*80)

# Load theorem DAG
print("\nLoading theorem dependency DAG...")
with open(CACHE_BUNDLE, "rb") as f:
    bundle = pickle.load(f)

G = bundle["G_original"]
print(f"  Loaded graph: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")

# ALL nodes are theorems (edge A→B means "B uses A in its proof")
all_theorems = set(G.nodes())
print(f"  Total theorems: {len(all_theorems):,}")

# Find all root nodes (in-degree 0) from all connected components
# These are the starting "known" theorems that enable discovery of downstream theorems
root_nodes = [n for n in all_theorems if G.in_degree(n) == 0]
print(f"  Root nodes (in-degree 0): {len(root_nodes):,}")

# Check connectivity
num_components = nx.number_weakly_connected_components(G)
print(f"  Weakly connected components: {num_components}")

# Get roots from each component
roots_by_component = []
for component in nx.weakly_connected_components(G):
    component_roots = [n for n in component if G.in_degree(n) == 0]
    if component_roots:
        roots_by_component.extend(component_roots)

print(f"  Roots covering all components: {len(roots_by_component):,}")

# Use all roots as starting axioms
axioms = root_nodes
print(f"  Starting axioms (all roots): {len(axioms):,}")

# OPTIMIZATION: Pre-cache all prerequisite sets
print("\nPre-caching prerequisite sets for all theorems...")
prereq_cache = {}
for node in all_theorems:
    prereq_cache[node] = set(G.predecessors(node))
print(f"  Cached {len(prereq_cache):,} prerequisite sets")

# Update global variable
theorem_nodes = all_theorems

results = {}

# ============================================================================
# EXPERIMENT 1: Adjacent Possible Dynamics
# ============================================================================
print("\n" + "="*80)
print("EXPERIMENT 1: Adjacent Possible Dynamics")
print("="*80)

def get_prerequisites(theorem):
    """Get all prerequisites of a theorem (cached)."""
    return prereq_cache.get(theorem, set())

def compute_adjacent_possible(known_set):
    """
    Compute adjacent possible: theorems whose ALL prerequisites are in known_set
    but which are not themselves in known_set.
    OPTIMIZED: Uses cached prerequisites.
    """
    adjacent = set()
    for node in theorem_nodes:
        if node in known_set:
            continue
        prereqs = prereq_cache.get(node, set())
        if prereqs.issubset(known_set):
            adjacent.add(node)
    return adjacent

# INCREMENTAL ADJACENT POSSIBLE (for discovery strategies)
class IncrementalAdjacentPossible:
    """
    Maintains adjacent possible incrementally as theorems are discovered.
    Much more efficient: O(1) updates instead of O(n) recomputation.
    """
    def __init__(self, theorem_nodes, prereq_cache):
        self.theorem_nodes = theorem_nodes
        self.prereq_cache = prereq_cache

        # Precompute total prerequisites count for each theorem
        self.total_prereqs = {t: len(prereq_cache.get(t, set())) for t in theorem_nodes}

        # Track how many prerequisites have been discovered
        self.prereqs_met = {t: 0 for t in theorem_nodes}

        # The current adjacent possible set
        self.adjacent = set()

        # Known theorems
        self.known = set()

    def initialize(self, axioms):
        """Initialize with axioms."""
        self.known = set(axioms)
        self.adjacent = set()

        # Mark axioms as having all prereqs met
        for ax in axioms:
            self.prereqs_met[ax] = self.total_prereqs.get(ax, 0)

        # Check all theorems to build initial A_t
        for thm in self.theorem_nodes:
            if thm in self.known:
                continue
            # Count how many prereqs are in axioms
            prereqs = self.prereq_cache.get(thm, set())
            met = sum(1 for p in prereqs if p in self.known)
            self.prereqs_met[thm] = met

            if met == self.total_prereqs[thm] and self.total_prereqs[thm] > 0:
                self.adjacent.add(thm)
            elif self.total_prereqs[thm] == 0 and thm not in self.known:
                # Axioms not yet in known
                self.adjacent.add(thm)

    def discover(self, theorem):
        """
        Discover a theorem: remove from A_t, add to known, update A_t.
        Returns the new adjacent possible set.
        """
        if theorem not in self.adjacent:
            # Axiom or already discovered
            if theorem in self.known:
                return self.adjacent
        else:
            self.adjacent.remove(theorem)

        self.known.add(theorem)

        # Update all THEOREM successors (theorems that depend on this one)
        try:
            all_successors = G.successors(theorem)
            # Only update theorem nodes (not premises)
            successors = [s for s in all_successors if s in self.theorem_nodes]
        except nx.NetworkXError:
            successors = []

        for succ in successors:
            if succ in self.known:
                continue

            # Increment prereqs_met counter
            self.prereqs_met[succ] += 1

            # Check if now accessible
            if self.prereqs_met[succ] == self.total_prereqs[succ]:
                self.adjacent.add(succ)

        return self.adjacent

    def get_adjacent(self):
        """Return current adjacent possible."""
        return self.adjacent.copy()

    def get_known(self):
        """Return known theorems."""
        return self.known.copy()

def expansion_factor(theorem, known_set):
    """
    How many new theorems enter adjacent possible after adding theorem?
    OPTIMIZED: Only checks theorems that could be affected (descendants of theorem).
    """
    # Only theorems that have 'theorem' as a prerequisite could enter A_t
    # when 'theorem' is added to known_set
    new_accessible = 0
    try:
        potential = set(G.successors(theorem))  # Direct descendants only
    except nx.NetworkXError:
        return 0

    for candidate in potential:
        if candidate in known_set:
            continue
        prereqs = prereq_cache.get(candidate, set())
        # Check if adding 'theorem' makes all prereqs known
        if prereqs.issubset(known_set | {theorem}) and not prereqs.issubset(known_set):
            new_accessible += 1

    return new_accessible

# Strategy 1: BFS (Breadth-First Search) - INCREMENTAL
def discover_bfs(axioms, max_steps=5000):
    """BFS discovery starting from axioms. Uses incremental A_t updates."""
    iap = IncrementalAdjacentPossible(theorem_nodes, prereq_cache)
    iap.initialize(axioms)

    trajectory = []
    step = 0

    while step < max_steps:
        A_t = iap.get_adjacent()
        trajectory.append({
            'step': step,
            'known': len(iap.known),
            'adjacent': len(A_t)
        })

        if not A_t:
            break

        # Discover all accessible theorems (BFS level)
        for thm in list(A_t):  # Copy to avoid modification during iteration
            iap.discover(thm)

        step += 1

    return trajectory, iap.get_known()

# Strategy 2: Random Walk - INCREMENTAL
def discover_random(axioms, max_steps=5000, seed=42):
    """Random walk: uniformly sample from A_t at each step. Uses incremental A_t."""
    random.seed(seed)
    iap = IncrementalAdjacentPossible(theorem_nodes, prereq_cache)
    iap.initialize(axioms)

    trajectory = []

    for step in range(max_steps):
        A_t = iap.get_adjacent()
        trajectory.append({
            'step': step,
            'known': len(iap.known),
            'adjacent': len(A_t)
        })

        if not A_t:
            break

        # Randomly pick one theorem from A_t
        chosen = random.choice(list(A_t))
        iap.discover(chosen)

    return trajectory, iap.get_known()

# Strategy 3: Greedy Expansion - INCREMENTAL
def discover_greedy(axioms, max_steps=5000):
    """Greedy: pick theorem from A_t that maximizes |A_{t+1}|. Uses incremental A_t."""
    iap = IncrementalAdjacentPossible(theorem_nodes, prereq_cache)
    iap.initialize(axioms)

    trajectory = []

    for step in range(max_steps):
        A_t = iap.get_adjacent()
        trajectory.append({
            'step': step,
            'known': len(iap.known),
            'adjacent': len(A_t)
        })

        if not A_t:
            break

        # Pick theorem with max expansion
        best_theorem = None
        best_expansion = -1

        # Sample subset if A_t is large
        sample_size = min(100, len(A_t))
        candidates = random.sample(list(A_t), sample_size)

        for candidate in candidates:
            exp = expansion_factor(candidate, iap.known)
            if exp > best_expansion:
                best_expansion = exp
                best_theorem = candidate

        iap.discover(best_theorem)

    return trajectory, iap.get_known()

print("\nRunning BFS discovery (no time limit, runs to completion)...")
bfs_traj, bfs_known = discover_bfs(axioms, max_steps=999999)
print(f"  BFS: Discovered {len(bfs_known):,} theorems in {len(bfs_traj)} steps")

print("\nRunning Random Walk discovery (timestep budget: 50,000)...")
random_traj, random_known = discover_random(axioms, max_steps=50000)
print(f"  Random: Discovered {len(random_known):,} theorems in {len(random_traj)} steps")

print("\nRunning Greedy Expansion discovery (timestep budget: 10,000)...")
greedy_traj, greedy_known = discover_greedy(axioms, max_steps=10000)
print(f"  Greedy: Discovered {len(greedy_known):,} theorems in {len(greedy_traj)} steps")

results['experiment1_adjacent_possible'] = {
    'bfs': bfs_traj,
    'random': random_traj,
    'greedy': greedy_traj,
    'summary': {
        'bfs_coverage': len(bfs_known) / len(theorem_nodes),
        'random_coverage': len(random_known) / len(theorem_nodes),
        'greedy_coverage': len(greedy_known) / len(theorem_nodes),
    }
}

# ============================================================================
# EXPERIMENT 2: Temporal Accessibility vs Discovery
# ============================================================================
print("\n" + "="*80)
print("EXPERIMENT 2: Temporal Accessibility vs Discovery")
print("="*80)

def compute_accessibility_times_bfs(axioms):
    """When does each theorem first enter adjacent possible (BFS optimal)?"""
    iap = IncrementalAdjacentPossible(theorem_nodes, prereq_cache)
    iap.initialize(axioms)

    accessibility = {}
    for axiom in axioms:
        accessibility[axiom] = 0

    step = 0
    while True:
        A_t = iap.get_adjacent()
        if not A_t:
            break

        for thm in A_t:
            if thm not in accessibility:
                accessibility[thm] = step + 1

        # Discover all accessible
        for thm in list(A_t):
            iap.discover(thm)

        step += 1

    return accessibility

def compute_dilution_factors(axioms, accessibility):
    """
    Dilution factor: |A_t| when theorem first enters adjacent possible.
    High dilution = many alternatives, harder to find.
    """
    iap = IncrementalAdjacentPossible(theorem_nodes, prereq_cache)
    iap.initialize(axioms)

    dilution = {}

    step = 0
    while True:
        A_t = iap.get_adjacent()
        if not A_t:
            break

        for thm in A_t:
            if thm not in dilution:
                dilution[thm] = len(A_t)

        # Discover all accessible
        for thm in list(A_t):
            iap.discover(thm)

        step += 1

    return dilution

print("\nComputing accessibility times (BFS optimal)...")
accessibility = compute_accessibility_times_bfs(axioms)
print(f"  Computed for {len(accessibility):,} theorems")

print("\nComputing dilution factors...")
dilution = compute_dilution_factors(axioms, accessibility)
print(f"  Mean dilution: {np.mean(list(dilution.values())):.1f}")
print(f"  Median dilution: {np.median(list(dilution.values())):.1f}")
print(f"  Max dilution: {max(dilution.values()):,}")

results['experiment2_accessibility'] = {
    'accessibility_stats': {
        'mean': np.mean(list(accessibility.values())),
        'median': np.median(list(accessibility.values())),
        'max': max(accessibility.values())
    },
    'dilution_stats': {
        'mean': np.mean(list(dilution.values())),
        'median': np.median(list(dilution.values())),
        'max': max(dilution.values())
    },
    'accessibility_distribution': list(accessibility.values())[:1000],  # Sample
    'dilution_distribution': list(dilution.values())[:1000]  # Sample
}

# ============================================================================
# EXPERIMENT 3: Pathway Diversity and Bottlenecks
# ============================================================================
print("\n" + "="*80)
print("EXPERIMENT 3: Pathway Diversity and Bottlenecks")
print("="*80)

def removal_impact(theorem):
    """
    Fraction of downstream theorems that become unreachable if theorem is removed.
    OPTIMIZED: Copies graph once, finds all reachable in one traversal.
    """
    # Get all descendants
    try:
        descendants = nx.descendants(G, theorem)
    except nx.NetworkXError:
        return 0.0

    if not descendants:
        return 0.0

    # OPTIMIZATION: Copy graph ONCE, then find all reachable from axioms
    G_copy = G.copy()
    G_copy.remove_node(theorem)

    # Find all nodes reachable from any axiom in ONE traversal
    reachable = set()
    for axiom in axioms:
        if axiom in G_copy:
            try:
                reachable.update(nx.descendants(G_copy, axiom))
                reachable.add(axiom)
            except nx.NetworkXError:
                pass

    # Count how many descendants are NOT reachable
    unreachable = len(descendants - reachable)

    return unreachable / len(descendants) if descendants else 0.0

print("\nComputing removal impacts (sampling 500 theorems)...")
sample_theorems = random.sample(list(theorem_nodes), min(500, len(theorem_nodes)))
removal_impacts = {}

for thm in tqdm(sample_theorems, desc="Removal impact"):
    removal_impacts[thm] = removal_impact(thm)

print(f"  Mean removal impact: {np.mean(list(removal_impacts.values())):.3f}")
print(f"  Max removal impact: {max(removal_impacts.values()):.3f}")

# Identify top bottlenecks
top_bottlenecks = sorted(removal_impacts.items(), key=lambda x: x[1], reverse=True)[:20]
print(f"\nTop 10 Bottleneck Theorems:")
for i, (thm, impact) in enumerate(top_bottlenecks[:10], 1):
    short_name = thm.split('.')[-1][:40] if '.' in thm else thm[:40]
    print(f"  {i:2d}. {short_name:40s} - {impact:.3f} downstream impact")

results['experiment3_bottlenecks'] = {
    'removal_impact_stats': {
        'mean': np.mean(list(removal_impacts.values())),
        'median': np.median(list(removal_impacts.values())),
        'max': max(removal_impacts.values())
    },
    'top_bottlenecks': [
        {'theorem': thm, 'impact': impact}
        for thm, impact in top_bottlenecks[:20]
    ],
    'removal_impact_distribution': list(removal_impacts.values())
}

# ============================================================================
# EXPERIMENT 6: Memory-Constrained Discovery
# ============================================================================
print("\n" + "="*80)
print("EXPERIMENT 6: Memory-Constrained Discovery")
print("="*80)

def discover_with_memory(axioms, memory_size, max_steps=3000, seed=42):
    """
    Discovery with bounded memory: theorem enters A_t only if all prerequisites
    are in last K discovered theorems.
    """
    random.seed(seed)
    known = set(axioms)
    memory = deque(axioms, maxlen=memory_size)
    discovered_count = len(axioms)

    for step in range(max_steps):
        # Adjacent possible given current memory
        A_t = set()
        memory_set = set(memory)  # Convert once for faster subset checks
        for node in theorem_nodes:
            if node in known:
                continue
            prereqs = prereq_cache.get(node, set())
            # Check if all prereqs in memory
            if prereqs.issubset(memory_set):
                A_t.add(node)

        if not A_t:
            break

        # Pick random theorem
        chosen = random.choice(list(A_t))
        known.add(chosen)
        memory.append(chosen)
        discovered_count += 1

    coverage = discovered_count / len(theorem_nodes)
    return coverage

print("\nTesting memory-constrained discovery...")
# Test: infinite (all visited), K=10000, K=1000, K=100
memory_sizes = [999999, 10000, 1000, 100]  # 999999 = effectively infinite
memory_labels = ['infinite', '10000', '1000', '100']
memory_results = []

for K, label in zip(memory_sizes, memory_labels):
    print(f"  Memory size K={label}...")
    # Reduced timestep budget for efficiency (was 100000)
    coverage = discover_with_memory(axioms, K, max_steps=10000)
    memory_results.append({'memory_size': K, 'memory_label': label, 'coverage': coverage})
    print(f"    Coverage: {coverage:.3f}")

results['experiment6_memory_constrained'] = {
    'memory_coverage': memory_results,
    'interpretation': "Phase transition analysis: does coverage jump sharply at critical K?"
}

# Save results
print("\n" + "="*80)
print("SAVING RESULTS")
print("="*80)

with open(OUTPUT_JSON, 'w') as f:
    json.dump(results, f, indent=2)

print(f"Saved results to: {OUTPUT_JSON}")

# Print summary
print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"\nExperiment 1 - Adjacent Possible Dynamics:")
print(f"  BFS coverage: {results['experiment1_adjacent_possible']['summary']['bfs_coverage']:.3f}")
print(f"  Random coverage: {results['experiment1_adjacent_possible']['summary']['random_coverage']:.3f}")
print(f"  Greedy coverage: {results['experiment1_adjacent_possible']['summary']['greedy_coverage']:.3f}")

print(f"\nExperiment 2 - Accessibility:")
print(f"  Mean accessibility time: {results['experiment2_accessibility']['accessibility_stats']['mean']:.1f} steps")
print(f"  Mean dilution factor: {results['experiment2_accessibility']['dilution_stats']['mean']:.1f} alternatives")

print(f"\nExperiment 3 - Bottlenecks:")
print(f"  Mean removal impact: {results['experiment3_bottlenecks']['removal_impact_stats']['mean']:.3f}")
print(f"  Top bottleneck: {top_bottlenecks[0][0].split('.')[-1]} ({top_bottlenecks[0][1]:.3f})")

print(f"\nExperiment 6 - Memory:")
print(f"  Coverage at K=infinite: {memory_results[0]['coverage']:.3f}")
print(f"  Coverage at K=10000: {memory_results[1]['coverage']:.3f}")
print(f"  Coverage at K=1000: {memory_results[2]['coverage']:.3f}")
print(f"  Coverage at K=100: {memory_results[3]['coverage']:.3f}")

print("\n" + "="*80)
print("ANALYSIS COMPLETE")
print("="*80)
