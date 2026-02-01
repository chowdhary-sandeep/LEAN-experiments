"""DAG Network Analysis from traced_theorems_unified_v2.jsonl - theorem to premises relationships."""

import json
import pickle
import networkx as nx
from pathlib import Path
from collections import defaultdict, Counter
from itertools import combinations
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
OUTPUT_PDF_EGONETS = str(_SCRIPT_DIR / "theorem_premise_network_analysis_egonets.pdf")
OUTPUT_PNG_EGONETS = str(_SCRIPT_DIR / "theorem_premise_network_analysis_egonets.png")
OUTPUT_PDF_MOTIFS = str(_SCRIPT_DIR / "theorem_premise_network_analysis_motifs.pdf")
OUTPUT_PNG_MOTIFS = str(_SCRIPT_DIR / "theorem_premise_network_analysis_motifs.png")
OUTPUT_HTML_DASHBOARD = str(_SCRIPT_DIR / "theorem_ego_network_dashboard.html")
CACHE_DIR = _SCRIPT_DIR / "cache"
CACHE_STAMP = CACHE_DIR / "stamp.json"
CACHE_BUNDLE = CACHE_DIR / "bundle.pkl"

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


def _get_data_stamp():
    """Return (path, mtime, size) for DATA_FILE to invalidate cache when source changes."""
    p = Path(DATA_FILE)
    if not p.exists():
        return None
    return (str(p.resolve()), p.stat().st_mtime, p.stat().st_size)


def _load_cache():
    """Load graph + degrees + build_info from cache if stamp matches. Returns (bundle, True) or (None, False)."""
    if not CACHE_STAMP.exists() or not CACHE_BUNDLE.exists():
        return None, False
    try:
        with open(CACHE_STAMP, "r", encoding="utf-8") as f:
            stamp = json.load(f)
        if tuple(stamp) != _get_data_stamp():
            return None, False
        with open(CACHE_BUNDLE, "rb") as f:
            bundle = pickle.load(f)
        return bundle, True
    except (json.JSONDecodeError, pickle.PickleError, OSError):
        return None, False


