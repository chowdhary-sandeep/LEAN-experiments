"""
FVS-based DAG cleaning and prediction pipeline for theorem dependency graph.

This script:
1. Makes the graph acyclic by removing a feedback vertex set (FVS)
2. Defines synthetic "time/radius" coordinates from sources
3. Creates prediction targets and datasets
4. Implements predictive strategies
5. Evaluates with proper protocols
"""

import json
import pickle
import networkx as nx
from pathlib import Path
from collections import defaultdict, deque
import numpy as np
import random
import time
import sys
import io
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
    from sklearn.linear_model import LinearRegression, PoissonRegressor
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.metrics import r2_score, mean_absolute_error
    from sklearn.preprocessing import StandardScaler
    from scipy.stats import spearmanr
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    warnings.warn("sklearn/scipy not available - prediction models will be skipped")

# Set UTF-8 encoding for stdout on Windows
if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Configuration
_SCRIPT_DIR = Path(__file__).resolve().parent
CACHE_DIR = _SCRIPT_DIR / "cache"
CACHE_BUNDLE = CACHE_DIR / "bundle.pkl"

# Cache prefix for FVS pipeline files
FVS_CACHE_PREFIX = "fvs_pipeline_"
FVS_CACHE_DAG = CACHE_DIR / f"{FVS_CACHE_PREFIX}dag.pkl"
FVS_CACHE_FVS = CACHE_DIR / f"{FVS_CACHE_PREFIX}fvs.pkl"
FVS_CACHE_STATS = CACHE_DIR / f"{FVS_CACHE_PREFIX}stats.pkl"
FVS_CACHE_RANKS = CACHE_DIR / f"{FVS_CACHE_PREFIX}ranks.pkl"
FVS_CACHE_TARGETS = CACHE_DIR / f"{FVS_CACHE_PREFIX}targets.pkl"

# Set random seed for reproducibility
random.seed(42)
np.random.seed(42)


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
        CACHE_DIR.mkdir(exist_ok=True)
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


def save_ranks_cache(ranks: Dict):
    """Save rank computation results to cache."""
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        with open(FVS_CACHE_RANKS, "wb") as f:
            pickle.dump(ranks, f, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"  Saved ranks to cache")
    except Exception as e:
        print(f"  Warning: Could not save ranks cache: {e}")


def load_ranks_cache() -> Optional[Dict]:
    """Load rank computation results from cache if available."""
    if FVS_CACHE_RANKS.exists():
        try:
            with open(FVS_CACHE_RANKS, "rb") as f:
                ranks = pickle.load(f)
            print(f"Loaded ranks from cache: {len(ranks):,} nodes")
            return ranks
        except Exception as e:
            print(f"Error loading ranks cache: {e}")
    return None


def save_targets_cache(targets: Dict):
    """Save target computation results to cache."""
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        with open(FVS_CACHE_TARGETS, "wb") as f:
            pickle.dump(targets, f, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"  Saved targets to cache")
    except Exception as e:
        print(f"  Warning: Could not save targets cache: {e}")


def load_targets_cache() -> Optional[Dict]:
    """Load target computation results from cache if available."""
    if FVS_CACHE_TARGETS.exists():
        try:
            with open(FVS_CACHE_TARGETS, "rb") as f:
                targets = pickle.load(f)
            print(f"Loaded targets from cache: {len(targets):,} nodes")
            return targets
        except Exception as e:
            print(f"Error loading targets cache: {e}")
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
        
        if show_progress:
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
            
            if show_progress:
                print(f"  Removed node: {v_star[:80]}... (score={scores[v_star]})")
    
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


