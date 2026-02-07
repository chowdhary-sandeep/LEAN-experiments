"""
Build proof DAGs from traced_theorems_unified_v2.jsonl.

Each proof is a sequence of tactic steps that transform proof states.
This visualizes the proof trajectory: state → tactic → new_state → ... → "no goals"

Uses brutalist black-and-white aesthetic with hierarchical left-to-right layout.
"""

import json
from pathlib import Path
from collections import defaultdict

# Configuration
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_FILE = SCRIPT_DIR / "jsons" / "traced_theorems_unified_v2.jsonl"
OUTPUT_HTML = SCRIPT_DIR / "01_within_proof_DAGs.html"


def load_theorems_with_proofs(jsonl_path, max_theorems=None):
    """
    Load theorems from JSONL, keeping only those with tactic proofs.

    Returns:
        list of theorem records with tactics
    """
    print(f"Loading theorems from {jsonl_path}...")
    theorems = []

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue

            try:
                thm = json.loads(line)
            except json.JSONDecodeError:
                print(f"Warning: Could not parse line {line_num}")
                continue

            # Only keep theorems with tactic proofs
            if thm.get("proof_type") == "tactic" and thm.get("tactics"):
                theorems.append(thm)

            if max_theorems and len(theorems) >= max_theorems:
                break

    print(f"  Found {len(theorems):,} theorems with tactic proofs")
    return theorems


def build_proof_dag(theorem):
    """
    Build a DAG structure for a single proof.

    The proof is sequential: tactics[i].state_after ≈ tactics[i+1].state_before
    We reuse state nodes when they match to create a proper linear chain.

    Returns:
        dict with nodes and edges representing the proof trajectory
    """
    tactics = theorem.get("tactics", [])

    # Build nodes (proof states) - use hash of state string as ID to reuse matching states
    nodes = {}
    edges = []
    state_id_map = {}  # Map state string to node ID

    def get_or_create_state_node(state_str, context, tactic_idx, is_initial, is_terminal):
        """Get existing node ID for state, or create new one."""
        # Use hash of state string as stable ID (truncate for readability)
        state_hash = str(abs(hash(state_str)))[:8]

        if state_str in state_id_map:
            # State already exists - reuse it
            node_id = state_id_map[state_str]
            # Update terminal status if needed
            if is_terminal:
                nodes[node_id]["is_terminal"] = True
            return node_id

        # Create new node
        node_id = f"s{state_hash}"
        state_id_map[state_str] = node_id

        # Truncate goal for display
        goal_str = context.get("goal", "")[:200]

        nodes[node_id] = {
            "id": node_id,
            "label": f"#{tactic_idx}",  # Simple label
            "state": state_str[:300],  # Truncate for JSON size
            "goal": goal_str,
            "num_hypotheses": len(context.get("hypotheses", {})),
            "num_variables": len(context.get("variables", {})),
            "is_initial": is_initial,
            "is_terminal": is_terminal,
            "tactic_index": tactic_idx
        }

        return node_id

    for i, tactic_record in enumerate(tactics):
        state_before = tactic_record.get("state_before", "")
        state_after = tactic_record.get("state_after", "")
        tactic_str = tactic_record.get("tactic", "")
        premises = tactic_record.get("premises", [])
        context = tactic_record.get("context", {})
        is_terminal = tactic_record.get("is_terminal", False)

        # Get or create state nodes
        state_before_id = get_or_create_state_node(
            state_before,
            context,
            i,
            is_initial=(i == 0),
            is_terminal=False
        )

        # Parse context for state_after (approximation - we don't have full context)
        after_context = {"goal": "", "hypotheses": {}, "variables": {}}
        state_after_id = get_or_create_state_node(
            state_after,
            after_context,
            i + 1,
            is_initial=False,
            is_terminal=is_terminal
        )

        # Add edge (tactic step)
        edge = {
            "from": state_before_id,
            "to": state_after_id,
            "tactic": tactic_str[:100],  # Truncate tactic for display
            "tactic_index": i,
            "premises": [p.get("full_name", "")[:80] for p in premises[:5]],  # Limit premises
            "num_goals_before": tactic_record.get("num_goals_before", 0),
            "num_goals_after": tactic_record.get("num_goals_after", 0)
        }
        edges.append(edge)

    return {
        "nodes": nodes,
        "edges": edges,
        "num_tactics": len(tactics)
    }


