"""DAG Network Analysis from corpus.jsonl - compute measures and visualize extreme nodes."""

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
from functools import lru_cache

# Set UTF-8 encoding for stdout on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Configuration
CORPUS_FILE = "corpus.jsonl"
MAX_ENTRIES = 10000
OUTPUT_PDF = "dag_network_analysis.pdf"
OUTPUT_PNG = "dag_network_analysis.png"

print("=" * 80)
print("Loading corpus data...")
print("=" * 80)
start_time = time.time()

# Build dependency graph incrementally while loading
print("\n" + "=" * 80)
print("Building dependency graph...")
print("=" * 80)

G = nx.DiGraph()
file_to_premises = {}  # Track premises per file
entries_processed = 0

# Build graph efficiently - process incrementally to save memory
with open(CORPUS_FILE, "r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        if i >= MAX_ENTRIES:
            break
        line = line.strip()
        if not line:
            continue

        entry = json.loads(line)
        file_path = entry.get("path")
        if not file_path:
            continue

        imports = entry.get("imports", [])
        premises = entry.get("premises", [])

        # Add node and premises
        G.add_node(file_path)
        file_to_premises[file_path] = premises

        # Add edges efficiently - only add valid imports
        valid_imports = [imp for imp in imports if imp and imp != file_path]  # Avoid self-loops
        if valid_imports:
            G.add_edges_from((file_path, imp) for imp in valid_imports)

        entries_processed += 1

graph_build_time = time.time() - start_time
print(f"Graph built from {entries_processed} entries in {graph_build_time:.2f}s:")
print(f"  Nodes (files): {G.number_of_nodes()}")
print(f"  Edges (imports): {G.number_of_edges()}")

# Pre-compute degrees once for efficiency
degree_start = time.time()
in_degrees = dict(G.in_degree())
out_degrees = dict(G.out_degree())
degree_time = time.time() - degree_start
print(f"  Degrees computed in {degree_time:.3f}s")

# Find root nodes and leaves efficiently
roots = [n for n, deg in in_degrees.items() if deg == 0]
leaves = [n for n, deg in out_degrees.items() if deg == 0]

print(f"  Root nodes (no imports): {len(roots)}")
print(f"  Leaf nodes (no dependents): {len(leaves)}")

# Find top nodes by degree
top_importers = sorted(out_degrees.items(), key=lambda x: x[1], reverse=True)[:10]
top_imported = sorted(in_degrees.items(), key=lambda x: x[1], reverse=True)[:10]

print(f"\nTop 10 files by outgoing edges (most imports):")
for path, count in top_importers:
    short_path = Path(path).name
    print(f"  {short_path}: {count} imports")

print(f"\nTop 10 files by incoming edges (most imported):")
for path, count in top_imported:
    short_path = Path(path).name
    print(f"  {short_path}: {count} dependents")

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

    # Basic graph properties - computed once
    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()
    density = n_edges / (n_nodes * (n_nodes - 1)) if n_nodes > 1 else 0  # Manual density for speed

    # DAG validation and components - batch compute
    print("  Computing basic properties and components...")
    try:
        is_dag = nx.is_directed_acyclic_graph(G)
        wcc = list(nx.weakly_connected_components(G))
        wcc_sizes = [len(comp) for comp in wcc]
    except:
        is_dag = False
        wcc = []
        wcc_sizes = []

    # Sources and sinks - use precomputed degrees
    sources = [n for n, deg in in_degrees.items() if deg == 0]
    sinks = [n for n, deg in out_degrees.items() if deg == 0]

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

    # Degree statistics - use numpy for efficiency
    print("  Computing degree statistics...")
    in_deg_values = np.array(list(in_degrees.values()))
    out_deg_values = np.array(list(out_degrees.values()))

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

    # Topological levels - use efficient algorithm
    print("  Computing topological levels...")
    measures['levels'] = {'node_levels': {}, 'max_level': 0, 'mean_level': 0, 'level_distribution': {}}

    if is_dag and n_nodes > 0:
        try:
            # More efficient level computation using BFS from sources
            node_levels = {}
            visited = set()
            queue = [(source, 0) for source in sources]  # (node, level)

            while queue:
                node, level = queue.pop(0)
                if node in visited:
                    continue
                visited.add(node)
                node_levels[node] = level

                # Add successors to queue with incremented level
                for successor in G.successors(node):
                    if successor not in visited:
                        queue.append((successor, level + 1))

            # Handle any remaining unvisited nodes (shouldn't happen in a DAG)
            for node in G.nodes():
                if node not in node_levels:
                    node_levels[node] = 0

            level_values = list(node_levels.values())
            measures['levels'] = {
                'node_levels': node_levels,
                'max_level': max(level_values) if level_values else 0,
                'mean_level': np.mean(level_values) if level_values else 0,
                'level_distribution': dict(Counter(level_values))
            }
        except Exception as e:
            print(f"  Warning: Could not compute topological levels: {e}")

    # Longest paths - efficient computation using BFS from sources
    print("  Computing longest paths...")
    measures['paths'] = {'node_max_depth': {}, 'max_depth': 0, 'mean_depth': 0}

    if is_dag and n_nodes > 0 and sources:
        try:
            # Efficient BFS from all sources to compute max depth for each node
            node_max_depth = {}
            visited = set()

            # Initialize queue with all sources at depth 0
            queue = [(source, 0) for source in sources]
            source_set = set(sources)

            while queue:
                node, depth = queue.pop(0)

                # Update max depth for this node
                if node not in node_max_depth or depth > node_max_depth[node]:
                    node_max_depth[node] = depth

                if node in visited:
                    continue
                visited.add(node)

                # Add successors with incremented depth
                for successor in G.successors(node):
                    if successor not in visited:
                        queue.append((successor, depth + 1))

            # Fill in any unvisited nodes (isolated nodes not reachable from sources)
            for node in G.nodes():
                if node not in node_max_depth:
                    node_max_depth[node] = 0

            depth_values = list(node_max_depth.values())
            measures['paths'] = {
                'node_max_depth': node_max_depth,
                'max_depth': max(depth_values) if depth_values else 0,
                'mean_depth': np.mean(depth_values) if depth_values else 0
            }
        except Exception as e:
            print(f"  Warning: Could not compute longest paths: {e}")

    print("  DAG measures computed efficiently.")
    return measures

def find_extreme_nodes(measures, G, in_degrees, out_degrees, top_k=5):
    """Find nodes with extreme values for each measure."""
    print("\n" + "=" * 80)
    print("Identifying extreme nodes...")
    print("=" * 80)
    
    extreme_nodes = {}
    
    # In-degree extremes
    sorted_in_deg = sorted(in_degrees.items(), key=lambda x: x[1], reverse=True)
    extreme_nodes['in_degree'] = {
        'high': [n for n, _ in sorted_in_deg[:top_k]],
        'low': [n for n, _ in sorted_in_deg[-top_k:] if in_degrees[n] == 0]  # Only sources
    }
    
    # Out-degree extremes
    sorted_out_deg = sorted(out_degrees.items(), key=lambda x: x[1], reverse=True)
    extreme_nodes['out_degree'] = {
        'high': [n for n, _ in sorted_out_deg[:top_k]],
        'low': [n for n, _ in sorted_out_deg[-top_k:] if out_degrees[n] == 0]  # Only sinks
    }
    
    # Level extremes
    if 'levels' in measures and measures['levels']['node_levels']:
        node_levels = measures['levels']['node_levels']
        sorted_levels = sorted(node_levels.items(), key=lambda x: x[1], reverse=True)
        extreme_nodes['level'] = {
            'high': [n for n, _ in sorted_levels[:top_k]],
            'low': [n for n, _ in sorted_levels[-top_k:]]
        }
    
    # Path depth extremes
    if 'paths' in measures and measures['paths']['node_max_depth']:
        node_max_depth = measures['paths']['node_max_depth']
        sorted_depth = sorted(node_max_depth.items(), key=lambda x: x[1], reverse=True)
        extreme_nodes['depth'] = {
            'high': [n for n, _ in sorted_depth[:top_k]],
            'low': [n for n, _ in sorted_depth[-top_k:]]
        }
    
    # Component extremes (largest component representatives)
    if 'basic' in measures:
        wcc = list(nx.weakly_connected_components(G))
        if wcc:
            largest_comp = max(wcc, key=len)
            smallest_comp = min(wcc, key=len)
            extreme_nodes['component'] = {
                'high': [list(largest_comp)[0]],  # Representative from largest
                'low': [list(smallest_comp)[0]] if len(smallest_comp) > 0 else []
            }
    
    print(f"  Found extreme nodes for {len(extreme_nodes)} measure types.")
    return extreme_nodes

def extract_ego_networks(G, extreme_nodes, measures, max_nodes=50, max_ego_networks=36):
    """Extract 2-hop ego networks for extreme nodes efficiently. Only constructs networks that will be visualized."""
    print("\n" + "=" * 80)
    print("Extracting ego networks (2-hop neighborhoods)...")
    print("=" * 80)

    ego_networks = []

    # Pre-compute all neighbors for efficiency
    print("  Pre-computing neighborhoods...")
    node_neighbors = {}
    for node in G.nodes():
        node_neighbors[node] = set(G.predecessors(node)) | set(G.successors(node))

    # Collect all extreme nodes with priority scores for selection
    candidate_nodes = []
    seen_nodes = set()

    for measure_type, extremes in extreme_nodes.items():
        for extreme_type, nodes in extremes.items():
            for node in nodes:
                if node not in seen_nodes and node in G:
                    # Calculate priority score based on potential ego network size
                    node_degree = len(node_neighbors.get(node, set()))

                    # Estimate 2-hop neighborhood size (rough approximation)
                    step1_nodes = node_neighbors.get(node, set())
                    step2_nodes = set()
                    for neighbor in step1_nodes:
                        step2_nodes.update(node_neighbors.get(neighbor, set()))
                    step2_nodes -= step1_nodes
                    step2_nodes.discard(node)

                    estimated_ego_size = 1 + len(step1_nodes) + min(len(step2_nodes), max_nodes)

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

    # Sort candidates by priority and select only top N that will be visualized
    candidate_nodes.sort(key=lambda x: x[3], reverse=True)
    selected_candidates = candidate_nodes[:max_ego_networks]

    print(f"  Found {len(candidate_nodes)} extreme nodes, processing top {len(selected_candidates)} for visualization...")

    # Process only the selected candidates
    for node, measure_type, extreme_type, _ in selected_candidates:
        try:
            # Get 1-hop neighbors (pre-computed)
            step1_nodes = node_neighbors.get(node, set())

            # Get 2-hop neighbors efficiently
            step2_nodes = set()
            for neighbor in step1_nodes:
                step2_nodes.update(node_neighbors.get(neighbor, set()))

            # Remove self-references and limit size
            step2_nodes.discard(node)
            step2_nodes -= step1_nodes  # Don't include 1-hop neighbors in 2-hop

            # Limit total nodes for performance
            all_ego_nodes = {node} | step1_nodes
            if len(step2_nodes) > max_nodes - len(all_ego_nodes):
                # Select most connected 2-hop neighbors
                step2_degrees = [(n, len(node_neighbors.get(n, set()))) for n in step2_nodes]
                step2_degrees.sort(key=lambda x: x[1], reverse=True)
                step2_nodes = {n for n, _ in step2_degrees[:max_nodes - len(all_ego_nodes)]}

            all_ego_nodes |= step2_nodes

            # Create subgraph efficiently - only if it has meaningful connections
            if len(all_ego_nodes) > 1:
                # Use edge_subgraph for better performance on large graphs
                relevant_edges = [(u, v) for u, v in G.edges() if u in all_ego_nodes and v in all_ego_nodes]
                ego = nx.DiGraph()
                ego.add_nodes_from(all_ego_nodes)
                ego.add_edges_from(relevant_edges)

                # Only keep if subgraph is connected and meaningful
                if ego.number_of_edges() > 0:
                    short_name = Path(node).name
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
            print(f"  Warning: Could not process ego network for {node}: {e}")
            continue

    print(f"  Extracted {len(ego_networks)} ego networks efficiently (only those for visualization).")
    return ego_networks

# Save original graph for analysis (before node removal)
G_original = G.copy()
in_degrees_original = in_degrees.copy()
out_degrees_original = out_degrees.copy()

# Compute measures on original graph
print("\nComputing measures...")
measures_start = time.time()
measures = compute_dag_measures(G_original, in_degrees_original, out_degrees_original)
measures_time = time.time() - measures_start
print(f"Measures computed in {measures_time:.2f}s")

# Find extreme nodes
extreme_nodes = find_extreme_nodes(measures, G_original, in_degrees_original, out_degrees_original, top_k=5)

# Extract ego networks (only for nodes that will be visualized)
print("\nExtracting ego networks...")
ego_start = time.time()
ego_networks = extract_ego_networks(G_original, extreme_nodes, measures, max_nodes=50, max_ego_networks=36)
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
    stats_text = f"""Graph Statistics
    
Nodes: {basic['nodes']:,}
Edges: {basic['edges']:,}
Density: {basic['density']:.6f}
Is DAG: {basic['is_dag']}
Components: {basic['num_components']}
Sources: {basic['num_sources']}
Sinks: {basic['num_sinks']}"""
    ax1.text(0.1, 0.5, stats_text, fontsize=10, family='monospace',
             verticalalignment='center', transform=ax1.transAxes)
    ax1.set_title('Basic Statistics', fontsize=12, fontweight='normal', pad=10)
    
    # Panel 2: In-Degree Distribution (log-log) - pre-compute for efficiency
    ax2 = fig.add_subplot(gs[0, 1])
    in_deg_values = list(in_degrees_original.values())
    if in_deg_values:
        # Use numpy for efficient counting
        unique_degrees, counts = np.unique(in_deg_values, return_counts=True)
        # For log-log, use degree+1 to handle zeros
        degrees_plot = unique_degrees + 1
        frequencies_plot = counts
        # Plot on log-log scale
        ax2.loglog(degrees_plot, frequencies_plot, 'o', color='black', markersize=3, alpha=0.7)
        ax2.set_xlabel('In-Degree+1 (log)', fontsize=9)
        ax2.set_ylabel('Frequency (log)', fontsize=9)
    ax2.set_title('In-Degree Distribution', fontsize=12, fontweight='normal', pad=10)
    ax2.tick_params(labelsize=8)

    # Panel 3: Out-Degree Distribution (log-linear) - pre-compute for efficiency
    ax3 = fig.add_subplot(gs[0, 2])
    out_deg_values = list(out_degrees_original.values())
    if out_deg_values:
        # Use numpy for efficient counting
        unique_degrees, counts = np.unique(out_deg_values, return_counts=True)
        # For log-linear, use degree+1 to handle zeros
        degrees_plot = unique_degrees + 1
        frequencies_plot = counts
        # Plot on log-linear scale
        ax3.semilogx(degrees_plot, frequencies_plot, 'o', color='black', markersize=3, alpha=0.7)
        ax3.set_xlabel('Out-Degree+1 (log)', fontsize=9)
        ax3.set_ylabel('Frequency', fontsize=9)
    ax3.set_title('Out-Degree Distribution', fontsize=12, fontweight='normal', pad=10)
    ax3.tick_params(labelsize=8)
    
    # Panel 4: Level Distribution
    ax4 = fig.add_subplot(gs[1, 0])
    if 'levels' in measures and measures['levels']['level_distribution']:
        level_dist = measures['levels']['level_distribution']
        levels = sorted(level_dist.keys())
        counts = [level_dist[l] for l in levels]
        ax4.bar(levels, counts, color='black', alpha=0.7, edgecolor='black', linewidth=0.5)
        ax4.set_xlabel('Topological Level', fontsize=9)
        ax4.set_ylabel('Number of Nodes', fontsize=9)
        ax4.set_title('Level Distribution', fontsize=12, fontweight='normal', pad=10)
    else:
        ax4.text(0.5, 0.5, 'No level data', ha='center', va='center', transform=ax4.transAxes)
        ax4.set_title('Level Distribution', fontsize=12, fontweight='normal', pad=10)
    ax4.tick_params(labelsize=8)
    
    # Panel 5: Component Size Distribution
    ax5 = fig.add_subplot(gs[1, 1])
    comp_sizes = basic['component_sizes']
    if comp_sizes:
        ax5.hist(comp_sizes, bins=min(50, len(set(comp_sizes))), 
                color='black', alpha=0.7, edgecolor='black', linewidth=0.5)
    ax5.set_xlabel('Component Size', fontsize=9)
    ax5.set_ylabel('Frequency', fontsize=9)
    ax5.set_title('Component Size Distribution', fontsize=12, fontweight='normal', pad=10)
    ax5.tick_params(labelsize=8)
    
    # Panel 6: Summary Table
    ax6 = fig.add_subplot(gs[1, 2])
    ax6.axis('off')
    deg_stats = measures['degrees']
    summary_text = f"""Degree Statistics

In-Degree:
  Min: {deg_stats['in_degree']['min']}
  Max: {deg_stats['in_degree']['max']}
  Mean: {deg_stats['in_degree']['mean']:.2f}
  Median: {deg_stats['in_degree']['median']:.1f}

Out-Degree:
  Min: {deg_stats['out_degree']['min']}
  Max: {deg_stats['out_degree']['max']}
  Mean: {deg_stats['out_degree']['mean']:.2f}
  Median: {deg_stats['out_degree']['median']:.1f}"""
    
    if 'levels' in measures:
        summary_text += f"\n\nMax Level: {measures['levels']['max_level']}"
        summary_text += f"\nMean Level: {measures['levels']['mean_level']:.2f}"
    
    if 'paths' in measures:
        summary_text += f"\n\nMax Depth: {measures['paths']['max_depth']}"
        summary_text += f"\nMean Depth: {measures['paths']['mean_depth']:.2f}"
    
    ax6.text(0.1, 0.5, summary_text, fontsize=9, family='monospace',
             verticalalignment='center', transform=ax6.transAxes)
    ax6.set_title('Summary Statistics', fontsize=12, fontweight='normal', pad=10)
    
    # ========================================================================
    # Bottom Section: Ego Network Grid
    # ========================================================================
    
    print(f"  Creating ego network visualizations ({len(ego_networks)} networks)...")

    # Determine grid size for ego networks
    n_ego = len(ego_networks)
    n_cols = 6
    n_rows = (n_ego + n_cols - 1) // n_cols
    
    for idx, ego_data in enumerate(ego_networks):
        row = 2 + (idx // n_cols)
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
        
        # Draw nodes
        node_colors_ego = []
        node_sizes_ego = []
        for node in ego.nodes():
            if node == center:
                node_colors_ego.append('#000000')  # Black for center
                node_sizes_ego.append(100)
            else:
                node_colors_ego.append('#666666')  # Gray for others
                node_sizes_ego.append(30)
        
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
                short = Path(n).name[:12]
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
print("DAG Network Analysis Complete!")
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