def compute_ranks(G_dag: nx.DiGraph, rank_type: str = "both") -> Dict[str, Dict[str, int]]:
    """
    Compute rank coordinates from sources.
    
    Args:
        G_dag: Acyclic directed graph
        rank_type: "max", "min", or "both"
    
    Returns:
        Dictionary mapping node -> {"r_max": int, "r_min": int}
    """
    print("\n" + "=" * 80)
    print(f"Step 2: Computing rank coordinates (type={rank_type})")
    print("=" * 80)
    
    # Find sources
    sources = [v for v in G_dag.nodes() if G_dag.in_degree(v) == 0]
    print(f"Found {len(sources):,} source nodes")
    
    ranks = {v: {} for v in G_dag.nodes()}
    
    if rank_type in ["max", "both"]:
        # Longest-path rank: r_max(v) = 0 if source, else 1 + max(parent ranks)
        print("\nComputing longest-path ranks (r_max)...")
        r_max = {}
        
        # Topological sort ensures we process nodes in order
        topo_order = list(nx.topological_sort(G_dag))
        
        if HAS_TQDM:
            pbar = tqdm(topo_order, desc="r_max")
        else:
            pbar = topo_order
        
        for v in pbar:
            if v in sources:
                r_max[v] = 0
            else:
                parents = list(G_dag.predecessors(v))
                if parents:
                    r_max[v] = 1 + max(r_max.get(p, -1) for p in parents)
                else:
                    r_max[v] = 0
        
        for v in G_dag.nodes():
            ranks[v]["r_max"] = r_max.get(v, 0)
        
        max_depth = max(r_max.values()) if r_max else 0
        print(f"  Max depth: {max_depth}")
    
    if rank_type in ["min", "both"]:
        # Shortest-to-source rank: BFS distance from sources
        print("\nComputing shortest-to-source ranks (r_min)...")
        r_min = {}
        queue = deque([(s, 0) for s in sources])
        visited = set(sources)
        
        for s in sources:
            r_min[s] = 0
        
        while queue:
            v, dist = queue.popleft()
            for w in G_dag.successors(v):
                if w not in visited:
                    visited.add(w)
                    r_min[w] = dist + 1
                    queue.append((w, dist + 1))
        
        # Nodes not reachable from sources get rank = max_rank + 1
        max_r_min = max(r_min.values()) if r_min else 0
        for v in G_dag.nodes():
            if v not in r_min:
                r_min[v] = max_r_min + 1
        
        for v in G_dag.nodes():
            ranks[v]["r_min"] = r_min.get(v, 0)
        
        print(f"  Max r_min: {max(r_min.values()) if r_min else 0}")
    
    return ranks


