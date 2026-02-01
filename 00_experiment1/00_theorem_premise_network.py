"""DAG Network Analysis from traced_theorems_unified_v2.jsonl - theorem to premises relationships."""

import json
import networkx as nx
from pathlib import Path
from collections import defaultdict, Counter
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import numpy as np
import sys
import io
import time
import os
from functools import lru_cache

# Try to import tqdm for progress bar, fallback to simple progress
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    def tqdm(iterable, desc="", total=None):
        return iterable

# Set UTF-8 encoding for stdout on Windows (skip in Jupyter - stdout has no .buffer)
if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Configuration: load from jsons/ next to this script, save PDF/PNG in script dir
_SCRIPT_DIR = Path(__file__).resolve().parent
_DATA_DIR = _SCRIPT_DIR / "jsons"
DATA_FILE = str(_DATA_DIR / "traced_theorems_unified_v2.jsonl")
OUTPUT_PDF = str(_SCRIPT_DIR / "theorem_premise_network_analysis.pdf")
OUTPUT_PNG = str(_SCRIPT_DIR / "theorem_premise_network_analysis.png")

# Tactic names and hypothesis patterns to exclude from "premises" (not real lemmas)
TACTIC_OR_HYP_FILTER = frozenset({
    # Common tactics
    "simpa", "symm", "rwa", "mpr", "mp", "rfl", "refl", "simp", "rw", "apply", "exact",
    "intro", "intros", "refine", "cases", "rcases", "obtain", "induction", "constructor",
    "ring", "linarith", "omega", "trivial", "decide", "aesop", "ext", "congr", "have",
    "show", "from", "by", "left", "right", "split", "contrapose", "push_neg", "norm_num",
    "positivity", "polyrith", "nlinarith", "field_simp", "assumption", "tidy", "omega",
    "gcongr", "rel_simp", "erw", "rwa", "era", "convert", "ac_rfl", "native_decide",
    # Hypothesis / local names (h + letter(s))
    "hx", "hf", "hs", "ha", "hb", "hc", "hd", "he", "hh", "hi", "hj", "hk", "hl", "hm",
    "hn", "ho", "hp", "hq", "hr", "ht", "hu", "hv", "hw", "hy", "hz", "h1", "h2", "h3",
    "ih", "IH", "this", "that",
})
def _is_tactic_or_hyp(name):
    """True if premise name (or its suffix) is a known tactic or hypothesis pattern."""
    if not name:
        return True
    suffix = name.split(".")[-1].strip()
    return suffix.lower() in TACTIC_OR_HYP_FILTER

print("=" * 80)
print("Loading theorem-premise data...")
print("=" * 80)
start_time = time.time()

# First, count total lines for progress bar
print("Counting lines in file...")
total_lines = 0
with open(DATA_FILE, "r", encoding="utf-8") as f:
    for _ in f:
        total_lines += 1
print(f"  Total lines: {total_lines:,}")

# Build dependency graph: premise -> theorem (theorem uses premise)
print("\n" + "=" * 80)
print("Building theorem-premise dependency graph...")
print("=" * 80)
print("  (Only processing theorems with proof_type='tactic')")

G = nx.DiGraph()
theorems_processed = 0
theorems_skipped = 0
n_term = 0
premises_seen = set()
theorems_seen = set()

# Build graph efficiently - process incrementally to save memory
with open(DATA_FILE, "r", encoding="utf-8") as f:
    # Create progress bar
    if HAS_TQDM:
        pbar = tqdm(total=total_lines, desc="Processing", unit="lines")
    else:
        pbar = None
        last_progress = 0
    
    for i, line in enumerate(f):
        if pbar:
            pbar.update(1)
        elif i % 10000 == 0:
            progress = int((i / total_lines) * 100) if total_lines > 0 else 0
            if progress != last_progress:
                print(f"  Progress: {progress}% ({i:,}/{total_lines:,} lines)")
                last_progress = progress
        
        line = line.strip()
        if not line:
            continue

        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Only process theorems with proof_type == "tactic"
        proof_type = entry.get("proof_type", "")
        if proof_type != "tactic":
            theorems_skipped += 1
            if proof_type == "term":
                n_term += 1
            continue

        # Get theorem full_name (target node - this is the first key in the row)
        theorem_full_name = entry.get("full_name")
        if not theorem_full_name:
            continue

        # Add theorem node (target)
        G.add_node(theorem_full_name, node_type="theorem")
        theorems_seen.add(theorem_full_name)

        # Get premises from all_premises dictionary
        # The keys of all_premises are the premise full_names (source nodes)
        all_premises = entry.get("all_premises", {})
        
        # Iterate over premise full_names (keys of all_premises dict)
        # These are the source nodes
        for premise_full_name in all_premises.keys():
            if not premise_full_name:
                continue
            
            # Add premise node (source)
            G.add_node(premise_full_name, node_type="premise")
            premises_seen.add(premise_full_name)
            
            # Add edge: premise (source) -> theorem (target)
            # This represents "theorem uses premise"
            # Avoid self-loops
            if premise_full_name != theorem_full_name:
                G.add_edge(premise_full_name, theorem_full_name)

        theorems_processed += 1
    
    if pbar:
        pbar.close()

graph_build_time = time.time() - start_time
print(f"\nGraph built in {graph_build_time:.2f}s:")
total_theorems = theorems_processed + theorems_skipped
print(f"  Theorems processed (tactic): {theorems_processed:,}")
print(f"  Theorems skipped (non-tactic): {theorems_skipped:,} (term: {n_term:,})")
print(f"  Nodes: {G.number_of_nodes():,}")
print(f"    - Premises: {len(premises_seen):,}")
print(f"    - Theorems: {len(theorems_seen):,}")
print(f"  Edges (premise->theorem): {G.number_of_edges():,}")

# Pre-compute degrees once for efficiency
degree_start = time.time()
in_degrees = dict(G.in_degree())
out_degrees = dict(G.out_degree())
degree_time = time.time() - degree_start
print(f"  Degrees computed in {degree_time:.3f}s")

# Find root nodes (premises not used by any theorem) and leaves (theorems that don't use any premises)
roots = [n for n, deg in in_degrees.items() if deg == 0]
leaves = [n for n, deg in out_degrees.items() if deg == 0]

# Separate by node type
root_premises = [n for n in roots if G.nodes[n].get("node_type") == "premise"]
root_theorems = [n for n in roots if G.nodes[n].get("node_type") == "theorem"]
leaf_premises = [n for n in leaves if G.nodes[n].get("node_type") == "premise"]
leaf_theorems = [n for n in leaves if G.nodes[n].get("node_type") == "theorem"]

