import json
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from collections import Counter
import matplotlib.patches as mpatches

# Load the graph JSON
JSON_FILE = "traced_files_graph.json"
TRIPARTITE_JSONL = "tripartite_edges_ast_idents_algebra_with_excerpt.jsonl"
OUTPUT_PNG = "traced_files_graph_stats.png"
OUTPUT_PNG_TRIPARTITE = "tripartite_edges_stats.png"

print("="*60)
print("STEP 1/6: Loading graph data...")
print("="*60)
with open(JSON_FILE, "r", encoding="utf-8") as f:
    graph_json = json.load(f)

nodes = graph_json['nodes']
edges = graph_json['edges']
print(f"[OK] Loaded {len(nodes)} nodes and {len(edges)} edges\n")

# Build NetworkX graph
print("="*60)
print("STEP 2/6: Building NetworkX graph...")
print("="*60)
G = nx.DiGraph()

# Add nodes
print("  Adding nodes...")
for i, node in enumerate(nodes):
    G.add_node(node['id'])
    if (i + 1) % 1000 == 0:
        print(f"    Progress: {i+1}/{len(nodes)} nodes added")

# Add edges
print("  Adding edges...")
for i, edge in enumerate(edges):
    G.add_edge(edge['source'], edge['target'])
    if (i + 1) % 1000 == 0:
        print(f"    Progress: {i+1}/{len(edges)} edges added")

print(f"[OK] Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges\n")

# Calculate network statistics
print("="*60)
print("STEP 3/6: Computing network statistics...")
print("="*60)

# Degree statistics
in_degrees = dict(G.in_degree())
out_degrees = dict(G.out_degree())
total_degrees = {n: in_degrees[n] + out_degrees[n] for n in G.nodes()}

in_degree_values = list(in_degrees.values())
out_degree_values = list(out_degrees.values())
total_degree_values = list(total_degrees.values())

# Find top nodes
top_in_degree = sorted(in_degrees.items(), key=lambda x: x[1], reverse=True)[:10]
top_out_degree = sorted(out_degrees.items(), key=lambda x: x[1], reverse=True)[:10]
top_total_degree = sorted(total_degrees.items(), key=lambda x: x[1], reverse=True)[:10]

# Network metrics
print("  Computing basic metrics...")
num_nodes = G.number_of_nodes()
num_edges = G.number_of_edges()
density = nx.density(G)
avg_in_degree = np.mean(in_degree_values) if in_degree_values else 0
avg_out_degree = np.mean(out_degree_values) if out_degree_values else 0

# Check if graph is weakly connected
print("  Checking connectivity...")
if nx.is_weakly_connected(G):
    print("    Graph is weakly connected, computing path statistics...")
    avg_path_length = nx.average_shortest_path_length(G.to_undirected())
    diameter = nx.diameter(G.to_undirected())
else:
    print("    Graph is disconnected, using largest component...")
    # For disconnected graphs, compute for largest component
    largest_cc = max(nx.weakly_connected_components(G), key=len)
    G_largest = G.subgraph(largest_cc).to_undirected()
    avg_path_length = nx.average_shortest_path_length(G_largest)
    diameter = nx.diameter(G_largest)
print("[OK] Network statistics computed\n")

# Create multipanel figure
print("="*60)
print("STEP 4/6: Creating visualization layout...")
print("="*60)
fig = plt.figure(figsize=(20, 14))
gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
print("[OK] Layout created\n")

# Color scheme
colors = {
    'primary': '#2E86AB',
    'secondary': '#A23B72',
    'accent': '#F18F01',
    'success': '#C73E1D',
    'bg': '#F5F5F5'
}

# Panel 1: In-degree distribution (log scale)
print("="*60)
print("STEP 5/6: Generating plots...")
print("="*60)
print("  Creating panel 1/9: In-degree distribution...")
ax1 = fig.add_subplot(gs[0, 0])
degree_counts = Counter(in_degree_values)
degrees = sorted(degree_counts.keys())
counts = [degree_counts[d] for d in degrees]
ax1.loglog(degrees, counts, 'o', color=colors['primary'], markersize=6, alpha=0.7)
ax1.set_xlabel('In-Degree (log)', fontsize=10, fontweight='bold')
ax1.set_ylabel('Frequency (log)', fontsize=10, fontweight='bold')
ax1.set_title('In-Degree Distribution', fontsize=12, fontweight='bold', pad=10)
ax1.grid(True, alpha=0.3, linestyle='--')
ax1.set_facecolor(colors['bg'])

