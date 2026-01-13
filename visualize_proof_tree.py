"""
Visualize proof trees as interactive HTML graphs in a brutalist 4x4 grid.
"""

import json
from pathlib import Path
from collections import defaultdict, deque


def compute_tree_metrics(nodes, edges):
    """
    Compute various metrics for a proof tree.
    
    Returns:
        dict with metrics: depth, median_depth, max_width, width_at_half_depth,
        avg_out_degree, pct_leaves, spine_score, imbalance
    """
    if not nodes or not edges:
        return {
            'depth': 0, 'median_depth': 0, 'max_width': 0, 'width_at_half_depth': 0,
            'avg_out_degree': 0, 'pct_leaves': 0, 'spine_score': 0, 'imbalance': 0
        }
    
    # Build graph structure
    out_edges = defaultdict(list)
    in_edges = defaultdict(list)
    for edge in edges:
        from_node = edge.get('from')
        to_node = edge.get('to')
        if from_node and to_node:
            out_edges[from_node].append(to_node)
            in_edges[to_node].append(from_node)
    
    # Find root (node with no incoming edges)
    roots = [nid for nid in nodes.keys() if nid not in in_edges or len(in_edges[nid]) == 0]
    if not roots:
        # If no clear root, use initial nodes
        roots = [nid for nid, info in nodes.items() if info.get('is_initial', False)]
    if not roots:
        roots = [list(nodes.keys())[0]] if nodes else []
    
    root = roots[0] if roots else None
    if not root:
        return {
            'depth': 0, 'median_depth': 0, 'max_width': 0, 'width_at_half_depth': 0,
            'avg_out_degree': 0, 'pct_leaves': 0, 'spine_score': 0, 'imbalance': 0
        }
    
    # BFS to compute depths and widths
    depths = {}
    queue = deque([(root, 0)])
    depths[root] = 0
    level_widths = defaultdict(int)
    
    while queue:
        node, depth = queue.popleft()
        level_widths[depth] += 1
        
        for child in out_edges.get(node, []):
            if child not in depths:
                depths[child] = depth + 1
                queue.append((child, depth + 1))
    
    # Compute metrics
    if not depths:
        return {
            'depth': 0, 'median_depth': 0, 'max_width': 0, 'width_at_half_depth': 0,
            'avg_out_degree': 0, 'pct_leaves': 0, 'spine_score': 0, 'imbalance': 0
        }
    
    max_depth = max(depths.values()) if depths else 0
    depth_values = list(depths.values())
    median_depth = sorted(depth_values)[len(depth_values) // 2] if depth_values else 0
    
    max_width = max(level_widths.values()) if level_widths else 0
    half_depth = max_depth // 2 if max_depth > 0 else 0
    width_at_half_depth = level_widths.get(half_depth, 0)
    
    # Out-degree statistics
    out_degrees = [len(out_edges.get(nid, [])) for nid in nodes.keys()]
    avg_out_degree = sum(out_degrees) / len(out_degrees) if out_degrees else 0
    leaves = [nid for nid in nodes.keys() if len(out_edges.get(nid, [])) == 0]
    pct_leaves = (len(leaves) / len(nodes) * 100) if nodes else 0
    
    # Spine score: longest path / N
    longest_path = max_depth + 1  # +1 to count nodes
    spine_score = longest_path / len(nodes) if nodes else 0
    
    # Imbalance: variance in out-degrees (simplified)
    if len(out_degrees) > 1:
        mean_od = avg_out_degree
        variance = sum((od - mean_od) ** 2 for od in out_degrees) / len(out_degrees)
        imbalance = variance  # Higher = more imbalanced
    else:
        imbalance = 0
    
    return {
        'depth': max_depth,
        'median_depth': median_depth,
        'max_width': max_width,
        'width_at_half_depth': width_at_half_depth,
        'avg_out_degree': round(avg_out_degree, 2),
        'pct_leaves': round(pct_leaves, 1),
        'spine_score': round(spine_score, 3),
        'imbalance': round(imbalance, 2)
    }


def visualize_proof_trees_grid(theorem_data_list, output_path="proof_trees_grid.html"):
    """
    Create an interactive HTML visualization of multiple proof trees in a 4x4 grid with navigation.
    
    Args:
        theorem_data_list: List of dictionaries, each with 'theorem_name' and 'proof_tree' keys
        output_path: Path to save the HTML file
    
    Returns:
        Path to the saved HTML file
    """
    # Prepare all networks data for all theorems
    all_networks_data = []
    for theorem_data in theorem_data_list:
        theorem_name = theorem_data.get('theorem_name', 'Unknown')
        proof_tree = theorem_data.get('proof_tree', {})
        nodes = proof_tree.get('nodes', {})
        edges = proof_tree.get('edges', [])
        
        # Calculate basic statistics
        num_tactics = len(edges)
        num_nodes = len(nodes)
        num_terminal = sum(1 for n in nodes.values() if n.get('is_terminal', False))
        num_initial = sum(1 for n in nodes.values() if n.get('is_initial', False))
        
        # Compute tree shape metrics
        metrics = compute_tree_metrics(nodes, edges)
        
        # Prepare nodes for vis-network (black and white only)
        vis_nodes = []
        for state_id, node_info in nodes.items():
            node = {
                'id': state_id,
                'label': state_id[:6] if len(state_id) > 6 else state_id,
            }
            
            # Black and white only - use border width to distinguish
            if node_info.get('is_initial'):
                node['color'] = {'background': '#FFFFFF', 'border': '#000000'}
                node['borderWidth'] = 4
            elif node_info.get('is_terminal'):
                node['color'] = {'background': '#000000', 'border': '#000000'}
                node['font'] = {'color': '#FFFFFF'}
                node['borderWidth'] = 4
            else:
                node['color'] = {'background': '#FFFFFF', 'border': '#000000'}
                node['borderWidth'] = 2
            
            vis_nodes.append(node)
        
        # Prepare edges for vis-network
        vis_edges = []
        for edge in edges:
            edge_data = {
                'from': edge.get('from'),
                'to': edge.get('to'),
                'label': edge.get('tactic', '')[:10] if edge.get('tactic') else '',  # Truncate long tactics
                'arrows': 'to',
                'color': {'color': '#000000'},
                'width': 2
            }
            
            # Removed title attribute to disable hover tooltips
            # Premises info will only be shown on click via detail box
            
            vis_edges.append(edge_data)
        
        all_networks_data.append({
            'theorem_name': theorem_name,
            'nodes': vis_nodes,
            'edges': vis_edges,
            'node_count': num_nodes,
            'edge_count': num_tactics,
            'terminal_count': num_terminal,
            'initial_count': num_initial,
            'metrics': metrics
        })
    
    # Create HTML content with brutalist design and navigation
    total_theorems = len(all_networks_data)
    total_pages = (total_theorems + 24) // 25  # Ceiling division for 5x5 grid
    
    # Create grid HTML structure (25 placeholders for 5x5 grid)
    grid_html = []
    for idx in range(25):
        grid_html.append(f'''
        <div class="grid-item" id="grid-item-{idx}">
            <div class="grid-label" id="label-{idx}"></div>
            <div class="grid-network" id="network-{idx}"></div>
        </div>''')
    
    # Prepare all data as JSON for JavaScript
    # Use json.dumps to create valid JSON (which is also valid JavaScript)
    all_data_json = json.dumps(all_networks_data, ensure_ascii=False)
    # Only need to escape </script> tags to prevent breaking HTML
    all_data_json_js = all_data_json.replace('</script>', '<\\/script>')
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Proof Trees Grid</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Courier New', 'Liberation Mono', 'DejaVu Sans Mono', monospace;
            background-color: #FFFFFF;
            padding: 0;
            margin: 0;
            overflow: hidden;
        }}
        .nav-bar {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 50px;
            background-color: #000000;
            color: #FFFFFF;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 20px;
            z-index: 1000;
            border-bottom: 4px solid #000000;
        }}
        .legend-box {{
            position: fixed;
            top: 50px;
            left: 50%;
            transform: translateX(-50%);
            background-color: #FFFFFF;
            border: 3px solid #000000;
            border-top: none;
            padding: 6px 12px;
            font-size: 8px;
            line-height: 1.2;
            z-index: 999;
            display: flex;
            align-items: center;
            gap: 12px;
            white-space: nowrap;
        }}
        .legend-title {{
            font-weight: bold;
            margin-right: 4px;
        }}
        .legend-item {{
            margin: 0;
        }}
        .nav-button {{
            background-color: #FFFFFF;
            color: #000000;
            border: 2px solid #000000;
            padding: 8px 20px;
            font-family: inherit;
            font-size: 12px;
            cursor: pointer;
            font-weight: bold;
        }}
        .nav-button:hover {{
            background-color: #000000;
            color: #FFFFFF;
        }}
        .nav-button:disabled {{
            background-color: #CCCCCC;
            color: #666666;
            cursor: not-allowed;
        }}
        .page-info {{
            font-size: 11px;
            font-weight: bold;
        }}
        .grid-container {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            grid-template-rows: repeat(5, 1fr);
            width: 100vw;
            height: calc(100vh - 80px);
            margin-top: 80px;
            gap: 0;
        }}
        .grid-item {{
            border: 4px solid #000000;
            background-color: #FFFFFF;
            overflow: hidden;
            position: relative;
        }}
        .grid-label {{
            position: absolute;
            top: 0;
            left: 0;
            background-color: #FFFFFF;
            color: #000000;
            padding: 3px 5px;
            font-size: 7px;
            font-weight: bold;
            z-index: 10;
            border-right: 2px solid #000000;
            border-bottom: 2px solid #000000;
            max-width: calc(100% - 10px);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            line-height: 1.1;
        }}
        .grid-network {{
            width: 100%;
            height: 100%;
        }}
        .node-detail-box {{
            position: fixed;
            bottom: 10px;
            left: 50%;
            transform: translateX(-50%);
            background-color: #FFFFFF;
            border: 3px solid #000000;
            padding: 8px 12px;
            font-size: 9px;
            font-family: inherit;
            z-index: 1001;
            max-width: 80%;
            display: none;
        }}
        .node-detail-box.active {{
            display: block;
        }}
    </style>
