#!/usr/bin/env python3
"""
Backend server for interactive ego network visualization dashboard.
Loads cached ego network data and serves HTML frontend with brutalist dark theme.
"""

import json
import pickle
from pathlib import Path
from flask import Flask, jsonify, render_template_string, send_from_directory
import networkx as nx

# Configuration  (HF Spaces: data in ./data/, lib in ./lib/)
_SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = _SCRIPT_DIR / "data"
CACHE_BUNDLE = DATA_DIR / "bundle.pkl"
LIB_DIR = _SCRIPT_DIR / "lib" / "vis-9.1.2"
CORPUS_CODE_INDEX = DATA_DIR / "corpus_code_index.json"
# Compact pre-processed file (replaces 717 MB traced_theorems_unified_v2.jsonl)
APP_NETWORK_DATA = DATA_DIR / "app_network_data.jsonl"
# Fallback: original large file (optional)
TRACED_THEOREMS_FILE = DATA_DIR / "traced_theorems_unified_v2.jsonl"

app = Flask(__name__)

# Load theorem index: prefer compact app_network_data.jsonl, fall back to original JSONL
# Uses byte-offset index for O(1) per-theorem lookup without loading all data into memory.
print("Loading theorem index...")
traced_theorems_index = {}
theorem_byte_offsets = {}  # theorem_name -> byte offset for fast proof-DAG lookups

_source_file = APP_NETWORK_DATA if APP_NETWORK_DATA.exists() else (
    TRACED_THEOREMS_FILE if TRACED_THEOREMS_FILE.exists() else None
)
if _source_file:
    try:
        with open(_source_file, "rb") as f:
            while True:
                offset = f.tell()
                raw_line = f.readline()
                if not raw_line:
                    break
                if not raw_line.strip():
                    continue
                try:
                    entry = json.loads(raw_line.decode("utf-8"))
                    full_name = entry.get("full_name", "")
                    if full_name:
                        traced_theorems_index[full_name] = {
                            "proof_text": entry.get("proof_text", ""),
                            "statement": entry.get("statement", ""),
                            "proof_type": entry.get("proof_type", "unknown")
                        }
                        if entry.get("proof_type") == "tactic":
                            theorem_byte_offsets[full_name] = offset
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
        print(f"  Loaded {len(traced_theorems_index):,} theorems from {_source_file.name}")
        print(f"  Indexed {len(theorem_byte_offsets):,} tactic theorem byte offsets")
    except Exception as e:
        print(f"  Warning: Failed to load theorem index: {e}")
        theorem_byte_offsets = {}
else:
    print("  Warning: No theorem data file found (app_network_data.jsonl or traced_theorems_unified_v2.jsonl)")
    theorem_byte_offsets = {}

# Load corpus code index (fallback for premises/theorems not in traced file)
print("Loading corpus code index...")
corpus_code_index = {}
if CORPUS_CODE_INDEX.exists():
    try:
        with open(CORPUS_CODE_INDEX, "r", encoding="utf-8") as f:
            corpus_code_index = json.load(f)
        print(f"  Loaded {len(corpus_code_index):,} code entries from corpus")
    except Exception as e:
        print(f"  Warning: Failed to load corpus code index: {e}")
        print(f"  Run 00_code/00_utils.py generate-corpus-index to generate it")
else:
    print(f"  Warning: Corpus code index not found at {CORPUS_CODE_INDEX}")
    print(f"  Run 00_corpus_to_code.py to generate it")

# Load cached data
print("Loading cached ego network data...")
try:
    with open(CACHE_BUNDLE, "rb") as f:
        bundle = pickle.load(f)
    G_original = bundle["G_original"]
    ego_network_data = bundle.get("ego_network_data", {})
    theorems_list = bundle.get("theorems_list", [])
    
    # If ego_network_data is missing, generate it from G_original
    if not ego_network_data or not theorems_list:
        print("  Ego network data not in cache, generating from graph...")
        theorems_list = [n for n in G_original.nodes() if G_original.nodes[n].get("node_type") == "theorem"]
        
        # Generate ego network data
        Out = {n: set(G_original.successors(n)) for n in G_original.nodes()}
        In = {n: set(G_original.predecessors(n)) for n in G_original.nodes()}
        all_edges_set = set(G_original.edges())
        
        ego_network_data = {}
        for theorem in theorems_list:
            # Get parents (nodes that point TO this theorem)
            parents = list(In[theorem])
            # Get children (nodes that this theorem points TO)
            # Note: children can be theorems (if this theorem is used as a premise)
            children = list(Out[theorem])
            
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
            
            ego_network_data[theorem] = {
                "parents": parents,
                "children": children,
                "edges": edges,
                "num_parents": len(parents),
                "num_children": len(children),
                "num_bypass_edges": sum(1 for p in parents for c in children if (p, c) in all_edges_set)
            }
        
        print(f"  Generated ego network data for {len(theorems_list):,} theorems")
    else:
        print(f"  Loaded {len(theorems_list):,} theorems from cache")
    
    # Calculate percentage of leaf nodes (theorems with no children)
    if G_original and theorems_list:
        Out = {n: set(G_original.successors(n)) for n in G_original.nodes()}
        theorems_with_children = [t for t in theorems_list if len(Out.get(t, [])) > 0]
        leaf_theorems = len(theorems_list) - len(theorems_with_children)
        leaf_percentage = (leaf_theorems / len(theorems_list) * 100) if theorems_list else 0
        print(f"  Leaf nodes: {leaf_theorems:,} ({leaf_percentage:.1f}%)")
        print(f"  Theorems with children: {len(theorems_with_children):,}")
    else:
        leaf_percentage = 0
except Exception as e:
    print(f"Error loading cache: {e}")
    leaf_percentage = 0
    import traceback
    traceback.print_exc()
    G_original = None
    ego_network_data = {}
    theorems_list = []