print("  Creating panel 2/9: Out-degree distribution...")
ax2 = fig.add_subplot(gs[0, 1])
degree_counts = Counter(out_degree_values)
degrees = sorted(degree_counts.keys())
counts = [degree_counts[d] for d in degrees]
ax2.loglog(degrees, counts, 'o', color=colors['secondary'], markersize=6, alpha=0.7)
ax2.set_xlabel('Out-Degree (log)', fontsize=10, fontweight='bold')
ax2.set_ylabel('Frequency (log)', fontsize=10, fontweight='bold')
ax2.set_title('Out-Degree Distribution', fontsize=12, fontweight='bold', pad=10)
ax2.grid(True, alpha=0.3, linestyle='--')
ax2.set_facecolor(colors['bg'])

print("  Creating panel 3/9: Total degree distribution...")
ax3 = fig.add_subplot(gs[0, 2])
degree_counts = Counter(total_degree_values)
degrees = sorted(degree_counts.keys())
counts = [degree_counts[d] for d in degrees]
ax3.loglog(degrees, counts, 'o', color=colors['accent'], markersize=6, alpha=0.7)
ax3.set_xlabel('Total Degree (log)', fontsize=10, fontweight='bold')
ax3.set_ylabel('Frequency (log)', fontsize=10, fontweight='bold')
ax3.set_title('Total Degree Distribution', fontsize=12, fontweight='bold', pad=10)
ax3.grid(True, alpha=0.3, linestyle='--')
ax3.set_facecolor(colors['bg'])

print("  Creating panel 4/9: Top nodes by in-degree...")
ax4 = fig.add_subplot(gs[1, 0])
top_in_names = [Path(n[0]).name[:25] + "..." if len(Path(n[0]).name) > 25 else Path(n[0]).name 
                for n in top_in_degree]
top_in_values = [n[1] for n in top_in_degree]
y_pos = np.arange(len(top_in_names))
ax4.barh(y_pos, top_in_values, color=colors['primary'], alpha=0.8)
ax4.set_yticks(y_pos)
ax4.set_yticklabels(top_in_names, fontsize=8)
ax4.set_xlabel('In-Degree', fontsize=10, fontweight='bold')
ax4.set_title('Top 10: Most Dependencies', fontsize=12, fontweight='bold', pad=10)
ax4.invert_yaxis()
ax4.grid(True, alpha=0.3, axis='x', linestyle='--')
ax4.set_facecolor(colors['bg'])

print("  Creating panel 5/9: Top nodes by out-degree...")
ax5 = fig.add_subplot(gs[1, 1])
top_out_names = [Path(n[0]).name[:25] + "..." if len(Path(n[0]).name) > 25 else Path(n[0]).name 
                 for n in top_out_degree]
top_out_values = [n[1] for n in top_out_degree]
y_pos = np.arange(len(top_out_names))
ax5.barh(y_pos, top_out_values, color=colors['secondary'], alpha=0.8)
ax5.set_yticks(y_pos)
ax5.set_yticklabels(top_out_names, fontsize=8)
ax5.set_xlabel('Out-Degree', fontsize=10, fontweight='bold')
ax5.set_title('Top 10: Most Dependents', fontsize=12, fontweight='bold', pad=10)
ax5.invert_yaxis()
ax5.grid(True, alpha=0.3, axis='x', linestyle='--')
ax5.set_facecolor(colors['bg'])

print("  Creating panel 6/9: In vs Out degree scatter...")
ax6 = fig.add_subplot(gs[1, 2])
ax6.scatter(in_degree_values, out_degree_values, alpha=0.4, s=20, 
           color=colors['accent'], edgecolors='none')