</head>
<body>
    <div class="nav-bar">
        <button class="nav-button" id="prev-btn" onclick="changePage(-1)">◀ PREV</button>
        <div class="page-info" id="page-info">Page 1 / {total_pages}</div>
        <button class="nav-button" id="next-btn" onclick="changePage(1)">NEXT ▶</button>
    </div>
    <div class="legend-box">
        <span class="legend-title">METRICS:</span>
        <span class="legend-item">N: nodes, E: edges |</span>
        <span class="legend-item">D: depth, MD: median depth |</span>
        <span class="legend-item">W: max width, W½: width@½depth |</span>
        <span class="legend-item">OD: avg out-degree, L%: %leaves |</span>
        <span class="legend-item">S: spine score |</span>
        <span class="legend-item">I: imbalance</span>
    </div>
    <div class="grid-container">
        {''.join(grid_html)}
    </div>
    <div class="node-detail-box" id="node-detail-box"></div>
    <script type="text/javascript">
        // Store all theorem data
        const allTheoremsData = {all_data_json_js};
        const theoremsPerPage = 25;
        let currentPage = 0;
        const totalPages = {total_pages};
        const networks = [];
        
        // Initialize networks array
        for (let i = 0; i < 25; i++) {{
            networks.push(null);
        }}
        
        function renderPage(page) {{
            const startIdx = page * theoremsPerPage;
            const endIdx = Math.min(startIdx + theoremsPerPage, allTheoremsData.length);
            
            // Clear all grids
            for (let i = 0; i < 25; i++) {{
                const labelEl = document.getElementById('label-' + i);
                const networkEl = document.getElementById('network-' + i);
                
                if (networkEl) {{
                    networkEl.innerHTML = '';
                }}
                
                if (labelEl) {{
                    labelEl.textContent = '';
                }}
                
                // Destroy existing network
                if (networks[i]) {{
                    networks[i].destroy();
                    networks[i] = null;
                }}
            }}
            
            // Render visible theorems
            for (let i = 0; i < endIdx - startIdx; i++) {{
                const theoremIdx = startIdx + i;
                const theoremData = allTheoremsData[theoremIdx];
                
                if (!theoremData) continue;
                
                const labelEl = document.getElementById('label-' + i);
                const networkEl = document.getElementById('network-' + i);
                
                if (!labelEl || !networkEl) continue;
                
                // Set label with theorem name and metrics
                const name = theoremData.theorem_name.split('.').pop() || theoremData.theorem_name;
                const m = theoremData.metrics || {{}};
                // Compact format: N E D W OD L% S I
                const od = typeof m.avg_out_degree === 'number' ? m.avg_out_degree.toFixed(1) : (m.avg_out_degree || 0);
                const leaves = typeof m.pct_leaves === 'number' ? m.pct_leaves.toFixed(0) : (m.pct_leaves || 0);
                const spine = typeof m.spine_score === 'number' ? m.spine_score.toFixed(2) : (m.spine_score || 0);
                const imb = typeof m.imbalance === 'number' ? m.imbalance.toFixed(1) : (m.imbalance || 0);
                const stats = 'N' + theoremData.node_count + ' E' + theoremData.edge_count + 
                             ' D' + (m.depth || 0) + ' W' + (m.max_width || 0) +
                             ' OD' + od + ' L' + leaves + '%' +
                             ' S' + spine + ' I' + imb;
                labelEl.textContent = name + ' | ' + stats;
                
                // Create network
                const nodes = new vis.DataSet(theoremData.nodes);
                const edges = new vis.DataSet(theoremData.edges);
                const data = {{ nodes: nodes, edges: edges }};
                const options = {{
                    nodes: {{
                        shape: 'box',
                        font: {{ size: 8, face: 'monospace' }},
                        margin: 4,
                        widthConstraint: {{ maximum: 80 }},
                        heightConstraint: {{ maximum: 30 }}
                    }},
                    edges: {{
                        font: {{ size: 6, align: 'middle' }},
                        smooth: {{ type: 'straight' }},
                        arrows: {{ to: {{ enabled: true, scaleFactor: 0.5 }} }},
                        width: 1.5
                    }},
                    layout: {{
                        hierarchical: {{
                            enabled: true,
                            direction: 'LR',
                            sortMethod: 'directed',
                            levelSeparation: 50,
                            nodeSpacing: 80,
                            treeSpacing: 100
                        }}
                    }},
                    physics: {{ enabled: false }},
                    interaction: {{ 
                        dragNodes: true, 
                        dragView: true, 
                        zoomView: true,
                        hover: false,
                        tooltipDelay: 0
                    }}
                }};
                
                networks[i] = new vis.Network(networkEl, data, options);
                
                // Store original font sizes and theorem data in closure
                const originalNodeFontSize = options.nodes.font.size;
                const originalEdgeFontSize = options.edges.font.size;
                const currentTheoremData = theoremData;
                const currentNodes = nodes;
                const currentEdges = edges;
                
                // Add click handler to reduce font size and show details
                networks[i].on('click', function(params) {{
                    if (params.nodes.length > 0) {{
                        const nodeId = params.nodes[0];
                        const nodeData = currentNodes.get(nodeId);
                        
                        // Reduce font size by 30% for all nodes and edges
                        const newNodeFontSize = Math.max(4, Math.floor(originalNodeFontSize * 0.7));
                        const newEdgeFontSize = Math.max(4, Math.floor(originalEdgeFontSize * 0.7));
                        
                        // Update all node font sizes
                        currentNodes.forEach(function(node) {{
                            currentNodes.update({{
                                id: node.id,
                                font: {{ size: newNodeFontSize, face: 'monospace' }}
                            }});
                        }});
                        
                        // Update all edge font sizes
                        currentEdges.forEach(function(edge) {{
                            currentEdges.update({{
                                id: edge.id,
                                font: {{ size: newEdgeFontSize, align: 'middle' }}
                            }});
                        }});
                        
                        // Show node details
                        const detailBox = document.getElementById('node-detail-box');
                        const nodeInfo = 'State: ' + nodeId + ' | Theorem: ' + currentTheoremData.theorem_name;
                        detailBox.textContent = nodeInfo;
                        detailBox.classList.add('active');
                        
                        // Hide details and restore font sizes after 3 seconds
                        setTimeout(function() {{
                            detailBox.classList.remove('active');
                            // Restore original font sizes
                            currentNodes.forEach(function(node) {{
                                currentNodes.update({{
                                    id: node.id,
                                    font: {{ size: originalNodeFontSize, face: 'monospace' }}
                                }});
                            }});
                            currentEdges.forEach(function(edge) {{
                                currentEdges.update({{
                                    id: edge.id,
                                    font: {{ size: originalEdgeFontSize, align: 'middle' }}
                                }});
                            }});
                        }}, 3000);
                    }} else {{
                        // Click on empty space - hide details
                        document.getElementById('node-detail-box').classList.remove('active');
                    }}
                }});
            }}
            
            // Update navigation
            document.getElementById('page-info').textContent = 'Page ' + (page + 1) + ' / ' + totalPages;
            document.getElementById('prev-btn').disabled = (page === 0);
            document.getElementById('next-btn').disabled = (page >= totalPages - 1);
        }}
        
        function changePage(delta) {{
            const newPage = currentPage + delta;
            if (newPage >= 0 && newPage < totalPages) {{
                currentPage = newPage;
                renderPage(currentPage);
            }}
        }}
        
        // Initial render
        renderPage(0);
    </script>
