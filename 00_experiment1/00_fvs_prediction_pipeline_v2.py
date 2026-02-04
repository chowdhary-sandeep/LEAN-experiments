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

# Set UTF-8 encoding for stdout on Windows
if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Configuration
_SCRIPT_DIR = Path(__file__).resolve().parent
CACHE_DIR = _SCRIPT_DIR / "cache"
CACHE_BUNDLE = CACHE_DIR / "bundle.pkl"

# Cache prefix for FVS pipeline files
FVS_CACHE_PREFIX = "fvs_pipeline_v2_"
FVS_CACHE_DAG = CACHE_DIR / f"{FVS_CACHE_PREFIX}dag.pkl"
FVS_CACHE_FVS = CACHE_DIR / f"{FVS_CACHE_PREFIX}fvs.pkl"
FVS_CACHE_STATS = CACHE_DIR / f"{FVS_CACHE_PREFIX}stats.pkl"
FVS_CACHE_DEPTHS = CACHE_DIR / f"{FVS_CACHE_PREFIX}depths.pkl"
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


def compute_features_r0(H_d: nx.DiGraph, v: str, depth: Dict[str, int]) -> Dict[str, float]:
    """
    Compute r=0 features (no future information).
    Features must be computable using only H_d plus information about v's parents.
    """
    if v not in H_d:
        return {}
    
    features = {}
    
    # Get parents in H_d
    parents = list(H_d.predecessors(v))
    features["parent_count"] = len(parents)
    
    if not parents:
        # No parents - set defaults
        features["parent_indeg_mean"] = 0.0
        features["parent_indeg_max"] = 0.0
        features["parent_outdeg_mean"] = 0.0
        features["parent_outdeg_max"] = 0.0
        features["parent_outdeg_sum"] = 0.0
        features["parent_depth_mean"] = 0.0
        features["parent_depth_max"] = 0.0
        features["parent_descendant_count_mean"] = 0.0
        features["parent_descendant_count_max"] = 0.0
        features["parent_diversity"] = 0.0
        features["depth"] = depth.get(v, 0)
        features["indeg"] = H_d.in_degree(v)
        return features
    
    # Parent statistics in H_d
    parent_indegs = [H_d.in_degree(p) for p in parents]
    parent_outdegs = [H_d.out_degree(p) for p in parents]
    parent_depths = [depth.get(p, 0) for p in parents]
    
    features["parent_indeg_mean"] = np.mean(parent_indegs)
    features["parent_indeg_max"] = np.max(parent_indegs)
    features["parent_outdeg_mean"] = np.mean(parent_outdegs)
    features["parent_outdeg_max"] = np.max(parent_outdegs)
    features["parent_outdeg_sum"] = np.sum(parent_outdegs)
    features["parent_depth_mean"] = np.mean(parent_depths)
    features["parent_depth_max"] = np.max(parent_depths)
    
    # Parent descendant counts within H_d (BFS forward from each parent)
    parent_desc_counts = []
    for p in parents:
        descendants = set()
        queue = deque([p])
        visited = {p}
        while queue:
            u = queue.popleft()
            for w in H_d.successors(u):
                if w not in visited and w != v:  # Don't count v itself
                    visited.add(w)
                    descendants.add(w)
                    queue.append(w)
        parent_desc_counts.append(len(descendants))
    
    features["parent_descendant_count_mean"] = np.mean(parent_desc_counts) if parent_desc_counts else 0.0
    features["parent_descendant_count_max"] = np.max(parent_desc_counts) if parent_desc_counts else 0.0
    
    # Parent diversity: pairwise ancestor-overlap among parents
    # Lower overlap = higher diversity
    if len(parents) > 1:
        overlaps = []
        for i, p1 in enumerate(parents):
            ancestors_p1 = set()
            queue = deque([p1])
            visited = {p1}
            while queue:
                u = queue.popleft()
                for w in H_d.predecessors(u):
                    if w not in visited:
                        visited.add(w)
                        ancestors_p1.add(w)
                        queue.append(w)
            
            for p2 in parents[i+1:]:
                ancestors_p2 = set()
                queue = deque([p2])
                visited = {p2}
                while queue:
                    u = queue.popleft()
                    for w in H_d.predecessors(u):
                        if w not in visited:
                            visited.add(w)
                            ancestors_p2.add(w)
                            queue.append(w)
                
                overlap = len(ancestors_p1 & ancestors_p2)
                total_ancestors = len(ancestors_p1 | ancestors_p2)
                if total_ancestors > 0:
                    overlaps.append(overlap / total_ancestors)
        
        features["parent_diversity"] = 1.0 - np.mean(overlaps) if overlaps else 1.0
    else:
        features["parent_diversity"] = 1.0
    
    # Node's own properties
    features["depth"] = depth.get(v, 0)
    features["indeg"] = H_d.in_degree(v)
    
    return features