def compute_targets(G_dag: nx.DiGraph) -> Dict[str, Dict[str, int]]:
    """
    Compute prediction targets for each node.
    
    Returns:
        Dictionary mapping node -> {"Y1": int, "Y2": int}
        Y1: total descendants count
        Y2: outdegree
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
    
    return targets


def compute_features_H_R(G_dag: nx.DiGraph, H_R: nx.DiGraph, v: str, 
                         ranks: Dict[str, Dict[str, int]], rank_type: str = "r_max") -> Dict[str, float]:
    """
    Compute features for node v using only subgraph H_R.
    
    Args:
        G_dag: Full DAG (for reference, but don't use for features)
        H_R: Induced subgraph on nodes with rank <= R
        v: Node to compute features for
        ranks: Rank dictionary
        rank_type: Which rank to use ("r_max" or "r_min")
    
    Returns:
        Dictionary of feature values
    """
    if v not in H_R:
        return {}
    
    features = {}
    
    # Basic degree features
    features["outdeg_HR"] = H_R.out_degree(v)
    features["indeg_HR"] = H_R.in_degree(v)
    features["rank"] = ranks[v].get(rank_type, 0)
    
    # Count features within H_R
    parents_HR = list(H_R.predecessors(v))
    children_HR = list(H_R.successors(v))
    features["parent_count"] = len(parents_HR)
    features["child_count"] = len(children_HR)
    
    # Ancestor count within H_R (BFS backward)
    ancestors = set()
    queue = deque([v])
    visited = {v}
    while queue:
        u = queue.popleft()
        for p in H_R.predecessors(u):
            if p not in visited:
                visited.add(p)
                ancestors.add(p)
                queue.append(p)
    features["ancestor_count"] = len(ancestors)
    
    # Reachable count forward within H_R
    reachable = set()
    queue = deque([v])
    visited = {v}
    while queue:
        u = queue.popleft()
        for w in H_R.successors(u):
            if w not in visited:
                visited.add(w)
                reachable.add(w)
                queue.append(w)
    features["reachable_count_forward_HR"] = len(reachable)
    
    # Diamond rate: count pairs of parents that share a child (or children that share a parent)
    diamond_count = 0
    # Parent pairs sharing a child
    for i, p1 in enumerate(parents_HR):
        for p2 in parents_HR[i+1:]:
            children_p1 = set(H_R.successors(p1))
            children_p2 = set(H_R.successors(p2))
            if children_p1 & children_p2:  # Intersection
                diamond_count += 1
    # Child pairs sharing a parent
    for i, c1 in enumerate(children_HR):
        for c2 in children_HR[i+1:]:
            parents_c1 = set(H_R.predecessors(c1))
            parents_c2 = set(H_R.predecessors(c2))
            if parents_c1 & parents_c2:  # Intersection
                diamond_count += 1
    
    features["diamond_rate"] = diamond_count
    
    return features


def create_dataset(G_dag: nx.DiGraph, ranks: Dict[str, Dict[str, int]], 
                   targets: Dict[str, Dict[str, int]], R: int, 
                   rank_type: str = "r_max") -> Tuple[List[Dict], List[float], List[int]]:
    """
    Create dataset for rank cutoff R.
    
    Returns:
        X: List of feature dictionaries
        Y1: List of Y1 targets
        Y2: List of Y2 targets
    """
    # Get nodes with rank <= R
    nodes_in_HR = [v for v in G_dag.nodes() 
                   if ranks[v].get(rank_type, float('inf')) <= R]
    
    # Create induced subgraph H_R
    H_R = G_dag.subgraph(nodes_in_HR).copy()
    
    X = []
    Y1 = []
    Y2 = []
    
    for v in nodes_in_HR:
        features = compute_features_H_R(G_dag, H_R, v, ranks, rank_type)
        if features:  # Only include if features computed successfully
            X.append(features)
            Y1.append(targets[v]["Y1"])
            Y2.append(targets[v]["Y2"])
    
    return X, Y1, Y2


def features_to_array(X: List[Dict], feature_names: List[str]) -> np.ndarray:
    """Convert list of feature dicts to numpy array."""
    return np.array([[x.get(fn, 0.0) for fn in feature_names] for x in X])


def evaluate_predictions(y_true, y_pred, task: str = "regression"):
    """Compute evaluation metrics."""
    if len(y_true) == 0 or len(y_pred) == 0:
        return {}
    
    metrics = {}
    
    if task == "regression":
        metrics["MAE"] = mean_absolute_error(y_true, y_pred) if HAS_SKLEARN else np.mean(np.abs(np.array(y_true) - np.array(y_pred)))
        metrics["R2"] = r2_score(y_true, y_pred) if HAS_SKLEARN else None
        
        # Rank correlation
        try:
            corr, pval = spearmanr(y_true, y_pred) if HAS_SKLEARN else (None, None)
            metrics["Spearman_rho"] = corr
        except:
            metrics["Spearman_rho"] = None
    
    elif task == "count":
        metrics["MAE"] = mean_absolute_error(y_true, y_pred) if HAS_SKLEARN else np.mean(np.abs(np.array(y_true) - np.array(y_pred)))
        # For count data, also compute mean
        metrics["mean_true"] = np.mean(y_true)
        metrics["mean_pred"] = np.mean(y_pred)
    
    return metrics


def train_and_evaluate(X_train, Y1_train, Y2_train, X_test, Y1_test, Y2_test, 
                       feature_names: List[str]):
    """Train models and evaluate on test set."""
    results = {}
    
    if not HAS_SKLEARN:
        return {"error": "sklearn not available"}
    
    # Convert to arrays
    X_train_arr = features_to_array(X_train, feature_names)
    X_test_arr = features_to_array(X_test, feature_names)
    
    # Handle NaN and inf values
    X_train_arr = np.nan_to_num(X_train_arr, nan=0.0, posinf=1e6, neginf=-1e6)
    X_test_arr = np.nan_to_num(X_test_arr, nan=0.0, posinf=1e6, neginf=-1e6)
    
    # Normalize features (helps with numerical stability)
    scaler = StandardScaler()
    X_train_arr = scaler.fit_transform(X_train_arr)
    X_test_arr = scaler.transform(X_test_arr)
    
    # Y1: Regression on log(1+Y1)
    print("\n  Training Y1 models...")
    Y1_train_log = np.log1p(Y1_train)
    
    # Linear regression
    lr_y1 = LinearRegression()
    try:
        lr_y1.fit(X_train_arr, Y1_train_log)
        Y1_pred_log = lr_y1.predict(X_test_arr)
        # Clip predictions to avoid extreme values
        Y1_pred_log = np.clip(Y1_pred_log, -10, 20)  # Reasonable range for log values
        Y1_pred = np.expm1(Y1_pred_log)
        # Ensure non-negative
        Y1_pred = np.maximum(0, Y1_pred)
    except Exception as e:
        print(f"    Error in Y1 Linear regression: {e}")
        Y1_pred = np.zeros(len(Y1_test))
    
    results["Y1_Linear"] = evaluate_predictions(Y1_test, Y1_pred, "regression")
    # Store feature importance (coefficients)
    results["Y1_Linear"]["feature_importance"] = {
        fn: abs(coef) for fn, coef in zip(feature_names, lr_y1.coef_)
    }
    
    # Gradient boosting
    gb_y1 = GradientBoostingRegressor(n_estimators=100, max_depth=5, random_state=42)
    try:
        gb_y1.fit(X_train_arr, Y1_train_log)
        Y1_pred_log_gb = gb_y1.predict(X_test_arr)
        # Clip predictions to avoid extreme values
        Y1_pred_log_gb = np.clip(Y1_pred_log_gb, -10, 20)
        Y1_pred_gb = np.expm1(Y1_pred_log_gb)
        # Ensure non-negative
        Y1_pred_gb = np.maximum(0, Y1_pred_gb)
    except Exception as e:
        print(f"    Error in Y1 Gradient Boosting: {e}")
        Y1_pred_gb = np.zeros(len(Y1_test))
    
    results["Y1_GBoost"] = evaluate_predictions(Y1_test, Y1_pred_gb, "regression")
    # Store feature importance
    results["Y1_GBoost"]["feature_importance"] = {
        fn: imp for fn, imp in zip(feature_names, gb_y1.feature_importances_)
    }
    
    # Y2: Count regression
    print("  Training Y2 models...")
    
    # Poisson regression
    poisson_y2 = PoissonRegressor(max_iter=200)
    try:
        poisson_y2.fit(X_train_arr, Y2_train)
        Y2_pred_poisson = poisson_y2.predict(X_test_arr)
        Y2_pred_poisson = np.maximum(0, np.round(Y2_pred_poisson)).astype(int)
        results["Y2_Poisson"] = evaluate_predictions(Y2_test, Y2_pred_poisson, "count")
        # Store feature importance (coefficients)
        results["Y2_Poisson"]["feature_importance"] = {
            fn: abs(coef) for fn, coef in zip(feature_names, poisson_y2.coef_)
        }
    except Exception as e:
        results["Y2_Poisson"] = {"error": str(e)}
    
    # Gradient boosting for Y2
    gb_y2 = GradientBoostingRegressor(n_estimators=100, max_depth=5, random_state=42)
    gb_y2.fit(X_train_arr, Y2_train)
    Y2_pred_gb = np.maximum(0, np.round(gb_y2.predict(X_test_arr))).astype(int)
    results["Y2_GBoost"] = evaluate_predictions(Y2_test, Y2_pred_gb, "count")
    # Store feature importance
    results["Y2_GBoost"]["feature_importance"] = {
        fn: imp for fn, imp in zip(feature_names, gb_y2.feature_importances_)
    }
    
    return results


def main():
    """Main pipeline execution."""
    print("=" * 80)
    print("FVS-based DAG Cleaning and Prediction Pipeline")
    print("=" * 80)
    
    # Load graph
    G = load_graph_from_cache()
    if G is None:
        print("ERROR: Could not load graph from cache.")
        print("Please run 00_theorem_premise_network.py first to build the graph.")
        return
    
    print(f"\nInitial graph: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")
    
    # Sanity check: verify graph is directed
    if not isinstance(G, nx.DiGraph):
        print("ERROR: Graph is not directed. Converting to DiGraph...")
        G = nx.DiGraph(G)
    
    # Check for self-loops
    self_loops = list(nx.selfloop_edges(G))
    if self_loops:
        print(f"  Found {len(self_loops)} self-loops (will be handled by FVS)")
    
    # Check if already acyclic
    try:
        list(nx.topological_sort(G))
        print("  WARNING: Graph is already acyclic! FVS will be empty.")
    except (nx.NetworkXError, nx.NetworkXUnfeasible):
        print("  Graph contains cycles (expected)")
    
    # Step 1: Compute FVS and make graph acyclic (check cache first)
    cached_fvs = load_fvs_cache()
    if cached_fvs is not None:
        G_dag, F, fvs_stats = cached_fvs
        print("  Using cached FVS results")
    else:
        G_dag, F, fvs_stats = greedy_scc_fvs(G)
        save_fvs_cache(G_dag, F, fvs_stats)
    
    print(f"\nFinal DAG: {G_dag.number_of_nodes():,} nodes, {G_dag.number_of_edges():,} edges")
    print(f"Removed nodes: {len(F):,}")
    
    # Step 2: Compute ranks (check cache first)
    ranks = load_ranks_cache()
    if ranks is None:
        ranks = compute_ranks(G_dag, rank_type="both")
        save_ranks_cache(ranks)
    else:
        print("  Using cached ranks")
    
    # Analyze rank distribution
    r_max_values = [ranks[v]["r_max"] for v in G_dag.nodes()]
    r_min_values = [ranks[v]["r_min"] for v in G_dag.nodes()]
    
    print("\nRank distribution:")
    print(f"  r_max: min={min(r_max_values)}, max={max(r_max_values)}, mean={np.mean(r_max_values):.2f}")
    print(f"  r_min: min={min(r_min_values)}, max={max(r_min_values)}, mean={np.mean(r_min_values):.2f}")
    
    # Step 3: Compute targets (check cache first)
    targets = load_targets_cache()
    if targets is None:
        targets = compute_targets(G_dag)
        save_targets_cache(targets)
    else:
        print("  Using cached targets")
    
    # Step 4 & 5: Evaluation protocol
    print("\n" + "=" * 80)
    print("Step 4-5: Predictive evaluation")
    print("=" * 80)
    
    # Choose R values based on graph depth
    max_r_max = max(r_max_values)
    R_values = [5, 10, 20, 40]
    R_values = [R for R in R_values if R <= max_r_max]
    if max_r_max > 40:
        R_values.append(min(60, max_r_max))
    
    print(f"\nEvaluating with R values: {R_values}")
    
    # Feature names (baseline + local structure)
    feature_names = [
        "outdeg_HR", "indeg_HR", "rank",
        "parent_count", "child_count", "ancestor_count",
        "reachable_count_forward_HR", "diamond_rate"
    ]
    
    all_results = []
    
    for R in R_values:
        print(f"\n{'='*80}")
        print(f"R = {R}")
        print(f"{'='*80}")
        
        # Create dataset for this R
        try:
            X, Y1, Y2 = create_dataset(G_dag, ranks, targets, R, rank_type="r_max")
        except Exception as e:
            print(f"  Error creating dataset for R={R}: {e}")
            continue
        
        if len(X) < 20:
            print(f"  Skipping R={R}: too few nodes ({len(X)})")
            continue
        
        # Sanity check: ensure all targets are non-negative
        if any(y < 0 for y in Y1) or any(y < 0 for y in Y2):
            print(f"  WARNING: Found negative targets for R={R}")
        
        print(f"  Nodes in H_R: {len(X):,}")
        print(f"  Y1 stats: min={min(Y1)}, max={max(Y1)}, mean={np.mean(Y1):.2f}")
        print(f"  Y2 stats: min={min(Y2)}, max={max(Y2)}, mean={np.mean(Y2):.2f}")
        
        # Split into train/test (80/20)
        n_train = int(0.8 * len(X))
        indices = list(range(len(X)))
        random.shuffle(indices)
        
        train_indices = indices[:n_train]
        test_indices = indices[n_train:]
        
        X_train = [X[i] for i in train_indices]
        Y1_train = [Y1[i] for i in train_indices]
        Y2_train = [Y2[i] for i in train_indices]
        
        X_test = [X[i] for i in test_indices]
        Y1_test = [Y1[i] for i in test_indices]
        Y2_test = [Y2[i] for i in test_indices]
        
        print(f"  Train: {len(X_train):,}, Test: {len(X_test):,}")
        
        # Train and evaluate
        results = train_and_evaluate(X_train, Y1_train, Y2_train, 
                                    X_test, Y1_test, Y2_test, feature_names)
        
        # Store results
        result_row = {"R": R, "n_nodes": len(X), **results}
        all_results.append(result_row)
        
        # Print results
        print("\n  Results:")
        for model_name, metrics in results.items():
            if isinstance(metrics, dict) and "error" not in metrics:
                print(f"    {model_name}:")
                for metric_name, value in metrics.items():
                    if metric_name == "feature_importance":
                        continue  # Skip feature importance in this summary
                    if value is not None:
                        if isinstance(value, (int, float)):
                            print(f"      {metric_name}: {value:.4f}")
                        else:
                            print(f"      {metric_name}: {value}")
    
    # Summary table
    print("\n" + "=" * 80)
    print("SUMMARY TABLE")
    print("=" * 80)
    print(f"{'R':<6} {'N':<8} {'Y1_Lin_R2':<12} {'Y1_GB_R2':<12} {'Y2_Pois_MAE':<14} {'Y2_GB_MAE':<12}")
    print("-" * 80)
    
    for row in all_results:
        R = row["R"]
        n = row["n_nodes"]
        y1_lr_r2 = row.get("Y1_Linear", {}).get("R2", None)
        y1_gb_r2 = row.get("Y1_GBoost", {}).get("R2", None)
        y2_pois_mae = row.get("Y2_Poisson", {}).get("MAE", None)
        y2_gb_mae = row.get("Y2_GBoost", {}).get("MAE", None)
        
        y1_lr_str = f"{y1_lr_r2:.4f}" if y1_lr_r2 is not None else "N/A"
        y1_gb_str = f"{y1_gb_r2:.4f}" if y1_gb_r2 is not None else "N/A"
        y2_pois_str = f"{y2_pois_mae:.4f}" if y2_pois_mae is not None else "N/A"
        y2_gb_str = f"{y2_gb_mae:.4f}" if y2_gb_mae is not None else "N/A"
        
        print(f"{R:<6} {n:<8} {y1_lr_str:<12} {y1_gb_str:<12} {y2_pois_str:<14} {y2_gb_str:<12}")
    
    # Diagnostic: feature importance (if available)
    print("\n" + "=" * 80)
    print("DIAGNOSTICS")
    print("=" * 80)
    print(f"Initial graph: {fvs_stats['initial_nodes']:,} nodes, {fvs_stats['initial_edges']:,} edges")
    print(f"FVS size: {fvs_stats['removed_after_improvement']:,} ({100*fvs_stats['removed_after_improvement']/fvs_stats['initial_nodes']:.2f}%)")
    print(f"Final DAG: {G_dag.number_of_nodes():,} nodes, {G_dag.number_of_edges():,} edges")
    print(f"Max depth (r_max): {max(r_max_values)}")
    print(f"Max depth (r_min): {max(r_min_values)}")
    
    # Feature importance analysis (from last R value)
    if all_results:
        last_result = all_results[-1]
        print("\nFeature importance (from best model, R={}):".format(last_result["R"]))
        
        # Get feature importance from Y1_GBoost (usually best)
        if "Y1_GBoost" in last_result and "feature_importance" in last_result["Y1_GBoost"]:
            fi = last_result["Y1_GBoost"]["feature_importance"]
            sorted_fi = sorted(fi.items(), key=lambda x: x[1], reverse=True)
            print("  Y1 (Gradient Boosting):")
            for fn, imp in sorted_fi[:5]:  # Top 5
                print(f"    {fn}: {imp:.4f}")
        
        if "Y2_GBoost" in last_result and "feature_importance" in last_result["Y2_GBoost"]:
            fi = last_result["Y2_GBoost"]["feature_importance"]
            sorted_fi = sorted(fi.items(), key=lambda x: x[1], reverse=True)
            print("  Y2 (Gradient Boosting):")
            for fn, imp in sorted_fi[:5]:  # Top 5
                print(f"    {fn}: {imp:.4f}")
    
    # Save removed nodes
    removed_file = _SCRIPT_DIR / "fvs_removed_nodes.txt"
    with open(removed_file, "w", encoding="utf-8") as f:
        f.write(f"Feedback Vertex Set: {len(F)} nodes removed\n")
        f.write("=" * 80 + "\n\n")
        for node in sorted(F):
            f.write(f"{node}\n")
    print(f"\nRemoved nodes saved to: {removed_file}")
    
    print("\n" + "=" * 80)
    print("Pipeline complete!")
    print("=" * 80)


def git_commit_and_push():
    """Commit and push changes to git before running."""
    try:
        # Check if we're in a git repo
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=_SCRIPT_DIR,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print("Not in a git repository, skipping git operations")
            return
        
        # Check for changes
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=_SCRIPT_DIR,
            capture_output=True,
            text=True
        )
        
        if not result.stdout.strip():
            print("No changes to commit")
            return
        
        print("\nCommitting changes to git...")
        # Add all changes
        subprocess.run(
            ["git", "add", "-A"],
            cwd=_SCRIPT_DIR,
            check=True
        )
        
        # Commit with timestamp
        commit_msg = f"Update FVS prediction pipeline - {time.strftime('%Y-%m-%d %H:%M:%S')}"
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=_SCRIPT_DIR,
            check=True
        )
        
        print("Pushing to remote...")
        # Push to remote
        subprocess.run(
            ["git", "push"],
            cwd=_SCRIPT_DIR,
            check=True
        )
        
        print("Git operations completed successfully\n")
    except subprocess.CalledProcessError as e:
        print(f"Warning: Git operation failed: {e}")
        print("Continuing with pipeline execution...\n")
    except FileNotFoundError:
        print("Git not found, skipping git operations\n")
    except Exception as e:
        print(f"Warning: Unexpected error in git operations: {e}")
        print("Continuing with pipeline execution...\n")


if __name__ == "__main__":
    # Commit and push changes before running
    git_commit_and_push()
    main()