ax6.set_xlabel('In-Degree', fontsize=10, fontweight='bold')
ax6.set_ylabel('Out-Degree', fontsize=10, fontweight='bold')
ax6.set_title('In vs Out Degree', fontsize=12, fontweight='bold', pad=10)
ax6.set_xscale('log')
ax6.set_yscale('log')
ax6.grid(True, alpha=0.3, linestyle='--')
ax6.set_facecolor(colors['bg'])

print("  Creating panel 7/9: Network statistics text...")
ax7 = fig.add_subplot(gs[2, 0])
ax7.axis('off')
stats_text = f"""
NETWORK STATISTICS

Basic Metrics:
  • Nodes: {num_nodes:,}
  • Edges: {num_edges:,}
  • Density: {density:.6f}
  
Degree Statistics:
  • Avg In-Degree: {avg_in_degree:.2f}
  • Avg Out-Degree: {avg_out_degree:.2f}
  • Max In-Degree: {max(in_degree_values) if in_degree_values else 0}
  • Max Out-Degree: {max(out_degree_values) if out_degree_values else 0}
  
Path Statistics:
  • Avg Path Length: {avg_path_length:.2f}
  • Diameter: {diameter}
  
Connectivity:
  • Weakly Connected: {nx.is_weakly_connected(G)}
  • Components: {nx.number_weakly_connected_components(G)}
"""
ax7.text(0.1, 0.5, stats_text, fontsize=11, family='monospace',
         verticalalignment='center', bbox=dict(boxstyle='round', 
         facecolor=colors['bg'], alpha=0.8, edgecolor='gray', linewidth=1))

# Panel 8: Degree histogram (linear scale, binned)
ax8 = fig.add_subplot(gs[2, 1])
bins = np.logspace(0, np.log10(max(total_degree_values) + 1), 10) if total_degree_values else [1, 10]
ax8.hist(total_degree_values, bins=30, color=colors['accent'], alpha=0.7, edgecolor='black', linewidth=0.5)
ax8.set_xlabel('Total Degree', fontsize=10, fontweight='bold')
ax8.set_ylabel('Frequency', fontsize=10, fontweight='bold')
ax8.set_title('Total Degree Histogram', fontsize=12, fontweight='bold', pad=10)
ax8.set_yscale('log')
ax8.grid(True, alpha=0.3, axis='y', linestyle='--')
ax8.set_facecolor(colors['bg'])

print("  Creating panel 9/9: Top nodes by total degree...")
ax9 = fig.add_subplot(gs[2, 2])
print("[OK] All panels created\n")
top_total_names = [Path(n[0]).name[:20] + "..." if len(Path(n[0]).name) > 20 else Path(n[0]).name 
                   for n in top_total_degree]
top_total_values = [n[1] for n in top_total_degree]
y_pos = np.arange(len(top_total_names))
ax9.barh(y_pos, top_total_values, color=colors['success'], alpha=0.8)
ax9.set_yticks(y_pos)
ax9.set_yticklabels(top_total_names, fontsize=8)
ax9.set_xlabel('Total Degree', fontsize=10, fontweight='bold')
ax9.set_title('Top 10: Most Connected', fontsize=12, fontweight='bold', pad=10)
ax9.invert_yaxis()
ax9.grid(True, alpha=0.3, axis='x', linestyle='--')
ax9.set_facecolor(colors['bg'])

# Main title
fig.suptitle('File Dependency Graph - Network Analysis', 
             fontsize=18, fontweight='bold', y=0.98)

# Save figure
print("="*60)
print("STEP 6/6: Saving figure...")
print("="*60)
print(f"  Saving to {OUTPUT_PNG}...")
plt.savefig(OUTPUT_PNG, dpi=200, bbox_inches='tight', facecolor='white', edgecolor='none')
plt.close()
print(f"[OK] Statistics visualization saved as {OUTPUT_PNG}\n")
print(f"\n{'='*60}")
print(f"Summary Statistics:")
print(f"  Nodes: {num_nodes:,}")
print(f"  Edges: {num_edges:,}")
print(f"  Density: {density:.6f}")
print(f"  Avg In-Degree: {avg_in_degree:.2f}")
print(f"  Avg Out-Degree: {avg_out_degree:.2f}")
print(f"  Max In-Degree: {max(in_degree_values) if in_degree_values else 0}")
print(f"  Max Out-Degree: {max(out_degree_values) if out_degree_values else 0}")
print(f"{'='*60}")

