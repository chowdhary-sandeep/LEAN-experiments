"""
FVS-based DAG cleaning and prediction pipeline v2.

Enhanced version with:
- Depth-based "known world" (d) instead of rank
- Peek radius (r) controlling future information access
- Two-stage prediction (classification + regression)
- Proper baselines and stratified evaluation
"""

import json
import pickle
import networkx as nx
from pathlib import Path
from collections import defaultdict, deque, Counter
import numpy as np
import random
import time
import sys
import io
import math
from typing import Dict, Set, List, Tuple, Optional
import warnings
import subprocess

# Try to import optional dependencies
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    def tqdm(iterable, desc="", total=None, **kwargs):
        return iterable

try:
    from sklearn.linear_model import LinearRegression, LogisticRegression
    from sklearn.ensemble import GradientBoostingRegressor, GradientBoostingClassifier
    from sklearn.metrics import (
        r2_score, mean_absolute_error, average_precision_score, 
        precision_recall_curve, roc_auc_score, ndcg_score
    )
    from scipy.stats import spearmanr
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    warnings.warn("sklearn/scipy not available - prediction models will be skipped")

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    warnings.warn("matplotlib not available - plots will be skipped")

# Set UTF-8 encoding for stdout on Windows
if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Configuration
_SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = _SCRIPT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
FIGS_DIR = _SCRIPT_DIR / "figs"
FIGS_DIR.mkdir(exist_ok=True)
CACHE_BUNDLE = _SCRIPT_DIR.parent / "cache" / "bundle.pkl"

# Data prefix for FVS pipeline files
FVS_CACHE_PREFIX = "1_fvs_pipeline_v2_"
FVS_CACHE_DAG = DATA_DIR / f"{FVS_CACHE_PREFIX}dag.pkl"
FVS_CACHE_FVS = DATA_DIR / f"{FVS_CACHE_PREFIX}fvs.pkl"
FVS_CACHE_STATS = DATA_DIR / f"{FVS_CACHE_PREFIX}stats.pkl"
FVS_CACHE_DEPTHS = DATA_DIR / f"{FVS_CACHE_PREFIX}depths.pkl"
FVS_CACHE_TARGETS = DATA_DIR / f"{FVS_CACHE_PREFIX}targets.pkl"

# Feature config path (same name as script)
DEFAULT_FEATURE_CONFIG = _SCRIPT_DIR / "1_future_prediction_pipeline_v2.json"

# Set random seed for reproducibility
random.seed(42)
np.random.seed(42)


# -------------------------------------------------------------------------------------- 
# Utility functions
# -------------------------------------------------------------------------------------- 

def entropy_from_counts(counts: List[int]) -> float:
    """Shannon entropy in nats, safe for empty/degenerate distributions."""
    total = float(sum(counts))
    if total <= 0:
        return 0.0
    ent = 0.0
    for c in counts:
        if c <= 0:
            continue
        p = c / total
        ent -= p * math.log(p)
    return float(ent)

def jaccard(a: Set, b: Set) -> float:
    """Jaccard similarity between two sets."""
    if not a and not b:
        return 1.0
    inter = len(a & b)
    union = len(a | b)
    return (inter / union) if union else 0.0

# -------------------------------------------------------------------------------------- 
# Feature config loading
# -------------------------------------------------------------------------------------- 