def format_ego_network_for_vis(theorem, G, ego_data, distance=1):
    """Format ego network data for vis-network visualization with NetworkX positioning."""
    if theorem not in ego_data:
        return None
    
    data = ego_data[theorem]
    parents = data["parents"]
    children = data["children"]
    edges = data["edges"]
    
    # Collect all nodes
    ego_nodes = set([theorem])
    ego_nodes.update(parents)
    ego_nodes.update(children)
    
    # Build NetworkX subgraph for layout computation
    ego_subgraph = nx.DiGraph()
    ego_subgraph.add_nodes_from(ego_nodes)
    for edge in edges:
        ego_subgraph.add_edge(edge["from"], edge["to"])
    
    # Compute x-coordinates using NetworkX layout (spring_layout works well for connected nodes)
    if len(ego_nodes) > 1:
        try:
            # Use spring_layout to bring connected nodes closer horizontally
            pos = nx.spring_layout(ego_subgraph, k=1.5, iterations=50, seed=42)
        except:
            # Fallback to circular layout if spring_layout fails
            pos = nx.circular_layout(ego_subgraph)
    else:
        pos = {list(ego_nodes)[0]: (0, 0)} if ego_nodes else {}
    
    # Group nodes by level for y-coordinate computation
    nodes_by_level = {}
    for node in ego_nodes:
        if node == theorem:
            level = 2  # Central node
        elif node in parents:
            level = 1  # Parents
        else:
            level = 3  # Children
        
        if level not in nodes_by_level:
            nodes_by_level[level] = []
        nodes_by_level[level].append(node)
    
    # Compute y-coordinates: base y per level + slight staggering within level
    level_y_base = {0: -200, 1: -100, 2: 0, 3: 100, 4: 200}  # Base y positions
    level_y_spacing = 12  # Vertical stagger spacing within level
    node_positions = {}
    
    for level, nodes_at_level in nodes_by_level.items():
        base_y = level_y_base.get(level, 0)
        n_at_level = len(nodes_at_level)
        for idx, node in enumerate(nodes_at_level):
            # Stagger: alternate vertical offset within level, centered around base_y
            if n_at_level == 1:
                stagger_offset = 0
            else:
                # Simple alternating pattern: even indices slightly up, odd indices slightly down
                if idx % 2 == 0:
                    stagger_offset = (idx // 2) * level_y_spacing
                else:
                    stagger_offset = -((idx + 1) // 2) * level_y_spacing
                # Center the stagger around base_y
                if n_at_level > 1:
                    max_offset = ((n_at_level - 1) // 2) * level_y_spacing
                    if max_offset > 0:
                        # Adjust to center around 0
                        if idx % 2 == 0:
                            stagger_offset = stagger_offset - max_offset / 2
                        else:
                            stagger_offset = stagger_offset + max_offset / 2
            node_positions[node] = {
                'x': pos[node][0] * 200 if node in pos else 0,  # Scale x-coordinates
                'y': base_y + stagger_offset
            }
    
    # Create node data with fixed positions
    # Filter nodes based on distance: only include nodes at or within the selected distance
    nodes = []
    for node in ego_nodes:
        # For distance 1, only include: theorem, parents, children
        # (This function is only called for distance 1, but adding check for safety)
        if distance == 1:
            if node != theorem and node not in parents and node not in children:
                continue
        
        short_name = node.split('.')[-1] if '.' in node else node[:50]
        node_type = G.nodes[node].get("node_type", "unknown")
        
        # Determine topological level
        if node == theorem:
            level = 2  # Central node
        elif node in parents:
            level = 1  # Parents
        else:
            level = 3  # Children
        
        if node == theorem:
            color = "#ffffff"
            border_color = "#ffffff"
            border_width = 2
        else:
            color = "#111822"
            border_color = "rgba(255,255,255,0.25)"
            border_width = 1

        node_data = {
            "id": node,
            "label": short_name,
            "title": node,
            "color": {"background": color, "border": border_color},
            "shape": "dot",
            "size": 9 if node == theorem else 5,
            "font": {"color": "#d0d8ee", "size": 13, "face": "Inter, Arial, sans-serif", "strokeWidth": 0},
            "borderWidth": border_width,
            "level": level,
            "x": node_positions[node]["x"],
            "y": node_positions[node]["y"],
            "fixed": {"x": True, "y": True},
        }
        nodes.append(node_data)
    
    return {
        "nodes": nodes,
        "edges": edges,
        "num_parents": data["num_parents"],
        "num_children": data["num_children"],
        "num_bypass_edges": data["num_bypass_edges"]
    }



def build_proof_dag_for_vis(theorem_entry):
    """Build within-proof DAG from theorem entry, formatted for vis-network.

    Same logic as 01_make_internal_proof_DAGs.py, dark background aesthetic.
    Returns None if no tactics found.
    """
    tactics = theorem_entry.get("tactics", [])
    if not tactics:
        return None

    nodes_dict = {}
    edges = []
    state_id_map = {}
    state_counter = [0]

    def get_or_create_state(state_str, is_initial, is_terminal):
        if state_str in state_id_map:
            node_id = state_id_map[state_str]
            if is_terminal:
                nodes_dict[node_id]["is_terminal"] = True
            return node_id
        node_id = f"s{state_counter[0]}"
        state_id_map[state_str] = node_id
        state_counter[0] += 1
        nodes_dict[node_id] = {
            "id": node_id,
            "label": node_id,
            "state": state_str[:300],
            "num_goals": state_str.count("\u22a2") if state_str else 0,
            "is_initial": is_initial,
            "is_terminal": is_terminal,
        }
        return node_id

    for i, tactic_record in enumerate(tactics):
        state_before = tactic_record.get("state_before", "")
        state_after = tactic_record.get("state_after", "")
        tactic_str = tactic_record.get("tactic", "")
        is_terminal = tactic_record.get("is_terminal", False)

        from_id = get_or_create_state(state_before, is_initial=(i == 0), is_terminal=False)
        to_id = get_or_create_state(state_after, is_initial=False, is_terminal=is_terminal)
        edges.append({"from": from_id, "to": to_id, "label": tactic_str[:12], "title": tactic_str})

    # BFS to assign topological levels (ensures vis-network TB layout works)
    from collections import deque
    adj = {nid: [] for nid in nodes_dict}
    in_deg = {nid: 0 for nid in nodes_dict}
    for e in edges:
        adj[e["from"]].append(e["to"])
        in_deg[e["to"]] = in_deg.get(e["to"], 0) + 1
    bfs_levels = {}
    q = deque([nid for nid in nodes_dict if in_deg.get(nid, 0) == 0])
    cur = 0
    while q:
        nxt = deque()
        for nid in q:
            bfs_levels[nid] = cur
            for s in adj[nid]:
                in_deg[s] -= 1
                if in_deg[s] == 0:
                    nxt.append(s)
        q = nxt
        cur += 1

    # Assign x/y positions directly — TB layout, fixed coords (vis-network hierarchical is unreliable)
    from collections import defaultdict
    level_groups = defaultdict(list)
    for nid in nodes_dict:
        level_groups[bfs_levels.get(nid, 0)].append(nid)

    Y_SEP = 110
    X_SEP = 130
    node_xy = {}
    for lev, nids in level_groups.items():
        n = len(nids)
        for i, nid in enumerate(sorted(nids)):
            node_xy[nid] = {"x": (i - (n - 1) / 2.0) * X_SEP, "y": lev * Y_SEP}

    vis_nodes = []
    for node_id, info in nodes_dict.items():
        pos = node_xy.get(node_id, {"x": 0, "y": 0})
        node = {
            "id": node_id,
            "label": node_id,
            "title": info.get("state", "")[:200],
            "x": pos["x"],
            "y": pos["y"],
            "fixed": {"x": True, "y": True},
        }
        white_font = {"color": "#FFFFFF", "size": 12, "face": "Inter, Arial, sans-serif", "strokeWidth": 0}
        black_font = {"color": "#000000", "size": 12, "face": "Inter, Arial, sans-serif", "strokeWidth": 0}
        if info.get("is_terminal"):
            node["color"] = {"background": "#FFFFFF", "border": "#FFFFFF"}
            node["font"] = black_font
            node["borderWidth"] = 4
        elif info.get("is_initial"):
            node["color"] = {"background": "#1a1a1a", "border": "#FFFFFF"}
            node["font"] = white_font
            node["borderWidth"] = 3
        else:
            node["color"] = {"background": "#000000", "border": "#FFFFFF"}
            node["font"] = white_font
            node["borderWidth"] = 2
        vis_nodes.append(node)

    vis_edges = []
    for edge in edges:
        vis_edges.append({
            "from": edge["from"],
            "to": edge["to"],
            "label": edge["label"],
            "title": edge["title"],
            "arrows": "to",
            "color": {"color": "rgba(255,255,255,0.5)", "highlight": "rgba(255,255,255,0.8)"},
            "width": 1.5,
            "font": {"color": "#FFFFFF", "size": 11, "face": "Inter, Arial, sans-serif", "align": "horizontal", "strokeWidth": 0},
        })

    return {
        "nodes": vis_nodes,
        "edges": vis_edges,
        "num_tactics": len(tactics),
        "num_states": len(vis_nodes),
    }


# HTML template with brutalist dark theme
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>THEOREM EGO NETWORK</title>
    <script type="text/javascript" src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.2/standalone/umd/vis-network.min.js"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.2/standalone/umd/vis-network.min.css" rel="stylesheet" type="text/css" />
    <style>
        :root {
            --bg: #07090f;
            --surface: #0c1018;
            --surface-2: #111822;
            --border: rgba(255,255,255,0.07);
            --border-hi: rgba(255,255,255,0.18);
            --text: #d0d8ee;
            --text-dim: #5a6a8a;
            --text-muted: #2e3a52;
            --accent: #4d7cfe;
            --accent-dim: rgba(77,124,254,0.1);
            --mono: 'Courier New', monospace;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: var(--mono);
            background: var(--bg);
            color: var(--text);
            padding: 8px 10px 10px;
            font-size: 12px;
        }
        .container { max-width: 100%; width: 100%; }
        .controls {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 7px 10px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 3px;
            margin-bottom: 5px;
        }
        label {
            color: var(--text-dim);
            font-size: 11px;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: .06em;
            white-space: nowrap;
        }
        input[type="text"] {
            width: 100%;
            padding: 6px 10px;
            background: var(--bg);
            color: var(--text);
            border: 1px solid var(--border-hi);
            font-family: var(--mono);
            font-size: 12px;
            outline: none;
            border-radius: 2px;
        }
        input[type="text"]:focus { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-dim); }
        .toggle-button {
            padding: 5px 13px;
            font-size: 11px;
            font-family: var(--mono);
            background: transparent;
            color: var(--text-dim);
            border: 1px solid var(--border);
            cursor: pointer;
            text-transform: uppercase;
            letter-spacing: .06em;
            font-weight: bold;
            border-radius: 2px;
            white-space: nowrap;
            transition: all .12s;
        }
        .toggle-button.active { background: var(--accent); color: #fff; border-color: var(--accent); }
        .toggle-button:not(.active):hover { border-color: var(--border-hi); color: var(--text); }
        .nav-button {
            padding: 6px 10px;
            background: transparent;
            color: var(--text-dim);
            border: 1px solid var(--border);
            font-family: var(--mono);
            font-size: 13px;
            cursor: pointer;
            border-radius: 2px;
            flex-shrink: 0;
            transition: all .12s;
        }
        .nav-button:hover { background: var(--surface-2); color: var(--text); border-color: var(--border-hi); }
        .info {
            background: var(--surface);
            color: var(--text-dim);
            padding: 5px 10px;
            margin-bottom: 5px;
            border: 1px solid var(--border);
            font-size: 10px;
            border-radius: 3px;
        }
        .info strong { color: var(--text); }
        #focusedNode {
            margin-bottom: 5px;
            padding: 5px 10px;
            border: 1px solid var(--border);
            background: var(--surface);
            font-size: 13px;
            border-radius: 3px;
            min-height: 28px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .main-content { display: flex; gap: 6px; width: 100%; }
        .network-container {
            flex: 0 0 64%;
            width: 64%;
            display: flex;
            gap: 0;
            border: 1px solid var(--border);
            border-radius: 3px;
            overflow: hidden;
        }
        .ego-net-half { flex: 2; min-width: 0; }
        .proof-dag-half {
            flex: 1;
            min-width: 0;
            height: 540px;
            border-left: 1px solid var(--border);
            background: var(--bg);
            display: flex;
            flex-direction: column;
        }
        .proof-dag-label {
            font-family: var(--mono);
            font-size: 9px;
            color: var(--text-muted);
            padding: 4px 10px;
            border-bottom: 1px solid var(--border);
            text-transform: uppercase;
            letter-spacing: .12em;
            flex-shrink: 0;
            background: var(--surface);
        }
        #proofDagNetwork { flex: 1; background: var(--bg); min-height: 0; }
        #network { width: 100%; height: 540px; background: var(--bg); position: relative; }
        .proof-panel {
            flex: 0 0 34%;
            width: 34%;
            height: 540px;
            border: 1px solid var(--border);
            background: var(--surface);
            display: flex;
            flex-direction: column;
            border-radius: 3px;
            overflow: hidden;
        }
        .proof-modal { display: block; width: 100%; height: 100%; overflow: auto; }
        .proof-modal-content {
            padding: 14px 16px;
            width: 100%;
            height: 100%;
            overflow: auto;
            display: flex;
            flex-direction: column;
        }
        .proof-modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 10px;
            flex-shrink: 0;
        }
        .proof-modal-title {
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: .08em;
            color: var(--text);
        }
        .proof-modal-close { display: none; }
        .proof-content {
            font-family: var(--mono);
            font-size: 11px;
            white-space: pre-wrap;
            word-wrap: break-word;
            line-height: 1.65;
            flex: 1;
            overflow: auto;
        }
        .proof-statement {
            color: var(--text);
            margin-bottom: 14px;
            padding: 8px 10px;
            border-left: 2px solid var(--accent);
            background: var(--accent-dim);
            font-size: 11px;
            white-space: pre-wrap;
            word-wrap: break-word;
            border-radius: 0 2px 2px 0;
            flex-shrink: 0;
        }
        .proof-text { color: var(--text-dim); font-size: 11px; line-height: 1.7; }
        #searchResults {
            font-family: var(--mono);
            font-size: 11px;
            background: var(--surface-2);
            border: 1px solid var(--border-hi) !important;
            border-radius: 2px;
        }
        .search-result-item {
            padding: 6px 10px;
            cursor: pointer;
            border-bottom: 1px solid var(--border);
            color: var(--text-dim);
        }
        .search-result-item:hover { background: var(--surface-2); color: var(--text); }
        .search-result-item.selected { background: var(--accent); color: #fff; }
        .legend {
            margin-top: 6px;
            padding: 5px 10px;
            border: 1px solid var(--border);
            background: var(--surface);
            border-radius: 3px;
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 4px;
        }
        .legend-title {
            font-size: 10px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: .1em;
            font-weight: bold;
            margin-right: 12px;
        }
        .legend-item { display: inline-flex; align-items: center; margin-right: 16px; font-size: 10px; color: var(--text-dim); gap: 5px; }
        .legend-color { display: inline-block; width: 8px; height: 8px; border-radius: 50%; }
        .legend-text { text-transform: uppercase; letter-spacing: .04em; }
        /* Picks panel */
        #picksPanel {
            display: none;
            position: absolute;
            top: 100%;
            right: 0;
            z-index: 2000;
            background: var(--surface-2);
            border: 1px solid var(--border-hi);
            border-radius: 3px;
            min-width: 340px;
            max-height: 340px;
            overflow-y: auto;
            margin-top: 4px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.5);
        }
        .picks-item {
            padding: 7px 12px;
            cursor: pointer;
            border-bottom: 1px solid var(--border);
            font-family: var(--mono);
            font-size: 10px;
            color: var(--text-dim);
            display: flex;
            flex-direction: column;
            gap: 2px;
        }
        .picks-item:hover { background: var(--surface); color: var(--text); }
        .picks-item-short { color: var(--accent); font-size: 11px; font-weight: bold; }
        .picks-item-full { color: var(--text-muted); font-size: 9px; letter-spacing: .02em; }
        #picksWrapper { position: relative; }
    </style>