print(f"  Root nodes (no incoming edges): {len(roots):,}")
print(f"    - Premises: {len(root_premises):,}")
print(f"    - Theorems: {len(root_theorems):,}")
print(f"  Leaf nodes (no outgoing edges): {len(leaves):,}")
print(f"    - Premises: {len(leaf_premises):,}")
print(f"    - Theorems: {len(leaf_theorems):,}")

# Find top nodes by degree
top_premises_by_out = sorted(
    [(n, out_degrees[n]) for n in premises_seen if n in out_degrees],
    key=lambda x: x[1], reverse=True
)[:10]
top_theorems_by_in = sorted(
    [(n, in_degrees[n]) for n in theorems_seen if n in in_degrees],
    key=lambda x: x[1], reverse=True
)[:10]

print(f"\nTop 10 premises by outgoing edges (most used by theorems):")
for name, count in top_premises_by_out:
    short_name = name.split('.')[-1] if '.' in name else name
    print(f"  {short_name[:60]}: {count} theorems")

print(f"\nTop 10 theorems by incoming edges (use most premises):")
for name, count in top_theorems_by_in:
    short_name = name.split('.')[-1] if '.' in name else name
    print(f"  {short_name[:60]}: {count} premises")

# ============================================================================
# Examples of unresolved lemmas (10 examples with confidence scores)
# ============================================================================
print("\n" + "=" * 80)
print("Examples of unresolved premises only (tactics/hypotheses excluded, 10 examples with confidence)")
print("=" * 80)

unresolved_examples = []  # list of (full_name, confidence, resolution_method, example_theorem)
seen_unresolved = set()