def load_feature_config(path: Path) -> Dict:
    """Load feature configuration from JSON."""
    if not path.exists():
        raise FileNotFoundError(f"Feature config not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg

def resolve_feature_set(cfg: Dict, r: int) -> List[str]:
    """Resolve r0/r1/r2 feature list from JSON, following 'base' inheritance."""
    key = f"r{r}"
    fs = cfg["feature_sets"].get(key)
    if fs is None:
        raise ValueError(f"feature_sets missing '{key}' in config")
    features: List[str] = []
    if "base" in fs:
        base_name = fs["base"]
        base_r = int(base_name.replace("r", ""))
        features.extend(resolve_feature_set(cfg, base_r))
    clusters = fs.get("include_clusters", [])
    for cl in clusters:
        if cl not in cfg["feature_clusters"]:
            continue
        feats = cfg["feature_clusters"][cl]["features"]
        features.extend(feats)
    # de-dup preserving order
    seen = set()
    out = []
    for f in features:
        if f not in seen:
            out.append(f)
            seen.add(f)
    return out

# -------------------------------------------------------------------------------------- 
# Graph loading
# -------------------------------------------------------------------------------------- 

def load_graph_from_cache() -> Optional[nx.DiGraph]:
    """Load the graph from cache if available."""
    if CACHE_BUNDLE.exists():
        try:
            with open(CACHE_BUNDLE, "rb") as f:
                bundle = pickle.load(f)
            G = bundle.get("G_original")
            if G is not None:
                print(f"Loaded graph from cache: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")
                return G
        except Exception as e:
            print(f"Error loading cache: {e}")
    return None


def save_fvs_cache(G_dag: nx.DiGraph, F: Set, stats: Dict):
    """Save FVS computation results to cache."""
    try:
        DATA_DIR.mkdir(exist_ok=True)
        with open(FVS_CACHE_DAG, "wb") as f:
            pickle.dump(G_dag, f, protocol=pickle.HIGHEST_PROTOCOL)
        with open(FVS_CACHE_FVS, "wb") as f:
            pickle.dump(F, f, protocol=pickle.HIGHEST_PROTOCOL)
        with open(FVS_CACHE_STATS, "wb") as f:
            pickle.dump(stats, f, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"  Saved FVS results to cache")
    except Exception as e:
        print(f"  Warning: Could not save FVS cache: {e}")


def load_fvs_cache() -> Optional[Tuple[nx.DiGraph, Set, Dict]]:
    """Load FVS computation results from cache if available."""
    if FVS_CACHE_DAG.exists() and FVS_CACHE_FVS.exists() and FVS_CACHE_STATS.exists():
        try:
            with open(FVS_CACHE_DAG, "rb") as f:
                G_dag = pickle.load(f)
            with open(FVS_CACHE_FVS, "rb") as f:
                F = pickle.load(f)
            with open(FVS_CACHE_STATS, "rb") as f:
                stats = pickle.load(f)
            print(f"Loaded FVS results from cache: {G_dag.number_of_nodes():,} nodes, {len(F):,} removed")
            return G_dag, F, stats
        except Exception as e:
            print(f"Error loading FVS cache: {e}")
    return None


def compute_sccs(G: nx.DiGraph) -> List[Set]:
    """Compute strongly connected components."""
    return list(nx.strongly_connected_components(G))


def greedy_scc_fvs(G: nx.DiGraph, show_progress: bool = True) -> Tuple[nx.DiGraph, Set, Dict]:
    """
    Compute FVS using greedy SCC-based approach.
    
    Returns:
        G_dag: Acyclic graph
        F: Set of removed vertices
        stats: Dictionary with statistics
    """
    print("\n" + "=" * 80)
    print("Step 1: Computing FVS using GreedySCC-FVS")
    print("=" * 80)
    
    G_work = G.copy()
    F = set()
    stats = {
        "initial_nodes": G.number_of_nodes(),
        "initial_edges": G.number_of_edges(),
        "sccs_found": 0,
        "nontrivial_sccs": 0,
        "removed_before_improvement": 0,
        "removed_after_improvement": 0
    }
    
    iteration = 0
    start_time = time.time()
    
    # Main loop: remove vertices from nontrivial SCCs
    while True:
        iteration += 1
        sccs = compute_sccs(G_work)
        stats["sccs_found"] = len(sccs)
        
        # Find nontrivial SCCs (size > 1 or self-loops)
        nontrivial_sccs = []
        for scc in sccs:
            if len(scc) > 1:
                nontrivial_sccs.append(scc)
            else:
                # Check for self-loops
                node = list(scc)[0]
                if G_work.has_edge(node, node):
                    nontrivial_sccs.append(scc)
        
        if not nontrivial_sccs:
            break
        
        stats["nontrivial_sccs"] += len(nontrivial_sccs)
        
        if show_progress and iteration == 1:
            print(f"\nIteration {iteration}: Found {len(nontrivial_sccs)} nontrivial SCC(s)")
        
        # Process each nontrivial SCC
        for scc in nontrivial_sccs:
            # Compute subgraph induced by SCC
            G_scc = G_work.subgraph(scc).copy()
            
            # Compute in/out degrees within SCC
            in_deg_scc = dict(G_scc.in_degree())
            out_deg_scc = dict(G_scc.out_degree())
            
            # Score: in_deg * out_deg
            scores = {v: in_deg_scc[v] * out_deg_scc[v] for v in scc}
            
            # Choose vertex with maximum score
            v_star = max(scc, key=lambda v: scores[v])
            
            # Remove v_star
            G_work.remove_node(v_star)
            F.add(v_star)
    
    stats["removed_before_improvement"] = len(F)
    elapsed = time.time() - start_time
    print(f"\nInitial FVS computed in {elapsed:.2f}s")
    print(f"  Removed {len(F):,} vertices ({100*len(F)/stats['initial_nodes']:.2f}%)")
    
    # Validate DAG
    try:
        list(nx.topological_sort(G_work))
        print("  ✓ Graph is now a DAG (topological sort succeeded)")
    except (nx.NetworkXError, nx.NetworkXUnfeasible):
        print("  ✗ WARNING: Graph still contains cycles!")
        return G_work, F, stats
    
    # Improvement: attempt reinsertion
    print("\n" + "-" * 80)
    print("Step 1.3: Attempting reinsertion improvement")
    print("-" * 80)
    
    F_list = list(F)
    random.shuffle(F_list)
    reinserted = []
    
    if show_progress and HAS_TQDM:
        pbar = tqdm(F_list, desc="Reinsertion check")
    else:
        pbar = F_list
    
    for v in pbar:
        # Temporarily add v back
        G_test = G_work.copy()
        G_test.add_node(v)
        
        # Add back all edges incident to v from original graph
        for u in G.predecessors(v):
            if u in G_test:
                G_test.add_edge(u, v)
        for w in G.successors(v):
            if w in G_test:
                G_test.add_edge(v, w)
        
        # Check if cycle is reintroduced
        try:
            list(nx.topological_sort(G_test))
            # No cycle - can reinsert
            G_work = G_test
            F.remove(v)
            reinserted.append(v)
        except (nx.NetworkXError, nx.NetworkXUnfeasible):
            # Cycle reintroduced - keep removed
            pass
    
    stats["removed_after_improvement"] = len(F)
    stats["reinserted"] = len(reinserted)
    
    print(f"\nReinsertion complete:")
    print(f"  Reinserted {len(reinserted):,} vertices")
    print(f"  Final FVS size: {len(F):,} ({100*len(F)/stats['initial_nodes']:.2f}%)")
    
    # Final validation
    try:
        list(nx.topological_sort(G_work))
        print("  ✓ Final graph is a DAG")
    except (nx.NetworkXError, nx.NetworkXUnfeasible):
        print("  ✗ WARNING: Final graph still contains cycles!")
    
    return G_work, F, stats


def compute_depth(G_dag: nx.DiGraph) -> Dict[str, int]:
    """
    Compute depth function: depth(v)=0 if indeg(v)=0; else depth(v)=1+max_{p in Parents(v)} depth(p).
    
    Returns:
        Dictionary mapping node -> depth
    """
    print("\n" + "=" * 80)
    print("Step 2: Computing depth function")
    print("=" * 80)
    
    # Find sources
    sources = [v for v in G_dag.nodes() if G_dag.in_degree(v) == 0]
    print(f"Found {len(sources):,} source nodes")
    
    depth = {}
    
    # Topological sort ensures we process nodes in order
    topo_order = list(nx.topological_sort(G_dag))
    
    if HAS_TQDM:
        pbar = tqdm(topo_order, desc="depth")
    else:
        pbar = topo_order
    
    for v in pbar:
        if v in sources:
            depth[v] = 0
        else:
            parents = list(G_dag.predecessors(v))
            if parents:
                depth[v] = 1 + max(depth.get(p, -1) for p in parents)
            else:
                depth[v] = 0
    
    max_depth = max(depth.values()) if depth else 0
    depth_dist = Counter(depth.values())
    print(f"  Max depth: {max_depth}")
    print(f"  Depth distribution (sample): {dict(sorted(list(depth_dist.items())[:10]))}")
    
    return depth


def compute_targets(G_dag: nx.DiGraph) -> Dict[str, Dict[str, int]]:
    """
    Compute prediction targets for each node.
    
    Returns:
        Dictionary mapping node -> {"Y1": int, "Y2": int, "Z1": float, "Z2": float}
        Y1: total descendants count
        Y2: outdegree
        Z1: log(1+Y1)
        Z2: log(1+Y2)
    """
    print("\n" + "=" * 80)
    print("Step 3: Computing prediction targets")
    print("=" * 80)
    
    targets = {}
    
    # Y2: outdegree (simple)
    print("Computing Y2 (outdegree)...")
    for v in G_dag.nodes():
        targets[v] = {"Y2": G_dag.out_degree(v)}
    
    # Y1: descendant count (optimized using reverse topological order)
    print("Computing Y1 (descendant count)...")
    
    # Use reverse topological order for dynamic programming
    reverse_topo = list(reversed(list(nx.topological_sort(G_dag))))
    
    if HAS_TQDM:
        pbar = tqdm(reverse_topo, desc="Y1")
    else:
        pbar = reverse_topo
    
    # Dynamic programming: Y1[v] = direct_children + sum(Y1[child] for child in children)
    for v in pbar:
        direct_children = list(G_dag.successors(v))
        # Count direct children plus all their descendants
        descendant_count = len(direct_children)
        for child in direct_children:
            descendant_count += targets[child]["Y1"]
        targets[v]["Y1"] = descendant_count
    
    # Compute log targets
    for v in G_dag.nodes():
        targets[v]["Z1"] = np.log1p(targets[v]["Y1"])
        targets[v]["Z2"] = np.log1p(targets[v]["Y2"])
    
    return targets


# -------------------------------------------------------------------------------------- 
# Feature Context and Computation
# -------------------------------------------------------------------------------------- 

class FeatureContext:
    """Context for feature computation, precomputing shared statistics."""
    def __init__(self, G_dag: nx.DiGraph, H_seen: nx.DiGraph, depth: Dict[str, int], d: int, params: Dict):
        self.G_dag = G_dag
        self.H_seen = H_seen
        self.depth = depth
        self.d = d
        self.params = params
        
        # Weakly connected component ids in H_seen (upstream mixture proxy)
        self.wcc_id = {}
        try:
            und = H_seen.to_undirected(as_view=True)
            for i, comp in enumerate(nx.connected_components(und)):
                for v in comp:
                    self.wcc_id[v] = i
        except Exception:
            for v in H_seen.nodes():
                self.wcc_id[v] = 0
        
        # Parent-set counter + inverted index (computed on H_seen nodes only)
        self.parentset_counter = Counter()
        self.parent_to_children_nodes = defaultdict(set)
        for v in H_seen.nodes():
            ps = frozenset(H_seen.predecessors(v))
            self.parentset_counter[ps] += 1
            for p in ps:
                self.parent_to_children_nodes[p].add(v)
        
        # beta(u) = # children at depth(u)+1 (inside H_seen)
        self.beta_next = defaultdict(int)
        for u, v in H_seen.edges():
            if self.depth.get(v, 0) == self.depth.get(u, 0) + 1:
                self.beta_next[u] += 1
        
        # Survival rate by depth (fraction with any child inside H_seen)
        counts_by_depth = defaultdict(int)
        alive_by_depth = defaultdict(int)
        for u in H_seen.nodes():
            t = self.depth.get(u, 0)
            counts_by_depth[t] += 1
            if H_seen.out_degree(u) > 0:
                alive_by_depth[t] += 1
        self.survival_rate_by_depth = {}
        for t, n in counts_by_depth.items():
            self.survival_rate_by_depth[t] = alive_by_depth[t] / n if n else 0.0
        
        # Module label (best-effort) for mixture features
        self.module_label = {}
        for v in H_seen.nodes():
            self.module_label[v] = self._infer_module(v)
        
        # Ancestor cache (on-demand)
        self._anc_cache = {}
    
    def _infer_module(self, v) -> str:
        """Infer module/namespace from node name or attributes."""
        attrs = self.H_seen.nodes[v] if v in self.H_seen.nodes else {}
        for k in ["module", "namespace", "file", "path"]:
            if k in attrs and attrs[k]:
                return str(attrs[k])
        s = str(v)
        if "." in s:
            return s.split(".")[0]
        if "/" in s:
            return s.split("/")[0]
        return "unknown"
    
    def parents_seen(self, v) -> List:
        """Get parents of v in H_seen."""
        if v in self.H_seen:
            return list(self.H_seen.predecessors(v))
        return [p for p in self.G_dag.predecessors(v) if p in self.H_seen]
    
    def indeg_seen(self, v) -> int:
        return len(self.parents_seen(v))
    
    def get_ancestors(self, u) -> Set:
        """Ancestors of u in H_seen (excluding u), computed by BFS backward with cap."""
        if u in self._anc_cache:
            return self._anc_cache[u]
        cap = int(self.params.get("ancestor_bfs_node_cap", 20000))
        anc = set()
        q = deque([u])
        visited = {u}
        while q and len(visited) < cap:
            x = q.popleft()
            for p in self.H_seen.predecessors(x):
                if p not in visited:
                    visited.add(p)
                    anc.add(p)
                    q.append(p)
        self._anc_cache[u] = anc
        return anc


def build_seen_graph(G_dag: nx.DiGraph, depth: Dict[str, int], d: int, strict_past: bool) -> nx.DiGraph:
    """
    Seen graph for a given frontier depth d.
    If strict_past=True: only nodes with depth < d are visible (conservative, prevents same-layer leakage).
    Else: nodes with depth <= d are visible (v2 behavior).
    """
    cutoff = d - 1 if strict_past else d
    nodes = [v for v in G_dag.nodes() if depth.get(v, 0) <= cutoff]
    return G_dag.subgraph(nodes).copy()


# Feature computation functions
def feat_depth(ctx: FeatureContext, v) -> float:
    return float(ctx.depth.get(v, 0))

def feat_indeg_seen(ctx: FeatureContext, v) -> float:
    return float(ctx.indeg_seen(v))

def feat_parent_count(ctx: FeatureContext, v) -> float:
    return float(len(ctx.parents_seen(v)))

def _parent_stats(ctx: FeatureContext, v):
    """Helper to compute parent statistics."""
    parents = ctx.parents_seen(v)
    if not parents:
        return parents, [], [], [], [], []
    indegs = [ctx.H_seen.in_degree(p) for p in parents]
    outdegs = [ctx.H_seen.out_degree(p) for p in parents]
    depths = [ctx.depth.get(p, 0) for p in parents]
    betas = [ctx.beta_next.get(p, 0) for p in parents]
    surv = [ctx.survival_rate_by_depth.get(ctx.depth.get(p, 0), 0.0) for p in parents]
    return parents, indegs, outdegs, depths, betas, surv

def feat_parent_indeg_mean(ctx, v): 
    parents, indegs, *_ = _parent_stats(ctx, v)
    return float(np.mean(indegs)) if indegs else 0.0

def feat_parent_indeg_max(ctx, v):
    parents, indegs, *_ = _parent_stats(ctx, v)
    return float(np.max(indegs)) if indegs else 0.0

def feat_parent_outdeg_mean(ctx, v):
    parents, _, outdegs, *_ = _parent_stats(ctx, v)
    return float(np.mean(outdegs)) if outdegs else 0.0

def feat_parent_outdeg_max(ctx, v):
    parents, _, outdegs, *_ = _parent_stats(ctx, v)
    return float(np.max(outdegs)) if outdegs else 0.0

def feat_parent_outdeg_sum(ctx, v):
    parents, _, outdegs, *_ = _parent_stats(ctx, v)
    return float(np.sum(outdegs)) if outdegs else 0.0

def feat_parent_depth_mean(ctx, v):
    parents, *_rest = _parent_stats(ctx, v)
    depths = _rest[2]
    return float(np.mean(depths)) if depths else 0.0

def feat_parent_depth_max(ctx, v):
    parents, *_rest = _parent_stats(ctx, v)
    depths = _rest[2]
    return float(np.max(depths)) if depths else 0.0

def _forward_desc_count_seen(ctx: FeatureContext, start, exclude=None) -> int:
    """Forward reachable unique nodes from start inside H_seen, capped."""
    cap = int(ctx.params.get("forward_bfs_node_cap", 20000))
    descendants = set()
    q = deque([start])
    visited = {start}
    while q and len(visited) < cap:
        u = q.popleft()
        for w in ctx.H_seen.successors(u):
            if w == exclude:
                continue
            if w not in visited:
                visited.add(w)
                descendants.add(w)
                q.append(w)
    return len(descendants)

def feat_parent_descendant_count_seen_mean(ctx, v):
    parents = ctx.parents_seen(v)
    if not parents:
        return 0.0
    vals = [_forward_desc_count_seen(ctx, p, exclude=v) for p in parents]
    return float(np.mean(vals)) if vals else 0.0

def feat_parent_descendant_count_seen_max(ctx, v):
    parents = ctx.parents_seen(v)
    if not parents:
        return 0.0
    vals = [_forward_desc_count_seen(ctx, p, exclude=v) for p in parents]
    return float(np.max(vals)) if vals else 0.0

def feat_parent_diversity(ctx, v):
    parents = ctx.parents_seen(v)
    if len(parents) <= 1:
        return 1.0
    overlaps = []
    anc_cache = {}
    for p in parents:
        anc_cache[p] = ctx.get_ancestors(p)
    for i, p1 in enumerate(parents):
        a1 = anc_cache[p1]
        for p2 in parents[i+1:]:
            a2 = anc_cache[p2]
            union = len(a1 | a2)
            if union == 0:
                overlaps.append(0.0)
            else:
                overlaps.append(len(a1 & a2) / union)
    return float(1.0 - np.mean(overlaps)) if overlaps else 1.0

def feat_parentset_cooccurrence_mean(ctx, v):
    parents = ctx.parents_seen(v)
    if len(parents) <= 1:
        return 0.0
    vals = []
    for i, p1 in enumerate(parents):
        s1 = ctx.parent_to_children_nodes.get(p1, set())
        for p2 in parents[i+1:]:
            s2 = ctx.parent_to_children_nodes.get(p2, set())
            vals.append(len(s1 & s2))
    return float(np.mean(vals)) if vals else 0.0

def feat_parentset_cooccurrence_max(ctx, v):
    parents = ctx.parents_seen(v)
    if len(parents) <= 1:
        return 0.0
    best = 0
    for i, p1 in enumerate(parents):
        s1 = ctx.parent_to_children_nodes.get(p1, set())
        for p2 in parents[i+1:]:
            s2 = ctx.parent_to_children_nodes.get(p2, set())
            best = max(best, len(s1 & s2))
    return float(best)

def feat_parentset_rarity_exact(ctx, v):
    parents = ctx.parents_seen(v)
    ps = frozenset(parents)
    return float(ctx.parentset_counter.get(ps, 0))

def feat_parentset_similarity_topk_mean(ctx, v):
    parents = ctx.parents_seen(v)
    if not parents:
        return 0.0
    ps = set(parents)
    cand = set()
    for p in parents:
        cand |= ctx.parent_to_children_nodes.get(p, set())
    if not cand:
        return 0.0
    topk = int(ctx.params.get("parentset_similarity_topk", 25))
    sims = []
    for u in cand:
        u_ps = set(ctx.H_seen.predecessors(u))
        sims.append(jaccard(ps, u_ps))
    sims.sort(reverse=True)
    sims = sims[:topk]
    return float(np.mean(sims)) if sims else 0.0

def feat_parentset_similarity_topk_max(ctx, v):
    parents = ctx.parents_seen(v)
    if not parents:
        return 0.0
    ps = set(parents)
    cand = set()
    for p in parents:
        cand |= ctx.parent_to_children_nodes.get(p, set())
    if not cand:
        return 0.0
    best = 0.0
    for u in cand:
        u_ps = set(ctx.H_seen.predecessors(u))
        best = max(best, jaccard(ps, u_ps))
    return float(best)

def _max_common_ancestor_depth(ctx: FeatureContext, p1, p2) -> int:
    a1 = ctx.get_ancestors(p1) | {p1}
    a2 = ctx.get_ancestors(p2) | {p2}
    if len(a1) > len(a2):
        a1, a2 = a2, a1
    best = -1
    for x in a1:
        if x in a2:
            best = max(best, ctx.depth.get(x, 0))
    return best if best >= 0 else 0

def feat_parent_lca_depth_pairwise_mean(ctx, v):
    parents = ctx.parents_seen(v)
    if len(parents) <= 1:
        return 0.0
    vals = []
    for i, p1 in enumerate(parents):
        for p2 in parents[i+1:]:
            vals.append(_max_common_ancestor_depth(ctx, p1, p2))
    return float(np.mean(vals)) if vals else 0.0

def feat_parent_lca_depth_pairwise_max(ctx, v):
    parents = ctx.parents_seen(v)
    if len(parents) <= 1:
        return 0.0
    best = 0
    for i, p1 in enumerate(parents):
        for p2 in parents[i+1:]:
            best = max(best, _max_common_ancestor_depth(ctx, p1, p2))
    return float(best)

def feat_parent_beta_mean(ctx, v):
    parents, *_rest = _parent_stats(ctx, v)
    betas = _rest[3]
    return float(np.mean(betas)) if betas else 0.0

def feat_parent_beta_max(ctx, v):
    parents = ctx.parents_seen(v)
    if not parents:
        return 0.0
    betas = [ctx.beta_next.get(p, 0) for p in parents]
    return float(np.max(betas)) if betas else 0.0

def feat_parent_survival_rate_by_depth_mean(ctx, v):
    parents, *_rest = _parent_stats(ctx, v)
    surv = _rest[4]
    return float(np.mean(surv)) if surv else 0.0

def feat_grandparent_count_unique(ctx, v):
    parents = ctx.parents_seen(v)
    gps = set()
    for p in parents:
        gps |= set(ctx.H_seen.predecessors(p))
    return float(len(gps))

def _upstream_nodes_within_hops(ctx: FeatureContext, v, hops: int) -> Set:
    start = ctx.parents_seen(v)
    seen = set(start)
    frontier = set(start)
    for _ in range(hops - 1):
        nxt = set()
        for u in frontier:
            for p in ctx.H_seen.predecessors(u):
                if p not in seen:
                    seen.add(p)
                    nxt.add(p)
        frontier = nxt
        if not frontier:
            break
    return seen

def feat_upstream_2hop_node_count(ctx, v):
    hops = int(ctx.params.get("max_upstream_hops_small", 2))
    nodes = _upstream_nodes_within_hops(ctx, v, hops=hops)
    return float(len(nodes))

def feat_upstream_2hop_edge_density(ctx, v):
    hops = int(ctx.params.get("max_upstream_hops_small", 2))
    nodes = _upstream_nodes_within_hops(ctx, v, hops=hops)
    n = len(nodes)
    if n <= 1:
        return 0.0
    sub = ctx.H_seen.subgraph(nodes)
    m = sub.number_of_edges()
    denom = n * (n - 1)
    return float(m / denom) if denom else 0.0

def feat_parent_wcc_unique(ctx, v):
    parents = ctx.parents_seen(v)
    if not parents:
        return 0.0
    comps = {ctx.wcc_id.get(p, 0) for p in parents}
    return float(len(comps))

def feat_parent_wcc_entropy(ctx, v):
    parents = ctx.parents_seen(v)
    if not parents:
        return 0.0
    counts = Counter(ctx.wcc_id.get(p, 0) for p in parents)
    return entropy_from_counts(list(counts.values()))

def feat_parent_module_unique(ctx, v):
    parents = ctx.parents_seen(v)
    if not parents:
        return 0.0
    mods = {ctx.module_label.get(p, "unknown") for p in parents}
    return float(len(mods))

def feat_parent_module_entropy(ctx, v):
    parents = ctx.parents_seen(v)
    if not parents:
        return 0.0
    counts = Counter(ctx.module_label.get(p, "unknown") for p in parents)
    return entropy_from_counts(list(counts.values()))

# r>=1 peek features (full DAG)
def feat_k1(ctx, v):
    return float(ctx.G_dag.out_degree(v))

def feat_child_count_r1(ctx, v):
    return float(ctx.G_dag.out_degree(v))

def feat_grandchild_count(ctx, v):
    children = list(ctx.G_dag.successors(v))
    gc = set()
    for c in children:
        for g in ctx.G_dag.successors(c):
            gc.add(g)
    return float(len(gc))

def feat_k2(ctx, v):
    return feat_grandchild_count(ctx, v)

FEATURE_COMPUTERS = {
    "depth": feat_depth,
    "indeg_seen": feat_indeg_seen,
    "parent_count": feat_parent_count,
    "parent_indeg_mean": feat_parent_indeg_mean,
    "parent_indeg_max": feat_parent_indeg_max,
    "parent_outdeg_mean": feat_parent_outdeg_mean,
    "parent_outdeg_max": feat_parent_outdeg_max,
    "parent_outdeg_sum": feat_parent_outdeg_sum,
    "parent_depth_mean": feat_parent_depth_mean,
    "parent_depth_max": feat_parent_depth_max,
    "parent_descendant_count_seen_mean": feat_parent_descendant_count_seen_mean,
    "parent_descendant_count_seen_max": feat_parent_descendant_count_seen_max,
    "parent_diversity": feat_parent_diversity,
    "parentset_cooccurrence_mean": feat_parentset_cooccurrence_mean,
    "parentset_cooccurrence_max": feat_parentset_cooccurrence_max,
    "parentset_rarity_exact": feat_parentset_rarity_exact,
    "parentset_similarity_topk_mean": feat_parentset_similarity_topk_mean,
    "parentset_similarity_topk_max": feat_parentset_similarity_topk_max,
    "parent_lca_depth_pairwise_mean": feat_parent_lca_depth_pairwise_mean,
    "parent_lca_depth_pairwise_max": feat_parent_lca_depth_pairwise_max,
    "parent_beta_mean": feat_parent_beta_mean,
    "parent_beta_max": feat_parent_beta_max,
    "parent_survival_rate_by_depth_mean": feat_parent_survival_rate_by_depth_mean,
    "grandparent_count_unique": feat_grandparent_count_unique,
    "upstream_2hop_node_count": feat_upstream_2hop_node_count,
    "upstream_2hop_edge_density": feat_upstream_2hop_edge_density,
    "parent_wcc_unique": feat_parent_wcc_unique,
    "parent_wcc_entropy": feat_parent_wcc_entropy,
    "parent_module_unique": feat_parent_module_unique,
    "parent_module_entropy": feat_parent_module_entropy,
    "k1": feat_k1,
    "child_count_r1": feat_child_count_r1,
    "grandchild_count": feat_grandchild_count,
    "k2": feat_k2,
}

def compute_feature_vector(ctx: FeatureContext, v, feature_names: List[str]) -> Dict[str, float]:
    """Compute all features for a node using FeatureContext."""
    feats = {}
    for fn in feature_names:
        comp = FEATURE_COMPUTERS.get(fn)
        if comp is None:
            # Fallback: try to compute from old method if feature not found
            feats[fn] = 0.0
            continue
        try:
            feats[fn] = float(comp(ctx, v))
        except Exception as e:
            feats[fn] = 0.0
    return feats


def compute_features_r0(G_dag: nx.DiGraph, H_seen: nx.DiGraph, v: str, depth: Dict[str, int], 
                        feature_cfg: Dict) -> Dict[str, float]:
    """
    Compute r=0 features using JSON config and FeatureContext.
    """
    params = feature_cfg.get("params", {})
    strict_past = bool(params.get("strict_past_seen_graph", True))
    feature_names = resolve_feature_set(feature_cfg, 0)
    ctx = FeatureContext(G_dag=G_dag, H_seen=H_seen, depth=depth, d=depth.get(v, 0), params=params)
    return compute_feature_vector(ctx, v, feature_names)


def compute_features_r1(G_dag: nx.DiGraph, H_seen: nx.DiGraph, v: str, depth: Dict[str, int], 
                        feature_cfg: Dict) -> Dict[str, float]:
    """
    Compute r=1 features (can see immediate children).
    """
    params = feature_cfg.get("params", {})
    strict_past = bool(params.get("strict_past_seen_graph", True))
    feature_names = resolve_feature_set(feature_cfg, 1)
    ctx = FeatureContext(G_dag=G_dag, H_seen=H_seen, depth=depth, d=depth.get(v, 0), params=params)
    return compute_feature_vector(ctx, v, feature_names)


def compute_features_r2(G_dag: nx.DiGraph, H_seen: nx.DiGraph, v: str, depth: Dict[str, int], 
                        feature_cfg: Dict) -> Dict[str, float]:
    """
    Compute r=2 features (can see children and grandchildren).
    """
    params = feature_cfg.get("params", {})
    strict_past = bool(params.get("strict_past_seen_graph", True))
    feature_names = resolve_feature_set(feature_cfg, 2)
    ctx = FeatureContext(G_dag=G_dag, H_seen=H_seen, depth=depth, d=depth.get(v, 0), params=params)
    return compute_feature_vector(ctx, v, feature_names)


def create_dataset(G_dag: nx.DiGraph, depth: Dict[str, int], targets: Dict[str, Dict[str, int]], 
                   d: int, r: int, feature_cfg: Dict) -> Tuple[List[Dict], List[int], List[int], List[float], List[float], List[str], List[str]]:
    """
    Create dataset for depth d and radius r using JSON feature config.
    
    Returns:
        X: List of feature dictionaries
        Y1: List of Y1 targets
        Y2: List of Y2 targets
        Z1: List of Z1 targets (log-transformed Y1)
        Z2: List of Z2 targets (log-transformed Y2)
        nodes: List of node identifiers
        feature_names: List of feature names
    """
    params = feature_cfg.get("params", {})
    strict_past = bool(params.get("strict_past_seen_graph", True))
    H_seen = build_seen_graph(G_dag, depth, d, strict_past=strict_past)
    
    V_d = [v for v in G_dag.nodes() if depth.get(v, 0) == d]
    feature_names = resolve_feature_set(feature_cfg, r)
    
    ctx = FeatureContext(G_dag=G_dag, H_seen=H_seen, depth=depth, d=d, params=params)
    
    X = []
    Y1 = []
    Y2 = []
    Z1 = []
    Z2 = []
    nodes = []
    
    if HAS_TQDM:
        pbar = tqdm(V_d, desc=f"features d={d} r={r}")
    else:
        pbar = V_d
    
    for v in pbar:
        features = compute_feature_vector(ctx, v, feature_names)
        X.append(features)
        Y1.append(int(targets[v]["Y1"]))
        Y2.append(int(targets[v]["Y2"]))
        Z1.append(float(targets[v]["Z1"]))
        Z2.append(float(targets[v]["Z2"]))
        nodes.append(v)
    
    return X, Y1, Y2, Z1, Z2, nodes, feature_names


def features_to_array(X: List[Dict], feature_names: List[str]) -> np.ndarray:
    """Convert list of feature dicts to numpy array."""
    return np.array([[x.get(fn, 0.0) for fn in feature_names] for x in X])


def evaluate_classification(y_true_binary, y_pred_proba):
    """Evaluate binary classification."""
    if not HAS_SKLEARN:
        return {}
    
    metrics = {}
    
    # PR-AUC
    try:
        metrics["PR_AUC"] = average_precision_score(y_true_binary, y_pred_proba)
    except:
        metrics["PR_AUC"] = None
    
    # ROC-AUC
    try:
        metrics["ROC_AUC"] = roc_auc_score(y_true_binary, y_pred_proba)
    except:
        metrics["ROC_AUC"] = None
    
    # Precision at fixed recall (or recall at fixed precision)
    try:
        precision, recall, thresholds = precision_recall_curve(y_true_binary, y_pred_proba)
        # Find precision closest to 0.8
        idx = np.argmin(np.abs(precision - 0.8))
        metrics["Recall_at_P80"] = recall[idx] if idx < len(recall) else None
    except:
        metrics["Recall_at_P80"] = None
    
    return metrics


def evaluate_regression(y_true, y_pred, use_log: bool = False):
    """Evaluate regression."""
    if len(y_true) == 0 or len(y_pred) == 0:
        return {}
    
    metrics = {}
    
    if use_log:
        # For log targets
        metrics["MAE"] = mean_absolute_error(y_true, y_pred) if HAS_SKLEARN else np.mean(np.abs(np.array(y_true) - np.array(y_pred)))
        metrics["R2"] = r2_score(y_true, y_pred) if HAS_SKLEARN else None
        
        # Spearman correlation
        try:
            corr, _ = spearmanr(y_true, y_pred) if HAS_SKLEARN else (None, None)
            metrics["Spearman_rho"] = corr
        except:
            metrics["Spearman_rho"] = None
    else:
        # For raw targets
        metrics["MAE"] = mean_absolute_error(y_true, y_pred) if HAS_SKLEARN else np.mean(np.abs(np.array(y_true) - np.array(y_pred)))
        metrics["R2"] = r2_score(y_true, y_pred) if HAS_SKLEARN else None
        
        # Spearman correlation
        try:
            corr, _ = spearmanr(y_true, y_pred) if HAS_SKLEARN else (None, None)
            metrics["Spearman_rho"] = corr
        except:
            metrics["Spearman_rho"] = None
    
    return metrics


def compute_ndcg_at_k(y_true, y_pred, k: int = None):
    """Compute NDCG@K for ranking."""
    if not HAS_SKLEARN or len(y_true) == 0:
        return None
    
    if k is None:
        k = max(100, len(y_true) // 100)  # Top 1% or at least 100
    
    k = min(k, len(y_true))
    
    # Get top k indices by predicted values
    top_k_indices = np.argsort(y_pred)[-k:][::-1]
    y_true_sorted = np.array(y_true)[top_k_indices]
    
    # Compute DCG
    dcg = np.sum(y_true_sorted / np.log2(np.arange(2, len(y_true_sorted) + 2)))
    
    # Compute IDCG (ideal DCG)
    y_true_sorted_ideal = np.sort(y_true)[::-1][:k]
    idcg = np.sum(y_true_sorted_ideal / np.log2(np.arange(2, len(y_true_sorted_ideal) + 2)))
    
    if idcg == 0:
        return 0.0
    
    return dcg / idcg


def train_and_evaluate_two_stage(X_train, Y1_train, Y2_train, Z1_train, Z2_train,
                                 X_test, Y1_test, Y2_test, Z1_test, Z2_test,
                                 feature_names: List[str], r: int):
    """Train two-stage models: classification then regression."""
    results = {}
    
    if not HAS_SKLEARN:
        return {"error": "sklearn not available"}
    
    # Convert to arrays
    X_train_arr = features_to_array(X_train, feature_names)
    X_test_arr = features_to_array(X_test, feature_names)
    
    # Handle NaN and inf
    X_train_arr = np.nan_to_num(X_train_arr, nan=0.0, posinf=1e6, neginf=-1e6)
    X_test_arr = np.nan_to_num(X_test_arr, nan=0.0, posinf=1e6, neginf=-1e6)
    
    # Normalize features
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    X_train_arr = scaler.fit_transform(X_train_arr)
    X_test_arr = scaler.transform(X_test_arr)
    
    # Stage 1: Classification - Predict I[Y2>0] and I[Y1>0]
    print("\n  Stage 1: Classification")
    
    # Y2 > 0 classification
    Y2_binary_train = (np.array(Y2_train) > 0).astype(int)
    Y2_binary_test = (np.array(Y2_test) > 0).astype(int)
    
    # Linear baseline
    lr_y2_clf = LogisticRegression(max_iter=1000, random_state=42)
    lr_y2_clf.fit(X_train_arr, Y2_binary_train)
    Y2_pred_proba_lr = lr_y2_clf.predict_proba(X_test_arr)[:, 1]
    results["Y2_Linear_Class"] = evaluate_classification(Y2_binary_test, Y2_pred_proba_lr)
    
    # Gradient boosting
    gb_y2_clf = GradientBoostingClassifier(n_estimators=100, max_depth=5, random_state=42)
    gb_y2_clf.fit(X_train_arr, Y2_binary_train)
    Y2_pred_proba_gb = gb_y2_clf.predict_proba(X_test_arr)[:, 1]
    results["Y2_GBoost_Class"] = evaluate_classification(Y2_binary_test, Y2_pred_proba_gb)
    
    # Y1 > 0 classification (separate from Y2 to avoid confusion)
    Y1_binary_train = (np.array(Y1_train) > 0).astype(int)
    Y1_binary_test = (np.array(Y1_test) > 0).astype(int)
    
    # Use separate classifier instances to ensure independence
    lr_y1_clf = LogisticRegression(max_iter=1000, random_state=42)
    lr_y1_clf.fit(X_train_arr, Y1_binary_train)
    Y1_pred_proba_lr = lr_y1_clf.predict_proba(X_test_arr)[:, 1]
    results["Y1_Linear_Class"] = evaluate_classification(Y1_binary_test, Y1_pred_proba_lr)
    
    gb_y1_clf = GradientBoostingClassifier(n_estimators=100, max_depth=5, random_state=42)
    gb_y1_clf.fit(X_train_arr, Y1_binary_train)
    Y1_pred_proba_gb = gb_y1_clf.predict_proba(X_test_arr)[:, 1]
    results["Y1_GBoost_Class"] = evaluate_classification(Y1_binary_test, Y1_pred_proba_gb)
    
    # Sanity check: ensure Y1 and Y2 predictions are different
    if len(Y1_binary_test) > 0 and len(Y2_binary_test) > 0:
        y1_y2_overlap = np.mean((Y1_binary_test == Y2_binary_test).astype(float))
        if y1_y2_overlap > 0.95:
            print(f"  Warning: Y1>0 and Y2>0 labels are {100*y1_y2_overlap:.1f}% identical - classifiers may produce similar results")
    
    # Stage 2: Conditional regression
    print("  Stage 2: Conditional regression")
    
    # Y1 regression on Y1>0 subset
    Y1_positive_train = np.array(Y1_train) > 0
    Y1_positive_test = np.array(Y1_test) > 0
    
    if np.sum(Y1_positive_train) > 10 and np.sum(Y1_positive_test) > 5:
        X_train_y1_pos = X_train_arr[Y1_positive_train]
        Z1_train_pos = np.array(Z1_train)[Y1_positive_train]
        X_test_y1_pos = X_test_arr[Y1_positive_test]
        Z1_test_pos = np.array(Z1_test)[Y1_positive_test]
        
        # Linear
        lr_y1_reg = LinearRegression()
        lr_y1_reg.fit(X_train_y1_pos, Z1_train_pos)
        Z1_pred_lr = lr_y1_reg.predict(X_test_y1_pos)
        results["Y1_Linear_Reg"] = evaluate_regression(Z1_test_pos, Z1_pred_lr, use_log=True)
        
        # Gradient boosting
        gb_y1_reg = GradientBoostingRegressor(n_estimators=100, max_depth=5, random_state=42)
        gb_y1_reg.fit(X_train_y1_pos, Z1_train_pos)
        Z1_pred_gb = gb_y1_reg.predict(X_test_y1_pos)
        results["Y1_GBoost_Reg"] = evaluate_regression(Z1_test_pos, Z1_pred_gb, use_log=True)
        
        # Store predictions for visualization
        Y1_test_pos = np.array(Y1_test)[Y1_positive_test]
        Y1_pred_full = np.zeros(len(Y1_test))
        Y1_pred_full[Y1_positive_test] = np.expm1(Z1_pred_gb)
        Z1_pred_full = np.zeros(len(Z1_test))
        Z1_pred_full[Y1_positive_test] = Z1_pred_gb
        Z1_test_full = np.log1p(np.array(Y1_test))
        results["Y1_predictions"] = {
            "true": Y1_test.tolist() if isinstance(Y1_test, np.ndarray) else list(Y1_test),
            "pred": Y1_pred_full.tolist(),
            "true_log": Z1_test_full.tolist(),
            "pred_log": Z1_pred_full.tolist()
        }
        
        # NDCG@K
        results["Y1_NDCG"] = {
            "NDCG@100": compute_ndcg_at_k(Y1_test, Y1_pred_full, k=100),
            "NDCG@1000": compute_ndcg_at_k(Y1_test, Y1_pred_full, k=1000),
        }
    
    # Y2 regression on Y2>0 subset
    Y2_positive_train = np.array(Y2_train) > 0
    Y2_positive_test = np.array(Y2_test) > 0
    
    if np.sum(Y2_positive_train) > 10 and np.sum(Y2_positive_test) > 5:
        X_train_y2_pos = X_train_arr[Y2_positive_train]
        Y2_train_pos = np.array(Y2_train)[Y2_positive_train]
        X_test_y2_pos = X_test_arr[Y2_positive_test]
        Y2_test_pos = np.array(Y2_test)[Y2_positive_test]
        
        # Linear
        lr_y2_reg = LinearRegression()
        lr_y2_reg.fit(X_train_y2_pos, Y2_train_pos)
        Y2_pred_lr = np.maximum(0, np.round(lr_y2_reg.predict(X_test_y2_pos))).astype(int)
        results["Y2_Linear_Reg"] = evaluate_regression(Y2_test_pos, Y2_pred_lr, use_log=False)
        
        # Gradient boosting
        gb_y2_reg = GradientBoostingRegressor(n_estimators=100, max_depth=5, random_state=42)
        gb_y2_reg.fit(X_train_y2_pos, Y2_train_pos)
        Y2_pred_gb = np.maximum(0, np.round(gb_y2_reg.predict(X_test_y2_pos))).astype(int)
        results["Y2_GBoost_Reg"] = evaluate_regression(Y2_test_pos, Y2_pred_gb, use_log=False)
        
        # Store predictions for visualization
        Y2_pred_full = np.zeros(len(Y2_test), dtype=int)
        Y2_pred_full[Y2_positive_test] = Y2_pred_gb
        results["Y2_predictions"] = {
            "true": Y2_test.tolist() if isinstance(Y2_test, np.ndarray) else list(Y2_test),
            "pred": Y2_pred_full.tolist()
        }
    
    # Feature importance (from best model, if available)
    if r == 0:
        # Try to get feature importance from Y1 regression if available
        if "Y1_GBoost_Reg" in results and np.sum(Y1_positive_train) > 10:
            try:
                results["feature_importance"] = {
                    fn: imp for fn, imp in zip(feature_names, gb_y1_reg.feature_importances_)
                }
            except:
                # Fallback: use Y2 regression if available
                if np.sum(Y2_positive_train) > 10:
                    try:
                        results["feature_importance"] = {
                            fn: imp for fn, imp in zip(feature_names, gb_y2_reg.feature_importances_)
                        }
                    except:
                        pass
    
    return results


def cascaded_prediction_y1_from_y2(X_train, Y1_train, Y2_train, Z1_train,
                                   X_test, Y1_test, Y2_test, Z1_test,
                                   feature_names: List[str]):
    """
    Cascaded prediction: Use predicted outdegree (Y2) to predict descendant count (Y1).
    This simulates using r=0 to predict Y2, then using predicted Y2 as level-1 information.
    """
    results = {}
    
    if not HAS_SKLEARN:
        return {"error": "sklearn not available"}
    
    # Convert to arrays
    X_train_arr = features_to_array(X_train, feature_names)
    X_test_arr = features_to_array(X_test, feature_names)
    
    # Handle NaN and inf
    X_train_arr = np.nan_to_num(X_train_arr, nan=0.0, posinf=1e6, neginf=-1e6)
    X_test_arr = np.nan_to_num(X_test_arr, nan=0.0, posinf=1e6, neginf=-1e6)
    
    # Normalize features
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    X_train_arr = scaler.fit_transform(X_train_arr)
    X_test_arr = scaler.transform(X_test_arr)
    
    # Step 1: Predict Y2 (outdegree) using r=0 features
    print("\n  Cascaded Prediction: Step 1 - Predict Y2")
    Y2_positive_train = np.array(Y2_train) > 0
    Y2_positive_test = np.array(Y2_test) > 0
    
    if np.sum(Y2_positive_train) > 10 and np.sum(Y2_positive_test) > 5:
        X_train_y2_pos = X_train_arr[Y2_positive_train]
        Y2_train_pos = np.array(Y2_train)[Y2_positive_train]
        X_test_y2_pos = X_test_arr[Y2_positive_test]
        Y2_test_pos = np.array(Y2_test)[Y2_positive_test]
        
        # Train Y2 regressor
        gb_y2_reg = GradientBoostingRegressor(n_estimators=100, max_depth=5, random_state=42)
        gb_y2_reg.fit(X_train_y2_pos, Y2_train_pos)
        Y2_pred_test = np.maximum(0, np.round(gb_y2_reg.predict(X_test_y2_pos))).astype(int)
        
        # Also predict for all test samples (including Y2=0)
        Y2_pred_all = np.maximum(0, np.round(gb_y2_reg.predict(X_test_arr))).astype(int)
        
        # Step 2: Use predicted Y2 as feature to predict Y1
        print("  Cascaded Prediction: Step 2 - Predict Y1 using predicted Y2")
        
        # Add predicted Y2 as a feature
        X_train_with_y2 = np.hstack([X_train_arr, np.array(Y2_train).reshape(-1, 1)])
        X_test_with_y2 = np.hstack([X_test_arr, Y2_pred_all.reshape(-1, 1)])
        
        # Normalize again with new feature
        scaler2 = StandardScaler()
        X_train_with_y2 = scaler2.fit_transform(X_train_with_y2)
        X_test_with_y2 = scaler2.transform(X_test_with_y2)
        
        # Predict Y1 on Y1>0 subset
        Y1_positive_train = np.array(Y1_train) > 0
        Y1_positive_test = np.array(Y1_test) > 0
        
        if np.sum(Y1_positive_train) > 10 and np.sum(Y1_positive_test) > 5:
            X_train_y1_pos = X_train_with_y2[Y1_positive_train]
            Z1_train_pos = np.array(Z1_train)[Y1_positive_train]
            X_test_y1_pos = X_test_with_y2[Y1_positive_test]
            Z1_test_pos = np.array(Z1_test)[Y1_positive_test]
            
            # Train Y1 regressor with predicted Y2 feature
            gb_y1_cascaded = GradientBoostingRegressor(n_estimators=100, max_depth=5, random_state=42)
            gb_y1_cascaded.fit(X_train_y1_pos, Z1_train_pos)
            Z1_pred_cascaded = gb_y1_cascaded.predict(X_test_y1_pos)
            
            # Evaluate overall
            results["Y1_Cascaded_Overall"] = evaluate_regression(Z1_test_pos, Z1_pred_cascaded, use_log=True)
            
            # Evaluate classwise by predicted Y2
            Y2_pred_test_all = Y2_pred_all[Y1_positive_test]
            Y1_test_pos = np.array(Y1_test)[Y1_positive_test]
            Z1_test_pos_arr = np.array(Z1_test_pos)
            
            # Group by predicted Y2 classes
            classwise_results = {}
            unique_y2_pred = np.unique(Y2_pred_test_all)
            
            for y2_class in unique_y2_pred:
                if y2_class < 0:
                    continue
                mask = Y2_pred_test_all == y2_class
                if np.sum(mask) >= 3:  # Need at least 3 samples
                    y1_true_class = Z1_test_pos_arr[mask]
                    y1_pred_class = Z1_pred_cascaded[mask]
                    
                    classwise_results[int(y2_class)] = {
                        "n_samples": int(np.sum(mask)),
                        "spearman": spearmanr(y1_true_class, y1_pred_class)[0] if HAS_SKLEARN and len(y1_true_class) > 1 else None,
                        "mae": mean_absolute_error(y1_true_class, y1_pred_class) if HAS_SKLEARN else np.mean(np.abs(y1_true_class - y1_pred_class)),
                        "mean_true": np.mean(np.expm1(y1_true_class)),
                        "mean_pred": np.mean(np.expm1(y1_pred_class)),
                    }
            
            results["Y1_Cascaded_Classwise"] = classwise_results
    
    return results


def compute_baselines(X_train, Y1_train, Y2_train, X_test, Y1_test, Y2_test, feature_names: List[str], H_d: nx.DiGraph, depth: Dict[str, int], V_d: Set[str]):
    """Compute baseline predictions."""
    baselines = {}
    
    # Zero baseline
    # For Y1: report MAE in log scale (Z1) to match regression metrics
    Z1_test = np.log1p(np.array(Y1_test))
    baselines["Zero"] = {
        "Y1_MAE_log": np.mean(np.abs(Z1_test)),  # Log scale (comparable to regression)
        "Y1_MAE_raw": np.mean(Y1_test),  # Raw scale (for reference)
        "Y2_MAE": np.mean(Y2_test),  # Raw scale (Y2 regression uses raw)
        "Y1_R2": 0.0,
        "Y2_R2": 0.0,
    }
    
    # Parent-mean baseline (if we have parent features)
    # Use max features since mean features were removed for redundancy
    if "parent_outdeg_max" in feature_names and "parent_descendant_count_seen_max" in feature_names:
        X_train_arr = features_to_array(X_train, feature_names)
        X_test_arr = features_to_array(X_test, feature_names)
        
        # Simple linear model using only parent max features
        parent_outdeg_idx = feature_names.index("parent_outdeg_max")
        parent_desc_idx = feature_names.index("parent_descendant_count_seen_max")
        
        X_simple_train = X_train_arr[:, [parent_outdeg_idx, parent_desc_idx]]
        X_simple_test = X_test_arr[:, [parent_outdeg_idx, parent_desc_idx]]
        
        # Y1 baseline
        try:
            Z1_train = np.log1p(np.array(Y1_train))
            Z1_test = np.log1p(np.array(Y1_test))
            lr_y1_base = LinearRegression()
            lr_y1_base.fit(X_simple_train, Z1_train)
            Z1_pred_base = lr_y1_base.predict(X_simple_test)
            Y1_pred_base = np.expm1(Z1_pred_base)
            baselines["Parent_Mean"] = {
                "Y1_MAE_log": mean_absolute_error(Z1_test, Z1_pred_base) if HAS_SKLEARN else np.mean(np.abs(Z1_test - Z1_pred_base)),  # Log scale
                "Y1_MAE_raw": mean_absolute_error(Y1_test, Y1_pred_base) if HAS_SKLEARN else np.mean(np.abs(np.array(Y1_test) - Y1_pred_base)),  # Raw scale
                "Y1_R2": r2_score(Y1_test, Y1_pred_base) if HAS_SKLEARN else None,
            }
        except:
            pass
        
        # Y2 baseline
        try:
            lr_y2_base = LinearRegression()
            lr_y2_base.fit(X_simple_train, Y2_train)
            Y2_pred_base = np.maximum(0, np.round(lr_y2_base.predict(X_simple_test))).astype(int)
            baselines["Parent_Mean"]["Y2_MAE"] = mean_absolute_error(Y2_test, Y2_pred_base) if HAS_SKLEARN else np.mean(np.abs(np.array(Y2_test) - Y2_pred_base))
            baselines["Parent_Mean"]["Y2_R2"] = r2_score(Y2_test, Y2_pred_base) if HAS_SKLEARN else None
        except:
            pass
    
    # Depth-only baseline
    if "depth" in feature_names:
        depth_idx = feature_names.index("depth")
        X_train_arr = features_to_array(X_train, feature_names)
        X_test_arr = features_to_array(X_test, feature_names)
        
        X_depth_train = X_train_arr[:, [depth_idx]]
        X_depth_test = X_test_arr[:, [depth_idx]]
        
        try:
            Z1_train = np.log1p(np.array(Y1_train))
            Z1_test = np.log1p(np.array(Y1_test))
            lr_depth = LinearRegression()
            lr_depth.fit(X_depth_train, Z1_train)
            Z1_pred_depth = lr_depth.predict(X_depth_test)
            Y1_pred_depth = np.expm1(Z1_pred_depth)
            baselines["Depth_Only"] = {
                "Y1_MAE_log": mean_absolute_error(Z1_test, Z1_pred_depth) if HAS_SKLEARN else np.mean(np.abs(Z1_test - Z1_pred_depth)),  # Log scale
                "Y1_MAE_raw": mean_absolute_error(Y1_test, Y1_pred_depth) if HAS_SKLEARN else np.mean(np.abs(np.array(Y1_test) - Y1_pred_depth)),  # Raw scale
                "Y1_R2": r2_score(Y1_test, Y1_pred_depth) if HAS_SKLEARN else None,
            }
        except:
            pass
    
    return baselines


def generate_visualization_plots(all_results: List[Dict]):
    """Generate visualization plots for prediction accuracy, Spearman correlation, and observed vs predicted."""
    if not HAS_MATPLOTLIB:
        return
    
    # Filter to r=0 results for main analysis
    r0_results = [r for r in all_results if r.get("r") == 0]
    if not r0_results:
        return
    
    # 1. Spearman correlation vs depth
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Prediction Performance Analysis (r=0)', fontsize=16, fontweight='bold')
    
    depths = [r["d"] for r in r0_results]
    
    # Plot 1: Spearman correlation for Y1
    ax1 = axes[0, 0]
    y1_spearman = []
    for r in r0_results:
        spearman = r.get("Y1_GBoost_Reg", {}).get("Spearman_rho", None)
        y1_spearman.append(spearman if spearman is not None else np.nan)
    
    ax1.plot(depths, y1_spearman, 'o-', linewidth=2, markersize=8, label='Y1 (Descendant Count)')
    ax1.set_xlabel('Depth d', fontsize=12)
    ax1.set_ylabel('Spearman Correlation', fontsize=12)
    ax1.set_title('Y1 Prediction: Spearman Correlation vs Depth', fontsize=13)
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    ax1.set_ylim([-1, 1])
    
    # Plot 2: PR-AUC for Y2 classification
    ax2 = axes[0, 1]
    y2_pr_auc = []
    for r in r0_results:
        pr_auc = r.get("Y2_GBoost_Class", {}).get("PR_AUC", None)
        y2_pr_auc.append(pr_auc if pr_auc is not None else np.nan)
    
    ax2.plot(depths, y2_pr_auc, 's-', linewidth=2, markersize=8, color='orange', label='Y2 (Outdegree)')
    ax2.set_xlabel('Depth d', fontsize=12)
    ax2.set_ylabel('PR-AUC', fontsize=12)
    ax2.set_title('Y2 Classification: PR-AUC vs Depth', fontsize=13)
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    ax2.set_ylim([0, 1])
    
    # Plot 3: MAE comparison (log scale for Y1)
    ax3 = axes[1, 0]
    y1_mae_log = []
    zero_y1_mae_log = []
    for r in r0_results:
        mae = r.get("Y1_GBoost_Reg", {}).get("MAE", None)
        zero_mae = r.get("baselines", {}).get("Zero", {}).get("Y1_MAE_log", None)
        y1_mae_log.append(mae if mae is not None else np.nan)
        zero_y1_mae_log.append(zero_mae if zero_mae is not None else np.nan)
    
    ax3.plot(depths, zero_y1_mae_log, '--', linewidth=2, label='Zero Baseline (log)', alpha=0.7)
    ax3.plot(depths, y1_mae_log, 'o-', linewidth=2, markersize=8, label='GBoost Model (log)', color='green')
    ax3.set_xlabel('Depth d', fontsize=12)
    ax3.set_ylabel('MAE (log scale)', fontsize=12)
    ax3.set_title('Y1 Prediction: MAE Comparison (log scale)', fontsize=13)
    ax3.grid(True, alpha=0.3)
    ax3.legend()
    
    # Plot 4: Y2 MAE comparison
    ax4 = axes[1, 1]
    y2_mae = []
    zero_y2_mae = []
    for r in r0_results:
        mae = r.get("Y2_GBoost_Reg", {}).get("MAE", None)
        zero_mae = r.get("baselines", {}).get("Zero", {}).get("Y2_MAE", None)
        y2_mae.append(mae if mae is not None else np.nan)
        zero_y2_mae.append(zero_mae if zero_mae is not None else np.nan)
    
    ax4.plot(depths, zero_y2_mae, '--', linewidth=2, label='Zero Baseline', alpha=0.7)
    ax4.plot(depths, y2_mae, 's-', linewidth=2, markersize=8, label='GBoost Model', color='red')
    ax4.set_xlabel('Depth d', fontsize=12)
    ax4.set_ylabel('MAE (raw scale)', fontsize=12)
    ax4.set_title('Y2 Prediction: MAE Comparison', fontsize=13)
    ax4.grid(True, alpha=0.3)
    ax4.legend()
    
    plt.tight_layout()
    plt.savefig(FIGS_DIR / "1_prediction_performance_summary.png", dpi=300, bbox_inches='tight')
    plt.savefig(FIGS_DIR / "1_prediction_performance_summary.pdf", bbox_inches='tight')
    plt.close()
    
    # 2. Observed vs Predicted scatter plots (for best depth)
    if r0_results:
        # Find depth with best Y1 Spearman correlation
        best_depth_idx = np.nanargmax(y1_spearman)
        best_result = r0_results[best_depth_idx]
        best_d = best_result["d"]
        
        # Create observed vs predicted plots
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle(f'Observed vs Predicted (r=0, d={best_d})', fontsize=16, fontweight='bold')
        
        # Y1: Log scale
        if "Y1_predictions" in best_result:
            ax1 = axes[0, 0]
            pred_data = best_result["Y1_predictions"]
            y1_true_log = np.array(pred_data["true_log"])
            y1_pred_log = np.array(pred_data["pred_log"])
            # Filter out zeros for log plot
            mask = (y1_true_log > 0) & (y1_pred_log > 0)
            if np.sum(mask) > 0:
                ax1.scatter(y1_true_log[mask], y1_pred_log[mask], alpha=0.5, s=20)
                # Diagonal line
                min_val = min(np.min(y1_true_log[mask]), np.min(y1_pred_log[mask]))
                max_val = max(np.max(y1_true_log[mask]), np.max(y1_pred_log[mask]))
                ax1.plot([min_val, max_val], [min_val, max_val], 'r--', linewidth=2, label='Perfect prediction')
                ax1.set_xlabel('Observed log(Y1+1)', fontsize=12)
                ax1.set_ylabel('Predicted log(Y1+1)', fontsize=12)
                ax1.set_title('Y1: Observed vs Predicted (log scale)', fontsize=13)
                ax1.legend()
                ax1.grid(True, alpha=0.3)
        
        # Y1: Raw scale (log-log for better visualization)
        if "Y1_predictions" in best_result:
            ax2 = axes[0, 1]
            pred_data = best_result["Y1_predictions"]
            y1_true = np.array(pred_data["true"])
            y1_pred = np.array(pred_data["pred"])
            # Log-log plot
            mask = (y1_true > 0) & (y1_pred > 0)
            if np.sum(mask) > 0:
                ax2.loglog(y1_true[mask], y1_pred[mask], 'o', alpha=0.5, markersize=4)
                # Diagonal line
                min_val = min(np.min(y1_true[mask]), np.min(y1_pred[mask]))
                max_val = max(np.max(y1_true[mask]), np.max(y1_pred[mask]))
                ax2.loglog([min_val, max_val], [min_val, max_val], 'r--', linewidth=2, label='Perfect prediction')
                ax2.set_xlabel('Observed Y1', fontsize=12)
                ax2.set_ylabel('Predicted Y1', fontsize=12)
                ax2.set_title('Y1: Observed vs Predicted (log-log scale)', fontsize=13)
                ax2.legend()
                ax2.grid(True, alpha=0.3)
        
        # Y2: Raw scale
        if "Y2_predictions" in best_result:
            ax3 = axes[1, 0]
            pred_data = best_result["Y2_predictions"]
            y2_true = np.array(pred_data["true"])
            y2_pred = np.array(pred_data["pred"])
            ax3.scatter(y2_true, y2_pred, alpha=0.5, s=20, color='orange')
            # Diagonal line
            max_val = max(np.max(y2_true), np.max(y2_pred))
            ax3.plot([0, max_val], [0, max_val], 'r--', linewidth=2, label='Perfect prediction')
            ax3.set_xlabel('Observed Y2', fontsize=12)
            ax3.set_ylabel('Predicted Y2', fontsize=12)
            ax3.set_title('Y2: Observed vs Predicted', fontsize=13)
            ax3.legend()
            ax3.grid(True, alpha=0.3)
        
        # Y2: Confusion matrix style (for classification)
        if "Y2_GBoost_Class" in best_result:
            ax4 = axes[1, 1]
            # Get classification probabilities if available
            # For now, show distribution of Y2 predictions vs true
            if "Y2_predictions" in best_result:
                pred_data = best_result["Y2_predictions"]
                y2_true = np.array(pred_data["true"])
                y2_pred = np.array(pred_data["pred"])
                bins = np.arange(-0.5, max(np.max(y2_true), np.max(y2_pred)) + 1.5, 1)
                ax4.hist(y2_true, bins=bins, alpha=0.5, label='Observed', color='blue')
                ax4.hist(y2_pred, bins=bins, alpha=0.5, label='Predicted', color='orange')
                ax4.set_xlabel('Y2 (Outdegree)', fontsize=12)
                ax4.set_ylabel('Frequency', fontsize=12)
                ax4.set_title('Y2: Distribution Comparison', fontsize=13)
                ax4.legend()
                ax4.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        plt.savefig(FIGS_DIR / f"1_observed_vs_predicted_d{best_d}.png", dpi=300, bbox_inches='tight')
        plt.savefig(FIGS_DIR / f"1_observed_vs_predicted_d{best_d}.pdf", bbox_inches='tight')
        plt.close()
        print(f"  Generated observed vs predicted plots (d={best_d})")
    
    # 3. Feature importance plot (if available)
    feature_importance_data = []
    for r in r0_results:
        if "feature_importance" in r:
            fi = r["feature_importance"]
            d = r["d"]
            for feat_name, importance in fi.items():
                feature_importance_data.append({
                    "feature": feat_name,
                    "importance": importance,
                    "depth": d
                })
    
    if feature_importance_data:
        # Aggregate feature importance across depths
        feat_agg = {}
        for item in feature_importance_data:
            feat = item["feature"]
            if feat not in feat_agg:
                feat_agg[feat] = []
            feat_agg[feat].append(item["importance"])
        
        # Average importance per feature
        feat_avg_imp = {feat: np.mean(imps) for feat, imps in feat_agg.items()}
        sorted_feats = sorted(feat_avg_imp.items(), key=lambda x: x[1], reverse=True)[:15]  # Top 15
        
        fig, ax = plt.subplots(figsize=(10, 8))
        features = [f[0] for f in sorted_feats]
        importances = [f[1] for f in sorted_feats]
        
        ax.barh(range(len(features)), importances, color='steelblue')
        ax.set_yticks(range(len(features)))
        ax.set_yticklabels(features)
        ax.set_xlabel('Average Feature Importance', fontsize=12)
        ax.set_title('Top 15 Feature Importances (r=0, averaged across depths)', fontsize=13)
        ax.grid(True, alpha=0.3, axis='x')
        plt.tight_layout()
        plt.savefig(FIGS_DIR / "1_feature_importance.png", dpi=300, bbox_inches='tight')
        plt.savefig(FIGS_DIR / "1_feature_importance.pdf", bbox_inches='tight')
        plt.close()
        print(f"  Generated feature importance plot")
    
    print(f"  All plots saved to {FIGS_DIR}")


def main():
    """Main pipeline execution."""
    print("=" * 80)
    print("FVS-based DAG Cleaning and Prediction Pipeline v2")
    print("=" * 80)
    
    # Load feature config
    try:
        feature_cfg = load_feature_config(DEFAULT_FEATURE_CONFIG)
        print(f"\nLoaded feature config: {DEFAULT_FEATURE_CONFIG.name}")
        params = feature_cfg.get("params", {})
        print(f"  strict_past_seen_graph: {params.get('strict_past_seen_graph', True)}")
    except Exception as e:
        print(f"ERROR: Could not load feature config: {e}")
        return
    
    # Load graph
    G = load_graph_from_cache()
    if G is None:
        print("ERROR: Could not load graph from cache.")
        print("Please run 00_theorem_premise_network.py first to build the graph.")
        return
    
    print(f"\nInitial graph: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")
    
    # Sanity check
    if not isinstance(G, nx.DiGraph):
        print("ERROR: Graph is not directed. Converting to DiGraph...")
        G = nx.DiGraph(G)
    
    # Step 1: Compute FVS and make graph acyclic
    cached_fvs = load_fvs_cache()
    if cached_fvs is not None:
        G_dag, F, fvs_stats = cached_fvs
        print("  Using cached FVS results")
    else:
        G_dag, F, fvs_stats = greedy_scc_fvs(G)
        save_fvs_cache(G_dag, F, fvs_stats)
    
    print(f"\nFinal DAG: {G_dag.number_of_nodes():,} nodes, {G_dag.number_of_edges():,} edges")
    print(f"Removed nodes: {len(F):,}")
    
    # Step 2: Compute depth
    if FVS_CACHE_DEPTHS.exists():
        try:
            with open(FVS_CACHE_DEPTHS, "rb") as f:
                depth = pickle.load(f)
            print("Loaded depths from cache")
        except:
            depth = compute_depth(G_dag)
            with open(FVS_CACHE_DEPTHS, "wb") as f:
                pickle.dump(depth, f)
    else:
        depth = compute_depth(G_dag)
        with open(FVS_CACHE_DEPTHS, "wb") as f:
            pickle.dump(depth, f)
    
    # Analyze depth distribution
    depth_values = list(depth.values())
    print(f"\nDepth distribution:")
    print(f"  min={min(depth_values)}, max={max(depth_values)}, mean={np.mean(depth_values):.2f}")
    
    # Step 3: Compute targets
    if FVS_CACHE_TARGETS.exists():
        try:
            with open(FVS_CACHE_TARGETS, "rb") as f:
                targets = pickle.load(f)
            print("Loaded targets from cache")
        except:
            targets = compute_targets(G_dag)
            with open(FVS_CACHE_TARGETS, "wb") as f:
                pickle.dump(targets, f)
    else:
        targets = compute_targets(G_dag)
        with open(FVS_CACHE_TARGETS, "wb") as f:
            pickle.dump(targets, f)
    
    # Step 4-5: Evaluation protocol
    print("\n" + "=" * 80)
    print("Step 4-5: Predictive evaluation")
    print("=" * 80)
    
    # Choose depth values: 5 to 15 in increments of 2
    max_depth_val = max(depth_values)
    d_values = list(range(5, 16, 2))  # [5, 7, 9, 11, 13, 15]
    d_values = [d for d in d_values if d <= max_depth_val]
    
    print(f"\nEvaluating with depth values: {d_values}")
    print(f"Radius values: r in {{0, 1, 2}}")
    
    all_results = []
    
    for d in d_values:
        print(f"\n{'='*80}")
        print(f"Depth d = {d}")
        print(f"{'='*80}")
        
        # Create H_d (observed graph)
        nodes_in_Hd = [v for v in G_dag.nodes() if depth.get(v, 0) <= d]
        H_d = G_dag.subgraph(nodes_in_Hd).copy()
        
        # Create V_d (frontier nodes)
        V_d = {v for v in G_dag.nodes() if depth.get(v, 0) == d}
        
        print(f"  H_d nodes: {len(nodes_in_Hd):,}")
        print(f"  V_d (frontier) nodes: {len(V_d):,}")
        
        if len(V_d) < 10:
            print(f"  Skipping d={d}: too few frontier nodes ({len(V_d)})")
            continue
        
        for r in [0, 1, 2]:
            print(f"\n  {'-'*76}")
            print(f"  Radius r = {r}")
            print(f"  {'-'*76}")
            
            # Create dataset
            try:
                # Load feature config
                feature_cfg = load_feature_config(DEFAULT_FEATURE_CONFIG)
                X, Y1, Y2, Z1, Z2, nodes, feature_names = create_dataset(G_dag, depth, targets, d, r, feature_cfg)
            except Exception as e:
                print(f"    Error creating dataset: {e}")
                continue
            
            if len(X) < 20:
                print(f"    Skipping r={r}: too few nodes ({len(X)})")
                continue
            
            print(f"    Dataset size: {len(X):,}")
            print(f"    Y1 stats: min={min(Y1)}, max={max(Y1)}, mean={np.mean(Y1):.2f}")
            print(f"    Y2 stats: min={min(Y2)}, max={max(Y2)}, mean={np.mean(Y2):.2f}")
            
            # Split into train/test (80/20)
            n_train = int(0.8 * len(X))
            indices = list(range(len(X)))
            random.shuffle(indices)
            
            train_indices = indices[:n_train]
            test_indices = indices[n_train:]
            
            X_train = [X[i] for i in train_indices]
            Y1_train = [Y1[i] for i in train_indices]
            Y2_train = [Y2[i] for i in train_indices]
            Z1_train = [Z1[i] for i in train_indices]
            Z2_train = [Z2[i] for i in train_indices]
            
            X_test = [X[i] for i in test_indices]
            Y1_test = [Y1[i] for i in test_indices]
            Y2_test = [Y2[i] for i in test_indices]
            Z1_test = [Z1[i] for i in test_indices]
            Z2_test = [Z2[i] for i in test_indices]
            
            print(f"    Train: {len(X_train):,}, Test: {len(X_test):,}")
            
            # Build H_d for baselines (needed for some baseline computations)
            nodes_in_Hd = [v for v in G_dag.nodes() if depth.get(v, 0) <= d]
            H_d = G_dag.subgraph(nodes_in_Hd).copy()
            
            # Compute baselines (feature_names already resolved from create_dataset)
            baselines = compute_baselines(X_train, Y1_train, Y2_train, X_test, Y1_test, Y2_test, 
                                         feature_names, H_d, depth, V_d)
            
            # Train and evaluate
            results = train_and_evaluate_two_stage(X_train, Y1_train, Y2_train, Z1_train, Z2_train,
                                                   X_test, Y1_test, Y2_test, Z1_test, Z2_test,
                                                   feature_names, r)
            
            # For r=0, also do cascaded prediction (use predicted Y2 to predict Y1)
            if r == 0:
                cascaded_results = cascaded_prediction_y1_from_y2(X_train, Y1_train, Y2_train, Z1_train,
                                                                  X_test, Y1_test, Y2_test, Z1_test,
                                                                  feature_names)
                results.update(cascaded_results)
            
            # Store results
            result_row = {
                "d": d,
                "r": r,
                "n_nodes": len(X),
                "n_frontier": len(V_d),
                "baselines": baselines,
                **results
            }
            all_results.append(result_row)
            
            # Print results summary
            print(f"\n    Results summary:")
            if "Y2_GBoost_Class" in results:
                pr_auc = results["Y2_GBoost_Class"].get("PR_AUC")
                if pr_auc:
                    print(f"      Y2 Classification PR-AUC: {pr_auc:.4f}")
            if "Y1_GBoost_Reg" in results:
                spearman = results["Y1_GBoost_Reg"].get("Spearman_rho")
                if spearman:
                    print(f"      Y1 Regression Spearman: {spearman:.4f}")
    
    # Summary report
    print("\n" + "=" * 80)
    print("SUMMARY REPORT")
    print("=" * 80)
    
    print("\nBaselines vs Models (r=0, primary claim):")
    print(f"{'d':<6} {'N':<8} {'Zero_Y1_log':<14} {'Zero_Y2':<12} {'Model_Y1_ρ':<14} {'Model_Y2_PR':<14}")
    print("-" * 80)
    print("Note: Y1 baselines use log-scale MAE (comparable to regression); Y2 uses raw-scale MAE")
    
    for row in all_results:
        if row["r"] == 0:
            d = row["d"]
            n = row["n_nodes"]
            # Use log-scale MAE for Y1 (comparable to regression metrics)
            zero_y1_log = row["baselines"]["Zero"].get("Y1_MAE_log", row["baselines"]["Zero"].get("Y1_MAE", None))
            zero_y2 = row["baselines"]["Zero"]["Y2_MAE"]
            
            y1_spearman = row.get("Y1_GBoost_Reg", {}).get("Spearman_rho", None)
            y2_pr_auc = row.get("Y2_GBoost_Class", {}).get("PR_AUC", None)
            
            y1_str = f"{y1_spearman:.4f}" if y1_spearman else "N/A"
            y2_str = f"{y2_pr_auc:.4f}" if y2_pr_auc else "N/A"
            zero_y1_str = f"{zero_y1_log:.4f}" if zero_y1_log is not None else "N/A"
            
            print(f"{d:<6} {n:<8} {zero_y1_str:<12} {zero_y2:<12.2f} {y1_str:<14} {y2_str:<14}")
    
    # Cascaded prediction summary (r=0 only)
    print("\n" + "=" * 80)
    print("CASCADED PREDICTION SUMMARY (r=0: Using Predicted Y2 to Predict Y1)")
    print("=" * 80)
    
    cascaded_rows = []
    for row in all_results:
        if row["r"] == 0 and "Y1_Cascaded_Overall" in row:
            cascaded_rows.append(row)
    
    if cascaded_rows:
        print(f"\n{'Depth d':<10} {'N':<8} {'Overall Spearman':<18} {'Overall MAE':<15}")
        print("-" * 60)
        for row in cascaded_rows:
            d = row["d"]
            n = row["n_nodes"]
            overall = row.get("Y1_Cascaded_Overall", {})
            spearman = overall.get("Spearman_rho", None)
            mae = overall.get("MAE", None)
            spearman_str = f"{spearman:.4f}" if spearman else "N/A"
            mae_str = f"{mae:.4f}" if mae else "N/A"
            print(f"{d:<10} {n:<8} {spearman_str:<18} {mae_str:<15}")
        
        # Classwise results table
        print(f"\n{'Depth d':<10} {'Pred Y2':<10} {'N':<8} {'Spearman':<12} {'MAE':<12} {'Mean True':<12} {'Mean Pred':<12}")
        print("-" * 80)
        for row in cascaded_rows:
            d = row["d"]
            classwise = row.get("Y1_Cascaded_Classwise", {})
            for y2_class in sorted(classwise.keys()):
                cw = classwise[y2_class]
                spearman = cw.get("spearman", None)
                mae = cw.get("mae", None)
                mean_true = cw.get("mean_true", None)
                mean_pred = cw.get("mean_pred", None)
                spearman_str = f"{spearman:.4f}" if spearman else "N/A"
                mae_str = f"{mae:.4f}" if mae else "N/A"
                mean_true_str = f"{mean_true:.1f}" if mean_true else "N/A"
                mean_pred_str = f"{mean_pred:.1f}" if mean_pred else "N/A"
                print(f"{d:<10} {y2_class:<10} {cw['n_samples']:<8} {spearman_str:<12} {mae_str:<12} {mean_true_str:<12} {mean_pred_str:<12}")
    
    # Save results to JSON
    out_path = DATA_DIR / f"{FVS_CACHE_PREFIX}results.json"
    DATA_DIR.mkdir(exist_ok=True)
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2)
        print(f"\nSaved results to JSON: {out_path}")
    except Exception as e:
        print(f"\nWarning: Could not save results to JSON: {e}")
    
    # Generate visualization plots
    if HAS_MATPLOTLIB and all_results:
        print("\n" + "=" * 80)
        print("Generating visualization plots")
        print("=" * 80)
        try:
            generate_visualization_plots(all_results)
            print(f"Saved plots to {FIGS_DIR}")
        except Exception as e:
            print(f"Warning: Could not generate plots: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("Pipeline complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