</head>
<body>
    <div class="container">
        <div class="controls">
            <label for="theoremInput">SELECT THEOREM:</label>
            <div style="display: flex; align-items: center; gap: 5px; flex: 1; position: relative;">
                <button id="prevButton" class="nav-button" onclick="navigateTheorem(-1)" title="Previous">◀</button>
                <div style="flex: 1; position: relative;">
                    <input type="text" id="theoremInput" placeholder="type to search theorems..."
                           oninput="handleSearchInput()"
                           onkeydown="handleSearchKeydown(event)"
                           autocomplete="off">
                    <div id="searchResults" style="display: none; position: absolute; z-index: 1000; max-height: 200px; overflow-y: auto; margin-top: 2px; left: 0; right: 0; box-sizing: border-box;"></div>
                </div>
                <button id="nextButton" class="nav-button" onclick="navigateTheorem(1)" title="Next">▶</button>
            </div>
            <button id="distanceToggle" class="toggle-button active" onclick="cycleDistance()" style="margin-top: 10px;">DISTANCE 2</button>
            <button id="downloadButton" class="toggle-button" onclick="downloadProofs()" style="margin-top: 10px; margin-left: 5px;" title="Download all proofs as markdown">DOWNLOAD PROOFS</button>
            <div id="picksWrapper" style="margin-top: 10px; margin-left: 5px; display: inline-block;">
                <button class="toggle-button" onclick="togglePicks(event)">✦ PICKS</button>
                <div id="picksPanel">
                    <div style="padding:7px 12px 5px; font-size:9px; color:var(--text-muted); text-transform:uppercase; letter-spacing:.08em; border-bottom:1px solid var(--border);">20 Curated Theorems</div>
                </div>
            </div>
        </div>
        
        <div class="info" id="networkInfo" style="display: none;">
            <strong>NETWORK STATISTICS:</strong>
            <span id="infoText"></span>
        </div>
        
        <div id="focusedNode">
            <span style="color: var(--text-muted); font-size: 10px; text-transform: uppercase; letter-spacing: .08em;">FOCUSED</span>
            <span id="focusedNodeName" style="color: var(--text); font-weight: bold;">--</span>
        </div>
        
        <div class="main-content">
            <div class="network-container">
                <div class="ego-net-half">
                    <div id="network"></div>
                </div>
                <div class="proof-dag-half">
                    <div class="proof-dag-label" id="proofDagLabel">Proof DAG</div>
                    <div id="proofDagNetwork"></div>
                </div>
            </div>
            
            <!-- Proof Panel - Always visible on right side -->
            <div id="proofModal" class="proof-panel empty">
                <div class="proof-modal-content">
                    <div class="proof-modal-header">
                        <div class="proof-modal-title" id="proofModalTitle">THEOREM PROOF</div>
                        <a id="mathlibLink" href="#" target="_blank" rel="noopener" style="display:none; font-size:10px; color:var(--accent); text-decoration:none; border:1px solid var(--accent-dim); padding:2px 8px; font-family:var(--mono); white-space:nowrap; border-radius:2px; letter-spacing:.04em;">&#8599; MATHLIB</a>
                    </div>
                    <div class="proof-content">
                        <div class="proof-statement" id="proofStatement">-- NO THEOREM SELECTED --</div>
                        <div class="proof-text" id="proofText"></div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="legend">
            <span class="legend-title">LEGEND</span>
            <span class="legend-item">
                <span class="legend-color" style="background:#ffffff; width:10px; height:10px;"></span>
                <span class="legend-text">CENTRAL</span>
            </span>
            <span class="legend-item">
                <span class="legend-color" style="background:#1a2038; border:1px solid rgba(255,255,255,0.3); width:8px; height:8px;"></span>
                <span class="legend-text">DEPENDENCY</span>
            </span>
            <span class="legend-item" style="color:var(--text-muted);">
                <span style="font-size:11px;">→</span>
                <span class="legend-text">USES</span>
            </span>
        </div>
    </div>
    
    <script type="text/javascript">
        let network = null;
        let allTheorems = [];
        let currentTheoremIndex = -1; // Current index in allTheorems
        let currentDistance = 2; // Default to distance 2
        let levelSeparators = []; // Store level separator y-positions
        let currentNodeDataSet = null; // Store current node dataset
        let hoveredNodeId = null; // Track currently hovered node
        let proofDagNetwork = null; // vis-network instance for within-proof DAG
        let searchResults = []; // Filtered search results
        let selectedSearchIndex = -1; // Currently selected search result
        
        // 20 curated interesting theorems
        const PICKS = [
            ["FirstOrder.Language.Substructure.cg_iff_empty_or_exists_nat_generating_family", "Countably generated substructure characterization"],
            ["MeasureTheory.hahn_decomposition", "Hahn decomposition of signed measures"],
            ["Nat.Prime.sum_four_squares", "Lagrange four-square theorem (every prime)"],
            ["Fermat42.not_minimal", "Fermat's Last Theorem for exponent 4"],
            ["PythagoreanTriple.isPrimitiveClassified_of_coprime_of_odd_of_pos", "Classification of primitive Pythagorean triples"],
            ["FreeGroup.injective_lift_of_ping_pong", "Ping-pong lemma → free group embedding"],
            ["fermatLastTheoremWith_nat_int_rat_tfae", "FLT equivalence: ℕ ↔ ℤ ↔ ℚ"],
            ["AddCircle.addWellApproximable_ae_empty_or_univ", "Diophantine approximation on the circle: 0/1 dichotomy"],
            ["PhragmenLindelof.horizontal_strip", "Phragmén–Lindelöf principle on a horizontal strip"],
            ["CategoryTheory.Limits.colimitLimitToLimitColimit_surjective", "Colimit-limit interchange surjectivity"],
            ["Polynomial.cyclotomic_eval_lt_add_one_pow_totient", "Cyclotomic polynomial evaluation bound"],
            ["Ideal.iSup_iInf_eq_top_iff_pairwise", "Chinese Remainder Theorem: pairwise coprimality"],
            ["Turing.ToPartrec.Code.exists_code", "Every partial recursive function has a code"],
            ["ProbabilityTheory.strong_law_aux1", "Strong law of large numbers (auxiliary)"],
            ["Matrix.det_blockDiagonal", "Determinant of block-diagonal matrix"],
            ["LieAlgebra.engel_isBot_of_isMin", "Engel's theorem for Lie algebras"],
            ["GromovHausdorff.hausdorffDist_optimal", "Gromov-Hausdorff distance via optimal embedding"],
            ["Nat.psp_from_prime_psp", "Constructing pseudoprimes from primes"],
            ["Ideal.subset_union_prime", "Prime avoidance lemma"],
            ["CategoryTheory.IsPushout.isVanKampen_iff", "Van Kampen condition for pushouts"],
        ];

        (function buildPicksPanel() {
            const panel = document.getElementById('picksPanel');
            PICKS.forEach(([full, desc]) => {
                const short = full.split('.').slice(-2).join('.');
                const item = document.createElement('div');
                item.className = 'picks-item';
                item.innerHTML = `<span class="picks-item-short">${short}</span><span class="picks-item-full">${desc}</span>`;
                item.title = full;
                item.onclick = () => { setCurrentTheorem(full, true); closePicks(); };
                panel.appendChild(item);
            });
        })();

        function togglePicks(e) {
            e.stopPropagation();
            const p = document.getElementById('picksPanel');
            p.style.display = p.style.display === 'block' ? 'none' : 'block';
        }
        function closePicks() { document.getElementById('picksPanel').style.display = 'none'; }
        document.addEventListener('click', function(e) {
            if (!document.getElementById('picksWrapper').contains(e.target)) closePicks();
        });

        // Load default theorem on page load
        window.addEventListener('DOMContentLoaded', function() {
            updateDistanceButton();
            // Start with a curated default theorem
            setCurrentTheorem('FirstOrder.Language.Substructure.cg_iff_empty_or_exists_nat_generating_family', true);
            
            // Load full list in background for navigation/search (non-blocking)
            ensureTheoremsLoaded().catch(error => {
                console.error('Error loading theorems list:', error);
            });
        });
        
        // Lazy load full theorem list when needed (for search/navigation)
        function ensureTheoremsLoaded() {
            if (allTheorems.length === 0) {
                return fetch('/api/theorems')
                    .then(response => response.json())
                    .then(data => {
                        allTheorems = data.theorems;
                        return allTheorems;
                    });
            }
            return Promise.resolve(allTheorems);
        }
        
        function setCurrentTheorem(theorem, updateInput = true) {
            if (updateInput) {
                const input = document.getElementById('theoremInput');
                if (input) {
                    input.value = theorem;
                }
            }
            // Update index if theorems are loaded
            if (allTheorems.length > 0) {
                currentTheoremIndex = allTheorems.indexOf(theorem);
            }
            updateNetwork();
        }
        
        function navigateTheorem(direction) {
            ensureTheoremsLoaded().then(() => {
                if (allTheorems.length === 0) return;
                
                if (currentTheoremIndex === -1) {
                    // If no current theorem, start at 0 or random
                    currentTheoremIndex = direction > 0 ? 0 : allTheorems.length - 1;
                } else {
                    currentTheoremIndex += direction;
                    if (currentTheoremIndex < 0) {
                        currentTheoremIndex = allTheorems.length - 1;
                    } else if (currentTheoremIndex >= allTheorems.length) {
                        currentTheoremIndex = 0;
                    }
                }
                
                const theorem = allTheorems[currentTheoremIndex];
                setCurrentTheorem(theorem, true);
            });
        }
        
        function handleSearchInput() {
            const input = document.getElementById('theoremInput');
            const query = input.value.trim().toLowerCase();
            const resultsDiv = document.getElementById('searchResults');
            
            if (query.length === 0) {
                resultsDiv.style.display = 'none';
                selectedSearchIndex = -1;
                return;
            }
            
            ensureTheoremsLoaded().then(() => {
                // Filter theorems that match the query
                searchResults = allTheorems.filter(theorem => 
                    theorem.toLowerCase().includes(query) || 
                    theorem.split('.').pop().toLowerCase().includes(query)
                ).slice(0, 20); // Limit to 20 results
                
                selectedSearchIndex = -1;
                displaySearchResults();
            });
        }
        
        function displaySearchResults() {
            const resultsDiv = document.getElementById('searchResults');
            
            if (searchResults.length === 0) {
                resultsDiv.style.display = 'none';
                return;
            }
            
            resultsDiv.innerHTML = '';
            searchResults.forEach((theorem, index) => {
                const item = document.createElement('div');
                item.className = 'search-result-item';
                if (index === selectedSearchIndex) {
                    item.classList.add('selected');
                }
                const shortName = theorem.split('.').pop() || theorem.substring(0, 60);
                item.textContent = shortName;
                item.title = theorem; // Full name in tooltip
                item.onclick = () => {
                    setCurrentTheorem(theorem, true);
                    resultsDiv.style.display = 'none';
                };
                resultsDiv.appendChild(item);
            });
            
            resultsDiv.style.display = 'block';
        }
        
        function handleSearchKeydown(event) {
            const resultsDiv = document.getElementById('searchResults');
            
            if (event.key === 'ArrowDown') {
                event.preventDefault();
                if (selectedSearchIndex < searchResults.length - 1) {
                    selectedSearchIndex++;
                    displaySearchResults();
                }
            } else if (event.key === 'ArrowUp') {
                event.preventDefault();
                if (selectedSearchIndex > 0) {
                    selectedSearchIndex--;
                    displaySearchResults();
                } else {
                    selectedSearchIndex = -1;
                    displaySearchResults();
                }
            } else if (event.key === 'Enter') {
                event.preventDefault();
                if (selectedSearchIndex >= 0 && selectedSearchIndex < searchResults.length) {
                    const theorem = searchResults[selectedSearchIndex];
                    setCurrentTheorem(theorem, true);
                    resultsDiv.style.display = 'none';
                } else if (searchResults.length === 1) {
                    // If only one result, select it
                    setCurrentTheorem(searchResults[0], true);
                    resultsDiv.style.display = 'none';
                } else if (searchResults.length > 0) {
                    // Select first result if multiple
                    setCurrentTheorem(searchResults[0], true);
                    resultsDiv.style.display = 'none';
                }
            } else if (event.key === 'Escape') {
                resultsDiv.style.display = 'none';
                selectedSearchIndex = -1;
            }
        }
        
        // Close search results when clicking outside
        document.addEventListener('click', function(event) {
            const input = document.getElementById('theoremInput');
            const resultsDiv = document.getElementById('searchResults');
            if (input && resultsDiv && !input.contains(event.target) && !resultsDiv.contains(event.target)) {
                resultsDiv.style.display = 'none';
            }
        });
        
        function cycleDistance() {
            // Cycle: 2 -> 3 -> 1 -> 2 -> ...
            if (currentDistance === 2) {
                currentDistance = 3;
            } else if (currentDistance === 3) {
                currentDistance = 1;
            } else {
                currentDistance = 2;
            }
            updateDistanceButton();
            updateNetwork();
        }
        
        function updateDistanceButton() {
            const button = document.getElementById('distanceToggle');
            button.textContent = `DISTANCE ${currentDistance}`;
            button.classList.add('active'); // Always active since it's the only button
        }
        
        // Initialize button state on page load
        window.addEventListener('DOMContentLoaded', function() {
            updateDistanceButton();
        });
        
        function closeProofModal() {
            // Clear the modal content but keep it visible
            document.getElementById('proofModalTitle').textContent = 'THEOREM PROOF';
            document.getElementById('proofStatement').textContent = '-- NO THEOREM SELECTED --';
            document.getElementById('proofText').textContent = '';
            document.getElementById('proofModal').classList.add('empty');
        }
        
        // Store the central theorem for auto-selection
        let centralTheoremNode = null;
        
        function showProof(theoremName) {
            if (!theoremName) {
                closeProofModal();
                return;
            }
            
            // Remove empty class to show content
            document.getElementById('proofModal').classList.remove('empty');
            
            fetch(`/api/theorem/${encodeURIComponent(theoremName)}`)
                .then(response => response.json())
                .then(data => {
                    const mathlibLink = document.getElementById('mathlibLink');
                    if (data.success) {
                        document.getElementById('proofModalTitle').textContent = theoremName;
                        // Display statement above proof text
                        document.getElementById('proofStatement').textContent = data.statement || '(No statement available)';
                        document.getElementById('proofText').textContent = data.proof_text || data.code || '(No proof available)';
                        if (mathlibLink) {
                            mathlibLink.href = `https://leanprover-community.github.io/mathlib4_docs/search.html?q=${encodeURIComponent(theoremName)}`;
                            mathlibLink.style.display = 'inline';
                        }
                    } else {
                        document.getElementById('proofModalTitle').textContent = theoremName;
                        document.getElementById('proofStatement').textContent = '-- NOT FOUND --';
                        document.getElementById('proofText').textContent = data.error || 'Theorem not found in corpus';
                        if (mathlibLink) mathlibLink.style.display = 'none';
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    document.getElementById('proofModalTitle').textContent = theoremName;
                    document.getElementById('proofStatement').textContent = '-- ERROR --';
                    document.getElementById('proofText').textContent = 'Error loading proof: ' + error.message;
                });
        }
        
        function downloadProofs() {
            const input = document.getElementById('theoremInput');
            const theorem = input ? input.value.trim() : '';
            
            if (!theorem) {
                alert('Please select a theorem first');
                return;
            }
            
            // Get current distance
            const distance = currentDistance;
            
            // Create download link
            const url = `/api/download-proofs/${encodeURIComponent(theorem)}/${distance}`;
            const link = document.createElement('a');
            link.href = url;
            // Sanitize filename: replace dots and slashes with underscores
            const safeFilename = theorem.replace(/\./g, '_').replace(/\//g, '_') + `_distance${distance}_proofs.md`;
            link.download = safeFilename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
        
        function updateNetwork() {
            const input = document.getElementById('theoremInput');
            const theorem = input ? input.value.trim() : '';
            const infoDiv = document.getElementById('networkInfo');
            const infoText = document.getElementById('infoText');
            
            if (!theorem) {
                if (network) {
                    network.destroy();
                    network = null;
                }
                infoDiv.style.display = 'none';
                centralTheoremNode = null;
                // Clear proof modal when no theorem selected
                closeProofModal();
                updateProofDag(null);
                return;
            }
            
            // Set central theorem for auto-selection
            centralTheoremNode = theorem;
            
            // Show proof immediately (statement and proof text)
            showProof(theorem);
            updateProofDag(theorem);

            // Fetch ego network data with current distance
            fetch(`/api/ego/${encodeURIComponent(theorem)}/${currentDistance}`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    if (!data.success) {
                        console.error('API error:', data.error || 'Unknown error');
                        alert('Error loading network data: ' + (data.error || 'Unknown error'));
                        return;
                    }
                    
                    if (!data.network || !data.network.nodes || !data.network.edges) {
                        console.error('Invalid network data structure:', data);
                        alert('Error: Invalid network data structure');
                        return;
                    }
                    
                    // Use nodes with fixed positions from NetworkX layout
                    const nodes = new vis.DataSet(data.network.nodes);
                    const edges = new vis.DataSet(data.network.edges);
                    
                    currentNodeDataSet = new vis.DataSet(nodes.get());

                    const container = document.getElementById('network');
                    if (network) { network.destroy(); }

                    const options = {
                        nodes: {
                            shape: "dot",
                            font: { color: "#FFFFFF", size: 13, face: "Inter, Arial, sans-serif", strokeWidth: 0 },
                        },
                        edges: {
                            arrows: { to: { enabled: true, scaleFactor: 0.56, type: 'arrow' } },
                            smooth: { type: 'straight', roundness: 0 },
                            color: { color: 'rgba(255,255,255,0.5)', highlight: 'rgba(255,255,255,0.8)' },
                            width: 1.5,
                        },
                        layout: { hierarchical: { enabled: false } },
                        physics: { enabled: false },
                        interaction: { hover: true, tooltipDelay: 100, zoomView: true, dragView: true, hoverConnectedEdges: false },
                    };

                    network = new vis.Network(container, {nodes: currentNodeDataSet, edges}, options);

                    centralTheoremNode = theorem;
                    showProof(centralTheoremNode);
                    updateFocusedNode(centralTheoremNode);
                    setTimeout(() => network.fit({ animation: false }), 100);

                    network.on("hoverNode", function(params) {
                        hoveredNodeId = params.node;
                        updateFocusedNode(params.node);
                        showProof(params.node);
                    });
                    network.on("blurNode", function(params) {
                        if (params.node !== centralTheoremNode) {
                            hoveredNodeId = centralTheoremNode;
                            updateFocusedNode(centralTheoremNode);
                            showProof(centralTheoremNode);
                        }
                    });
                    network.on("click", function(params) {
                        if (params.nodes.length > 0) {
                            const nodeId = params.nodes[0];
                            centralTheoremNode = nodeId;
                            showProof(nodeId);
                            hoveredNodeId = nodeId;
                            updateFocusedNode(nodeId);
                        }
                    });
                    
                    // Update info
                    let distanceText = '';
                    if (currentDistance === 1) {
                        distanceText = ' (DISTANCE 1)';
                        infoText.innerHTML = `
                            PARENTS (D1): <strong>${data.network.num_parents}</strong> | 
                            CHILDREN (D1): <strong>${data.network.num_children}</strong> | 
                            BYPASS EDGES: <strong>${data.network.num_bypass_edges}</strong> | 
                            TOTAL NODES: <strong>${data.network.nodes.length}</strong> | 
                            TOTAL EDGES: <strong>${data.network.edges.length}</strong>${distanceText}
                        `;
                    } else if (currentDistance === 2) {
                        distanceText = ' (DISTANCE 2)';
                        const parents2 = data.network.num_parents2 || 0;
                        const children2 = data.network.num_children2 || 0;
                        infoText.innerHTML = `
                            PARENTS (D1): <strong>${data.network.num_parents}</strong> | 
                            PARENTS (D2): <strong>${parents2}</strong> | 
                            CHILDREN (D1): <strong>${data.network.num_children}</strong> | 
                            CHILDREN (D2): <strong>${children2}</strong> | 
                            TOTAL NODES: <strong>${data.network.nodes.length}</strong> | 
                            TOTAL EDGES: <strong>${data.network.edges.length}</strong>${distanceText}
                        `;
                    } else {
                        distanceText = ' (DISTANCE 3)';
                        const parents2 = data.network.num_parents2 || 0;
                        const children2 = data.network.num_children2 || 0;
                        const parents3 = data.network.num_parents3 || 0;
                        const children3 = data.network.num_children3 || 0;
                        infoText.innerHTML = `
                            PARENTS (D1): <strong>${data.network.num_parents}</strong> | 
                            PARENTS (D2): <strong>${parents2}</strong> | 
                            PARENTS (D3): <strong>${parents3}</strong> | 
                            CHILDREN (D1): <strong>${data.network.num_children}</strong> | 
                            CHILDREN (D2): <strong>${children2}</strong> | 
                            CHILDREN (D3): <strong>${children3}</strong> | 
                            TOTAL NODES: <strong>${data.network.nodes.length}</strong> | 
                            TOTAL EDGES: <strong>${data.network.edges.length}</strong>${distanceText}
                        `;
                    }
                    infoDiv.style.display = 'block';
                })
                .catch(error => {
                    console.error('Error loading network data:', error);
                    alert('Error loading network data: ' + error.message);
                });
        }
        
        function updateFocusedNode(nodeId) {
            const el = document.getElementById('focusedNodeName');
            if (!el) return;
            el.textContent = nodeId || '--';
            el.style.color = '#FFFFFF';
        }

        function updateProofDag(theorem) {
            const container = document.getElementById('proofDagNetwork');
            const labelEl = document.getElementById('proofDagLabel');
            if (!container) return;

            if (!theorem) {
                if (proofDagNetwork) { proofDagNetwork.destroy(); proofDagNetwork = null; }
                if (labelEl) labelEl.textContent = 'Proof DAG';
                container.innerHTML = '';
                return;
            }

            if (labelEl) labelEl.textContent = 'LOADING...';

            fetch(`/api/proof-dag/${encodeURIComponent(theorem)}`)
                .then(r => r.json())
                .then(data => {
                    if (proofDagNetwork) { proofDagNetwork.destroy(); proofDagNetwork = null; }

                    if (!data.success) {
                        if (labelEl) labelEl.textContent = 'Proof DAG  |  N/A';
                        container.innerHTML = '<div style="color:#333;font-size:10px;padding:20px;font-family:Courier New;">no tactic proof</div>';
                        return;
                    }

                    const stats = `N${data.dag.num_states} E${data.dag.num_tactics}`;
                    if (labelEl) labelEl.textContent = `Proof DAG  |  ${stats}`;

                    const nodes = new vis.DataSet(data.dag.nodes);
                    const edges = new vis.DataSet(data.dag.edges);

                    proofDagNetwork = new vis.Network(container, {nodes, edges}, {
                        nodes: {
                            shape: 'box',
                            margin: { top: 4, bottom: 4, left: 6, right: 6 },
                            widthConstraint: { maximum: 55 },
                            heightConstraint: { maximum: 25 },
                            font: { color: '#FFFFFF', strokeWidth: 0 },
                        },
                        edges: {
                            smooth: { type: 'cubicBezier' },
                            arrows: { to: { enabled: true, scaleFactor: 0.4 } },
                            width: 1.5,
                            font: { color: '#FFFFFF', strokeWidth: 0, size: 11, align: 'horizontal' },
                        },
                        layout: { hierarchical: { enabled: false } },
                        physics: { enabled: false },
                        interaction: { hover: true, tooltipDelay: 100, zoomView: true, dragView: true }
                    });
                    setTimeout(() => proofDagNetwork.fit({ animation: false }), 80);
                })
                .catch(err => {
                    if (labelEl) labelEl.textContent = 'Proof DAG  |  ERROR';
                    console.error('Error loading proof DAG:', err);
                });
        }
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """Serve the main HTML dashboard."""
    return render_template_string(HTML_TEMPLATE)


def get_sorted_theorems():
    """Helper function to get sorted theorem list."""
    # Sort theorems: those with children first, then alphabetically
    if G_original and ego_network_data:
        Out = {n: set(G_original.successors(n)) for n in G_original.nodes()}
        theorems_with_children = [t for t in theorems_list if len(Out.get(t, [])) > 0]
        theorems_without_children = [t for t in theorems_list if len(Out.get(t, [])) == 0]
        
        # Sort each group alphabetically
        theorems_with_children.sort(key=lambda x: x.split('.')[-1] if '.' in x else x)
        theorems_without_children.sort(key=lambda x: x.split('.')[-1] if '.' in x else x)
        
        # Combine: theorems with children first
        theorems_sorted = theorems_with_children + theorems_without_children
    else:
        theorems_sorted = sorted(theorems_list, key=lambda x: x.split('.')[-1] if '.' in x else x)
    
    return theorems_sorted


@app.route('/api/theorems')
def get_theorems():
    """API endpoint to get list of all theorems."""
    theorems_sorted = get_sorted_theorems()
    return jsonify({"theorems": theorems_sorted})


@app.route('/api/theorem/random')
def get_random_theorem():
    """API endpoint to get a random theorem."""
    import random
    theorems_sorted = get_sorted_theorems()
    if theorems_sorted:
        random_theorem = random.choice(theorems_sorted)
        return jsonify({"success": True, "theorem": random_theorem})
    else:
        return jsonify({"success": False, "error": "No theorems available"})


@app.route('/api/theorem/<theorem>/next')
def get_next_theorem(theorem):
    """API endpoint to get next theorem in sequence."""
    theorems_sorted = get_sorted_theorems()
    try:
        index = theorems_sorted.index(theorem)
        next_index = (index + 1) % len(theorems_sorted)
        return jsonify({"success": True, "theorem": theorems_sorted[next_index]})
    except ValueError:
        return jsonify({"success": False, "error": "Theorem not found"})


@app.route('/api/theorem/<theorem>/prev')
def get_prev_theorem(theorem):
    """API endpoint to get previous theorem in sequence."""
    theorems_sorted = get_sorted_theorems()
    try:
        index = theorems_sorted.index(theorem)
        prev_index = (index - 1) % len(theorems_sorted)
        return jsonify({"success": True, "theorem": theorems_sorted[prev_index]})
    except ValueError:
        return jsonify({"success": False, "error": "Theorem not found"})


@app.route('/api/ego/<theorem>')
def get_ego_network(theorem):
    """API endpoint to get ego network data for a specific theorem."""
    return get_ego_network_with_distance(theorem, distance=1)

@app.route('/api/ego/<theorem>/<int:distance>')
def get_ego_network_with_distance(theorem, distance=1):
    """API endpoint to get ego network data for a specific theorem with specified distance."""
    if not G_original:
        return jsonify({"success": False, "error": "Graph not loaded"})
    
    if theorem not in G_original:
        return jsonify({"success": False, "error": "Theorem not found"})
    
    # Generate ego network for requested distance
    if distance == 1:
        # Use cached data if available
        if theorem in ego_network_data:
            network_data = format_ego_network_for_vis(theorem, G_original, ego_network_data, distance=1)
        else:
            network_data = generate_ego_network_for_theorem(theorem, G_original, distance=1)
    else:
        # Generate distance-2 network on the fly
        network_data = generate_ego_network_for_theorem(theorem, G_original, distance=distance)
    
    if network_data is None:
        return jsonify({"success": False, "error": "Failed to format network data"})
    
    return jsonify({"success": True, "network": network_data})


@app.route('/api/theorem/<theorem>')
def get_theorem_proof(theorem):
    """API endpoint to get theorem proof from traced_theorems_unified_v2.jsonl (preferred) or corpus."""
    # Priority 1: Check traced_theorems_unified_v2.jsonl (has original proof_text)
    if traced_theorems_index and theorem in traced_theorems_index:
        entry = traced_theorems_index[theorem]
        return jsonify({
            "success": True,
            "statement": entry.get("statement", ""),
            "proof_text": entry.get("proof_text", ""),
            "code": entry.get("proof_text", ""),  # For compatibility
            "proof_type": entry.get("proof_type", "tactic")
        })
    
    # Priority 2: Fall back to corpus_code_index.json
    if corpus_code_index and theorem in corpus_code_index:
        code = corpus_code_index[theorem]
        
        # Try to extract statement from code (basic parsing)
        statement = ""
        if code.startswith("theorem"):
            # Extract statement part (everything before :=)
            parts = code.split(":=", 1)
            if len(parts) > 0:
                statement = parts[0].strip()
        elif code.startswith("def"):
            parts = code.split(":=", 1)
            if len(parts) > 0:
                statement = parts[0].strip()
        elif code.startswith("class"):
            parts = code.split("where", 1)
            if len(parts) > 0:
                statement = parts[0].strip()
        
        return jsonify({
            "success": True,
            "statement": statement,
            "proof_text": code,  # Full code including proof
            "code": code,
            "proof_type": "corpus"  # Indicates it's from corpus
        })
    
    # Not found in either source
    return jsonify({"success": False, "error": f"Theorem '{theorem}' not found in traced theorems or corpus"})


@app.route('/api/download-proofs/<theorem>/<int:distance>')
def download_proofs(theorem, distance):
    """API endpoint to download all proofs from ego network as markdown."""
    from flask import Response
    
    if not G_original:
        return jsonify({"success": False, "error": "Graph not loaded"}), 500
    
    if theorem not in G_original:
        return jsonify({"success": False, "error": "Theorem not found"}), 404
    
    if not traced_theorems_index and not corpus_code_index:
        return jsonify({"success": False, "error": "Neither traced theorems nor corpus code index loaded"}), 500
    
    # Generate ego network to get all nodes
    network_data = generate_ego_network_for_theorem(theorem, G_original, distance=distance)
    
    if network_data is None:
        return jsonify({"success": False, "error": "Failed to generate network data"}), 500
    
    # Extract all unique node IDs from the network
    nodes = network_data.get("nodes", [])
    node_ids = set()
    for node in nodes:
        node_id = node.get("id") or node.get("label")
        if node_id:
            node_ids.add(node_id)
    
    # Sort nodes for consistent output
    sorted_nodes = sorted(node_ids)
    
    # Build markdown content
    md_lines = []
    md_lines.append(f"# Ego Network Proofs: {theorem}")
    md_lines.append("")
    md_lines.append(f"**Distance Level:** {distance}")
    md_lines.append(f"**Total Nodes:** {len(sorted_nodes)}")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")
    
    # Add proof for each node
    for i, node_id in enumerate(sorted_nodes, 1):
        md_lines.append(f"## {i}. {node_id}")
        md_lines.append("")
        
        # Priority 1: Get proof from traced_theorems_unified_v2.jsonl (original proof_text)
        proof_text = ""
        statement = ""
        source = "none"
        
        if traced_theorems_index and node_id in traced_theorems_index:
            entry = traced_theorems_index[node_id]
            proof_text = entry.get("proof_text", "")
            statement = entry.get("statement", "")
            source = "traced"
        elif corpus_code_index and node_id in corpus_code_index:
            proof_text = corpus_code_index[node_id]
            source = "corpus"
        
        if proof_text:
            # Add statement if available
            if statement:
                md_lines.append(f"**Statement:** `{statement}`")
                md_lines.append("")
            md_lines.append("```lean")
            md_lines.append(proof_text)
            md_lines.append("```")
            if source == "traced":
                md_lines.append("")
                md_lines.append("*Source: traced_theorems_unified_v2.jsonl (original proof)*")
        else:
            md_lines.append("*Proof not available*")
        
        md_lines.append("")
        md_lines.append("---")
        md_lines.append("")
    
    # Convert to string
    md_content = "\n".join(md_lines)
    
    # Create response with proper headers for file download
    response = Response(
        md_content,
        mimetype='text/markdown',
        headers={
            'Content-Disposition': f'attachment; filename="{theorem.replace(".", "_").replace("/", "_")}_distance{distance}_proofs.md"'
        }
    )
    
    return response


def generate_ego_network_for_theorem(theorem, G, distance=1):
    """Generate ego network data for a theorem with specified distance."""
    Out = {n: set(G.successors(n)) for n in G.nodes()}
    In = {n: set(G.predecessors(n)) for n in G.nodes()}
    all_edges_set = set(G.edges())
    
    if distance == 1:
        # Standard 1-hop ego network
        parents = set(In[theorem])
        children = set(Out[theorem])
        ego_nodes = set([theorem])
        ego_nodes.update(parents)
        ego_nodes.update(children)
        
        # Collect ALL edges between any ego nodes (complete subgraph)
        edges = []
        for u in ego_nodes:
            for v in ego_nodes:
                if (u, v) in all_edges_set and u != v:
                    edges.append({"from": u, "to": v})
        
        num_parents = len(parents)  # Direct parents (distance 1)
        num_children = len(children)  # Direct children (distance 1)
        # Count bypass edges (parent->child edges that skip the central theorem)
        num_bypass = sum(1 for p in parents for c in children if (p, c) in all_edges_set)
    elif distance == 2:
        # Distance-2: include parents of parents and children of children
        parents = set(In[theorem])
        children = set(Out[theorem])
        
        # Parents of parents (distance 2 upstream)
        parents2 = set()
        for p in parents:
            parents2.update(In[p])
        parents2.discard(theorem)  # Remove self
        
        # Children of children (distance 2 downstream)
        children2 = set()
        for c in children:
            children2.update(Out[c])
        children2.discard(theorem)  # Remove self
        # Exclude nodes that are already in parents, children, or parents2 (they're distance 1 or 2 upstream)
        children2 = children2 - parents - children - parents2
        
        ego_nodes = set([theorem])
        ego_nodes.update(parents)
        ego_nodes.update(children)
        ego_nodes.update(parents2)
        ego_nodes.update(children2)
        
        # Collect ALL edges between any ego nodes (cross-connections)
        edges = []
        for u in ego_nodes:
            for v in ego_nodes:
                if (u, v) in all_edges_set and u != v:
                    edges.append({"from": u, "to": v})
        
        num_parents = len(parents)  # Direct parents (distance 1)
        num_children = len(children)  # Direct children (distance 1)
        num_parents2 = len(parents2)  # Grandparents (distance 2 upstream)
        num_children2 = len(children2)  # Grandchildren (distance 2 downstream)
        num_bypass = 0  # Not meaningful for distance 2
    else:
        # Distance 3: include up to 3 hops
        parents = set(In[theorem])
        children = set(Out[theorem])
        
        # Parents of parents (distance 2 upstream)
        parents2 = set()
        for p in parents:
            parents2.update(In[p])
        parents2.discard(theorem)
        
        # Parents of parents2 (distance 3 upstream)
        parents3 = set()
        for p2 in parents2:
            parents3.update(In[p2])
        parents3.discard(theorem)
        parents3 = parents3 - parents - parents2  # Exclude already counted
        
        # Children of children (distance 2 downstream)
        children2 = set()
        for c in children:
            children2.update(Out[c])
        children2.discard(theorem)
        children2 = children2 - parents - children - parents2 - parents3
        
        # Children of children2 (distance 3 downstream)
        children3 = set()
        for c2 in children2:
            children3.update(Out[c2])
        children3.discard(theorem)
        children3 = children3 - parents - children - parents2 - parents3 - children2
        
        ego_nodes = set([theorem])
        ego_nodes.update(parents)
        ego_nodes.update(children)
        ego_nodes.update(parents2)
        ego_nodes.update(children2)
        ego_nodes.update(parents3)
        ego_nodes.update(children3)
        
        # Collect ALL edges between any ego nodes
        edges = []
        for u in ego_nodes:
            for v in ego_nodes:
                if (u, v) in all_edges_set and u != v:
                    edges.append({"from": u, "to": v})
        
        num_parents = len(parents)
        num_children = len(children)
        num_parents2 = len(parents2)
        num_children2 = len(children2)
        num_parents3 = len(parents3)
        num_children3 = len(children3)
        num_bypass = 0
    
    # Filter nodes and edges based on distance before building layout
    if distance == 1:
        # For distance 1, only include: theorem, parents, children
        filtered_nodes = set([theorem])
        filtered_nodes.update(parents)
        filtered_nodes.update(children)
        # Filter edges to only include edges between filtered nodes
        filtered_edges = [e for e in edges if e["from"] in filtered_nodes and e["to"] in filtered_nodes]
    elif distance == 2:
        # For distance 2, include: theorem, parents, children, parents2, children2
        filtered_nodes = set([theorem])
        filtered_nodes.update(parents)
        filtered_nodes.update(children)
        filtered_nodes.update(parents2)
        filtered_nodes.update(children2)
        filtered_edges = [e for e in edges if e["from"] in filtered_nodes and e["to"] in filtered_nodes]
    else:
        # For distance 3, include all nodes
        filtered_nodes = ego_nodes
        filtered_edges = edges
    
    # Build NetworkX subgraph for layout computation (using filtered nodes/edges)
    ego_subgraph = nx.DiGraph()
    ego_subgraph.add_nodes_from(filtered_nodes)
    for edge in filtered_edges:
        ego_subgraph.add_edge(edge["from"], edge["to"])
    
    # Compute x-coordinates using NetworkX layout (using filtered nodes)
    if len(filtered_nodes) > 1:
        try:
            # Use spring_layout to bring connected nodes closer horizontally
            pos = nx.spring_layout(ego_subgraph, k=1.5, iterations=50, seed=42)
        except:
            # Fallback to circular layout if spring_layout fails
            pos = nx.circular_layout(ego_subgraph)
    else:
        pos = {list(filtered_nodes)[0]: (0, 0)} if filtered_nodes else {}
    
    # Group nodes by level for y-coordinate computation (using filtered nodes)
    nodes_by_level = {}
    for node in filtered_nodes:
        if node == theorem:
            level = 2  # Central node
        elif distance == 1:
            if node in parents:
                level = 1  # Parents
            else:
                level = 3  # Children
        elif distance == 2:
            # Distance 2: 5 levels
            if node in parents2:
                level = 0  # Grandparents
            elif node in parents:
                level = 1  # Parents
            elif node in children:
                level = 3  # Children
            else:  # children2
                level = 4  # Grandchildren
        else:
            # Distance 3: 7 levels
            if node in parents3:
                level = -1  # Great-grandparents
            elif node in parents2:
                level = 0  # Grandparents
            elif node in parents:
                level = 1  # Parents
            elif node in children:
                level = 3  # Children
            elif node in children2:
                level = 4  # Grandchildren
            else:  # children3
                level = 5  # Great-grandchildren
        
        if level not in nodes_by_level:
            nodes_by_level[level] = []
        nodes_by_level[level].append(node)
    
    # Compute y-coordinates: base y per level + slight staggering within level
    # Ensure levels never overlap by using larger separation
    if distance == 1:
        level_y_base = {1: -150, 2: 0, 3: 150}  # Base y positions for distance 1
        level_separation = 150
    elif distance == 2:
        level_y_base = {0: -200, 1: -100, 2: 0, 3: 100, 4: 200}
        level_separation = 100
    else:  # distance 3
        level_y_base = {-1: -300, 0: -200, 1: -100, 2: 0, 3: 100, 4: 200, 5: 300}
        level_separation = 100
    
    level_y_spacing = 15  # Vertical stagger spacing within level (smaller than level separation)
    node_positions = {}
    
    for level, nodes_at_level in nodes_by_level.items():
        base_y = level_y_base.get(level, 0)
        n_at_level = len(nodes_at_level)
        for idx, node in enumerate(nodes_at_level):
            # Stagger: alternate vertical offset within level, centered around base_y
            if n_at_level == 1:
                stagger_offset = 0
            else:
                # Simple alternating pattern: even indices slightly up, odd indices slightly down
                if idx % 2 == 0:
                    stagger_offset = (idx // 2) * level_y_spacing
                else:
                    stagger_offset = -((idx + 1) // 2) * level_y_spacing
                # Center the stagger around base_y
                if n_at_level > 1:
                    max_offset = ((n_at_level - 1) // 2) * level_y_spacing
                    if max_offset > 0:
                        # Adjust to center around 0
                        if idx % 2 == 0:
                            stagger_offset = stagger_offset - max_offset / 2
                        else:
                            stagger_offset = stagger_offset + max_offset / 2
            node_positions[node] = {
                'x': pos[node][0] * 300 if node in pos else 0,  # Scale x-coordinates more (use more horizontal space)
                'y': base_y + stagger_offset
            }
    
    # Compute level_y_positions for separator lines
    level_y_positions = {}
    min_level = min(nodes_by_level.keys()) if nodes_by_level else 2
    max_level = max(nodes_by_level.keys()) if nodes_by_level else 2
    
    for level in range(min_level, max_level + 1):
        if level not in nodes_by_level:
            continue
        n_at_level = len(nodes_by_level[level])
        max_stagger = ((n_at_level - 1) // 2) * level_y_spacing if n_at_level > 1 else 0
        base_y = level_y_base.get(level, 0)
        level_y_positions[level] = {
            'base': base_y,
            'min_y': base_y - max_stagger - 15,
            'max_y': base_y + max_stagger + 15
        }
    
    # Create node data with fixed positions (using filtered nodes)
    nodes = []
    for node in filtered_nodes:
        short_name = node.split('.')[-1] if '.' in node else node[:50]
        node_type = G.nodes[node].get("node_type", "unknown")
        
        # Determine topological level
        if node == theorem:
            level = 2  # Central node
        elif distance == 1:
            if node in parents:
                level = 1  # Parents
            else:
                level = 3  # Children
        elif distance == 2:
            # Distance 2: 5 levels
            if node in parents2:
                level = 0  # Grandparents
            elif node in parents:
                level = 1  # Parents
            elif node in children:
                level = 3  # Children
            else:  # children2
                level = 4  # Grandchildren
        else:
            # Distance 3: 7 levels
            if node in parents3:
                level = -1  # Great-grandparents
            elif node in parents2:
                level = 0  # Grandparents
            elif node in parents:
                level = 1  # Parents
            elif node in children:
                level = 3  # Children
            elif node in children2:
                level = 4  # Grandchildren
            else:  # children3
                level = 5  # Great-grandchildren
        
        # Brutalist dark theme - box shape matching within-proof DAG
        if node == theorem:
            color = "#FFFFFF"
            border_color = "#FFFFFF"
            border_width = 3
        else:
            color = "#000000"
            border_color = "#FFFFFF"
            border_width = 2

        node_data = {
            "id": node,
            "label": short_name,
            "title": node,
            "color": {"background": color, "border": border_color},
            "shape": "dot",
            "size": 10 if node == theorem else 5,
            "font": {"color": "#FFFFFF", "size": 13, "face": "Inter, Arial, sans-serif", "strokeWidth": 0},
            "borderWidth": border_width,
            "level": level,
            "x": node_positions[node]["x"],
            "y": node_positions[node]["y"],
            "fixed": {"x": True, "y": True},
        }
        nodes.append(node_data)
    
    if distance == 1:
        return {
            "nodes": nodes,
            "edges": filtered_edges,
            "level_y_positions": level_y_positions,  # For drawing separator lines
            "num_parents": num_parents,
            "num_children": num_children,
            "num_bypass_edges": num_bypass
        }
    elif distance == 2:
        return {
            "nodes": nodes,
            "edges": filtered_edges,
            "level_y_positions": level_y_positions,  # For drawing separator lines
            "num_parents": num_parents,
            "num_children": num_children,
            "num_parents2": num_parents2,
            "num_children2": num_children2,
            "num_bypass_edges": num_bypass
        }
    else:  # distance 3
        return {
            "nodes": nodes,
            "edges": filtered_edges,
            "level_y_positions": level_y_positions,  # For drawing separator lines
            "num_parents": num_parents,
            "num_children": num_children,
            "num_parents2": num_parents2,
            "num_children2": num_children2,
            "num_parents3": num_parents3,
            "num_children3": num_children3,
            "num_bypass_edges": num_bypass
        }


@app.route('/api/proof-dag/<path:theorem>')
def get_proof_dag(theorem):
    """API endpoint to get within-proof DAG for a theorem."""
    if not theorem_byte_offsets:
        return jsonify({"success": False, "error": "Proof DAG index not available"})
    if theorem not in theorem_byte_offsets:
        return jsonify({"success": False, "error": "Theorem not found or has no tactic proof"})
    try:
        offset = theorem_byte_offsets[theorem]
        source = APP_NETWORK_DATA if APP_NETWORK_DATA.exists() else TRACED_THEOREMS_FILE
        with open(source, "rb") as f:
            f.seek(offset)
            raw_line = f.readline()
        entry = json.loads(raw_line.decode("utf-8"))
        dag = build_proof_dag_for_vis(entry)
        if dag is None:
            return jsonify({"success": False, "error": "No tactics found in proof"})
        return jsonify({"success": True, "dag": dag})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/lib/<path:filename>')
def serve_lib(filename):
    """Serve vis-network library files."""
    return send_from_directory(str(LIB_DIR), filename)


if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("Starting ego network dashboard server...")
    print("=" * 80)
    print(f"  Server will be available at: http://localhost:5000")
    print(f"  Press Ctrl+C to stop the server")
    print("=" * 80 + "\n")
    app.run(debug=False, host='0.0.0.0', port=7860)