def _save_cache(bundle):
    """Save bundle to cache and write stamp."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _get_data_stamp()
    if stamp is None:
        return
    with open(CACHE_STAMP, "w", encoding="utf-8") as f:
        json.dump(list(stamp), f)  # list for JSON
    with open(CACHE_BUNDLE, "wb") as f:
        pickle.dump(bundle, f, protocol=pickle.HIGHEST_PROTOCOL)


print("=" * 80)
print("Loading theorem-premise data...")
print("=" * 80)
start_time = time.time()

# Try load from cache (graph + degrees + build_info)
bundle, from_cache = _load_cache()
if from_cache and bundle is not None:
    print("  Using cache (graph + measures + ego networks).")
    G_original = bundle["G_original"]
    in_degrees_original = bundle["in_degrees_original"]
    out_degrees_original = bundle["out_degrees_original"]
    theorems_processed = bundle["theorems_processed"]
    theorems_skipped = bundle["theorems_skipped"]
    n_term = bundle["n_term"]
    total_theorems = bundle["total_theorems"]
    G = G_original
    in_degrees = in_degrees_original
    out_degrees = out_degrees_original
    premises_seen = {n for n in G_original.nodes() if G_original.nodes[n].get("node_type") == "premise"}
    theorems_seen = {n for n in G_original.nodes() if G_original.nodes[n].get("node_type") == "theorem"}
    graph_build_time = 0.0
    degree_time = 0.0
    measures = bundle.get("measures")
    ego_networks = bundle.get("ego_networks")
    print("  Loaded graph and degrees from cache.")
else:
    from_cache = False
    measures = None
    ego_networks = None
    graph_build_start = time.time()
    # First, count total lines for progress bar
    print("  Cache not found or outdated; building from data.")
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
            # Skip tactics and hypothesis names (simpa, hx, symm, etc.) - not real lemmas
            for premise_full_name in all_premises.keys():
                if not premise_full_name or _is_tactic_or_hyp(premise_full_name):
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

    graph_build_time = time.time() - graph_build_start
    total_theorems = theorems_processed + theorems_skipped
    # Pre-compute degrees once for efficiency
    degree_start = time.time()
    in_degrees = dict(G.in_degree())
    out_degrees = dict(G.out_degree())
    degree_time = time.time() - degree_start
    G_original = G.copy()
    in_degrees_original = in_degrees.copy()
    out_degrees_original = out_degrees.copy()

if from_cache:
    print("\nLoaded from cache (graph + degrees):")
else:
    print(f"\nGraph built in {graph_build_time:.2f}s:")
print(f"  Theorems processed (tactic): {theorems_processed:,}")
print(f"  Theorems skipped (non-tactic): {theorems_skipped:,} (term: {n_term:,})")
print(f"  Nodes: {G.number_of_nodes():,}")
print(f"    - Premises: {len(premises_seen):,}")
print(f"    - Theorems: {len(theorems_seen):,}")
print(f"  Edges (premise->theorem): {G.number_of_edges():,}")
if not from_cache:
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

# G_original, in_degrees_original, out_degrees_original already set (from build or cache)

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

# ============================================================================
# Transitivity and Motif Detection
# ============================================================================

def compute_transitivity(G, in_degrees):
    """
    Compute fraction of theorems v that are connected to at least one parent of their parent.
    Parent = premise used in v's proof (incoming edge to v).
    """
    print("\nComputing transitivity...")
    trans_start = time.time()
    theorem_nodes = [n for n in G.nodes() if G.nodes[n].get("node_type") == "theorem"]
    transitive_count = 0
    total_with_grandparents = 0
    
    for v in theorem_nodes:
        # Get parents of v (premises used by v)
        parents_v = list(G.predecessors(v))
        if len(parents_v) == 0:
            continue
        
        # For each parent u, get its parents (grandparents of v)
        grandparents = set()
        for u in parents_v:
            grandparents.update(G.predecessors(u))
        
        if len(grandparents) == 0:
            continue
        
        total_with_grandparents += 1
        # Check if v is connected to any grandparent
        if any(G.has_edge(gp, v) for gp in grandparents):
            transitive_count += 1
    
    transitivity = transitive_count / total_with_grandparents if total_with_grandparents > 0 else 0.0
    print(f"  Transitivity: {transitive_count:,} / {total_with_grandparents:,} = {transitivity:.4f}")
    print(f"  Time: {time.time() - trans_start:.2f}s")
    return transitivity


def classify_3node_motif(subgraph):
    """
    Classify a 3-node directed subgraph into one of 13 possible motif types.
    Returns motif type name and edge pattern.
    """
    nodes = list(subgraph.nodes())
    if len(nodes) != 3:
        return None, None
    
    edges = set(subgraph.edges())
    n_edges = len(edges)
    
    # Build adjacency sets for quick lookup
    out_edges = {n: set() for n in nodes}
    in_edges = {n: set() for n in nodes}
    for u, v in edges:
        out_edges[u].add(v)
        in_edges[v].add(u)
    
    a, b, c = nodes
    
    # Classify based on edge count and pattern
    if n_edges == 0:
        return "M0: Empty", "No edges"
    elif n_edges == 1:
        if (a, b) in edges:
            return "M1: Single edge", "A→B"
        elif (b, c) in edges:
            return "M1: Single edge", "B→C"
        else:
            return "M1: Single edge", "A→C"
    elif n_edges == 2:
        if (a, b) in edges and (b, c) in edges:
            return "M2: Chain", "A→B→C"
        elif (a, b) in edges and (a, c) in edges:
            return "M3: Fan-out", "A→B, A→C"
        elif (a, c) in edges and (b, c) in edges:
            return "M4: Fan-in", "A→C, B→C"
        elif (a, b) in edges and (c, b) in edges:
            return "M5: Mutual", "A→B, C→B"
        elif (a, b) in edges and (b, a) in edges:
            return "M6: Mutual pair", "A↔B"
        else:
            return "M7: Other 2-edge", "Other"
    elif n_edges == 3:
        if (a, b) in edges and (b, c) in edges and (a, c) in edges:
            return "M8: Feed-forward loop", "A→B→C, A→C"
        elif (a, b) in edges and (b, c) in edges and (c, a) in edges:
            return "M9: Cycle", "A→B→C→A"
        elif (a, b) in edges and (b, a) in edges and (a, c) in edges:
            return "M10: Mutual+edge", "A↔B, A→C"
        else:
            return "M11: Other 3-edge", "Other"
    elif n_edges == 4:
        if (a, b) in edges and (b, a) in edges and (a, c) in edges and (b, c) in edges:
            return "M12: Mutual+fan", "A↔B, A→C, B→C"
        else:
            return "M13: Other 4-edge", "Other"
    elif n_edges == 5:
        return "M14: Near-complete", "5 edges"
    elif n_edges == 6:
        return "M15: Complete", "All 6 edges"
    else:
        return f"M{n_edges}: Unknown", f"{n_edges} edges"


def make_dag_by_removing_cycles(G):
    """
    Convert a directed graph to a DAG by removing minimal edges (feedback arc set).
    Uses a greedy approach: find cycles and remove edges to break them.
    
    Returns: (G_dag, removed_edges) where G_dag is a DAG and removed_edges is the list of removed edges.
    """
    print("  Converting graph to DAG by removing cycles...")
    G_dag = G.copy()
    removed_edges = []
    
    # Check if already a DAG
    if nx.is_directed_acyclic_graph(G_dag):
        print("    Graph is already a DAG, no edges removed")
        return G_dag, removed_edges
    
    # Try NetworkX's feedback_arc_set first (most efficient if available)
    try:
        # Check if feedback_arc_set is available
        if hasattr(nx.algorithms, 'feedback') and hasattr(nx.algorithms.feedback, 'feedback_arc_set'):
            print("    Using NetworkX feedback_arc_set algorithm...")
            fas = nx.algorithms.feedback.feedback_arc_set(G_dag)
            for edge in fas:
                if G_dag.has_edge(*edge):
                    G_dag.remove_edge(*edge)
                    removed_edges.append(edge)
            print(f"    Removed {len(fas)} edges using feedback_arc_set")
            if nx.is_directed_acyclic_graph(G_dag):
                print("    Successfully converted to DAG")
                return G_dag, removed_edges
    except (AttributeError, ImportError, Exception) as e:
        print(f"    feedback_arc_set not available ({e}), using manual cycle removal...")
    
    # Manual cycle removal: find strongly connected components (SCCs) - cycles are within SCCs
    print("    Finding strongly connected components...")
    sccs = list(nx.strongly_connected_components(G_dag))
    cyclic_sccs = [scc for scc in sccs if len(scc) > 1]
    
    if not cyclic_sccs:
        print("    No cycles found, graph is a DAG")
        return G_dag, removed_edges
    
    print(f"    Found {len(cyclic_sccs)} strongly connected components with cycles")
    
    # For each cyclic SCC, find and remove edges to break cycles
    total_removed = 0
    
    for idx, scc in enumerate(cyclic_sccs):
        if len(scc) == 1:
            continue
        
        if len(cyclic_sccs) > 10 and idx % 10 == 0:
            print(f"    Processing SCC {idx+1}/{len(cyclic_sccs)}...")
        
        # Create subgraph for this SCC
        G_scc = G_dag.subgraph(scc).copy()
        
        # Find cycles and remove edges greedily
        max_iterations = 50  # Limit iterations per SCC
        iteration = 0
        
        while iteration < max_iterations:
            try:
                # Try to find a simple cycle
                cycle = None
                # Try a few starting nodes
                nodes_to_try = list(G_scc.nodes())[:min(10, len(G_scc))]
                for node in nodes_to_try:
                    try:
                        cycle = list(nx.find_cycle(G_scc, node, orientation='original'))
                        if cycle:
                            break
                    except nx.NetworkXNoCycle:
                        continue
                
                if not cycle:
                    break  # No more cycles in this SCC
                
                # Remove the first edge of the cycle (greedy)
                edge_to_remove = cycle[0]  # (u, v) tuple
                if G_dag.has_edge(*edge_to_remove):
                    G_dag.remove_edge(*edge_to_remove)
                    removed_edges.append(edge_to_remove)
                    total_removed += 1
                    # Also remove from SCC subgraph for next iteration
                    if G_scc.has_edge(*edge_to_remove):
                        G_scc.remove_edge(*edge_to_remove)
                
            except nx.NetworkXNoCycle:
                break
            except Exception as e:
                # If finding cycles fails, use heuristic: remove edges to high in-degree nodes
                in_degrees_scc = dict(G_scc.in_degree())
                if in_degrees_scc:
                    # Remove edge to node with highest in-degree
                    max_node = max(in_degrees_scc.items(), key=lambda x: x[1])[0]
                    predecessors = list(G_scc.predecessors(max_node))
                    if predecessors:
                        edge_to_remove = (predecessors[0], max_node)
                        if G_dag.has_edge(*edge_to_remove):
                            G_dag.remove_edge(*edge_to_remove)
                            removed_edges.append(edge_to_remove)
                            total_removed += 1
                            if G_scc.has_edge(*edge_to_remove):
                                G_scc.remove_edge(*edge_to_remove)
                break
            
            iteration += 1
    
    # Verify result is a DAG
    is_dag = nx.is_directed_acyclic_graph(G_dag)
    print(f"    Removed {total_removed} edges to break cycles")
    print(f"    Result is DAG: {is_dag}")
    
    if not is_dag:
        print("    Warning: Still contains cycles after manual removal")
        # Try one more pass with aggressive removal
        remaining_cycles = 0
        try:
            for _ in range(10):  # Try up to 10 more cycles
                cycle = list(nx.find_cycle(G_dag))
                if cycle:
                    edge_to_remove = cycle[0]
                    G_dag.remove_edge(*edge_to_remove)
                    removed_edges.append(edge_to_remove)
                    total_removed += 1
                    remaining_cycles += 1
                else:
                    break
        except nx.NetworkXNoCycle:
            pass
        
        if remaining_cycles > 0:
            print(f"    Removed {remaining_cycles} additional edges in final pass")
            is_dag = nx.is_directed_acyclic_graph(G_dag)
            print(f"    Final result is DAG: {is_dag}")
    
    return G_dag, removed_edges


def detect_3node_motifs(G, sample_size=None):
    """
    Efficiently count feed-forward loops (3-node transitive triangles) only.
    
    Only computes: Transitive triangle / Feed-forward loop (u→v, v→w, u→w)
    
    Algorithm based on efficient DAG motif counting using topological order and set intersections.
    """
    print("\nDetecting 3-node DAG motifs (using efficient topological order algorithm)...")
    motif_start = time.time()
    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()
    
    # Verify DAG and convert if needed
    G_work = G
    removed_edges = []
    if not nx.is_directed_acyclic_graph(G):
        print("  Graph is not a DAG, removing cycles to create DAG...")
        G_work, removed_edges = make_dag_by_removing_cycles(G)
        if not nx.is_directed_acyclic_graph(G_work):
            print("  Warning: Failed to convert to DAG, proceeding anyway (may have errors)")
        else:
            print(f"  Using DAG version: {G_work.number_of_nodes():,} nodes, {G_work.number_of_edges():,} edges")
            if removed_edges:
                print(f"  (Removed {len(removed_edges):,} edges to break cycles)")
    
    # Preprocess: Build adjacency sets (using DAG version)
    print("  Building adjacency dictionaries...")
    Out = {n: set(G_work.successors(n)) for n in G_work.nodes()}
    In = {n: set(G_work.predecessors(n)) for n in G_work.nodes()}
    all_edges_set = set(G_work.edges())
    
    motif_counts = Counter()
    motif_patterns = {}
    
    # For large graphs, sample edges/nodes for efficiency
    all_edges_list = list(G_work.edges())
    all_nodes_list = list(G_work.nodes())
    n_nodes_work = G_work.number_of_nodes()
    n_edges_work = G_work.number_of_edges()
    
    # Determine if we need sampling (use DAG version sizes)
    use_sampling = sample_size is not None and (n_edges_work > sample_size or n_nodes_work > sample_size)
    
    if use_sampling:
        import random
        if n_edges_work > sample_size:
            sample_edges = random.sample(all_edges_list, min(sample_size, n_edges_work))
            print(f"  Sampling {len(sample_edges):,} edges from {n_edges_work:,} total")
        else:
            sample_edges = all_edges_list
        
        if n_nodes_work > sample_size:
            sample_nodes = random.sample(all_nodes_list, min(sample_size, n_nodes_work))
            print(f"  Sampling {len(sample_nodes):,} nodes from {n_nodes_work:,} total")
        else:
            sample_nodes = all_nodes_list
    else:
        sample_edges = all_edges_list
        sample_nodes = all_nodes_list
        print(f"  Processing all {n_edges_work:,} edges and {n_nodes_work:,} nodes")
    
    # Count transitive triangles (feed-forward loops): u→v, v→w, u→w
    # For each edge u→v, compute Out(u) ∩ Out(v)
    print("  Counting feed-forward loops (transitive triangles)...")
    transitive_count = 0
    if HAS_TQDM:
        edge_iter = tqdm(sample_edges, desc="    Processing edges", unit="edges")
    else:
        edge_iter = sample_edges
    
    for u, v in edge_iter:
        # Intersection of Out(u) and Out(v) gives w such that u→w and v→w
        # Combined with u→v, this forms transitive triangle u→v, v→w, u→w
        intersection = Out[u] & Out[v]
        transitive_count += len(intersection)
    
    # Scale count if sampling
    if use_sampling and len(sample_edges) < n_edges_work:
        scale_factor = n_edges_work / len(sample_edges)
        transitive_count = int(transitive_count * scale_factor)
    
    if transitive_count > 0:
        motif_counts["Feed-forward loop"] = transitive_count
        motif_patterns["Feed-forward loop"] = "A→B→C, A→C"
    
    total = sum(motif_counts.values())
    print(f"  Summary:")
    print(f"  Found {total:,} feed-forward loops")
    if use_sampling:
        print(f"  (Counts scaled from sampled {len(sample_edges):,} edges)")
    print(f"  Time: {time.time() - motif_start:.2f}s")
    
    return dict(motif_counts), motif_patterns, removed_edges


def detect_4node_motifs(G, sample_size=None):
    """
    Efficiently count 4-node DAG motifs using ESU-style enumeration with topological ordering.
    
    Detects:
    - 4-chains (u→v→w→x, induced, no shortcuts)
    - Diamonds (u→v, u→w, v→x, w→x, with v and w incomparable)
    
    Uses efficient algorithms that exploit DAG structure.
    """
    print("\nDetecting 4-node DAG motifs (using efficient enumeration)...")
    motif_start = time.time()
    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()
    
    # Verify DAG and convert if needed
    G_work = G
    removed_edges = []
    if not nx.is_directed_acyclic_graph(G):
        print("  Graph is not a DAG, removing cycles to create DAG...")
        G_work, removed_edges = make_dag_by_removing_cycles(G)
        if not nx.is_directed_acyclic_graph(G_work):
            print("  Warning: Failed to convert to DAG, proceeding anyway (may have errors)")
        else:
            print(f"  Using DAG version: {G_work.number_of_nodes():,} nodes, {G_work.number_of_edges():,} edges")
    
    # Preprocess: Build adjacency sets
    print("  Building adjacency dictionaries...")
    Out = {n: set(G_work.successors(n)) for n in G_work.nodes()}
    In = {n: set(G_work.predecessors(n)) for n in G_work.nodes()}
    all_edges_set = set(G_work.edges())
    
    motif_counts = Counter()
    motif_patterns = {}
    
    n_nodes_work = G_work.number_of_nodes()
    n_edges_work = G_work.number_of_edges()
    
    # Determine if we need sampling
    use_sampling = sample_size is not None and (n_edges_work > sample_size or n_nodes_work > sample_size)
    
    if use_sampling:
        import random
        all_edges_list = list(G_work.edges())
        if n_edges_work > sample_size:
            sample_edges = random.sample(all_edges_list, min(sample_size, n_edges_work))
            print(f"  Sampling {len(sample_edges):,} edges from {n_edges_work:,} total")
        else:
            sample_edges = all_edges_list
    else:
        sample_edges = list(G_work.edges())
        print(f"  Processing all {n_edges_work:,} edges")
    
    # ========================================================================
    # Count diamonds (u→v, u→w, v→x, w→x, with v and w incomparable)
    # Structure: Two paths from u to x via v and w, where v and w have no edge
    # Algorithm: For each node x with at least 2 predecessors, check pairs of predecessors
    # ========================================================================
    print("  Counting diamonds...")
    diamond_count = 0
    
    # Get all nodes with at least 2 predecessors (potential x nodes)
    candidate_x_nodes = [n for n in G_work.nodes() if len(In[n]) >= 2]
    
    if use_sampling and len(candidate_x_nodes) > sample_size:
        import random
        candidate_x_nodes = random.sample(candidate_x_nodes, sample_size)
        print(f"  Sampling {len(candidate_x_nodes):,} nodes from {len([n for n in G_work.nodes() if len(In[n]) >= 2]):,} candidates")
    
    if HAS_TQDM:
        node_iter = tqdm(candidate_x_nodes, desc="    Processing nodes", unit="nodes")
    else:
        node_iter = candidate_x_nodes
    
    for x in node_iter:
        in_x = In[x]
        if len(in_x) < 2:
            continue
        
        # Check all pairs of predecessors (v, w) of x
        in_x_list = list(in_x)
        for idx, v in enumerate(in_x_list):
            for w in in_x_list[idx+1:]:
                # Check that v→x and w→x exist (already true since v, w ∈ In(x))
                # Now check if there exists a common predecessor u of both v and w
                # such that u→v and u→w exist, and v and w are incomparable (no edge between them)
                
                # Find common predecessors of v and w
                common_preds = In[v] & In[w]
                
                for u in common_preds:
                    # Check that u→v and u→w exist (already true since u ∈ In[v] ∩ In[w])
                    # Check that v and w are incomparable (no edge between them)
                    if (v, w) not in all_edges_set and (w, v) not in all_edges_set:
                        # Found a diamond: u→v, u→w, v→x, w→x
                        diamond_count += 1
    
    # Scale count if sampling
    if use_sampling and len(candidate_x_nodes) < len([n for n in G_work.nodes() if len(In[n]) >= 2]):
        node_scale_factor = len([n for n in G_work.nodes() if len(In[n]) >= 2]) / len(candidate_x_nodes)
        diamond_count = int(diamond_count * node_scale_factor)
    
    if diamond_count > 0:
        motif_counts["Diamond"] = diamond_count
        motif_patterns["Diamond"] = "A→B, A→C, B→D, C→D (B,C incomparable)"
    
    total = sum(motif_counts.values())
    print(f"  Summary:")
    print(f"  Found {total:,} 4-node DAG motifs across {len(motif_counts)} types")
    if use_sampling:
        print(f"  (Counts scaled from sampled data)")
    print(f"  Time: {time.time() - motif_start:.2f}s")
    
    return dict(motif_counts), motif_patterns


def compute_ego_feedforward(x, Out, In, all_edges_set):
    """
    Compute feed-forward triads with x in the middle: FF(x) = sum over children c of |In(c) ∩ P|
    where P = In(x) are parents, C = Out(x) are children.
    """
    P = In[x]  # Parents
    C = Out[x]  # Children
    
    if not P or not C:
        return 0
    
    # Mark parents for fast lookup
    P_set = set(P)
    
    # For each child c, count how many of its predecessors are in P
    FF_count = 0
    for c in C:
        in_c = In[c]
        FF_count += len(in_c & P_set)
    
    return FF_count


def compute_ego_diamonds(x, Out, In, all_edges_set):
    """
    Compute diamonds where x is one of the two middle nodes.
    For candidate co-middle node w, count diamonds using (x, w).
    """
    P = In[x]  # Parents
    C = Out[x]  # Children
    
    if not P or not C:
        return 0
    
    # Build U = union of Out(u) for u in P (one-step forward from parents)
    U = set()
    for u in P:
        U.update(Out[u])
    
    # Build V = union of In(v) for v in C (one-step backward from children)
    V = set()
    for v in C:
        V.update(In[v])
    
    # Only w in U ∩ V can contribute
    candidates = U & V
    candidates.discard(x)  # Remove x itself
    
    P_set = set(P)
    C_set = set(C)
    
    diamond_count = 0
    for w in candidates:
        # a_w = |In(w) ∩ P|
        a_w = len(In[w] & P_set)
        # b_w = |Out(w) ∩ C|
        b_w = len(Out[w] & C_set)
        
        # Optional: filter if x→w or w→x exists (induced filter)
        if (x, w) in all_edges_set or (w, x) in all_edges_set:
            continue
        
        diamond_count += a_w * b_w
    
    return diamond_count


def compute_ego_topology_features(x, Out, In, all_edges_set):
    """
    Compute ego-topology features for node x:
    - Bypass density: ρ_bypass(x) = FF(x) / (|P| * |C|)
    - Child-wise disruption index: D(x)
    - Effective compression usage: U_eff(x)
    - Optimal code length: ℓ_opt(x) ∝ -log U_eff(x)
    """
    P = In[x]
    C = Out[x]
    
    features = {}
    
    # Bypass density
    FF_x = compute_ego_feedforward(x, Out, In, all_edges_set)
    if len(P) * len(C) > 0:
        features['bypass_density'] = FF_x / (len(P) * len(C))
    else:
        features['bypass_density'] = 0.0
    
    # Child-wise disruption
    disruptive_count = 0
    consolidating_count = 0
    r_c_values = []
    P_set = set(P)
    
    for c in C:
        r_c = len(In[c] & P_set)
        r_c_values.append(r_c)
        if r_c == 0:
            disruptive_count += 1
        else:
            consolidating_count += 1
    
    if len(C) > 0:
        features['disruption_index'] = (disruptive_count - consolidating_count) / len(C)
    else:
        features['disruption_index'] = 0.0
    
    # Effective compression usage
    U_eff = 0.0
    if len(P) > 0:
        for r_c in r_c_values:
            U_eff += (1 - r_c / len(P))
    else:
        U_eff = len(C)  # If no parents, all children count fully
    
    features['effective_usage'] = U_eff
    
    # Optimal code length (proportional to -log U_eff)
    if U_eff > 0:
        features['optimal_code_length'] = -np.log(U_eff)
    else:
        features['optimal_code_length'] = float('inf')
    
    features['feedforward_count'] = FF_x
    features['num_parents'] = len(P)
    features['num_children'] = len(C)
    
    return features


def degree_preserving_edge_swap(G, tau, num_swaps=1000):
    """
    Generate a randomized graph using degree-preserving edge-swap Markov chain.
    
    Constraint: exact in/out degrees and topological order τ.
    Move: pick edges a→b and c→d; propose a→d and c→b (swap targets) if:
    - τ(a) < τ(d) and τ(c) < τ(b) (topological order respected)
    - edges don't already exist
    
    This preserves degrees and guarantees no cycles.
    """
    G_rand = G.copy()
    all_edges_list = list(G_rand.edges())
    all_edges_set = set(G_rand.edges())
    
    import random
    
    successful_swaps = 0
    attempts = 0
    max_attempts = num_swaps * 10  # Allow some rejection
    
    while successful_swaps < num_swaps and attempts < max_attempts:
        attempts += 1
        
        # Pick two random edges
        if len(all_edges_list) < 2:
            break
        
        edge1 = random.choice(all_edges_list)
        edge2 = random.choice(all_edges_list)
        
        if edge1 == edge2:
            continue
        
        a, b = edge1
        c, d = edge2
        
        # Check topological order constraints: τ(a) < τ(d) and τ(c) < τ(b)
        if tau[a] >= tau[d] or tau[c] >= tau[b]:
            continue
        
        # Check that new edges don't already exist
        if (a, d) in all_edges_set or (c, b) in all_edges_set:
            continue
        
        # Perform swap
        G_rand.remove_edge(a, b)
        G_rand.remove_edge(c, d)
        G_rand.add_edge(a, d)
        G_rand.add_edge(c, b)
        
        # Update edge list and set
        all_edges_list.remove((a, b))
        all_edges_list.remove((c, d))
        all_edges_list.append((a, d))
        all_edges_list.append((c, b))
        
        all_edges_set.remove((a, b))
        all_edges_set.remove((c, d))
        all_edges_set.add((a, d))
        all_edges_set.add((c, b))
        
        successful_swaps += 1
    
    return G_rand


def compute_motif_z_scores(G_true, motif_counts_true, num_random=10, num_swaps=None):
    """
    Generate random networks and compute z-scores for motif counts.
    
    Returns: dict mapping motif names to z-scores
    """
    print(f"\nGenerating {num_random} random networks for z-score computation...")
    
    # Get topological order
    try:
        tau_list = list(nx.topological_sort(G_true))
        tau = {node: idx for idx, node in enumerate(tau_list)}
    except:
        print("  Warning: Graph is not a DAG, cannot compute topological order")
        return {}
    
    # Determine number of swaps (default: 10x number of edges)
    if num_swaps is None:
        num_swaps = G_true.number_of_edges() * 10
    
    # Generate random networks and count motifs
    random_motif_counts = defaultdict(list)
    
    if HAS_TQDM:
        rand_iter = tqdm(range(num_random), desc="  Generating random networks", unit="networks")
    else:
        rand_iter = range(num_random)
    
    for i in rand_iter:
        G_rand = degree_preserving_edge_swap(G_true, tau, num_swaps=num_swaps)
        
        # Count motifs in random network (only feed-forward and diamond)
        # Feed-forward loops
        Out_rand = {n: set(G_rand.successors(n)) for n in G_rand.nodes()}
        ff_count = 0
        for u, v in G_rand.edges():
            intersection = Out_rand[u] & Out_rand[v]
            ff_count += len(intersection)
        random_motif_counts["Feed-forward loop"].append(ff_count)
        
        # Diamonds
        In_rand = {n: set(G_rand.predecessors(n)) for n in G_rand.nodes()}
        all_edges_set_rand = set(G_rand.edges())
        diamond_count = 0
        candidate_x_nodes = [n for n in G_rand.nodes() if len(In_rand[n]) >= 2]
        for x in candidate_x_nodes:
            in_x = In_rand[x]
            if len(in_x) < 2:
                continue
            in_x_list = list(in_x)
            for idx, v in enumerate(in_x_list):
                for w in in_x_list[idx+1:]:
                    common_preds = In_rand[v] & In_rand[w]
                    for u in common_preds:
                        if (v, w) not in all_edges_set_rand and (w, v) not in all_edges_set_rand:
                            diamond_count += 1
        random_motif_counts["Diamond"].append(diamond_count)
    
    # Compute z-scores
    z_scores = {}
    for motif_name in motif_counts_true.keys():
        if motif_name not in random_motif_counts:
            continue
        
        true_count = motif_counts_true[motif_name]
        random_counts = random_motif_counts[motif_name]
        
        if len(random_counts) == 0:
            continue
        
        mean_random = np.mean(random_counts)
        std_random = np.std(random_counts)
        
        if std_random > 0:
            z_score = (true_count - mean_random) / std_random
        else:
            z_score = 0.0
        
        z_scores[motif_name] = {
            'z_score': z_score,
            'true_count': true_count,
            'mean_random': mean_random,
            'std_random': std_random
        }
    
    return z_scores


# Compute measures and extract ego networks (or use from cache)
if measures is not None and ego_networks is not None:
    measures_time = 0.0
    ego_time = 0.0
    print("\nUsing cached measures and ego networks.")
    # Still compute transitivity and motifs if not cached
    if 'transitivity' not in measures:
        transitivity = compute_transitivity(G_original, in_degrees_original)
        measures['transitivity'] = transitivity
    if 'motif_counts' not in measures:
        motif_counts, motif_patterns, feedback_arc_set = detect_3node_motifs(G_original, sample_size=50000 if G_original.number_of_nodes() > 50000 else None)
        measures['motif_counts'] = motif_counts
        measures['motif_patterns'] = motif_patterns
        measures['feedback_arc_set'] = feedback_arc_set
    else:
        feedback_arc_set = measures.get('feedback_arc_set', [])
    
    if 'motif_4_counts' not in measures:
        motif_4_counts, motif_4_patterns = detect_4node_motifs(G_original, sample_size=50000 if G_original.number_of_nodes() > 50000 else None)
        measures['motif_4_counts'] = motif_4_counts
        measures['motif_4_patterns'] = motif_4_patterns
    
    # Compute z-scores and ego features if not cached
    if 'motif_z_scores' not in measures:
        all_motif_counts = {}
        all_motif_counts.update(measures.get('motif_counts', {}))
        all_motif_counts.update(measures.get('motif_4_counts', {}))
        z_scores = compute_motif_z_scores(G_original, all_motif_counts, num_random=10)
        measures['motif_z_scores'] = z_scores
    
    if 'ego_topology_features' not in measures:
        print("\nComputing ego-local motifs and topology features...")
        Out_all = {n: set(G_original.successors(n)) for n in G_original.nodes()}
        In_all = {n: set(G_original.predecessors(n)) for n in G_original.nodes()}
        all_edges_set_all = set(G_original.edges())
        
        ego_features = {}
        ego_ff_counts = {}
        ego_diamond_counts = {}
        
        theorems_to_process = [n for n in G_original.nodes() if G_original.nodes[n].get("node_type") == "theorem"]
        
        if HAS_TQDM:
            node_iter = tqdm(theorems_to_process, desc="  Processing theorems", unit="nodes")
        else:
            node_iter = theorems_to_process
        
        for x in node_iter:
            ego_ff_counts[x] = compute_ego_feedforward(x, Out_all, In_all, all_edges_set_all)
            ego_diamond_counts[x] = compute_ego_diamonds(x, Out_all, In_all, all_edges_set_all)
            ego_features[x] = compute_ego_topology_features(x, Out_all, In_all, all_edges_set_all)
        
        measures['ego_feedforward'] = ego_ff_counts
        measures['ego_diamonds'] = ego_diamond_counts
        measures['ego_topology_features'] = ego_features
    
    # Report feedback arc set if present
    if feedback_arc_set:
        print(f"\nFeedback Arc Set: {len(feedback_arc_set)} edges removed to create DAG")
        print("  Sample of removed edges (first 10):")
        for i, (u, v) in enumerate(feedback_arc_set[:10]):
            u_short = u.split('.')[-1] if '.' in u else u[:50]
            v_short = v.split('.')[-1] if '.' in v else v[:50]
            print(f"    {i+1}. {u_short} → {v_short}")
        if len(feedback_arc_set) > 10:
            print(f"    ... and {len(feedback_arc_set) - 10} more edges")
        
        # Save feedback arc set to file
        feedback_arc_file = _SCRIPT_DIR / "feedback_arc_set.txt"
        with open(feedback_arc_file, 'w', encoding='utf-8') as f:
            f.write(f"Feedback Arc Set: {len(feedback_arc_set)} edges removed to create DAG\n")
            f.write("=" * 80 + "\n\n")
            for u, v in feedback_arc_set:
                f.write(f"{u}\t→\t{v}\n")
        print(f"  Saved feedback arc set to: {feedback_arc_file}")
    else:
        print("\nFeedback Arc Set: No edges removed (graph was already a DAG)")
else:
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

    # Compute transitivity and motifs
    transitivity = compute_transitivity(G_original, in_degrees_original)
    measures['transitivity'] = transitivity
    
    # Detect 3-node motifs (only feed-forward loops)
    motif_counts, motif_patterns, feedback_arc_set = detect_3node_motifs(G_original, sample_size=50000 if G_original.number_of_nodes() > 50000 else None)
    measures['motif_counts'] = motif_counts
    measures['motif_patterns'] = motif_patterns
    measures['feedback_arc_set'] = feedback_arc_set
    
    # Detect 4-node motifs (only diamonds)
    motif_4_counts, motif_4_patterns = detect_4node_motifs(G_original, sample_size=50000 if G_original.number_of_nodes() > 50000 else None)
    measures['motif_4_counts'] = motif_4_counts
    measures['motif_4_patterns'] = motif_4_patterns
    
    # Combine motif counts for z-score computation
    all_motif_counts = {}
    all_motif_counts.update(motif_counts)
    all_motif_counts.update(motif_4_counts)
    
    # Compute z-scores using degree-preserving randomization
    print("\nComputing motif z-scores...")
    z_scores = compute_motif_z_scores(G_original, all_motif_counts, num_random=10)
    measures['motif_z_scores'] = z_scores
    
    # Compute ego-local motifs and topology features for all nodes
    print("\nComputing ego-local motifs and topology features...")
    Out_all = {n: set(G_original.successors(n)) for n in G_original.nodes()}
    In_all = {n: set(G_original.predecessors(n)) for n in G_original.nodes()}
    all_edges_set_all = set(G_original.edges())
    
    ego_features = {}
    ego_ff_counts = {}
    ego_diamond_counts = {}
    
    # Only compute for theorems (not premises) to save time
    theorems_to_process = [n for n in G_original.nodes() if G_original.nodes[n].get("node_type") == "theorem"]
    
    if HAS_TQDM:
        node_iter = tqdm(theorems_to_process, desc="  Processing theorems", unit="nodes")
    else:
        node_iter = theorems_to_process
    
    for x in node_iter:
        ego_ff_counts[x] = compute_ego_feedforward(x, Out_all, In_all, all_edges_set_all)
        ego_diamond_counts[x] = compute_ego_diamonds(x, Out_all, In_all, all_edges_set_all)
        ego_features[x] = compute_ego_topology_features(x, Out_all, In_all, all_edges_set_all)
    
    measures['ego_feedforward'] = ego_ff_counts
    measures['ego_diamonds'] = ego_diamond_counts
    measures['ego_topology_features'] = ego_features
    
    # Report and save feedback arc set
    if feedback_arc_set:
        print(f"\nFeedback Arc Set: {len(feedback_arc_set)} edges removed to create DAG")
        print("  Sample of removed edges (first 10):")
        for i, (u, v) in enumerate(feedback_arc_set[:10]):
            u_short = u.split('.')[-1] if '.' in u else u[:50]
            v_short = v.split('.')[-1] if '.' in v else v[:50]
            print(f"    {i+1}. {u_short} → {v_short}")
        if len(feedback_arc_set) > 10:
            print(f"    ... and {len(feedback_arc_set) - 10} more edges")
        
        # Save feedback arc set to file
        feedback_arc_file = _SCRIPT_DIR / "feedback_arc_set.txt"
        with open(feedback_arc_file, 'w', encoding='utf-8') as f:
            f.write(f"Feedback Arc Set: {len(feedback_arc_set)} edges removed to create DAG\n")
            f.write("=" * 80 + "\n\n")
            for u, v in feedback_arc_set:
                f.write(f"{u}\t→\t{v}\n")
        print(f"  Saved feedback arc set to: {feedback_arc_file}")
    else:
        print("\nFeedback Arc Set: No edges removed (graph was already a DAG)")
    
    # Generate ego network data before saving to cache
    print("\nGenerating ego network data for dashboard cache...")
    theorems_list_cache = [n for n in G_original.nodes() if G_original.nodes[n].get("node_type") == "theorem"]
    ego_network_data_cache = generate_ego_network_data(G_original, theorems_list_cache)
    
    # Save full bundle to cache (so next run can skip graph + measures + ego)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _save_cache({
        "G_original": G_original,
        "in_degrees_original": in_degrees_original,
        "out_degrees_original": out_degrees_original,
        "theorems_processed": theorems_processed,
        "theorems_skipped": theorems_skipped,
        "n_term": n_term,
        "total_theorems": total_theorems,
        "measures": measures,
        "ego_networks": ego_networks,
        "ego_network_data": ego_network_data_cache,
        "theorems_list": theorems_list_cache
    })
    print(f"  Cache saved to {CACHE_DIR} (next run will use it).")

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
    
    # Save unresolved premises to txt for analyses (one full_name per line, sorted)
    unresolved_txt = _SCRIPT_DIR / "unresolved_premises.txt"
    with open(unresolved_txt, "w", encoding="utf-8") as f:
        for name in sorted(unresolved_premises):
            f.write(name + "\n")
    print(f"    ✓ Saved {len(unresolved_premises):,} unresolved premises to {unresolved_txt}")
    
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
    transitivity = measures.get('transitivity', 0.0)
    stats_text = f"""Graph Statistics
    