def compute_features_r1(G_dag: nx.DiGraph, H_d: nx.DiGraph, v: str, depth: Dict[str, int], d: int) -> Dict[str, float]:
    """
    Compute r=1 features (can see immediate children).
    """
    features = compute_features_r0(H_d, v, depth)
    
    # Add immediate children information from full G_dag
    children = list(G_dag.successors(v))
    features["k1"] = len(children)  # Observed outdegree at r=1
    features["child_count_r1"] = len(children)
    
    return features


def compute_features_r2(G_dag: nx.DiGraph, H_d: nx.DiGraph, v: str, depth: Dict[str, int], d: int) -> Dict[str, float]:
    """
    Compute r=2 features (can see children and grandchildren).
    """
    features = compute_features_r1(G_dag, H_d, v, depth, d)
    
    # Add grandchildren information
    children = list(G_dag.successors(v))
    grandchildren = set()
    for child in children:
        for grandchild in G_dag.successors(child):
            grandchildren.add(grandchild)
    
    features["grandchild_count"] = len(grandchildren)
    features["k2"] = len(grandchildren)
    
    return features


def create_dataset(G_dag: nx.DiGraph, H_d: nx.DiGraph, V_d: Set[str], depth: Dict[str, int], 
                   targets: Dict[str, Dict[str, int]], d: int, r: int) -> Tuple[List[Dict], List[int], List[int], List[float], List[float]]:
    """
    Create dataset for depth d and radius r.
    
    Returns:
        X: List of feature dictionaries
        Y1: List of Y1 targets
        Y2: List of Y2 targets
        Z1: List of Z1 targets (log)
        Z2: List of Z2 targets (log)
    """
    X = []
    Y1 = []
    Y2 = []
    Z1 = []
    Z2 = []
    
    for v in V_d:
        if r == 0:
            features = compute_features_r0(H_d, v, depth)
        elif r == 1:
            features = compute_features_r1(G_dag, H_d, v, depth, d)
        elif r == 2:
            features = compute_features_r2(G_dag, H_d, v, depth, d)
        else:
            raise ValueError(f"Invalid radius r={r}")
        
        if features:  # Only include if features computed successfully
            X.append(features)
            Y1.append(targets[v]["Y1"])
            Y2.append(targets[v]["Y2"])
            Z1.append(targets[v]["Z1"])
            Z2.append(targets[v]["Z2"])
    
    return X, Y1, Y2, Z1, Z2


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
    
    # Y1 > 0 classification
    Y1_binary_train = (np.array(Y1_train) > 0).astype(int)
    Y1_binary_test = (np.array(Y1_test) > 0).astype(int)
    
    lr_y1_clf = LogisticRegression(max_iter=1000, random_state=42)
    lr_y1_clf.fit(X_train_arr, Y1_binary_train)
    Y1_pred_proba_lr = lr_y1_clf.predict_proba(X_test_arr)[:, 1]
    results["Y1_Linear_Class"] = evaluate_classification(Y1_binary_test, Y1_pred_proba_lr)
    
    gb_y1_clf = GradientBoostingClassifier(n_estimators=100, max_depth=5, random_state=42)
    gb_y1_clf.fit(X_train_arr, Y1_binary_train)
    Y1_pred_proba_gb = gb_y1_clf.predict_proba(X_test_arr)[:, 1]
    results["Y1_GBoost_Class"] = evaluate_classification(Y1_binary_test, Y1_pred_proba_gb)
    
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
        
        # NDCG@K
        Y1_test_pos = np.array(Y1_test)[Y1_positive_test]
        Y1_pred_full = np.zeros(len(Y1_test))
        Y1_pred_full[Y1_positive_test] = np.expm1(Z1_pred_gb)
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
    baselines["Zero"] = {
        "Y1_MAE": np.mean(Y1_test),
        "Y2_MAE": np.mean(Y2_test),
        "Y1_R2": 0.0,
        "Y2_R2": 0.0,
    }
    
    # Parent-mean baseline (if we have parent features)
    if "parent_outdeg_mean" in feature_names and "parent_descendant_count_mean" in feature_names:
        X_train_arr = features_to_array(X_train, feature_names)
        X_test_arr = features_to_array(X_test, feature_names)
        
        # Simple linear model using only parent means
        parent_outdeg_idx = feature_names.index("parent_outdeg_mean")
        parent_desc_idx = feature_names.index("parent_descendant_count_mean")
        
        X_simple_train = X_train_arr[:, [parent_outdeg_idx, parent_desc_idx]]
        X_simple_test = X_test_arr[:, [parent_outdeg_idx, parent_desc_idx]]
        
        # Y1 baseline
        try:
            lr_y1_base = LinearRegression()
            lr_y1_base.fit(X_simple_train, np.log1p(Y1_train))
            Y1_pred_base = np.expm1(lr_y1_base.predict(X_simple_test))
            baselines["Parent_Mean"] = {
                "Y1_MAE": mean_absolute_error(Y1_test, Y1_pred_base) if HAS_SKLEARN else np.mean(np.abs(np.array(Y1_test) - Y1_pred_base)),
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
            lr_depth = LinearRegression()
            lr_depth.fit(X_depth_train, np.log1p(Y1_train))
            Y1_pred_depth = np.expm1(lr_depth.predict(X_depth_test))
            baselines["Depth_Only"] = {
                "Y1_MAE": mean_absolute_error(Y1_test, Y1_pred_depth) if HAS_SKLEARN else np.mean(np.abs(np.array(Y1_test) - Y1_pred_depth)),
                "Y1_R2": r2_score(Y1_test, Y1_pred_depth) if HAS_SKLEARN else None,
            }
        except:
            pass
    
    return baselines


def main():
    """Main pipeline execution."""
    print("=" * 80)
    print("FVS-based DAG Cleaning and Prediction Pipeline v2")
    print("=" * 80)
    
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
    
    # Choose depth values
    max_depth_val = max(depth_values)
    d_values = [5, 10, 20, 30]
    d_values = [d for d in d_values if d <= max_depth_val]
    if max_depth_val > 30:
        d_values.append(min(40, max_depth_val))
    
    print(f"\nEvaluating with depth values: {d_values}")
    print(f"Radius values: r in {{0, 1, 2}}")
    
    # Feature names for r=0
    feature_names_r0 = [
        "parent_count", "parent_indeg_mean", "parent_indeg_max",
        "parent_outdeg_mean", "parent_outdeg_max", "parent_outdeg_sum",
        "parent_depth_mean", "parent_depth_max",
        "parent_descendant_count_mean", "parent_descendant_count_max",
        "parent_diversity", "depth", "indeg"
    ]
    
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
                X, Y1, Y2, Z1, Z2 = create_dataset(G_dag, H_d, V_d, depth, targets, d, r)
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
            
            # Get feature names based on r
            if r == 0:
                feature_names = feature_names_r0
            elif r == 1:
                feature_names = feature_names_r0 + ["k1", "child_count_r1"]
            elif r == 2:
                feature_names = feature_names_r0 + ["k1", "child_count_r1", "grandchild_count", "k2"]
            
            # Compute baselines
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
    print(f"{'d':<6} {'N':<8} {'Zero_Y1':<12} {'Zero_Y2':<12} {'Model_Y1_ρ':<14} {'Model_Y2_PR':<14}")
    print("-" * 80)
    
    for row in all_results:
        if row["r"] == 0:
            d = row["d"]
            n = row["n_nodes"]
            zero_y1 = row["baselines"]["Zero"]["Y1_MAE"]
            zero_y2 = row["baselines"]["Zero"]["Y2_MAE"]
            
            y1_spearman = row.get("Y1_GBoost_Reg", {}).get("Spearman_rho", None)
            y2_pr_auc = row.get("Y2_GBoost_Class", {}).get("PR_AUC", None)
            
            y1_str = f"{y1_spearman:.4f}" if y1_spearman else "N/A"
            y2_str = f"{y2_pr_auc:.4f}" if y2_pr_auc else "N/A"
            
            print(f"{d:<6} {n:<8} {zero_y1:<12.2f} {zero_y2:<12.2f} {y1_str:<14} {y2_str:<14}")
    
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
    
    print("\n" + "=" * 80)
    print("Pipeline complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