# ========== Load and analyze tripartite edges data ==========
print("\n" + "="*60)
print("LOADING TRIPARTITE EDGES DATA...")
print("="*60)

tripartite_edges = []
if Path(TRIPARTITE_JSONL).exists():
    print(f"Loading {TRIPARTITE_JSONL}...")
    with open(TRIPARTITE_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                tripartite_edges.append(json.loads(line))
    print(f"[OK] Loaded {len(tripartite_edges)} tripartite edges\n")
else:
    print(f"[WARNING] {TRIPARTITE_JSONL} not found. Skipping tripartite analysis.")
    tripartite_edges = None

if tripartite_edges:
    # Analyze tripartite edges
    print("="*60)
    print("ANALYZING TRIPARTITE EDGES...")
    print("="*60)
    
    # Extract statistics
    theorems = [e['theorem'] for e in tripartite_edges]
    tactics = [e['tactic'] for e in tripartite_edges]
    files = [e['file'] for e in tripartite_edges]
    
    # Premises statistics
    all_premises = []
    premises_per_edge = []
    for e in tripartite_edges:
        prems = e.get('premises_ast', [])
        premises_per_edge.append(len(prems))
        all_premises.extend(prems)
    
    # Unique counts
    unique_theorems = len(set(theorems))
    unique_tactics = len(set(tactics))
    unique_files = len(set(files))
    unique_premises = len(set((p.get('full_name', ''), p.get('def_path', '')) for p in all_premises))
    
    # Premise statistics
    premise_full_names = [p.get('full_name', '') for p in all_premises if p.get('full_name')]
    premise_paths = [p.get('def_path', '') for p in all_premises if p.get('def_path')]
    premise_excerpts = [p.get('def_excerpt', '') for p in all_premises if p.get('def_excerpt')]
    
    # Top items
    top_theorems = Counter(theorems).most_common(10)
    top_tactics = Counter(tactics).most_common(10)
    top_premises = Counter(premise_full_names).most_common(10)
    top_files = Counter(files).most_common(10)
    
    # Tactic length distribution
    tactic_lengths = [len(t) for t in tactics]
    
    # State statistics
    states_before = [e.get('state_before', '') for e in tripartite_edges]
    states_after = [e.get('state_after', '') for e in tripartite_edges]
    state_before_lengths = [len(s) for s in states_before if s]
    state_after_lengths = [len(s) for s in states_after if s]
    
    print(f"[OK] Analysis complete\n")
    
    # Create second figure for tripartite edges
    print("="*60)
    print("CREATING TRIPARTITE EDGES VISUALIZATION...")
    print("="*60)
    fig2 = plt.figure(figsize=(20, 14))
    gs2 = fig2.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
    
    # Panel 1: Premises per edge distribution
    print("  Creating panel 1/9: Premises per edge distribution...")
    ax1 = fig2.add_subplot(gs2[0, 0])
    degree_counts = Counter(premises_per_edge)
    degrees = sorted(degree_counts.keys())
    counts = [degree_counts[d] for d in degrees]
    ax1.loglog(degrees, counts, 'o', color=colors['primary'], markersize=6, alpha=0.7)
    ax1.set_xlabel('Premises per Edge (log)', fontsize=10, fontweight='bold')
    ax1.set_ylabel('Frequency (log)', fontsize=10, fontweight='bold')
    ax1.set_title('Premises per Edge Distribution', fontsize=12, fontweight='bold', pad=10)
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.set_facecolor(colors['bg'])
    
    # Panel 2: Tactic length distribution
    print("  Creating panel 2/9: Tactic length distribution...")
    ax2 = fig2.add_subplot(gs2[0, 1])
    ax2.hist(tactic_lengths, bins=50, color=colors['secondary'], alpha=0.7, edgecolor='black', linewidth=0.5)
    ax2.set_xlabel('Tactic Length (chars)', fontsize=10, fontweight='bold')
    ax2.set_ylabel('Frequency', fontsize=10, fontweight='bold')
    ax2.set_title('Tactic Length Distribution', fontsize=12, fontweight='bold', pad=10)
    ax2.set_yscale('log')
    ax2.grid(True, alpha=0.3, axis='y', linestyle='--')
    ax2.set_facecolor(colors['bg'])
    
    # Panel 3: Top 10 tactics
    print("  Creating panel 3/9: Top tactics...")
    ax3 = fig2.add_subplot(gs2[0, 2])
    top_tac_names = [t[0][:30] + "..." if len(t[0]) > 30 else t[0] for t in top_tactics]
    top_tac_values = [t[1] for t in top_tactics]
    y_pos = np.arange(len(top_tac_names))
    ax3.barh(y_pos, top_tac_values, color=colors['accent'], alpha=0.8)
    ax3.set_yticks(y_pos)
    ax3.set_yticklabels(top_tac_names, fontsize=8)
    ax3.set_xlabel('Frequency', fontsize=10, fontweight='bold')
    ax3.set_title('Top 10 Tactics', fontsize=12, fontweight='bold', pad=10)
    ax3.invert_yaxis()
    ax3.grid(True, alpha=0.3, axis='x', linestyle='--')
    ax3.set_facecolor(colors['bg'])
    
    # Panel 4: Top 10 theorems
    print("  Creating panel 4/9: Top theorems...")
    ax4 = fig2.add_subplot(gs2[1, 0])
    top_thm_names = [t[0][:25] + "..." if len(t[0]) > 25 else t[0] for t in top_theorems]
    top_thm_values = [t[1] for t in top_theorems]
    y_pos = np.arange(len(top_thm_names))
    ax4.barh(y_pos, top_thm_values, color=colors['primary'], alpha=0.8)
    ax4.set_yticks(y_pos)
    ax4.set_yticklabels(top_thm_names, fontsize=8)
    ax4.set_xlabel('Edges', fontsize=10, fontweight='bold')
    ax4.set_title('Top 10 Theorems (by edges)', fontsize=12, fontweight='bold', pad=10)
    ax4.invert_yaxis()
    ax4.grid(True, alpha=0.3, axis='x', linestyle='--')
    ax4.set_facecolor(colors['bg'])
    
    # Panel 5: Top 10 premises
    print("  Creating panel 5/9: Top premises...")
    ax5 = fig2.add_subplot(gs2[1, 1])
    top_prem_names = [p[0][:25] + "..." if len(p[0]) > 25 else p[0] for p in top_premises]
    top_prem_values = [p[1] for p in top_premises]
    y_pos = np.arange(len(top_prem_names))
    ax5.barh(y_pos, top_prem_values, color=colors['secondary'], alpha=0.8)
    ax5.set_yticks(y_pos)
    ax5.set_yticklabels(top_prem_names, fontsize=8)
    ax5.set_xlabel('Frequency', fontsize=10, fontweight='bold')
    ax5.set_title('Top 10 Premises', fontsize=12, fontweight='bold', pad=10)
    ax5.invert_yaxis()
    ax5.grid(True, alpha=0.3, axis='x', linestyle='--')
    ax5.set_facecolor(colors['bg'])
    
    # Panel 6: Top 10 files
    print("  Creating panel 6/9: Top files...")
    ax6 = fig2.add_subplot(gs2[1, 2])
    top_file_names = [Path(f[0]).name[:20] + "..." if len(Path(f[0]).name) > 20 else Path(f[0]).name 
                      for f in top_files]
    top_file_values = [f[1] for f in top_files]
    y_pos = np.arange(len(top_file_names))
    ax6.barh(y_pos, top_file_values, color=colors['accent'], alpha=0.8)
    ax6.set_yticks(y_pos)
    ax6.set_yticklabels(top_file_names, fontsize=8)
    ax6.set_xlabel('Edges', fontsize=10, fontweight='bold')
    ax6.set_title('Top 10 Files (by edges)', fontsize=12, fontweight='bold', pad=10)
    ax6.invert_yaxis()
    ax6.grid(True, alpha=0.3, axis='x', linestyle='--')
    ax6.set_facecolor(colors['bg'])
    
    # Panel 7: Statistics text
    print("  Creating panel 7/9: Statistics text...")
    ax7 = fig2.add_subplot(gs2[2, 0])
    ax7.axis('off')
    stats_text = f"""
TRIPARTITE EDGES STATISTICS

Basic Metrics:
  • Total Edges: {len(tripartite_edges):,}
  • Unique Theorems: {unique_theorems:,}
  • Unique Tactics: {unique_tactics:,}
  • Unique Files: {unique_files:,}
  • Unique Premises: {unique_premises:,}
  
Premises:
  • Total Premises: {len(all_premises):,}
  • Avg Premises/Edge: {np.mean(premises_per_edge):.2f}
  • Max Premises/Edge: {max(premises_per_edge) if premises_per_edge else 0}
  • Edges with Excerpts: {len([p for p in all_premises if p.get('def_excerpt')]):,}
  
Tactics:
  • Avg Tactic Length: {np.mean(tactic_lengths):.2f} chars
  • Max Tactic Length: {max(tactic_lengths) if tactic_lengths else 0} chars
  
States:
  • Avg State Before: {np.mean(state_before_lengths):.1f} chars
  • Avg State After: {np.mean(state_after_lengths):.1f} chars
"""
    ax7.text(0.1, 0.5, stats_text, fontsize=10, family='monospace',
             verticalalignment='center', bbox=dict(boxstyle='round', 
             facecolor=colors['bg'], alpha=0.8, edgecolor='gray', linewidth=1))
    
    # Panel 8: Premises per edge histogram
    print("  Creating panel 8/9: Premises per edge histogram...")
    ax8 = fig2.add_subplot(gs2[2, 1])
    ax8.hist(premises_per_edge, bins=30, color=colors['accent'], alpha=0.7, edgecolor='black', linewidth=0.5)
    ax8.set_xlabel('Premises per Edge', fontsize=10, fontweight='bold')
    ax8.set_ylabel('Frequency', fontsize=10, fontweight='bold')
    ax8.set_title('Premises per Edge Histogram', fontsize=12, fontweight='bold', pad=10)
    ax8.set_yscale('log')
    ax8.grid(True, alpha=0.3, axis='y', linestyle='--')
    ax8.set_facecolor(colors['bg'])
    
    # Panel 9: State length comparison
    print("  Creating panel 9/9: State length comparison...")
    ax9 = fig2.add_subplot(gs2[2, 2])
    if state_before_lengths and state_after_lengths:
        ax9.scatter(state_before_lengths, state_after_lengths, alpha=0.3, s=10, 
                   color=colors['success'], edgecolors='none')
        ax9.set_xlabel('State Before Length (chars)', fontsize=10, fontweight='bold')
        ax9.set_ylabel('State After Length (chars)', fontsize=10, fontweight='bold')
        ax9.set_title('State Length Comparison', fontsize=12, fontweight='bold', pad=10)
        ax9.set_xscale('log')
        ax9.set_yscale('log')
        ax9.grid(True, alpha=0.3, linestyle='--')
    else:
        ax9.text(0.5, 0.5, 'No state data', ha='center', va='center', fontsize=12)
        ax9.set_title('State Length Comparison', fontsize=12, fontweight='bold', pad=10)
    ax9.set_facecolor(colors['bg'])
    
    print("[OK] All panels created\n")
    
    # Main title
    fig2.suptitle('Tripartite Edges - Network Analysis', 
                  fontsize=18, fontweight='bold', y=0.98)
    
    # Save figure
    print("="*60)
    print("SAVING TRIPARTITE EDGES VISUALIZATION...")
    print("="*60)
    print(f"  Saving to {OUTPUT_PNG_TRIPARTITE}...")
    plt.savefig(OUTPUT_PNG_TRIPARTITE, dpi=200, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()
    print(f"[OK] Tripartite edges visualization saved as {OUTPUT_PNG_TRIPARTITE}\n")
    
    print(f"{'='*60}")
    print(f"Tripartite Edges Summary:")
    print(f"  Total Edges: {len(tripartite_edges):,}")
    print(f"  Unique Theorems: {unique_theorems:,}")
    print(f"  Unique Tactics: {unique_tactics:,}")
    print(f"  Unique Files: {unique_files:,}")
    print(f"  Unique Premises: {unique_premises:,}")
    print(f"  Avg Premises/Edge: {np.mean(premises_per_edge):.2f}")
    print(f"{'='*60}")
