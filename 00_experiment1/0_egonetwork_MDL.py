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

# Configuration
_SCRIPT_DIR = Path(__file__).resolve().parent
CACHE_DIR = _SCRIPT_DIR / "cache"
CACHE_BUNDLE = CACHE_DIR / "bundle.pkl"
LIB_DIR = _SCRIPT_DIR.parent / "lib" / "vis-9.1.2"

app = Flask(__name__)

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
except Exception as e:
    print(f"Error loading cache: {e}")
    import traceback
    traceback.print_exc()
    G_original = None
    ego_network_data = {}
    theorems_list = []


def format_ego_network_for_vis(theorem, G, ego_data, distance=1):
    """Format ego network data for vis-network visualization."""
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
    
    # Create node data with topological levels
    nodes = []
    for node in ego_nodes:
        short_name = node.split('.')[-1] if '.' in node else node[:50]
        node_type = G.nodes[node].get("node_type", "unknown")
        
        # Determine topological level for staggering
        if node == theorem:
            level = 2  # Central node
        elif node in parents:
            level = 1  # Parents
        else:
            level = 3  # Children
        
        # Brutalist dark theme: black/white only
        if node == theorem:
            color = "#FFFFFF"  # White for central theorem
            border_color = "#000000"
            shape = "box"
        elif node_type == "premise":
            color = "#000000"  # Black for premises
            border_color = "#FFFFFF"
            shape = "ellipse"
        else:  # child theorem
            color = "#FFFFFF"  # White for child theorems
            border_color = "#000000"
            shape = "ellipse"
        
        nodes.append({
            "id": node,
            "label": short_name,
            "title": node,
            "color": {
                "background": color,
                "border": border_color
            },
            "shape": shape,
            "font": {
                "size": 11 if node == theorem else 10,
                "color": "#000000" if color == "#FFFFFF" else "#FFFFFF"
            },
            "borderWidth": 2,
            "level": level
        })
    
    return {
        "nodes": nodes,
        "edges": edges,
        "num_parents": data["num_parents"],
        "num_children": data["num_children"],
        "num_bypass_edges": data["num_bypass_edges"]
    }


