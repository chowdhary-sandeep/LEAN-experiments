"""
Create cinematic MP4 animation of agent traversing theorem network via DFS.
High aesthetics: curved edges that draw from tail to tip, adjacent possible visualization.
"""

import pickle
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Circle
from matplotlib.path import Path
import matplotlib.patches as mpatches
from collections import deque
import numpy as np
import imageio.v2 as imageio
from pathlib import Path as FilePath

print("Loading graph...")
with open("cache/bundle.pkl", "rb") as f:
    bundle = pickle.load(f)

G = bundle["G_original"]
print(f"Loaded: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# Find suitable root for DFS
print("\nFinding root with deep DFS structure...")
roots = [n for n in G.nodes() if G.in_degree(n) == 0]
selected_root = None

for root in roots:
    # Check DFS depth and reachable count
    try:
        reachable = nx.descendants(G, root)
        if 50 <= len(reachable) <= 200:
            # Check depth via DFS
            depths = nx.single_source_shortest_path_length(G, root)
            max_depth = max(depths.values()) if depths else 0
            if max_depth >= 6:
                selected_root = root
                print(f"Selected: {root}")
                print(f"  Reachable: {len(reachable)}")
                print(f"  Max depth: {max_depth}")
                break
    except:
        continue

if not selected_root:
    # Fallback
    selected_root = roots[100]
    print(f"Fallback root: {selected_root}")

# DFS traversal with backtracking tracking
print("\nGenerating DFS traversal...")

def dfs_with_states(graph, start, max_depth=7, max_nodes=50):
    """
    Returns list of animation states:
    Each state: {
        'type': 'move' | 'backtrack',
        'from': node,
        'to': node,
        'visited': set of visited nodes,
        'current': current node,
        'adjacent_possible': set of faint nodes visible from current
    }
    """
    states = []
    visited = set()
    stack = [(start, 0, None)]  # (node, depth, parent)
    visited_order = []

    while stack and len(visited_order) < max_nodes:
        node, depth, parent = stack.pop()

        if node in visited or depth > max_depth:
            continue

        visited.add(node)
        visited_order.append(node)

        # Get adjacent possible (unvisited successors)
        adjacent = [s for s in graph.successors(node) if s not in visited]

        # Create state
        state = {
            'type': 'move',
            'from': parent,
            'to': node,
            'visited': visited.copy(),
            'current': node,
            'adjacent_possible': set(adjacent[:8])  # Limit to avoid clutter
        }
        states.append(state)

        # Add unvisited successors to stack (reversed for DFS order)
        for succ in reversed(adjacent[:8]):
            stack.append((succ, depth + 1, node))

    return states

states = dfs_with_states(G, selected_root, max_depth=7, max_nodes=45)
print(f"Generated {len(states)} animation states")

# Build subgraph for visualization
all_nodes = set()
for state in states:
    all_nodes.add(state['to'])
    all_nodes.update(state['adjacent_possible'])

subgraph = G.subgraph(all_nodes).copy()
print(f"Subgraph: {subgraph.number_of_nodes()} nodes")

# Hierarchical left-to-right layout (tree expanding rightward)
print("Computing hierarchical layout...")

def hierarchical_layout(G, root):
    """Create left-to-right tree layout based on depth from root"""
    # Compute levels (distance from root)
    levels = nx.single_source_shortest_path_length(G, root)

    # Group nodes by level
    level_nodes = {}
    for node, level in levels.items():
        if level not in level_nodes:
            level_nodes[level] = []
        level_nodes[level].append(node)

    pos = {}
    max_level = max(levels.values())

    for level, nodes in level_nodes.items():
        # X coordinate: left to right based on depth
        x = (level / max_level) * 4 - 2  # Range: -2 to 2

        # Y coordinates: spread vertically
        n_nodes = len(nodes)
        if n_nodes == 1:
            y_positions = [0]
        else:
            # Spread based on number of nodes at this level
            spread = min(4, 0.5 * np.sqrt(n_nodes))
            y_positions = np.linspace(-spread, spread, n_nodes)

        for i, node in enumerate(nodes):
            pos[node] = np.array([x, y_positions[i]])

    return pos

pos = hierarchical_layout(subgraph, selected_root)

# Shorten labels
def shorten(name):
    return name.split('.')[-1] if '.' in name else name[:15]

labels = {n: shorten(n) for n in subgraph.nodes()}

# Animation parameters
FPS = 30
FRAMES_PER_TRANSITION = 25  # ~0.83s per transition
PAUSE_FRAMES = 15

# Setup figure with high DPI
fig, ax = plt.subplots(figsize=(19.2, 10.8), facecolor='white', dpi=100)
fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

def draw_curved_edge(ax, pos_from, pos_to, progress=1.0, color='black',
                     alpha=1.0, linewidth=1.5, style='solid'):
    """Draw curved Bézier edge with animation progress (0-1)"""
    x1, y1 = pos_from
    x2, y2 = pos_to

    # Control point for curve (offset perpendicular to line)
    mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
    dx, dy = x2 - x1, y2 - y1
    length = np.sqrt(dx**2 + dy**2)
    if length < 0.01:
        return

    # Perpendicular offset (creates curve)
    perp_x, perp_y = -dy / length, dx / length
    curve_strength = 0.15
    ctrl_x = mid_x + perp_x * curve_strength
    ctrl_y = mid_y + perp_y * curve_strength

    # Bézier curve points
    t = np.linspace(0, progress, max(2, int(50 * progress)))
    bezier_x = (1-t)**2 * x1 + 2*(1-t)*t * ctrl_x + t**2 * x2
    bezier_y = (1-t)**2 * y1 + 2*(1-t)*t * ctrl_y + t**2 * y2

    ax.plot(bezier_x, bezier_y, color=color, alpha=alpha,
           linewidth=linewidth, linestyle=style, zorder=1)

    # Arrow head at tip (if fully drawn)
    if progress > 0.95:
        arrow = mpatches.FancyArrowPatch(
            (bezier_x[-2], bezier_y[-2]), (bezier_x[-1], bezier_y[-1]),
            arrowstyle='->', mutation_scale=15, linewidth=linewidth,
            color=color, alpha=alpha, zorder=1
        )
        ax.add_patch(arrow)

def draw_frame(state_idx, sub_frame=0):
    """Draw animation frame for given state and sub-frame"""
    ax.clear()
    ax.set_facecolor('white')
    ax.axis('off')
    ax.set_xlim(-2.5, 2.5)
    ax.set_ylim(-5, 5)  # More vertical space for tree expansion
    ax.set_aspect('equal')

    if state_idx >= len(states):
        state_idx = len(states) - 1

    state = states[state_idx]
    current_node = state['current']
    visited = state['visited']
    adjacent_possible = state['adjacent_possible']

    # Calculate animation progress for current transition
    if state['from'] is not None:
        progress = min(1.0, sub_frame / FRAMES_PER_TRANSITION)
    else:
        progress = 1.0

    # Fade factors for adjacent possible
    # If we're moving (progress < 1), show old adjacent fading + new appearing
    if progress < 1.0 and state_idx > 0:
        # Fading out previous adjacent possible
        prev_adjacent = states[state_idx - 1]['adjacent_possible']
        fade_out = 1.0 - progress
        for node in prev_adjacent:
            if node != state['to'] and node in pos:
                alpha = 0.2 * fade_out
                circle = Circle(pos[node], 0.08, color='lightgray',
                              alpha=alpha, zorder=2)
                ax.add_patch(circle)

    # Draw edges between visited nodes (solid black, curved)
    drawn_edges = set()
    for i in range(state_idx + 1):
        s = states[i]
        if s['from'] is not None and s['from'] in pos and s['to'] in pos:
            edge_key = (s['from'], s['to'])
            if edge_key not in drawn_edges:
                # Current edge being drawn
                if i == state_idx:
                    draw_curved_edge(ax, pos[s['from']], pos[s['to']],
                                   progress, color='black', alpha=0.8, linewidth=2)
                else:
                    # Already drawn edges
                    draw_curved_edge(ax, pos[s['from']], pos[s['to']],
                                   1.0, color='black', alpha=0.6, linewidth=1.5)
                drawn_edges.add(edge_key)

    # Draw faint edges to adjacent possible (after transition completes)
    if progress > 0.95:
        for adj_node in adjacent_possible:
            if current_node in pos and adj_node in pos:
                draw_curved_edge(ax, pos[current_node], pos[adj_node],
                               1.0, color='gray', alpha=0.15,
                               linewidth=1, style='dashed')

    # Draw visited nodes (solid black)
    for node in visited:
        if node == current_node:
            continue
        if node in pos:
            circle = Circle(pos[node], 0.12, color='black', zorder=3)
            ax.add_patch(circle)
            # Label
            ax.text(pos[node][0], pos[node][1] - 0.25, labels[node],
                   fontsize=7, ha='center', va='top',
                   fontfamily='sans-serif', alpha=0.7)

    # Draw adjacent possible nodes (faint)
    if progress > 0.95:
        for node in adjacent_possible:
            if node in pos:
                circle = Circle(pos[node], 0.10, color='lightgray',
                              alpha=0.25, zorder=2)
                ax.add_patch(circle)
                ax.text(pos[node][0], pos[node][1] - 0.22, labels[node],
                       fontsize=6, ha='center', va='top',
                       fontfamily='sans-serif', alpha=0.3)

    # Draw current node (glowing, larger)
    if current_node in pos:
        # Glow effect
        glow_alpha = 0.3 + 0.2 * np.sin(sub_frame * 0.3)
        glow = Circle(pos[current_node], 0.20, color='red',
                     alpha=glow_alpha, zorder=4)
        ax.add_patch(glow)
        # Main circle
        circle = Circle(pos[current_node], 0.14, color='black',
                       edgecolor='red', linewidth=2, zorder=5)
        ax.add_patch(circle)
        # Label
        ax.text(pos[current_node][0], pos[current_node][1] - 0.28,
               labels[current_node], fontsize=8, ha='center', va='top',
               fontfamily='sans-serif', weight='bold')

    # Title annotation
    ax.text(0.02, 0.98, f"DFS Exploration: {shorten(current_node)}",
           transform=ax.transAxes, fontsize=11, va='top',
           fontfamily='sans-serif', weight='bold')

    # Step counter
    ax.text(0.98, 0.98, f"Step {state_idx + 1}/{len(states)}",
           transform=ax.transAxes, fontsize=9, va='top', ha='right',
           fontfamily='sans-serif',
           bbox=dict(boxstyle='round,pad=0.5', facecolor='white',
                    alpha=0.7, edgecolor='gray'))

# Generate all frames
print("Rendering frames...")
frames = []
temp_dir = FilePath("temp_frames")
temp_dir.mkdir(exist_ok=True)

frame_count = 0
for state_idx in range(len(states)):
    # Animate transition
    for sub_frame in range(FRAMES_PER_TRANSITION):
        if frame_count % 50 == 0:
            print(f"  Frame {frame_count}")
        draw_frame(state_idx, sub_frame)

        frame_path = temp_dir / f"frame_{frame_count:05d}.png"
        plt.savefig(frame_path, dpi=100, facecolor='white', edgecolor='none')
        frames.append(imageio.imread(frame_path))
        frame_count += 1

    # Pause at each node
    for _ in range(PAUSE_FRAMES):
        draw_frame(state_idx, FRAMES_PER_TRANSITION)
        frame_path = temp_dir / f"frame_{frame_count:05d}.png"
        plt.savefig(frame_path, dpi=100, facecolor='white', edgecolor='none')
        frames.append(imageio.imread(frame_path))
        frame_count += 1

plt.close()

# Cleanup temp files
print("Cleaning up...")
for f in temp_dir.glob("*.png"):
    f.unlink()
temp_dir.rmdir()

# Save video
output_file = "animation.mp4"
print(f"Encoding video: {output_file}")
imageio.mimsave(output_file, frames, fps=FPS, codec='libx264',
                pixelformat='yuv420p', quality=8, macro_block_size=1)

print(f"\n[SUCCESS] Animation created: {output_file}")
print(f"  Duration: {len(frames)/FPS:.1f}s")
print(f"  Frames: {len(frames)} @ {FPS} fps")
print(f"  Resolution: {frames[0].shape[1]}x{frames[0].shape[0]}")
print(f"  Ready for X.com!")