Nodes: {basic['nodes']:,}
Edges: {basic['edges']:,}
Density: {basic['density']:.6f}
Is DAG: {basic['is_dag']}
Components: {basic['num_components']}
Sources: {basic['num_sources']}
Sinks: {basic['num_sinks']}
Transitivity: {transitivity:.4f}
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

    # Panel 3b: Out-degree / (In+1) per node (distribution), same size/aesthetics as In-Degree
    ax3b = fig.add_subplot(gs[2, 0])
    in_deg = in_degrees_original
    out_deg = out_degrees_original
    ratios = []
    for n in G_original.nodes():
        i = in_deg.get(n, 0)
        o = out_deg.get(n, 0)
        ratios.append(o / (i + 1))
    if ratios:
        ratios = np.array(ratios)
        # Bin for log-log plot (same style as In-Degree: log-log, black markers)
        r_max = float(np.max(ratios))
        high = max(r_max, 0.1) + 1
        bins = np.logspace(-2, np.log10(high), 51)
        hist, bin_edges = np.histogram(ratios, bins=bins)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        # Plot on log-log like In-Degree (x+1 vs frequency)
        x_plot = bin_centers + 1
        ax3b.loglog(x_plot, hist, 'o', color='black', markersize=3, alpha=0.7)
        ax3b.set_xlabel('Out/(In+1)+1 (log)', fontsize=9)
        ax3b.set_ylabel('Frequency (log)', fontsize=9)
        ax3b.set_title('Out/(In+1) Distribution', fontsize=12, fontweight='normal', pad=10)
        ax3b.grid(True, alpha=0.3)
    else:
        ax3b.axis('off')
        ax3b.text(0.5, 0.5, 'No degree data', ha='center', va='center', transform=ax3b.transAxes)
        ax3b.set_title('Out/(In+1) Distribution', fontsize=12, fontweight='normal', pad=10)
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
    
    # Save main figure (stats only; ego networks in separate figure)
    print(f"  Saving to {output_pdf} and {output_png}...")
    plt.savefig(output_pdf, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.savefig(output_png, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()
    print(f"  Multipanel figure saved!")


def create_ego_figure(ego_networks, output_pdf, output_png, G_ref):
    """Create a separate figure with only ego network visualizations."""
    print("\n  Creating ego networks figure...")
    n_ego = len(ego_networks)
    n_cols = 6
    n_rows = max(1, (n_ego + n_cols - 1) // n_cols)
    fig = plt.figure(figsize=(24, 4 * n_rows), facecolor='white')
    gs = GridSpec(n_rows, n_cols, figure=fig, hspace=0.35, wspace=0.25,
                  left=0.03, right=0.97, top=0.96, bottom=0.02)
    
    for idx, ego_data in enumerate(ego_networks):
        row = idx // n_cols
        col = idx % n_cols
        if row >= n_rows:
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
        
        try:
            n_nodes = ego.number_of_nodes()
            if n_nodes <= 2:
                pos = nx.spring_layout(ego, k=1.0, iterations=10, seed=42)
            elif n_nodes <= 10:
                pos = nx.spring_layout(ego, k=0.8, iterations=15, seed=42)
            else:
                pos = nx.spring_layout(ego, k=0.5, iterations=20, seed=42)
        except Exception:
            pos = nx.circular_layout(ego)
        
        node_colors_ego = []
        node_sizes_ego = []
        ego_out_degrees = dict(ego.out_degree())
        max_out_deg = max(ego_out_degrees.values()) if ego_out_degrees.values() else 1
        
        for node in ego.nodes():
            if node == center:
                node_colors_ego.append('#000000')
                center_out_deg = ego_out_degrees.get(node, 0)
                node_sizes_ego.append(50 + (center_out_deg / max_out_deg) * 100 if max_out_deg > 0 else 100)
            else:
                node_type = G_ref.nodes[node].get("node_type", "unknown")
                node_colors_ego.append('#666666' if node_type == "premise" else '#999999')
                node_out_deg = ego_out_degrees.get(node, 0)
                node_sizes_ego.append(20 + (node_out_deg / max_out_deg) * 30 if max_out_deg > 0 else 30)
        
        nx.draw_networkx_nodes(ego, pos, node_color=node_colors_ego,
                              node_size=node_sizes_ego, alpha=0.9,
                              linewidths=0.5, edgecolors='black', ax=ax)
        nx.draw_networkx_edges(ego, pos, alpha=0.3, arrows=True,
                              arrowsize=8, edge_color='#000000', width=0.5, ax=ax)
        labels_ego = {center: name[:15]}
        other_nodes = [n for n in ego.nodes() if n != center]
        if other_nodes:
            for n, _ in sorted([(n, ego.degree(n)) for n in other_nodes], key=lambda x: x[1], reverse=True)[:2]:
                labels_ego[n] = (n.split('.')[-1] if '.' in n else n)[:12]
        nx.draw_networkx_labels(ego, pos, labels_ego, font_size=6,
                               font_color='#000000', font_weight='normal', ax=ax)
        title = f"{measure_type} ({extreme_type})"
        title += f"\n{name} (val={value})" if value is not None else f"\n{name}"
        ax.set_title(title, fontsize=7, fontweight='normal', pad=3)
        ax.axis('off')
    
    for idx in range(len(ego_networks), n_rows * n_cols):
        row = idx // n_cols
        col = idx % n_cols
        ax = fig.add_subplot(gs[row, col])
        ax.axis('off')
    
    print(f"  Saving ego figure to {output_pdf} and {output_png}...")
    plt.savefig(output_pdf, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.savefig(output_png, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()
    print(f"  Ego networks figure saved!")


def draw_motif_diagram(ax, pattern_str):
    """Draw a 3-node motif diagram based on pattern string."""
    # Parse pattern to extract edges
    G_motif = nx.DiGraph()
    nodes = ['A', 'B', 'C']
    G_motif.add_nodes_from(nodes)
    
    # Parse edges from pattern (e.g., "A→B→C, A→C" or "A↔B")
    if '→' in pattern_str:
        parts = pattern_str.split(',')
        for part in parts:
            part = part.strip()
            if '→' in part:
                edges = part.split('→')
                for i in range(len(edges) - 1):
                    u = edges[i].strip()
                    v = edges[i+1].strip()
                    if u in nodes and v in nodes:
                        G_motif.add_edge(u, v)
            elif '↔' in part:
                u, v = part.split('↔')
                u, v = u.strip(), v.strip()
                if u in nodes and v in nodes:
                    G_motif.add_edge(u, v)
                    G_motif.add_edge(v, u)
    
    # Layout: triangle with A top, B bottom-left, C bottom-right
    pos = {'A': (0.5, 0.9), 'B': (0.1, 0.1), 'C': (0.9, 0.1)}
    
    # Draw nodes
    nx.draw_networkx_nodes(G_motif, pos, node_color='lightblue', node_size=800,
                          ax=ax, alpha=0.8, edgecolors='black', linewidths=2)
    # Draw edges
    nx.draw_networkx_edges(G_motif, pos, ax=ax, arrows=True, arrowsize=20,
                          edge_color='black', width=2, alpha=0.8, arrowstyle='->')
    # Draw labels
    nx.draw_networkx_labels(G_motif, pos, font_size=14, font_weight='bold', ax=ax)
    ax.set_xlim(-0.1, 1.1)
    ax.set_ylim(-0.1, 1.1)
    ax.axis('off')


def create_motif_figure(motif_counts, motif_patterns, output_pdf, output_png):
    """Create a figure showing 3-node motif counts and visualizations."""
    print("\n  Creating motif figure...")
    if not motif_counts:
        print("  No motifs found.")
        return
    
    # Sort motifs by count (descending)
    sorted_motifs = sorted(motif_counts.items(), key=lambda x: x[1], reverse=True)
    n_motifs = len(sorted_motifs)
    n_cols = 4
    n_rows = (n_motifs + n_cols - 1) // n_cols
    
    fig = plt.figure(figsize=(20, 5 * n_rows), facecolor='white')
    gs = GridSpec(n_rows, n_cols, figure=fig, hspace=0.5, wspace=0.3,
                  left=0.05, right=0.95, top=0.96, bottom=0.02)
    
    total = sum(motif_counts.values())
    
    for idx, (motif_type, count) in enumerate(sorted_motifs):
        row = idx // n_cols
        col = idx % n_cols
        ax = fig.add_subplot(gs[row, col])
        
        pattern = motif_patterns.get(motif_type, "Unknown")
        pct = 100 * count / total if total > 0 else 0
        
        # Draw motif diagram
        try:
            draw_motif_diagram(ax, pattern)
        except:
            # Fallback to text if drawing fails
            ax.axis('off')
            ax.text(0.5, 0.5, pattern, fontsize=9, ha='center', va='center',
                   transform=ax.transAxes)
        
        # Add title with count
        title = f"{motif_type}\nCount: {count:,} ({pct:.2f}%)"
        ax.set_title(title, fontsize=10, fontweight='bold', pad=15)
    
    # Fill empty slots
    for idx in range(n_motifs, n_rows * n_cols):
        row = idx // n_cols
        col = idx % n_cols
        ax = fig.add_subplot(gs[row, col])
        ax.axis('off')
    
    print(f"  Saving motif figure to {output_pdf} and {output_png}...")
    plt.savefig(output_pdf, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.savefig(output_png, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()
    print(f"  Motif figure saved!")

# Create the multipanel figure (stats only), ego networks figure, and motif figure
print("\nCreating visualization...")
viz_start = time.time()
create_multipanel_figure(measures, ego_networks, OUTPUT_PDF, OUTPUT_PNG)
create_ego_figure(ego_networks, OUTPUT_PDF_EGONETS, OUTPUT_PNG_EGONETS, G_original)
motif_counts = measures.get('motif_counts', {})
motif_patterns = measures.get('motif_patterns', {})
if motif_counts:
    create_motif_figure(motif_counts, motif_patterns, OUTPUT_PDF_MOTIFS, OUTPUT_PNG_MOTIFS)

# Report 4-node motifs (diamonds)
motif_4_counts = measures.get('motif_4_counts', {})
motif_4_patterns = measures.get('motif_4_patterns', {})
if motif_4_counts:
    print("\n4-node Motif Summary (Diamonds):")
    total_4 = sum(motif_4_counts.values())
    for motif_type, count in sorted(motif_4_counts.items(), key=lambda x: x[1], reverse=True):
        pct = 100 * count / total_4 if total_4 > 0 else 0
        pattern = motif_4_patterns.get(motif_type, "Unknown")
        print(f"  {motif_type}: {count:,} ({pct:.2f}%) - {pattern}")

# Report z-scores
z_scores = measures.get('motif_z_scores', {})
if z_scores:
    print("\nMotif Z-Scores (vs degree-preserving random networks):")
    for motif_name, z_data in z_scores.items():
        print(f"  {motif_name}:")
        print(f"    Z-score: {z_data['z_score']:.3f}")
        print(f"    True count: {z_data['true_count']:,}")
        print(f"    Random mean: {z_data['mean_random']:.1f} ± {z_data['std_random']:.1f}")

# Report ego-topology summary
ego_features = measures.get('ego_topology_features', {})
if ego_features:
    print("\nEgo-Topology Features Summary:")
    bypass_densities = [f['bypass_density'] for f in ego_features.values() if 'bypass_density' in f]
    disruption_indices = [f['disruption_index'] for f in ego_features.values() if 'disruption_index' in f]
    effective_usages = [f['effective_usage'] for f in ego_features.values() if 'effective_usage' in f]
    
    if bypass_densities:
        print(f"  Bypass density: mean={np.mean(bypass_densities):.4f}, median={np.median(bypass_densities):.4f}")
    if disruption_indices:
        print(f"  Disruption index: mean={np.mean(disruption_indices):.4f}, median={np.median(disruption_indices):.4f}")
    if effective_usages:
        print(f"  Effective usage: mean={np.mean(effective_usages):.2f}, median={np.median(effective_usages):.2f}")
    
    # Find top theorems by various metrics
    if ego_features:
        top_bypass = sorted(ego_features.items(), key=lambda x: x[1].get('bypass_density', 0), reverse=True)[:5]
        top_disruption = sorted(ego_features.items(), key=lambda x: x[1].get('disruption_index', 0), reverse=True)[:5]
        top_usage = sorted(ego_features.items(), key=lambda x: x[1].get('effective_usage', 0), reverse=True)[:5]
        
        print("\n  Top 5 theorems by bypass density:")
        for i, (thm, feat) in enumerate(top_bypass, 1):
            thm_short = thm.split('.')[-1] if '.' in thm else thm[:50]
            print(f"    {i}. {thm_short}: {feat.get('bypass_density', 0):.4f}")
        
        print("\n  Top 5 theorems by disruption index:")
        for i, (thm, feat) in enumerate(top_disruption, 1):
            thm_short = thm.split('.')[-1] if '.' in thm else thm[:50]
            print(f"    {i}. {thm_short}: {feat.get('disruption_index', 0):.4f}")
        
        print("\n  Top 5 theorems by effective usage:")
        for i, (thm, feat) in enumerate(top_usage, 1):
            thm_short = thm.split('.')[-1] if '.' in thm else thm[:50]
            print(f"    {i}. {thm_short}: {feat.get('effective_usage', 0):.2f}")
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
print(f"    - PDF (ego nets): {OUTPUT_PDF_EGONETS}")
print(f"    - PNG (ego nets): {OUTPUT_PNG_EGONETS}")
if motif_counts:
    print(f"    - PDF (motifs): {OUTPUT_PDF_MOTIFS}")
    print(f"    - PNG (motifs): {OUTPUT_PNG_MOTIFS}")
print(f"    - HTML Dashboard: {OUTPUT_HTML_DASHBOARD}")
print(f"\n  Summary:")
print(f"    - Nodes analyzed: {measures['basic']['nodes']:,}")
print(f"    - Edges analyzed: {measures['basic']['edges']:,}")
print(f"    - Ego networks visualized: {len(ego_networks)}")
print(f"    - Components: {measures['basic']['num_components']}")
print(f"    - Max level: {measures['levels'].get('max_level', 'N/A')}")
print(f"    - Max depth: {measures['paths'].get('max_depth', 'N/A')}")

# ============================================================================
# Generate HTML Dashboard for Interactive Ego Network Visualization
# ============================================================================

def generate_ego_network_data(G, theorems_list):
    """
    Generate ego network data for all theorems: parents, children, and all edges.
    Returns a dictionary mapping theorem names to their ego network data.
    """
    print("\nGenerating ego network data for HTML dashboard...")
    ego_data = {}
    
    Out = {n: set(G.successors(n)) for n in G.nodes()}
    In = {n: set(G.predecessors(n)) for n in G.nodes()}
    all_edges_set = set(G.edges())
    
    for theorem in theorems_list:
        parents = list(In[theorem])
        children = list(Out[theorem])
        
        # Collect all nodes in ego network
        ego_nodes = set([theorem])
        ego_nodes.update(parents)
        ego_nodes.update(children)
        
        # Collect all edges:
        # 1. Parent -> theorem
        # 2. Theorem -> child
        # 3. Parent -> child (bypass edges)
        edges = []
        
        # Parent -> theorem edges
        for parent in parents:
            if (parent, theorem) in all_edges_set:
                edges.append({"from": parent, "to": theorem})
        
        # Theorem -> child edges
        for child in children:
            if (theorem, child) in all_edges_set:
                edges.append({"from": theorem, "to": child})
        
        # Parent -> child edges (bypass edges)
        for parent in parents:
            for child in children:
                if (parent, child) in all_edges_set:
                    edges.append({"from": parent, "to": child})
        
        # Create node data with labels and types
        nodes = []
        for node in ego_nodes:
            short_name = node.split('.')[-1] if '.' in node else node[:50]
            node_type = G.nodes[node].get("node_type", "unknown")
            color = "#ff6b6b" if node == theorem else ("#4ecdc4" if node_type == "premise" else "#95e1d3")
            shape = "box" if node == theorem else "ellipse"
            
            nodes.append({
                "id": node,
                "label": short_name,
                "title": node,  # Full name on hover
                "color": color,
                "shape": shape,
                "font": {"size": 14 if node == theorem else 12}
            })
        
        ego_data[theorem] = {
            "nodes": nodes,
            "edges": edges,
            "num_parents": len(parents),
            "num_children": len(children),
            "num_bypass_edges": sum(1 for p in parents for c in children if (p, c) in all_edges_set)
        }
    
    print(f"  Generated ego network data for {len(ego_data)} theorems")
    return ego_data


# HTML generation removed - now handled by 0_egonetwork_MDL.py backend