</body>
</html>"""
    
    # Save HTML file
    output_path = Path(output_path)
    output_path.write_text(html_content, encoding='utf-8')
    
    return str(output_path)


def visualize_proof_tree(theorem_data, output_path=None):
    """
    Create an interactive HTML visualization of a single proof tree.
    Wrapper for backward compatibility - calls grid version with single item.
    
    Args:
        theorem_data: Dictionary with 'theorem_name' and 'proof_tree' keys
        output_path: Path to save the HTML file. If None, uses theorem_name + '_tree.html'
    
    Returns:
        Path to the saved HTML file
    """
    if output_path is None:
        theorem_name = theorem_data.get('theorem_name', 'Unknown')
        safe_name = theorem_name.replace('/', '_').replace('.', '_')
        output_path = f"{safe_name}_tree.html"
    
    return visualize_proof_trees_grid([theorem_data], output_path)


if __name__ == "__main__":
    # Example usage
    example_data = {
        "theorem_name": "test_theorem",
        "proof_tree": {
            "nodes": {
                "state1": {"state_id": "state1", "is_initial": True, "is_terminal": False},
                "state2": {"state_id": "state2", "is_initial": False, "is_terminal": True}
            },
            "edges": [
                {"from": "state1", "to": "state2", "tactic": "simp", "premises": ["premise1"]}
            ]
        }
    }
    
    # Single tree
    output = visualize_proof_tree(example_data)
    print(f"Visualization saved to: {output}")
    
    # Grid of multiple trees
    multiple_data = [example_data] * 16
    grid_output = visualize_proof_trees_grid(multiple_data)
    print(f"Grid visualization saved to: {grid_output}")