# HTML template with brutalist dark theme
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>THEOREM EGO NETWORK</title>
    <script type="text/javascript" src="/lib/vis-network.min.js"></script>
    <link href="/lib/vis-network.css" rel="stylesheet" type="text/css" />
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Courier New', monospace;
            background: #000000;
            color: #FFFFFF;
            padding: 10px;
            font-size: 12px;
            margin: 0;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            border: 2px solid #FFFFFF;
            padding: 10px;
            background: #000000;
        }
        h1 {
            font-size: 18px;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin: 0 0 10px 0;
            border-bottom: 2px solid #FFFFFF;
            padding-bottom: 5px;
        }
        .controls {
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }
        .toggle-button {
            padding: 5px 15px;
            font-size: 12px;
            font-family: 'Courier New', monospace;
            background: #000000;
            color: #FFFFFF;
            border: 2px solid #FFFFFF;
            cursor: pointer;
            text-transform: uppercase;
            font-weight: bold;
        }
        .toggle-button.active {
            background: #FFFFFF;
            color: #000000;
        }
        .toggle-button:hover {
            background: #FFFFFF;
            color: #000000;
        }
        label {
            font-weight: bold;
            font-size: 12px;
            text-transform: uppercase;
        }
        select {
            padding: 5px 10px;
            font-size: 12px;
            font-family: 'Courier New', monospace;
            background: #000000;
            color: #FFFFFF;
            border: 2px solid #FFFFFF;
            min-width: 300px;
            cursor: pointer;
        }
        select:focus {
            outline: none;
            border-color: #FFFFFF;
        }
        .info {
            background: #FFFFFF;
            color: #000000;
            padding: 8px;
            margin-bottom: 10px;
            border: 2px solid #000000;
            font-weight: bold;
            font-size: 11px;
        }
        .info strong {
            text-transform: uppercase;
        }
        .info.note {
            background: #000000;
            color: #FFFFFF;
            border: 2px solid #FFFFFF;
            font-size: 10px;
            font-weight: normal;
            padding: 6px;
        }
        #network {
            width: 100%;
            height: 500px;
            border: 2px solid #FFFFFF;
            background: #000000;
        }
        .legend {
            margin-top: 10px;
            padding: 8px;
            border: 2px solid #FFFFFF;
            background: #000000;
        }
        .legend-title {
            font-weight: bold;
            font-size: 11px;
            text-transform: uppercase;
            margin-bottom: 5px;
            border-bottom: 1px solid #FFFFFF;
            padding-bottom: 3px;
        }
        .legend-item {
            display: inline-block;
            margin-right: 20px;
            margin-top: 5px;
            font-size: 10px;
        }
        .legend-color {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid #FFFFFF;
            margin-right: 5px;
            vertical-align: middle;
        }
        .legend-text {
            font-weight: bold;
            text-transform: uppercase;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>THEOREM EGO NETWORK</h1>
        
        <div class="controls">
            <label for="theoremSelect">SELECT THEOREM:</label>
            <select id="theoremSelect" onchange="updateNetwork()">
                <option value="">-- SELECT --</option>
            </select>
            <button id="distanceToggle" class="toggle-button active" onclick="toggleDistance()">DISTANCE 2</button>
        </div>
        
        <div class="info note" style="margin-bottom: 10px;">
            <strong>NOTE:</strong> Most theorems (88%) are leaf nodes with no children. Theorems with children are listed first in the dropdown.
        </div>
        
        <div class="info" id="networkInfo" style="display: none;">
            <strong>NETWORK STATISTICS:</strong>
            <span id="infoText"></span>
        </div>
        
        <div id="network"></div>
        
        <div class="legend">
            <div class="legend-title">LEGEND</div>
            <span class="legend-item">
                <span class="legend-color" style="background: #FFFFFF; border-color: #000000;"></span>
                <span class="legend-text">CENTRAL THEOREM</span>
            </span>
            <span class="legend-item">
                <span class="legend-color" style="background: #000000; border-color: #FFFFFF;"></span>
                <span class="legend-text">PREMISE (PARENT)</span>
            </span>
            <span class="legend-item">
                <span class="legend-color" style="background: #FFFFFF; border-color: #000000;"></span>
                <span class="legend-text">THEOREM (CHILD)</span>
            </span>
            <span class="legend-item">
                <span style="color: #FFFFFF;">→</span>
                <span class="legend-text">DEPENDENCY EDGE</span>
            </span>
        </div>
    </div>
    
    <script type="text/javascript">
        let network = null;
        let allTheorems = [];
        let currentDistance = 2; // Default to distance 2
        
        // Load theorem list on page load
        fetch('/api/theorems')
            .then(response => response.json())
            .then(data => {
                allTheorems = data.theorems;
                const select = document.getElementById('theoremSelect');
                allTheorems.forEach(theorem => {
                    const shortName = theorem.split('.').pop() || theorem.substring(0, 60);
                    const option = document.createElement('option');
                    option.value = theorem;
                    option.textContent = shortName;
                    select.appendChild(option);
                });
            });
        
        function toggleDistance() {
            currentDistance = currentDistance === 1 ? 2 : 1;
            const button = document.getElementById('distanceToggle');
            button.textContent = `DISTANCE ${currentDistance}`;
            button.classList.toggle('active', currentDistance === 2);
            updateNetwork();
        }
        
        // Initialize button state on page load
        window.addEventListener('DOMContentLoaded', function() {
            const button = document.getElementById('distanceToggle');
            button.textContent = `DISTANCE ${currentDistance}`;
            button.classList.toggle('active', currentDistance === 2);
        });
        
        function updateNetwork() {
            const select = document.getElementById('theoremSelect');
            const theorem = select.value;
            const infoDiv = document.getElementById('networkInfo');
            const infoText = document.getElementById('infoText');
            
            if (!theorem) {
                if (network) {
                    network.destroy();
                    network = null;
                }
                infoDiv.style.display = 'none';
                return;
            }
            
            // Fetch ego network data with current distance
            fetch(`/api/ego/${encodeURIComponent(theorem)}/${currentDistance}`)
                .then(response => response.json())
                .then(data => {
                    if (!data.success) {
                        alert('Error loading network data');
                        return;
                    }
                    
                    // Process nodes: ensure level property is set for vis-network hierarchical layout
                    const processedNodes = data.network.nodes.map(node => {
                        const processedNode = {...node};
                        // vis-network hierarchical layout uses 'level' property
                        if (processedNode.level === undefined) {
                            processedNode.level = 2; // Default to central level
                        }
                        return processedNode;
                    });
                    
                    const nodes = new vis.DataSet(processedNodes);
                    const edges = new vis.DataSet(data.network.edges);
                    
                    const container = document.getElementById('network');
                    
                    if (network) {
                        network.destroy();
                    }
                    
                    const maxLevel = Math.max(...processedNodes.map(n => n.level || 2));
                    const levelSeparation = maxLevel > 3 ? 70 : 90;
                    
                    const options = {
                        nodes: {
                            borderWidth: 2,
                            shadow: false,
                            font: {
                                size: 10,
                                face: 'Courier New'
                            },
                            size: 18,
                            fixed: {
                                x: false,
                                y: false
                            }
                        },
                        edges: {
                            arrows: {
                                to: {
                                    enabled: true,
                                    scaleFactor: 0.7,
                                    type: 'arrow'
                                }
                            },
                            smooth: {
                                type: 'straight',
                                roundness: 0
                            },
                            color: {
                                color: '#FFFFFF',
                                highlight: '#FFFFFF'
                            },
                            width: 1.5
                        },
                        layout: {
                            hierarchical: {
                                enabled: true,
                                direction: 'UD',
                                sortMethod: 'directed',
                                levelSeparation: levelSeparation,
                                nodeSpacing: 60,
                                treeSpacing: 80,
                                blockShifting: true,
                                edgeMinimization: true,
                                parentCentralization: true,
                                shakeTowards: 'leaves'
                            }
                        },
                        physics: {
                            enabled: false
                        },
                        interaction: {
                            hover: true,
                            tooltipDelay: 100,
                            zoomView: true,
                            dragView: true
                        }
                    };
                    
                    network = new vis.Network(container, {nodes: nodes, edges: edges}, options);
                    
                    // Update info
                    const distanceText = currentDistance === 2 ? ' (DISTANCE 2)' : '';
                    infoText.innerHTML = `
                        PARENTS: <strong>${data.network.num_parents}</strong> | 
                        CHILDREN: <strong>${data.network.num_children}</strong> | 
                        BYPASS EDGES: <strong>${data.network.num_bypass_edges}</strong> | 
                        TOTAL NODES: <strong>${data.network.nodes.length}</strong> | 
                        TOTAL EDGES: <strong>${data.network.edges.length}</strong>${distanceText}
                    `;
                    infoDiv.style.display = 'block';
                    
                    network.once('stabilizationEnd', function() {
                        network.fit();
                    });
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Error loading network data');
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


@app.route('/api/theorems')
def get_theorems():
    """API endpoint to get list of all theorems."""
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
    
    return jsonify({"theorems": theorems_sorted})


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
        
        # Collect edges: parent->theorem, theorem->child, parent->child
        edges = []
        for p in parents:
            if (p, theorem) in all_edges_set:
                edges.append({"from": p, "to": theorem})
        for c in children:
            if (theorem, c) in all_edges_set:
                edges.append({"from": theorem, "to": c})
        for p in parents:
            for c in children:
                if (p, c) in all_edges_set:
                    edges.append({"from": p, "to": c})
        
        num_parents = len(parents)
        num_children = len(children)
        num_bypass = sum(1 for p in parents for c in children if (p, c) in all_edges_set)
    else:
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
        
        num_parents = len(parents)
        num_children = len(children)
        num_bypass = 0  # Not meaningful for distance 2
    
    # Create node data with topological levels for staggering
    nodes = []
    for node in ego_nodes:
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
        else:
            # Distance 2: 5 levels
            if node in parents2:
                level = 0  # Grandparents
            elif node in parents:
                level = 1  # Parents
            elif node in children:
                level = 3  # Children
            else:  # children2
                level = 4  # Grandchildren
        
        # Brutalist dark theme
        if node == theorem:
            color = "#FFFFFF"
            border_color = "#000000"
            shape = "box"
        elif node_type == "premise":
            color = "#000000"
            border_color = "#FFFFFF"
            shape = "ellipse"
        else:
            color = "#FFFFFF"
            border_color = "#000000"
            shape = "ellipse"
        
        nodes.append({
            "id": node,
            "label": short_name,
            "title": node,
            "color": {
                "background": color,
                "border": border_color
            },
            "shape": shape,
            "font": {
                "size": 11 if node == theorem else 10,
                "color": "#000000" if color == "#FFFFFF" else "#FFFFFF"
            },
            "borderWidth": 2,
            "level": level
        })
    
    return {
        "nodes": nodes,
        "edges": edges,
        "num_parents": num_parents,
        "num_children": num_children,
        "num_bypass_edges": num_bypass
    }


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
    app.run(debug=True, host='0.0.0.0', port=5000)