with open(DATA_FILE, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("proof_type") != "tactic":
            continue
        theorem_name = entry.get("full_name", "")
        for tac in entry.get("tactics", []):
            for p in tac.get("premises", []):
                conf = p.get("confidence", 1.0)
                full_name = p.get("full_name", "") or p.get("surface_name", "")
                if not full_name or _is_tactic_or_hyp(full_name):
                    continue
                # Treat as unresolved if confidence is 0 or very low
                if conf == 0.0 or (conf < 0.5 and full_name not in seen_unresolved):
                    seen_unresolved.add(full_name)
                    method = p.get("resolution_method", "unknown")
                    unresolved_examples.append((full_name, conf, method, theorem_name))
                    if len(unresolved_examples) >= 10:
                        break
            if len(unresolved_examples) >= 10:
                break
        if len(unresolved_examples) >= 10:
            break

# If we have fewer than 10 from strict unresolved, add low-confidence examples
if len(unresolved_examples) < 10:
    seen = {x[0] for x in unresolved_examples}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("proof_type") != "tactic":
                continue
            theorem_name = entry.get("full_name", "")
            for tac in entry.get("tactics", []):
                for p in tac.get("premises", []):
                    conf = p.get("confidence", 1.0)
                    full_name = p.get("full_name", "") or p.get("surface_name", "")
                    if not full_name or _is_tactic_or_hyp(full_name):
                        continue
                    if full_name not in seen and conf < 1.0:
                        seen.add(full_name)
                        method = p.get("resolution_method", "unknown")
                        unresolved_examples.append((full_name, conf, method, theorem_name))
                        if len(unresolved_examples) >= 10:
                            break
                if len(unresolved_examples) >= 10:
                    break
            if len(unresolved_examples) >= 10:
                break

for i, (full_name, conf, method, thm) in enumerate(unresolved_examples[:10], 1):
    short_lemma = full_name.split('.')[-1] if '.' in full_name else full_name
    short_thm = (thm.split('.')[-1] if thm and '.' in thm else (thm or ""))[:50]
    full_display = full_name[:70] + ("..." if len(full_name) > 70 else "")
    print(f"  {i}. lemma: {full_display}")
    print(f"     confidence: {conf:.4f}  resolution: {method}  example theorem: {short_thm}")
if not unresolved_examples:
    print("  (No unresolved lemma examples found in data.)")

# ============================================================================
# 10 examples of tactic proofs with unresolved premises (full proof text)
# ============================================================================
print("\n" + "=" * 80)
print("10 examples of tactic proofs with unresolved premises (full proof)")
print("=" * 80)

unresolved_tactic_examples = []  # list of (full_name, proof_text)
with open(DATA_FILE, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("proof_type") != "tactic":
            continue
        theorem_name = entry.get("full_name", "")
        proof_text = entry.get("proof_text", "") or ""
        has_unresolved = False
        for tac in entry.get("tactics", []):
            for p in tac.get("premises", []):
                if p.get("confidence", 1.0) == 0.0:
                    has_unresolved = True
                    break
            if has_unresolved:
                break
        if has_unresolved and theorem_name:
            unresolved_tactic_examples.append((theorem_name, proof_text))
            if len(unresolved_tactic_examples) >= 10:
                break

for i, (full_name, proof_text) in enumerate(unresolved_tactic_examples[:10], 1):
    short_name = (full_name.split(".")[-1] if "." in full_name else full_name)[:60]
    print(f"\n  {i}. theorem: {short_name}")
    print(f"     full_name: {full_name[:70]}{'...' if len(full_name) > 70 else ''}")
    print("     proof:")
    for ln in (proof_text or "(no proof text)").split("\n")[:50]:
        print(f"       {ln}")
    if (proof_text or "").count("\n") >= 50:
        print("       ...")
if not unresolved_tactic_examples:
    print("  (No tactic proofs with unresolved premises found.)")

# ============================================================================
# 10 examples of term proofs (full proof text)
# ============================================================================
print("\n" + "=" * 80)
print("10 examples of term proofs (full proof)")
print("=" * 80)

term_proof_examples = []  # list of (full_name, proof_text)
with open(DATA_FILE, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("proof_type") != "term":
            continue
        theorem_name = entry.get("full_name", "")
        proof_text = entry.get("proof_text", "") or ""
        if theorem_name:
            term_proof_examples.append((theorem_name, proof_text))
            if len(term_proof_examples) >= 10:
                break

for i, (full_name, proof_text) in enumerate(term_proof_examples[:10], 1):
    short_name = (full_name.split(".")[-1] if "." in full_name else full_name)[:60]
    print(f"\n  {i}. theorem: {short_name}")
    print(f"     full_name: {full_name[:70]}{'...' if len(full_name) > 70 else ''}")
    print("     proof:")
    text = proof_text or "(term proof; no proof text in data)"
    for ln in text.split("\n")[:50]:
        print(f"       {ln}")
    if text.count("\n") >= 50:
        print("       ...")
if not term_proof_examples:
    print("  (No term proofs found.)")

# Save original graph for analysis (before node removal)
G_original = G.copy()
in_degrees_original = in_degrees.copy()
out_degrees_original = out_degrees.copy()

# ============================================================================
# DAG Network Measures Computation
# ============================================================================

def compute_dag_measures(G, in_degrees, out_degrees):
    """Compute DAG-specific network measures efficiently using optimized NetworkX functions."""
    print("\n" + "=" * 80)
    print("Computing DAG network measures...")
    print("=" * 80)

    measures = {}
    step_start = time.time()

    # Step 1: Basic graph properties
    print("\n[Step 1/5] Computing basic graph properties...")
    step1_start = time.time()
    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()
    density = n_edges / (n_nodes * (n_nodes - 1)) if n_nodes > 1 else 0  # Manual density for speed
    print(f"  ✓ Nodes: {n_nodes:,}, Edges: {n_edges:,}, Density: {density:.6f}")
    print(f"  Time: {time.time() - step1_start:.3f}s")

    # Step 2: DAG validation and components
    print("\n[Step 2/5] Validating DAG and computing components...")
    step2_start = time.time()
    try:
        print("  → Checking if graph is DAG...")
        is_dag = nx.is_directed_acyclic_graph(G)
        print(f"  → Computing weakly connected components...")
        wcc = list(nx.weakly_connected_components(G))
        wcc_sizes = [len(comp) for comp in wcc]
        print(f"  ✓ Is DAG: {is_dag}, Components: {len(wcc):,}")
    except Exception as e:
        print(f"  ✗ Error: {e}")
        is_dag = False
        wcc = []
        wcc_sizes = []
    print(f"  Time: {time.time() - step2_start:.3f}s")

    # Step 3: Sources and sinks
    print("\n[Step 3/5] Identifying sources and sinks...")
    step3_start = time.time()
    sources = [n for n, deg in in_degrees.items() if deg == 0]
    sinks = [n for n, deg in out_degrees.items() if deg == 0]
    print(f"  ✓ Sources: {len(sources):,}, Sinks: {len(sinks):,}")
    print(f"  Time: {time.time() - step3_start:.3f}s")

    measures['basic'] = {
        'nodes': n_nodes,
        'edges': n_edges,
        'density': density,
        'is_dag': is_dag,
        'num_components': len(wcc),
        'component_sizes': wcc_sizes,
        'num_sources': len(sources),
        'num_sinks': len(sinks)
    }

    # Step 4: Degree statistics
    print("\n[Step 4/5] Computing degree statistics...")
    step4_start = time.time()
    print("  → Converting degrees to numpy arrays...")
    in_deg_values = np.array(list(in_degrees.values()))
    out_deg_values = np.array(list(out_degrees.values()))
    print("  → Computing statistics (min, max, mean, median)...")
    
    measures['degrees'] = {
        'in_degree': {
            'min': int(in_deg_values.min()) if len(in_deg_values) else 0,
            'max': int(in_deg_values.max()) if len(in_deg_values) else 0,
            'mean': float(in_deg_values.mean()) if len(in_deg_values) else 0,
            'median': float(np.median(in_deg_values)) if len(in_deg_values) else 0
        },
        'out_degree': {
            'min': int(out_deg_values.min()) if len(out_deg_values) else 0,
            'max': int(out_deg_values.max()) if len(out_deg_values) else 0,
            'mean': float(out_deg_values.mean()) if len(out_deg_values) else 0,
            'median': float(np.median(out_deg_values)) if len(out_deg_values) else 0
        }
    }
    print(f"  ✓ In-degree: min={measures['degrees']['in_degree']['min']}, max={measures['degrees']['in_degree']['max']}, mean={measures['degrees']['in_degree']['mean']:.2f}")
    print(f"  ✓ Out-degree: min={measures['degrees']['out_degree']['min']}, max={measures['degrees']['out_degree']['max']}, mean={measures['degrees']['out_degree']['mean']:.2f}")
    print(f"  Time: {time.time() - step4_start:.3f}s")

    # Step 5a: Topological levels
    print("\n[Step 5a/6] Computing topological levels...")
    step5a_start = time.time()
    measures['levels'] = {'node_levels': {}, 'max_level': 0, 'mean_level': 0, 'level_distribution': {}}

    if is_dag and n_nodes > 0:
        try:
            print(f"  → Starting BFS from {len(sources):,} sources...")
            # More efficient level computation using BFS from sources
            node_levels = {}
            visited = set()
            queue = [(source, 0) for source in sources]  # (node, level)
            
            total_to_process = n_nodes
            processed = 0
            last_progress = 0

            while queue:
                node, level = queue.pop(0)
                if node in visited:
                    continue
                visited.add(node)
                node_levels[node] = level
                processed += 1
                
                # Progress indicator
                if processed % 10000 == 0 or processed == total_to_process:
                    progress = int((processed / total_to_process) * 100) if total_to_process > 0 else 0
                    if progress != last_progress:
                        print(f"  → Progress: {progress}% ({processed:,}/{total_to_process:,} nodes)")
                        last_progress = progress

                # Add successors to queue with incremented level
                for successor in G.successors(node):
                    if successor not in visited:
                        queue.append((successor, level + 1))

            # Handle any remaining unvisited nodes (shouldn't happen in a DAG)
            print("  → Handling unvisited nodes...")
            for node in G.nodes():
                if node not in node_levels:
                    node_levels[node] = 0

            print("  → Computing level statistics...")
            level_values = list(node_levels.values())
            measures['levels'] = {
                'node_levels': node_levels,
                'max_level': max(level_values) if level_values else 0,
                'mean_level': np.mean(level_values) if level_values else 0,
                'level_distribution': dict(Counter(level_values))
            }
            print(f"  ✓ Max level: {measures['levels']['max_level']}, Mean level: {measures['levels']['mean_level']:.2f}")
        except Exception as e:
            print(f"  ✗ Warning: Could not compute topological levels: {e}")
    else:
        print("  → Skipping (not a DAG or empty graph)")
    print(f"  Time: {time.time() - step5a_start:.3f}s")

    # Step 5b: Longest paths
    print("\n[Step 5b/6] Computing longest paths (max depth)...")
    step5b_start = time.time()
    measures['paths'] = {'node_max_depth': {}, 'max_depth': 0, 'mean_depth': 0}

    if is_dag and n_nodes > 0 and sources:
        try:
            print(f"  → Starting BFS from {len(sources):,} sources...")
            # Efficient BFS from all sources to compute max depth for each node
            node_max_depth = {}
            visited = set()

            # Initialize queue with all sources at depth 0
            queue = [(source, 0) for source in sources]
            source_set = set(sources)
            
            total_to_process = n_nodes
            processed = 0
            last_progress = 0

            while queue:
                node, depth = queue.pop(0)

                # Update max depth for this node
                if node not in node_max_depth or depth > node_max_depth[node]:
                    node_max_depth[node] = depth

                if node in visited:
                    continue
                visited.add(node)
                processed += 1
                
                # Progress indicator
                if processed % 10000 == 0 or processed == total_to_process:
                    progress = int((processed / total_to_process) * 100) if total_to_process > 0 else 0
                    if progress != last_progress:
                        print(f"  → Progress: {progress}% ({processed:,}/{total_to_process:,} nodes)")
                        last_progress = progress

                # Add successors with incremented depth
                for successor in G.successors(node):
                    if successor not in visited:
                        queue.append((successor, depth + 1))

            # Fill in any unvisited nodes (isolated nodes not reachable from sources)
            print("  → Handling unvisited nodes...")
            for node in G.nodes():
                if node not in node_max_depth:
                    node_max_depth[node] = 0

            print("  → Computing depth statistics...")
            depth_values = list(node_max_depth.values())
            measures['paths'] = {
                'node_max_depth': node_max_depth,
                'max_depth': max(depth_values) if depth_values else 0,
                'mean_depth': np.mean(depth_values) if depth_values else 0
            }
            print(f"  ✓ Max depth: {measures['paths']['max_depth']}, Mean depth: {measures['paths']['mean_depth']:.2f}")
        except Exception as e:
            print(f"  ✗ Warning: Could not compute longest paths: {e}")
    else:
        print("  → Skipping (not a DAG, empty graph, or no sources)")
    print(f"  Time: {time.time() - step5b_start:.3f}s")

    total_time = time.time() - step_start
    print(f"\n✓ All DAG measures computed in {total_time:.2f}s")
    return measures

def find_extreme_nodes(measures, G, in_degrees, out_degrees, top_k=5):
    """Find nodes with extreme values for each measure."""
    print("\n" + "=" * 80)
    print("Identifying extreme nodes...")
    print("=" * 80)
    
    extreme_nodes = {}
    step_start = time.time()
    
    # In-degree extremes
    print("\n  [1/5] Finding in-degree extremes...")
    step1_start = time.time()
    print("    → Sorting nodes by in-degree...")
    sorted_in_deg = sorted(in_degrees.items(), key=lambda x: x[1], reverse=True)
    extreme_nodes['in_degree'] = {
        'high': [n for n, _ in sorted_in_deg[:top_k]],
        'low': [n for n, _ in sorted_in_deg[-top_k:] if in_degrees[n] == 0]  # Only sources
    }
    print(f"    ✓ Found {len(extreme_nodes['in_degree']['high'])} high, {len(extreme_nodes['in_degree']['low'])} low")
    print(f"    Time: {time.time() - step1_start:.3f}s")
    
    # Out-degree extremes
    print("\n  [2/5] Finding out-degree extremes...")
    step2_start = time.time()
    print("    → Sorting nodes by out-degree...")
    sorted_out_deg = sorted(out_degrees.items(), key=lambda x: x[1], reverse=True)
    extreme_nodes['out_degree'] = {
        'high': [n for n, _ in sorted_out_deg[:top_k]],
        'low': [n for n, _ in sorted_out_deg[-top_k:] if out_degrees[n] == 0]  # Only sinks
    }
    print(f"    ✓ Found {len(extreme_nodes['out_degree']['high'])} high, {len(extreme_nodes['out_degree']['low'])} low")
    print(f"    Time: {time.time() - step2_start:.3f}s")
    
    # Level extremes
    print("\n  [3/5] Finding level extremes...")
    step3_start = time.time()
    if 'levels' in measures and measures['levels']['node_levels']:
        print("    → Sorting nodes by level...")
        node_levels = measures['levels']['node_levels']
        sorted_levels = sorted(node_levels.items(), key=lambda x: x[1], reverse=True)
        extreme_nodes['level'] = {
            'high': [n for n, _ in sorted_levels[:top_k]],
            'low': [n for n, _ in sorted_levels[-top_k:]]
        }
        print(f"    ✓ Found {len(extreme_nodes['level']['high'])} high, {len(extreme_nodes['level']['low'])} low")
    else:
        print("    → Skipping (no level data)")
    print(f"    Time: {time.time() - step3_start:.3f}s")
    
    # Path depth extremes
    print("\n  [4/5] Finding depth extremes...")
    step4_start = time.time()
    if 'paths' in measures and measures['paths']['node_max_depth']:
        print("    → Sorting nodes by max depth...")
        node_max_depth = measures['paths']['node_max_depth']
        sorted_depth = sorted(node_max_depth.items(), key=lambda x: x[1], reverse=True)
        extreme_nodes['depth'] = {
            'high': [n for n, _ in sorted_depth[:top_k]],
            'low': [n for n, _ in sorted_depth[-top_k:]]
        }
        print(f"    ✓ Found {len(extreme_nodes['depth']['high'])} high, {len(extreme_nodes['depth']['low'])} low")
    else:
        print("    → Skipping (no depth data)")
    print(f"    Time: {time.time() - step4_start:.3f}s")
    
    # Component extremes
    print("\n  [5/5] Finding component extremes...")
    step5_start = time.time()
    if 'basic' in measures:
        print("    → Computing weakly connected components...")
        wcc = list(nx.weakly_connected_components(G))
        if wcc:
            print("    → Finding largest and smallest components...")
            largest_comp = max(wcc, key=len)
            smallest_comp = min(wcc, key=len)
            extreme_nodes['component'] = {
                'high': [list(largest_comp)[0]],  # Representative from largest
                'low': [list(smallest_comp)[0]] if len(smallest_comp) > 0 else []
            }
            print(f"    ✓ Found {len(extreme_nodes['component']['high'])} high, {len(extreme_nodes['component']['low'])} low")
        else:
            print("    → No components found")
    else:
        print("    → Skipping (no basic data)")
    print(f"    Time: {time.time() - step5_start:.3f}s")
    
    total_time = time.time() - step_start
    print(f"\n  ✓ Found extreme nodes for {len(extreme_nodes)} measure types in {total_time:.2f}s")
    return extreme_nodes

def extract_ego_networks(G, extreme_nodes, measures, max_nodes=50, max_ego_networks=36):
    """Extract 1-hop ego networks for extreme nodes efficiently. Only constructs networks that will be visualized."""
    print("\n" + "=" * 80)
    print("Extracting ego networks (1-hop neighborhoods)...")
    print("=" * 80)

    ego_networks = []

    # Pre-compute all neighbors for efficiency
    print("\n  [Step 1/3] Pre-computing neighborhoods...")
    step1_start = time.time()
    node_neighbors = {}
    total_nodes = G.number_of_nodes()
    if HAS_TQDM:
        pbar = tqdm(total=total_nodes, desc="    Computing neighbors", unit="nodes")
    else:
        pbar = None
        last_progress = 0
    
    for idx, node in enumerate(G.nodes()):
        if pbar:
            pbar.update(1)
        elif idx % 10000 == 0:
            progress = int((idx / total_nodes) * 100) if total_nodes > 0 else 0
            if progress != last_progress:
                print(f"    → Progress: {progress}% ({idx:,}/{total_nodes:,} nodes)")
                last_progress = progress
        node_neighbors[node] = set(G.predecessors(node)) | set(G.successors(node))
    
    if pbar:
        pbar.close()
    print(f"    ✓ Pre-computed neighborhoods for {len(node_neighbors):,} nodes")
    print(f"    Time: {time.time() - step1_start:.3f}s")

    # Collect all extreme nodes with priority scores for selection
    print("\n  [Step 2/3] Collecting and scoring candidate nodes...")
    step2_start = time.time()
    candidate_nodes = []
    seen_nodes = set()
    
    total_candidates = sum(len(nodes) for extremes in extreme_nodes.values() for nodes in extremes.values())
    processed = 0
    if HAS_TQDM:
        pbar2 = tqdm(total=total_candidates, desc="    Scoring candidates", unit="nodes")
    else:
        pbar2 = None
        last_progress2 = 0

    for measure_type, extremes in extreme_nodes.items():
        for extreme_type, nodes in extremes.items():
            for node in nodes:
                if pbar2:
                    pbar2.update(1)
                elif processed % 1000 == 0:
                    progress = int((processed / total_candidates) * 100) if total_candidates > 0 else 0
                    if progress != last_progress2:
                        print(f"    → Progress: {progress}% ({processed:,}/{total_candidates:,} candidates)")
                        last_progress2 = progress
                processed += 1
                if node not in seen_nodes and node in G:
                    # Calculate priority score based on potential ego network size
                    node_degree = len(node_neighbors.get(node, set()))

                    # Estimate 1-hop neighborhood size
                    step1_nodes = node_neighbors.get(node, set())
                    estimated_ego_size = 1 + len(step1_nodes)

                    # Base priority on estimated network size, with bonuses for extreme types
                    priority_score = estimated_ego_size

                    # Boost for extreme values within their measure type
                    if measure_type == 'in_degree':
                        degree_value = G.in_degree(node)
                        if extreme_type == 'high':
                            priority_score *= (1 + degree_value / max(G.in_degree(n) for n in G.nodes()) if G.in_degree else 1)
                        else:  # low
                            priority_score *= 0.5  # Still show some sources
                    elif measure_type == 'out_degree':
                        degree_value = G.out_degree(node)
                        if extreme_type == 'high':
                            priority_score *= (1 + degree_value / max(G.out_degree(n) for n in G.nodes()) if G.out_degree else 1)
                        else:  # low
                            priority_score *= 0.5  # Still show some sinks
                    elif measure_type == 'level' and 'levels' in measures:
                        level_value = measures['levels']['node_levels'].get(node, 0)
                        if extreme_type == 'high':
                            priority_score *= (1 + level_value / max(measures['levels']['node_levels'].values()) if measures['levels']['node_levels'] else 1)
                    elif measure_type == 'depth' and 'paths' in measures:
                        depth_value = measures['paths']['node_max_depth'].get(node, 0)
                        if extreme_type == 'high':
                            priority_score *= (1 + depth_value / max(measures['paths']['node_max_depth'].values()) if measures['paths']['node_max_depth'] else 1)

                    candidate_nodes.append((node, measure_type, extreme_type, priority_score))
                    seen_nodes.add(node)
    
    if pbar2:
        pbar2.close()
    print(f"    ✓ Collected {len(candidate_nodes)} candidate nodes")
    print(f"    Time: {time.time() - step2_start:.3f}s")

    # Sort candidates by priority and select top 3 per measure type and extreme type
    print("\n  [Step 3/3] Processing selected ego networks...")
    step3_start = time.time()
    print("    → Sorting candidates by priority...")
    candidate_nodes.sort(key=lambda x: x[3], reverse=True)
    
    # Select top 3 per (measure_type, extreme_type) combination
    selected_candidates = []
    counts_per_type = defaultdict(int)
    max_per_type = 3
    
    for node, measure_type, extreme_type, _ in candidate_nodes:
        key = (measure_type, extreme_type)
        if counts_per_type[key] < max_per_type:
            selected_candidates.append((node, measure_type, extreme_type, _))
            counts_per_type[key] += 1
    
    print(f"    → Processing {len(selected_candidates)} candidates (3 per type) for visualization...")
    if HAS_TQDM:
        pbar3 = tqdm(total=len(selected_candidates), desc="    Extracting ego networks", unit="networks")
    else:
        pbar3 = None

    # Process only the selected candidates
    for idx, (node, measure_type, extreme_type, _) in enumerate(selected_candidates):
        if pbar3:
            pbar3.update(1)
        elif idx % 5 == 0:
            print(f"    → Progress: {idx}/{len(selected_candidates)} networks")
        try:
            # Get 1-hop neighbors (pre-computed)
            step1_nodes = node_neighbors.get(node, set())

            # Build ego network with center node and 1-hop neighbors only
            all_ego_nodes = {node} | step1_nodes
            
            # Limit total nodes for performance if needed
            if len(all_ego_nodes) > max_nodes:
                # Select most connected 1-hop neighbors
                step1_degrees = [(n, len(node_neighbors.get(n, set()))) for n in step1_nodes]
                step1_degrees.sort(key=lambda x: x[1], reverse=True)
                # Keep center node and top (max_nodes - 1) neighbors
                top_neighbors = {n for n, _ in step1_degrees[:max_nodes - 1]}
                all_ego_nodes = {node} | top_neighbors

            # Create subgraph efficiently - only if it has meaningful connections
            if len(all_ego_nodes) > 1:
                # Use edge_subgraph for better performance on large graphs
                relevant_edges = [(u, v) for u, v in G.edges() if u in all_ego_nodes and v in all_ego_nodes]
                ego = nx.DiGraph()
                ego.add_nodes_from(all_ego_nodes)
                ego.add_edges_from(relevant_edges)

                # Only keep if subgraph is connected and meaningful
                if ego.number_of_edges() > 0:
                    short_name = node.split('.')[-1] if '.' in node else node
                    value = None
                    if measure_type == 'in_degree':
                        value = in_degrees.get(node, 0)
                    elif measure_type == 'out_degree':
                        value = out_degrees.get(node, 0)
                    elif measure_type == 'level' and 'levels' in measures:
                        value = measures['levels']['node_levels'].get(node, 0)
                    elif measure_type == 'depth' and 'paths' in measures:
                        value = measures['paths']['node_max_depth'].get(node, 0)

                    ego_networks.append({
                        'graph': ego,
                        'center': node,
                        'measure_type': measure_type,
                        'extreme_type': extreme_type,
                        'value': value,
                        'name': short_name
                    })

        except Exception as e:
            print(f"    ✗ Warning: Could not process ego network for {node}: {e}")
            continue
    
    if pbar3:
        pbar3.close()
    print(f"    ✓ Extracted {len(ego_networks)} ego networks")
    print(f"    Time: {time.time() - step3_start:.3f}s")
    return ego_networks

# Compute measures on original graph
print("\nComputing measures...")
measures_start = time.time()
measures = compute_dag_measures(G_original, in_degrees_original, out_degrees_original)
measures['proof_types'] = {
    'tactic': theorems_processed,
    'term': n_term,
    'total': total_theorems
}
measures_time = time.time() - measures_start
print(f"Measures computed in {measures_time:.2f}s")

# Find extreme nodes
extreme_nodes = find_extreme_nodes(measures, G_original, in_degrees_original, out_degrees_original, top_k=5)

# Extract ego networks (only for nodes that will be visualized)
print("\nExtracting ego networks...")
ego_start = time.time()
ego_networks = extract_ego_networks(G_original, extreme_nodes, measures, max_nodes=50, max_ego_networks=100)  # Will select 3 per type
ego_time = time.time() - ego_start
print(f"Ego networks extracted in {ego_time:.2f}s")

# ============================================================================
# Create Multipanel Figure
# ============================================================================

def create_multipanel_figure(measures, ego_networks, output_pdf, output_png):
    """Create comprehensive multipanel figure with statistics and ego networks."""
    print("\n" + "=" * 80)
    print("Creating multipanel figure...")
    print("=" * 80)
    
    # Compute unique unresolved premises percentage
    print("  Computing unique unresolved premises percentage...")
    unique_unresolved_start = time.time()
    all_premises = set()  # All unique premises
    unresolved_premises = set()  # Unique unresolved premises
    
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                thm = json.loads(line)
                # Only process tactic proofs
                if thm.get("proof_type") != "tactic":
                    continue
                
                # Extract all premises from tactics
                premises = [
                    p
                    for t in thm.get("tactics", [])
                    for p in t.get("premises", [])
                ]
                
                for p in premises:
                    full_name = p.get("full_name", "")
                    if full_name:
                        all_premises.add(full_name)
                        if p.get("confidence", 1.0) == 0.0:
                            unresolved_premises.add(full_name)
            except (json.JSONDecodeError, KeyError):
                continue
    
    unique_unresolved_pct = (100 * len(unresolved_premises) / len(all_premises)) if all_premises else 0.0
    print(f"    ✓ Unique unresolved premises: {len(unresolved_premises):,} / {len(all_premises):,} ({unique_unresolved_pct:.2f}%)")
    print(f"    Time: {time.time() - unique_unresolved_start:.2f}s")
    
    # Create large figure
    fig = plt.figure(figsize=(24, 30), facecolor='white')
    gs = GridSpec(8, 6, figure=fig, hspace=0.4, wspace=0.3, 
                  left=0.05, right=0.95, top=0.97, bottom=0.03)
    
    # ========================================================================
    # Top Section: Statistics Panels (6 panels, 2x3 grid)
    # ========================================================================
    
    # Panel 1: Basic Statistics
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.axis('off')
    basic = measures['basic']
    pt = measures.get('proof_types', {})
    tot = pt.get('total') or 1
    tactic_pct = 100 * (pt.get('tactic') or 0) / tot
    term_pct = 100 * (pt.get('term') or 0) / tot
    stats_text = f"""Graph Statistics
    
Nodes: {basic['nodes']:,}
Edges: {basic['edges']:,}
Density: {basic['density']:.6f}
Is DAG: {basic['is_dag']}
Components: {basic['num_components']}
Sources: {basic['num_sources']}
Sinks: {basic['num_sinks']}
Unresolved Premises: {unique_unresolved_pct:.2f}%
Tactic proofs: {tactic_pct:.1f}%
Term proofs: {term_pct:.1f}%"""
    ax1.text(0.1, 0.5, stats_text, fontsize=10, family='monospace',
             verticalalignment='center', transform=ax1.transAxes)
    ax1.set_title('Basic Statistics', fontsize=12, fontweight='normal', pad=10)
    
    # Panel 2: Premise Resolution Rates (moved from Panel 6)
    ax2 = fig.add_subplot(gs[0, 1])
    print("  Computing premise resolution rates...")
    resolution_start = time.time()
    
    # Collect resolution data
    resolved_pcts = []
    unresolved_pcts = []
    
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                thm = json.loads(line)
                # Only process tactic proofs
                if thm.get("proof_type") != "tactic":
                    continue
                
                # Extract all premises from tactics
                premises = [
                    p
                    for t in thm.get("tactics", [])
                    for p in t.get("premises", [])
                ]
                
                if not premises:
                    continue
                
                # Count unresolved (confidence == 0.0)
                unresolved = sum(p.get("confidence", 1.0) == 0.0 for p in premises)
                total = len(premises)
                unresolved_pct = 100 * unresolved / total
                resolved_pct = 100 - unresolved_pct
                
                resolved_pcts.append(resolved_pct)
                unresolved_pcts.append(unresolved_pct)
            except (json.JSONDecodeError, KeyError):
                continue
    
    print(f"    ✓ Processed {len(resolved_pcts):,} theorems in {time.time() - resolution_start:.2f}s")
    
    if resolved_pcts:
        # Create histogram data
        bins = np.linspace(0, 100, 51)
        resolved_hist, _ = np.histogram(resolved_pcts, bins=bins)
        unresolved_hist, _ = np.histogram(unresolved_pcts, bins=bins)
        bin_centers = (bins[:-1] + bins[1:]) / 2
        
        # Plot both with markers only (no lines)
        ax2.plot(bin_centers, resolved_hist, 'o', label='Resolved', color='#2e7d32', markersize=3, alpha=0.7)
        ax2.plot(bin_centers, unresolved_hist, 'o', label='Unresolved', color='#c62828', markersize=3, alpha=0.7)
        ax2.set_xlabel('Percentage (%)', fontsize=9)
        ax2.set_ylabel('Number of Theorems', fontsize=9)
        ax2.set_title('Premise Resolution Rates', fontsize=12, fontweight='normal', pad=10)
        ax2.legend(fontsize=8, loc='best')
        ax2.grid(True, alpha=0.3)
    else:
        ax2.axis('off')
        pt = measures.get('proof_types', {})
        fallback = f"""No premise resolution data
(tactic proofs: {pt.get('tactic', 0):,})"""
        ax2.text(0.5, 0.5, fallback, fontsize=10, family='monospace',
                 ha='center', va='center', transform=ax2.transAxes)
        ax2.set_title('Premise Resolution Rates', fontsize=12, fontweight='normal', pad=10)
    ax2.tick_params(labelsize=8)
    
    # Panel 3: In-Degree Distribution (log-log) - pre-compute for efficiency
    ax3 = fig.add_subplot(gs[0, 2])
    in_deg_values = list(in_degrees_original.values())
    if in_deg_values:
        # Use numpy for efficient counting
        unique_degrees, counts = np.unique(in_deg_values, return_counts=True)
        # For log-log, use degree+1 to handle zeros
        degrees_plot = unique_degrees + 1
        frequencies_plot = counts
        # Plot on log-log scale
        ax3.loglog(degrees_plot, frequencies_plot, 'o', color='black', markersize=3, alpha=0.7)
        ax3.set_xlabel('In-Degree+1 (log)', fontsize=9)
        ax3.set_ylabel('Frequency (log)', fontsize=9)
    else:
        ax3.axis('off')
        ax3.text(0.5, 0.5, 'No in-degree data', ha='center', va='center', transform=ax3.transAxes)
    ax3.set_title('In-Degree Distribution', fontsize=12, fontweight='normal', pad=10)
    ax3.tick_params(labelsize=8)

    # Panel 3b: Out-degree / Total degree per node (distribution)
    ax3b = fig.add_subplot(gs[2, 0:3])  # full width of row 2
    in_deg = in_degrees_original
    out_deg = out_degrees_original
    ratios = []
    for n in G_original.nodes():
        i = in_deg.get(n, 0)
        o = out_deg.get(n, 0)
        total = i + o
        if total > 0:
            ratios.append(o / total)
    if ratios:
        bins = np.linspace(0, 1, 51)
        hist, _ = np.histogram(ratios, bins=bins)
        bin_centers = (bins[:-1] + bins[1:]) / 2
        ax3b.fill_between(bin_centers, hist, alpha=0.6, color='#1565c0')
        ax3b.plot(bin_centers, hist, 'o', color='#0d47a1', markersize=2, alpha=0.8)
        ax3b.set_xlabel('Out-degree / (In + Out) per node', fontsize=9)
        ax3b.set_ylabel('Number of nodes', fontsize=9)
        ax3b.set_title('Distribution of out_degree / total_degree per node', fontsize=12, fontweight='normal', pad=10)
        ax3b.grid(True, alpha=0.3)
    else:
        ax3b.axis('off')
        ax3b.text(0.5, 0.5, 'No degree data', ha='center', va='center', transform=ax3b.transAxes)
        ax3b.set_title('Out / Total degree per node', fontsize=12, fontweight='normal', pad=10)
    ax3b.tick_params(labelsize=8)

    # Panel 4: Out-Degree Distribution (log-linear) - pre-compute for efficiency
    ax4 = fig.add_subplot(gs[1, 0])
    out_deg_values = list(out_degrees_original.values())
    if out_deg_values:
        # Use numpy for efficient counting
        unique_degrees, counts = np.unique(out_deg_values, return_counts=True)
        # For log-linear, use degree+1 to handle zeros
        degrees_plot = unique_degrees + 1
        frequencies_plot = counts
        # Plot on log-linear scale
        ax4.semilogx(degrees_plot, frequencies_plot, 'o', color='black', markersize=3, alpha=0.7)
        ax4.set_xlabel('Out-Degree+1 (log)', fontsize=9)
        ax4.set_ylabel('Frequency', fontsize=9)
    else:
        ax4.axis('off')
        ax4.text(0.5, 0.5, 'No out-degree data', ha='center', va='center', transform=ax4.transAxes)
    ax4.set_title('Out-Degree Distribution', fontsize=12, fontweight='normal', pad=10)
    ax4.tick_params(labelsize=8)
    
    # Panel 5: Level Distribution (or Proof Types when no level data)
    ax5 = fig.add_subplot(gs[1, 1])
    if 'levels' in measures and measures['levels']['level_distribution']:
        level_dist = measures['levels']['level_distribution']
        levels = sorted(level_dist.keys())
        counts = [level_dist[l] for l in levels]
        ax5.bar(levels, counts, color='black', alpha=0.7, edgecolor='black', linewidth=0.5)
        ax5.set_xlabel('Topological Level', fontsize=9)
        ax5.set_ylabel('Number of Nodes', fontsize=9)
        ax5.set_title('Level Distribution', fontsize=12, fontweight='normal', pad=10)
    else:
        # Use this subplot for Proof Types so no slot is empty
        pt = measures.get('proof_types', {})
        n_tactic = pt.get('tactic') or 0
        n_term = pt.get('term') or 0
        if n_tactic or n_term:
            labels = ['Tactic', 'Term']
            vals = [n_tactic, n_term]
            colors = ['#2e7d32', '#1565c0']
            bars = ax5.bar(labels, vals, color=colors, alpha=0.8, edgecolor='black', linewidth=0.5)
            ax5.set_ylabel('Number of Theorems', fontsize=9)
            ax5.set_title('Proof Types (level data N/A)', fontsize=12, fontweight='normal', pad=10)
            for b, v in zip(bars, vals):
                ax5.text(b.get_x() + b.get_width() / 2, b.get_height() + max(vals) * 0.01,
                        f'{v:,}', ha='center', va='bottom', fontsize=9)
        else:
            ax5.text(0.5, 0.5, 'No level data', ha='center', va='center', transform=ax5.transAxes)
            ax5.set_title('Level Distribution', fontsize=12, fontweight='normal', pad=10)
    ax5.tick_params(labelsize=8)
    
    # Panel 6: Component Size Distribution (log-log)
    ax6 = fig.add_subplot(gs[1, 2])
    comp_sizes = basic['component_sizes']
    if comp_sizes:
        # Count frequencies for each component size
        from collections import Counter
        size_counts = Counter(comp_sizes)
        sizes = sorted(size_counts.keys())
        counts = [size_counts[s] for s in sizes]
        
        # Plot on log-log scale with points
        # Use size+1 to handle size=1 (log(1)=0)
        sizes_plot = np.array(sizes) + 1
        counts_plot = np.array(counts)
        
        ax6.loglog(sizes_plot, counts_plot, 'o', color='black', markersize=3, alpha=0.7)
        ax6.set_xlabel('Component Size+1 (log)', fontsize=9)
        ax6.set_ylabel('Frequency (log)', fontsize=9)
        ax6.set_title('Component Size Distribution', fontsize=12, fontweight='normal', pad=10)
        
        # Set x-axis to show only whole numbers
        from matplotlib.ticker import LogLocator
        ax6.xaxis.set_major_locator(LogLocator(base=10, numticks=15))
        ax6.xaxis.set_minor_locator(LogLocator(base=10, subs=np.arange(2, 10), numticks=15))
    else:
        # Use subplot instead of leaving empty: show graph summary
        ax6.axis('off')
        summary = f"""Component summary
Nodes: {basic['nodes']:,}
Edges: {basic['edges']:,}
Components: {basic['num_components']}"""
        ax6.text(0.5, 0.5, summary, fontsize=10, family='monospace',
                 ha='center', va='center', transform=ax6.transAxes)
        ax6.set_title('Component Size (no distribution)', fontsize=12, fontweight='normal', pad=10)
    ax6.tick_params(labelsize=8)
    
    # ========================================================================
    # Bottom Section: Ego Network Grid (starts at row 3; rows 0-2 are stats)
    # ========================================================================
    
    print(f"  Creating ego network visualizations ({len(ego_networks)} networks)...")

    # Determine grid size for ego networks
    n_ego = len(ego_networks)
    n_cols = 6
    stats_rows = 3  # rows 0, 1, 2 used by statistics panels
    n_rows = (n_ego + n_cols - 1) // n_cols
    
    for idx, ego_data in enumerate(ego_networks):
        row = stats_rows + (idx // n_cols)
        col = idx % n_cols
        
        if row >= 8:  # Don't exceed figure bounds
            break
            
        ax = fig.add_subplot(gs[row, col])
        ego = ego_data['graph']
        center = ego_data['center']
        measure_type = ego_data['measure_type']
        extreme_type = ego_data['extreme_type']
        value = ego_data['value']
        name = ego_data['name']
        
        if ego.number_of_nodes() == 0:
            ax.text(0.5, 0.5, 'Empty', ha='center', va='center', transform=ax.transAxes)
            ax.set_title(f"{measure_type}\n{name}", fontsize=8, fontweight='normal')
            ax.axis('off')
            continue
        
        # Compute layout for ego network - optimized parameters
        try:
            n_nodes = ego.number_of_nodes()
            if n_nodes <= 2:
                pos = nx.spring_layout(ego, k=1.0, iterations=10, seed=42)
            elif n_nodes <= 10:
                pos = nx.spring_layout(ego, k=0.8, iterations=15, seed=42)
            else:
                # For larger networks, use faster layout
                pos = nx.spring_layout(ego, k=0.5, iterations=20, seed=42)
        except Exception:
            # Fallback to circular layout for problematic graphs
            pos = nx.circular_layout(ego)
        
        # Draw nodes - color by node type, size by out degree
        node_colors_ego = []
        node_sizes_ego = []
        # Get out degrees for sizing
        ego_out_degrees = dict(ego.out_degree())
        max_out_deg = max(ego_out_degrees.values()) if ego_out_degrees.values() else 1
        
        for node in ego.nodes():
            if node == center:
                node_colors_ego.append('#000000')  # Black for center
                # Center node size based on its out degree
                center_out_deg = ego_out_degrees.get(node, 0)
                node_sizes_ego.append(50 + (center_out_deg / max_out_deg) * 100 if max_out_deg > 0 else 100)
            else:
                node_type = G_original.nodes[node].get("node_type", "unknown")
                if node_type == "premise":
                    node_colors_ego.append('#666666')  # Gray for premises
                else:
                    node_colors_ego.append('#999999')  # Lighter gray for theorems
                # Size by out degree (min 20, max 50)
                node_out_deg = ego_out_degrees.get(node, 0)
                node_sizes_ego.append(20 + (node_out_deg / max_out_deg) * 30 if max_out_deg > 0 else 30)
        
        nx.draw_networkx_nodes(ego, pos, node_color=node_colors_ego,
                              node_size=node_sizes_ego, alpha=0.9,
                              linewidths=0.5, edgecolors='black', ax=ax)
        
        # Draw edges
        nx.draw_networkx_edges(ego, pos, alpha=0.3, arrows=True,
                              arrowsize=8, edge_color='#000000', width=0.5, ax=ax)
        
        # Draw labels (only for center and a few key nodes)
        labels_ego = {}
        labels_ego[center] = name[:15]  # Truncate long names
        # Add labels for up to 2 other high-degree nodes
        other_nodes = [n for n in ego.nodes() if n != center]
        if other_nodes:
            other_degrees = [(n, ego.degree(n)) for n in other_nodes]
            other_degrees.sort(key=lambda x: x[1], reverse=True)
            for n, _ in other_degrees[:2]:
                short = (n.split('.')[-1] if '.' in n else n)[:12]
                labels_ego[n] = short
        
        nx.draw_networkx_labels(ego, pos, labels_ego, font_size=6,
                               font_color='#000000', font_weight='normal', ax=ax)
        
        # Title
        title = f"{measure_type} ({extreme_type})"
        if value is not None:
            title += f"\n{name} (val={value})"
        else:
            title += f"\n{name}"
        ax.set_title(title, fontsize=7, fontweight='normal', pad=3)
        ax.axis('off')
    
    # Fill remaining empty slots
    total_slots = n_rows * n_cols
    for idx in range(len(ego_networks), min(total_slots, 36)):
        row = 2 + (idx // n_cols)
        col = idx % n_cols
        if row < 8:
            ax = fig.add_subplot(gs[row, col])
            ax.axis('off')
    
    # Save figure
    print(f"  Saving to {output_pdf} and {output_png}...")
    plt.savefig(output_pdf, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.savefig(output_png, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()
    print(f"  Multipanel figure saved!")

# Create the multipanel figure
print("\nCreating visualization...")
viz_start = time.time()
create_multipanel_figure(measures, ego_networks, OUTPUT_PDF, OUTPUT_PNG)
viz_time = time.time() - viz_start
print(f"Visualization created in {viz_time:.2f}s")

# Print summary
total_time = time.time() - start_time
print("\n" + "=" * 80)
print("Theorem-Premise Network Analysis Complete!")
print("=" * 80)
print(f"  Total execution time: {total_time:.2f}s")
print(f"  Performance breakdown:")
print(f"    - Graph building: {graph_build_time:.2f}s")
print(f"    - Degree computation: {degree_time:.3f}s")
print(f"    - Measures computation: {measures_time:.2f}s")
print(f"    - Ego network extraction: {ego_time:.2f}s")
print(f"    - Visualization: {viz_time:.2f}s")
print(f"\n  Output files:")
print(f"    - PDF: {OUTPUT_PDF}")
print(f"    - PNG: {OUTPUT_PNG}")
print(f"\n  Summary:")
print(f"    - Nodes analyzed: {measures['basic']['nodes']:,}")
print(f"    - Edges analyzed: {measures['basic']['edges']:,}")
print(f"    - Ego networks visualized: {len(ego_networks)}")
print(f"    - Components: {measures['basic']['num_components']}")
print(f"    - Max level: {measures['levels'].get('max_level', 'N/A')}")
print(f"    - Max depth: {measures['paths'].get('max_depth', 'N/A')}")
