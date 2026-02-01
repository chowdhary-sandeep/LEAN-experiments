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
    print(f"  Loaded {len(theorems_list):,} theorems")
except Exception as e:
    print(f"Error loading cache: {e}")
    G_original = None
    ego_network_data = {}
    theorems_list = []


def format_ego_network_for_vis(theorem, G, ego_data):
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
    
    # Create node data
    nodes = []
    for node in ego_nodes:
        short_name = node.split('.')[-1] if '.' in node else node[:50]
        node_type = G.nodes[node].get("node_type", "unknown")
        
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
                "size": 14 if node == theorem else 12,
                "color": "#000000" if color == "#FFFFFF" else "#FFFFFF"
            },
            "borderWidth": 3
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
            padding: 20px;
            font-size: 14px;
        }
        .container {
            max-width: 1600px;
            margin: 0 auto;
            border: 4px solid #FFFFFF;
            padding: 20px;
            background: #000000;
        }
        h1 {
            font-size: 32px;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 4px;
            margin-bottom: 20px;
            border-bottom: 4px solid #FFFFFF;
            padding-bottom: 10px;
        }
        .controls {
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 15px;
            flex-wrap: wrap;
        }
        label {
            font-weight: bold;
            font-size: 16px;
            text-transform: uppercase;
        }
        select {
            padding: 10px 15px;
            font-size: 14px;
            font-family: 'Courier New', monospace;
            background: #000000;
            color: #FFFFFF;
            border: 3px solid #FFFFFF;
            min-width: 400px;
            cursor: pointer;
        }
        select:focus {
            outline: none;
            border-color: #FFFFFF;
        }
        .info {
            background: #FFFFFF;
            color: #000000;
            padding: 15px;
            margin-bottom: 20px;
            border: 3px solid #000000;
            font-weight: bold;
        }
        .info strong {
            text-transform: uppercase;
        }
        #network {
            width: 100%;
            height: 800px;
            border: 4px solid #FFFFFF;
            background: #000000;
        }
        .legend {
            margin-top: 20px;
            padding: 15px;
            border: 3px solid #FFFFFF;
            background: #000000;
        }
        .legend-title {
            font-weight: bold;
            font-size: 16px;
            text-transform: uppercase;
            margin-bottom: 10px;
            border-bottom: 2px solid #FFFFFF;
            padding-bottom: 5px;
        }
        .legend-item {
            display: inline-block;
            margin-right: 30px;
            margin-top: 10px;
        }
        .legend-color {
            display: inline-block;
            width: 30px;
            height: 30px;
            border: 3px solid #FFFFFF;
            margin-right: 8px;
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
            
            // Fetch ego network data
            fetch(`/api/ego/${encodeURIComponent(theorem)}`)
                .then(response => response.json())
                .then(data => {
                    if (!data.success) {
                        alert('Error loading network data');
                        return;
                    }
                    
                    const nodes = new vis.DataSet(data.network.nodes);
                    const edges = new vis.DataSet(data.network.edges);
                    
                    const container = document.getElementById('network');
                    
                    if (network) {
                        network.destroy();
                    }
                    
                    const options = {
                        nodes: {
                            borderWidth: 3,
                            shadow: false,
                            font: {
                                size: 12,
                                face: 'Courier New'
                            }
                        },
                        edges: {
                            arrows: {
                                to: {
                                    enabled: true,
                                    scaleFactor: 1.0,
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
                            width: 2
                        },
                        layout: {
                            hierarchical: {
                                enabled: true,
                                direction: 'UD',
                                sortMethod: 'directed',
                                levelSeparation: 200,
                                nodeSpacing: 250,
                                treeSpacing: 300
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
                    infoText.innerHTML = `
                        PARENTS: <strong>${data.network.num_parents}</strong> | 
                        CHILDREN: <strong>${data.network.num_children}</strong> | 
                        BYPASS EDGES: <strong>${data.network.num_bypass_edges}</strong> | 
                        TOTAL NODES: <strong>${data.network.nodes.length}</strong> | 
                        TOTAL EDGES: <strong>${data.network.edges.length}</strong>
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
    theorems_sorted = sorted(theorems_list, key=lambda x: x.split('.')[-1] if '.' in x else x)
    return jsonify({"theorems": theorems_sorted})


@app.route('/api/ego/<theorem>')
def get_ego_network(theorem):
    """API endpoint to get ego network data for a specific theorem."""
    if not G_original or theorem not in ego_network_data:
        return jsonify({"success": False, "error": "Theorem not found"})
    
    network_data = format_ego_network_for_vis(theorem, G_original, ego_network_data)
    if network_data is None:
        return jsonify({"success": False, "error": "Failed to format network data"})
    
    return jsonify({"success": True, "network": network_data})


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