def select_interesting_theorems(theorems, count=48):
    """
    Select interesting theorems for visualization (3 pages of 4x4 = 48 theorems).

    Prioritize:
    - Medium length (5-30 tactics) for readability
    - Complete proofs (reaches "no goals")
    - Variety in complexity
    """
    # Filter complete proofs with reasonable length
    candidates = []
    for thm in theorems:
        num_tactics = thm.get("metrics", {}).get("num_tactics", 0)
        tactics = thm.get("tactics", [])

        # Check if proof is complete
        is_complete = False
        if tactics:
            last_tactic = tactics[-1]
            is_complete = last_tactic.get("is_terminal", False)

        if 5 <= num_tactics <= 30 and is_complete:
            candidates.append((thm, num_tactics))

    # Sort by length and take variety
    candidates.sort(key=lambda x: x[1])

    # Take samples across the range
    selected = []
    step = max(1, len(candidates) // count)
    for i in range(0, len(candidates), step):
        if len(selected) >= count:
            break
        selected.append(candidates[i][0])

    print(f"  Selected {len(selected)} theorems (from {len(candidates)} candidates)")
    return selected


def generate_html(theorems_with_dags, output_path):
    """
    Generate interactive HTML visualization of proof DAGs.

    Uses vis-network with hierarchical left-to-right layout.
    Brutalist black-and-white aesthetic with 4x4 grid and paging.
    """

    # Prepare data for JSON embedding
    all_networks_data = []
    for thm, dag in theorems_with_dags:
        # Prepare nodes for vis-network (black and white only)
        vis_nodes = []
        for node_id, node_info in dag["nodes"].items():
            node = {
                'id': node_id,
                'label': node_info.get("label", node_id[:6]),
                'title': node_info.get("goal", "")  # Tooltip on hover
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
        for edge in dag["edges"]:
            edge_data = {
                'from': edge.get('from'),
                'to': edge.get('to'),
                'label': edge.get('tactic', '')[:10],  # Short label
                'title': edge.get('tactic', ''),  # Full tactic on hover
                'arrows': 'to',
                'color': {'color': '#000000'},
                'width': 2
            }
            vis_edges.append(edge_data)

        theorem_name = thm.get("full_name", "Unknown")
        short_name = theorem_name.split('.')[-1] if '.' in theorem_name else theorem_name

        all_networks_data.append({
            'theorem_name': theorem_name,
            'short_name': short_name,
            'nodes': vis_nodes,
            'edges': vis_edges,
            'node_count': len(dag["nodes"]),
            'edge_count': dag["num_tactics"],
            'num_premises': thm.get("metrics", {}).get("num_premises", 0)
        })

    # Create HTML content
    total_theorems = len(all_networks_data)
    total_pages = (total_theorems + 15) // 16  # Ceiling division for 4x4 grid

    # Create grid HTML structure (16 placeholders for 4x4 grid)
    grid_html = []
    for idx in range(16):
        grid_html.append(f'''
        <div class="grid-item" id="grid-item-{idx}">
            <div class="grid-label" id="label-{idx}"></div>
            <div class="grid-network" id="network-{idx}"></div>
        </div>''')

    # Prepare all data as JSON for JavaScript
    all_data_json = json.dumps(all_networks_data, ensure_ascii=False)
    all_data_json_js = all_data_json.replace('</script>', '<\\/script>')

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Proof DAGs - Within-Proof State Trajectories</title>
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
            font-size: 9px;
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
            grid-template-columns: repeat(4, 1fr);
            grid-template-rows: repeat(4, 1fr);
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
            font-size: 8px;
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
    </style>
</head>
<body>
    <div class="nav-bar">
        <button class="nav-button" id="prev-btn" onclick="changePage(-1)">◀ PREV</button>
        <div class="page-info" id="page-info">Page 1 / {total_pages}</div>
        <button class="nav-button" id="next-btn" onclick="changePage(1)">NEXT ▶</button>
    </div>
    <div class="legend-box">
        <span class="legend-title">PROOF DAGs:</span>
        <span class="legend-item">Each graph = tactic sequence within ONE proof</span>
        <span class="legend-item">|</span>
        <span class="legend-item">White border (thick) = initial state</span>
        <span class="legend-item">|</span>
        <span class="legend-item">Black fill = terminal (proof complete)</span>
        <span class="legend-item">|</span>
        <span class="legend-item">N=states, E=tactics, P=premises</span>
    </div>
    <div class="grid-container">
        {''.join(grid_html)}
    </div>
    <script type="text/javascript">
        // Store all theorem data
        const allTheoremsData = {all_data_json_js};
        const theoremsPerPage = 16;
        let currentPage = 0;
        const totalPages = {total_pages};
        const networks = [];

        // Initialize networks array
        for (let i = 0; i < 16; i++) {{
            networks.push(null);
        }}

        function renderPage(page) {{
            const startIdx = page * theoremsPerPage;
            const endIdx = Math.min(startIdx + theoremsPerPage, allTheoremsData.length);

            // Clear all grids
            for (let i = 0; i < 16; i++) {{
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

                // Set label with theorem name and stats
                const stats = 'N' + theoremData.node_count + ' E' + theoremData.edge_count + ' P' + theoremData.num_premises;
                labelEl.textContent = theoremData.short_name + ' | ' + stats;

                // Create network with hierarchical layout (left-to-right)
                const nodes = new vis.DataSet(theoremData.nodes);
                const edges = new vis.DataSet(theoremData.edges);
                const data = {{ nodes: nodes, edges: edges }};
                const options = {{
                    nodes: {{
                        shape: 'box',
                        font: {{ size: 10, face: 'monospace', color: '#000000' }},
                        margin: 5,
                        widthConstraint: {{ maximum: 60 }},
                        heightConstraint: {{ maximum: 30 }}
                    }},
                    edges: {{
                        font: {{ size: 7, align: 'top', color: '#000000' }},
                        smooth: {{ type: 'cubicBezier' }},
                        arrows: {{ to: {{ enabled: true, scaleFactor: 0.6 }} }},
                        width: 2
                    }},
                    layout: {{
                        hierarchical: {{
                            enabled: true,
                            direction: 'LR',
                            sortMethod: 'directed',
                            levelSeparation: 80,
                            nodeSpacing: 60,
                            treeSpacing: 80
                        }}
                    }},
                    physics: {{
                        enabled: false
                    }},
                    interaction: {{
                        dragNodes: true,
                        dragView: true,
                        zoomView: true,
                        hover: true
                    }}
                }};

                networks[i] = new vis.Network(networkEl, data, options);
            }}

            // Update page info
            document.getElementById('page-info').textContent = 'Page ' + (page + 1) + ' / ' + totalPages;

            // Update button states
            document.getElementById('prev-btn').disabled = (page === 0);
            document.getElementById('next-btn').disabled = (page === totalPages - 1);
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

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"HTML visualization saved to: {output_path}")


def main():
    """Main function to build proof DAGs and generate HTML."""
    print("="*70)
    print("BUILDING WITHIN-PROOF DAGs")
    print("="*70)

    # Load theorems
    theorems = load_theorems_with_proofs(DATA_FILE, max_theorems=2000)

    if not theorems:
        print("No theorems with tactic proofs found!")
        return

    # Select interesting subset (3 pages of 4x4 = 48 theorems)
    selected = select_interesting_theorems(theorems, count=48)

    # Build DAGs
    print(f"\nBuilding proof DAGs...")
    theorems_with_dags = []
    for thm in selected:
        dag = build_proof_dag(thm)
        theorems_with_dags.append((thm, dag))

        # Diagnostic: show first few
        if len(theorems_with_dags) <= 3:
            print(f"  {thm['full_name'][:50]}: {dag['num_tactics']} tactics -> {len(dag['nodes'])} states")

    print(f"  Built {len(theorems_with_dags)} proof DAGs")

    # Generate HTML
    print(f"\nGenerating HTML visualization...")
    generate_html(theorems_with_dags, OUTPUT_HTML)

    print(f"\n{'='*70}")
    print("DONE!")
    print(f"Open {OUTPUT_HTML} in your browser to view the proof DAGs.")
    print(f"4x4 grid with page navigation | Black & white brutalist design")
    print("="*70)


if __name__ == "__main__":
    main()
